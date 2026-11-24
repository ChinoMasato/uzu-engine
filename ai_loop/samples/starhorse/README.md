# スターホース牧場 — U.ZU Engine 版サンプル（B-1329）

Godot 製『スターホース牧場』との比較用に、同じ題材・同じ音素材で
U.ZU Engine（Godot フォーク）の道具立てだけで作ったミニ版。
フル移植ではなく、画面3つ＋レース1本の最小構成。

## 画面

1. **タイトル／牧場**（`screens/farm.tscn`）: ロゴ＋所有馬一覧。
   B-1326 の racing 世界観とキット部品（DataTable／DetailPanel／Chip）
   を JSON spec（`specs/farm.json`）から構築。行選択で詳細パネル連動。
   コマンド「レース登録」で出馬表へ。
2. **出馬表**（`screens/entries.tscn`）: 中山11R 春風ステークス（芝1800m）
   8頭立て。spec は `specs/entries.json`。「レース映像」でレースへ、「戻る」で牧場へ。
3. **レース再生**（`race.gd`）: 2D の簡易シミュレーション。直線コースを
   8頭が枠色の勝負服で走り、スピード／スタミナ／脚質（逃げ・先行・差し・追込）
   ＋乱数で順位が決まる。局面（ゲートイン→スタート→序盤→中盤→
   最終直線→ゴール→結果）に同期して実況ボイスが流れる。

## 音（Godot 版と同一素材）

- 実況ボイス29本: `audio/voice/`（対応表は同フォルダの `README.md`）。
  局面イベント→該当ボイスをキュー再生する仕組みは `commentary.gd`。
  Voice バス専用、BGM とは分離（`default_bus_layout.tres`）。
  発火は全て `event_log` に記録され、ヘッドレス検証の対象になる。
- ファンファーレ: `audio/fanfare.mp3`（レース開始前）。
- BGM: `audio/bgm_hero.mp3`（Suno「The Hero's Journey」、タイトル／牧場でループ）。

## 動かし方

```sh
# spec から画面シーンを生成（specs/*.json を変えたら再実行）
python3 make_specs.py
python3 ../../uzu.py ui . --spec res://specs/farm.json
python3 ../../uzu.py ui . --spec res://specs/entries.json

# 通常実行（リポジトリのエディタバイナリで）
../../../bin/godot.linuxbsd.editor.x86_64 --path .
```

## 検証

```sh
python3 verify_race.py   # ヘッドレス自動プレイ: 完走＋実況の発火列が局面順か
python3 capture.py       # 3画面の撮影（shots/ へ、レース中 fps 実測つき）
```

`verify_race.py` は固定シード（1329）・30倍速で1レースを回し、
順位確定と実況19本の発火順（01→02→03→04→序盤→中盤→13→14→17→18→
20→23→27→28→29）を JSON で照合する。
