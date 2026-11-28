# Skills over MCP (SEP-2640) 仕様確認メモ・実証計画・併用設計

## 1. SEP-2640 の要点

SEP-2640（Skills over MCP）は、MCP サーバーがツール（`tools/*`）だけでなく、ツール群の使い方・運用手順・ノウハウをまとめた **Skills** もクライアントへ配信するための MCP 拡張仕様である。

- **拡張 ID**: `io.modelcontextprotocol/skills`
- **URI スキーム**: スキルは `skill://<name>/SKILL.md` の形式で識別される（同フォルダ内の補助ファイルも `skill://<name>/<file>` として扱われる）。
- **capabilities 広告（二箇所）**:
  - `initialize` のレスポンス `capabilities` に `"resources": {}` と `"extensions": {"io.modelcontextprotocol/skills": {}}` を含める。
  - `server/discover`（`protocolVersion: "2026-07-28"`）でも同じ `capabilities` と `serverInfo` を返す。
- **取得の二経路**:
  1. **Skills 専用メソッド**:
     - `skills/list`: スキル一覧（`uri`, `frontmatter`, `resources` 配列の `uri` / `digest` (`sha256:...`) / `size`）に加え、`ttlMs`・`cacheScope` を返す。
     - `skills/get`: `params.uri` に対応する 1 件のスキルエントリを返し、未知 URI には JSON-RPC エラー `-32602` を返す。
  2. **MCP Resources 経路**:
     - `resources/list`: 各スキルの `SKILL.md` と同フォルダの付属ファイルを `skill://<name>/<file>` として列挙する。
     - `resources/read`: 指定 URI の本文を `contents` 配列で返し、未知 URI には `-32602` を返す。

## 2. クライアント対応の実測（2026-11-27）

- **検証環境**: Claude Code `2.1.332` ＋ SEP-2640 最小テストサーバー（`uzu-marker` スキル配信、`server.log` で JSON-RPC 往復を記録）。
- **観測結果**:
  - ホスト（Claude Code）は起動・接続時に `server/discover` を試行した。
  - 続いて `resources/list` および `resources/read` を呼び出し、`skill://uzu-marker/SKILL.md` の一覧取得と本文読み込みに成功した。
  - 一方で、`skills/list`（および `skills/get`）は呼ばれず、読み込んだスキルがスラッシュコマンドのスキル一覧に表示されることもなかった。
- **結論**:
  - 現時点のクライアント（ホスト）実装は **「入口（Capabilities 検出・`resources/*` 経由での発見と読み込み）まで」** 対応しており、専用メソッド `skills/list` を使った UI／スラッシュコマンドへのスキル提示は実装途上である。
  - そのため、サーバー側では `skills/list`・`skills/get` と `resources/list`・`resources/read` の**両経路を実装しておく**ことで、現行ホストの発見・読み込みと将来のフル対応クライアントの双方に備える必要がある。

## 3. 本実装の範囲と実証の残り

### 本実装の範囲（B-1333）
- `ai_loop/mcp_server.py` への配信機能追加（`SKILLS_DIR = ai_loop/skills` の走査、`initialize` / `server/discover` への capabilities 追加、`skills/list` / `skills/get` / `resources/list` / `resources/read` 実装）。
- エンジン配信用の最初の実スキル `ai_loop/skills/uzu-verify/SKILL.md` の追加。
- 単体テスト `ai_loop/tests/test_mcp_skills.py` による契約検証。

### 実証の残り（U.ZU 実サーバー × Claude Code 実機確認）
最小テストサーバーで確認できた発見・読み込みの挙動を、実際の U.ZU MCP サーバー（`ai_loop/mcp_server.py`）に対しても確認する。

1. **テスト用プロジェクトへ local スコープで MCP 登録する**
   JSON-RPC ログ（必要なら stderr/tee 経由、またはラッパースクリプトで標準入出力を記録）を確認できる状態で登録する。
   ```bash
   cd /path/to/test-project
   claude mcp add --scope local uzu-engine -- python3 /path/to/ai_loop/mcp_server.py --project /path/to/test-project
   ```

2. **Claude Code を起動し、MCP 接続を確立する**
   テスト用プロジェクト上で Claude Code を起動し、uzu-engine サーバーが正常起動することを確認する。

3. **JSON-RPC 往復のログを確認する**
   - initialize / server/discover の応答に io.modelcontextprotocol/skills と resources が含まれていること。
   - resources/list で skill://uzu-verify/SKILL.md が返り、resources/read で本文が取得できていること（またクライアントが skills/list を呼ぶ場合は期待どおり応答できること）。
   - 従来の tools/list・tools/call の動作に影響がないこと。

## 4. 併用設計

クライアントの SEP-2640 対応が過渡期であり、非対応クライアントも存在するため、スキル配布は二系統を併用する。

- 正本（Single Source of Truth）: エンジンリポジトリ内の ai_loop/skills/<name>/SKILL.md を正本とする。
- MCP 配信経路（追加経路）: SEP-2640 対応クライアントへは ai_loop/mcp_server.py が ai_loop/skills/ を直接読み込んで配信する。
- ローカルスキル経路（既存存続）: 非対応クライアントやスラッシュコマンド一覧での明示呼び出し向けに、従来のローカル配置経路（~/.claude/skills/ やプロジェクトローカルの .claude/skills/ 等）は廃止せず存続させる。ローカル配置ファイルは正本（ai_loop/skills/）からの写しとして位置づけ、内容の更新は正本を起点に行う。

## 5. 安全面の留保

MCP 経由で配信されるスキル（SKILL.md）は、AI エージェントにとって「手順書＝実行指示」として解釈・実行される。外部や未検証の MCP サーバーからスキルを取り込む場合、意図しないコマンド実行や破壊的操作を誘発するリスクがある。

- 配信元の信頼性検証（署名・ダイジェスト検証、信頼済みサーバーの許可リスト）
- スキル内の破壊的操作に対するユーザー承認境界・サンドボックス方針

これらのセキュリティ設計は、外部スキル採用を判断する段階で別途検討・策定するものとし、本項目（エンジン同梱スキルの配信基盤整備）では扱わない。
