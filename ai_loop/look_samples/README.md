# look_samples の約束事

見本（撮影サンプル）を作るときの規約。新しい見本フォルダを作る前に読むこと。

## フォントは必ず明示する（B-1316、2026-11-22）

- **システムフォントのフォールバックに頼らない。** VM のフォールバックは
  Noto Sans CJK の TC フェイスに解決されることがあり、、。の字形が
  中央寄り（TC／HK の慣習）になって、日本語として誤った見た目になる。
  B-1311／B-1313 の見本で実際に起き、オーナーの指摘で発覚した。
- 見本プロジェクトでは、チェックを通った JP フォントをプロジェクトに
  入れて、テーマ作成時に明示する。

### フォントの事前チェック

```sh
python3 ai_loop/uzu.py font-locale-check path/to/font.ttf
# TTC のフェイスを選ぶ場合（フェイス名の確認は --list-faces）
python3 ai_loop/uzu.py font-locale-check path/to/font.ttc --face 0
```

`ok: true`（終了コード 0）のフォントだけを使う。判定は 、（U+3001）と
。（U+3002）のインク上端が、同じフォントのかな・漢字から測った本文帯の
下半分にあること（JP フェイスは帯の 0.33〜0.36、TC／HK は 0.65〜0.67）。

### 設定例（UZUUI テーマ）

『灯りの欠片』の配布フォント（Noto Sans CJK JP のサブセット、
`ai_loop/samples/hikari/art/game_font.ttf`、チェック pass 実測済み）を
見本プロジェクトにコピーして使う場合:

```gdscript
const FONT := preload("res://art/game_font.ttf")

# ワールドテーマ
ui_root.theme = UZUUI.create_world_theme("wafu", {"font": FONT, "font_size": 19})
# 既定テーマなら UZUUI.create_theme({"font": FONT, ...})
```

`ui` 仕様（JSON）で作る場合は、テーマ指定に `"font": "res://art/game_font.ttf"`
を含める（ai_loop/ui_tool.gd の THEME_KEYS 参照）。素の Label 等に直接付ける
場合は `add_theme_font_override("font", FONT)`。
