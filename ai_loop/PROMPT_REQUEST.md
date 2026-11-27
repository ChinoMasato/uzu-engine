# エンジンから AI へのプロンプト要求（B-1327）

U.ZU のツールが依頼を発行し、AI エージェントが取得して実行し、同じ ID で成果を返す。
発行側は回収した成果を次の工程へ渡せる。設計モードでは AI が使った全文も回収し、要素表やテンプレートの見直しに使える。

## 要求の形式 `uzu-prompt-request/1`

| フィールド | 型と意味 |
|---|---|
| `format` | 文字列 `uzu-prompt-request/1` |
| `id` | 保管先で一意の ID。`[a-z0-9][a-z0-9_-]{0,63}` |
| `kind` | 空白だけではない文字列。例は `image`（素材生成）、`text`、`eval`（評価）。発行側と実行側で意味を共有する |
| `mode` | `fixed` または `design` |
| `prompt` | `fixed` で必須のプロンプト全文。AI はそのまま使う。`design` では省略する |
| `brief` | `design` で必須のオブジェクト。 `objective` は目的を表す文字列、`constraints` は制約を表す文字列の配列（空配列可）。`fixed` では省略する |
| `expect` | `file`、`json`、`text` のいずれか |
| `context` | 発行側と実行側が共有する参照資料やメタデータを含むオブジェクト。空なら `{}` |

文字列の `prompt`、`objective` と各制約は空白だけの値を受け付けない。
追加フィールドは保存される。JSON のエンコーディングは UTF-8。

設計モードでスクリーンショットの評価を依頼する例。

```json
{
  "format": "uzu-prompt-request/1",
  "id": "check-lighthouse",
  "kind": "eval",
  "mode": "design",
  "brief": {
    "objective": "スクリーンショットを仕様イラストと比較する",
    "constraints": ["構図と色を別々に評価する", "passed と metrics を含む JSON を返す"]
  },
  "expect": "json",
  "context": {
    "reference": "illustration.png",
    "shot": "screenshot.png"
  }
}
```

## 結果の形式 `uzu-prompt-result/1`

| フィールド | 型と意味 |
|---|---|
| `format` | 文字列 `uzu-prompt-result/1` |
| `id` | 要求と CLI の ID に一致する文字列 |
| `type` | 要求の `expect` に一致する文字列 |
| `value` | `file` は既存の通常ファイルを指すプロジェクト相対パス（区切りは `/`、`..` は不可）。`json` は任意の JSON 値（`null` を含む）。`text` は文字列（空文字列可） |
| `used_prompt` | 実際に使用したプロンプト全文。空白だけの値は不可。`design` では必須。`fixed` では任意で、指定する場合は要求の `prompt` と完全に一致する |

```json
{
  "format": "uzu-prompt-result/1",
  "id": "check-lighthouse",
  "type": "json",
  "value": {"passed": false, "metrics": {"composition": 0.82, "color_distance": 0.41}},
  "used_prompt": "screenshot.png と illustration.png の構図の一致と色の距離を求め、passed と metrics を含む JSON を返してください。"
}
```

`file` の成果物はプロジェクト内で維持する。提出時にはリンク解決後もファイルがプロジェクト内にあることを確認し、結果 JSON に相対パスを保存する。評価の `value.passed` などは依頼固有のデータで、CLI の `ok` は操作の成否を示す。

## CLI と保管先

```sh
python3 ai_loop/uzu.py prompt-request PROJECT issue --request request.json
python3 ai_loop/uzu.py prompt-request PROJECT list
python3 ai_loop/uzu.py prompt-request PROJECT get check-lighthouse
python3 ai_loop/uzu.py prompt-request PROJECT submit check-lighthouse --result result.json
python3 ai_loop/uzu.py prompt-request PROJECT get check-lighthouse
```

`PROJECT` は `project.godot` があるディレクトリ。入力 JSON のパスは呼び出し元の作業ディレクトリを基準とする。各保管操作で `--store DIR` を指定できる。既定は `PROJECT/.uzu/prompt-requests` で、相対指定は `PROJECT` が基準。

- `issue` は `request-ID.json` を保存し、`state: "pending"` と `request` を返す。
- `list` は保留中の要求を ID 順に `requests` 配列で返す。
- `get ID` は `state` と `request` を返し、`state: "done"` のときは `result` も返す。
- `submit ID` は `result-ID.json` を保存し、`state: "done"` と `result` を返す。

要求と結果は同じディレクトリに追加される。要求ファイルがあれば `pending`、対応する結果ファイルもあれば `done`。一時ファイルを閉じてからハードリンクで公開するため、同じ ID に同時に書き込んでも先に公開した内容が残る。保管先にはハードリンク対応のファイルシステムが必要。二重提出や応答が途切れた場合は `get ID` で確定した結果を取得できる。

各操作は `ok`、`command`、操作名を表す `action`（引数解析に成功した場合）を含む JSON 1 行を標準出力へ返す。終了コードは 0 が成功、1 が未登録 ID や登録済み ID との競合、2 が引数・形式・ファイル操作のエラー。エラーには `error` が付く。`--help` はヘルプを表示する。

## 要素表とテンプレートの合成

```sh
python3 ai_loop/uzu.py prompt-request PROJECT compose --elements elements.json --template prompt.txt
```

要素表は UTF-8 の JSON オブジェクトで、各値は文字列。たとえば `{"subject":"灯台","style":"夕暮れの手描き風"}` を、UTF-8 のテンプレート `$style の ${subject} を描く。` に適用すると、応答の `prompt` は `夕暮れの手描き風 の 灯台 を描く。` になる。`$name` と `${name}` の名前には ASCII の英数字とアンダースコアを使い、先頭は英字またはアンダースコアとする。`$$` はリテラルの `$`。未定義の要素や壊れた置換記法はエラーになる。置換は一度だけで、挿入した要素に含まれる記号、空白、改行もそのまま残る。固定モードの発行側は応答の `prompt` を要求 JSON に入れる。

## 往復の検証

```sh
python3 ai_loop/tests/test_prompt_request.py
```

固定・設計の両モードで、素材生成とスクリーンショット評価を実行する。素材生成スタブは PNG を保存し、発行側が回収したパスを `uzu.py image-scene PROJECT --image PNG --no-build` に渡す。評価スタブはスクリーンショットと仕様イラストを `spec_diff` で比較し、数値を結果 JSON に返す。設計モードでは、スタブが `brief` から設計した全文が提出後も保持されることを確認する。このテストは `uzu.py selftest tools` と CI の `selftest all` に含まれる。
