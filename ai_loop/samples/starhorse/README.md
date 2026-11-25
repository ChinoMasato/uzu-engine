# スターホース牧場 — U.ZU Engine 版サンプル（B-1329／B-1330）

Godot 製『スターホース牧場』との比較用に、同じ題材・同じ音素材で
U.ZU Engine（Godot フォーク）の道具立てだけで作った版。
B-1329 のミニ版（矩形＋円のレース）を、B-1330 で支給アート
（ChatGPT 生成）を使ったアート主導の構成に作り替えた。

## 画面

1. **タイトル**（`screens/title.tscn`）: 夕日の牧場のキービジュアル
   全面＋ロゴ（92px・縁取り＋金影）＋タグライン＋メニュー。
   出現モーションと sweep、BGM はここから流れる。
2. **牧場**（`screens/farm.tscn`）: 朝の牧場アートの上に B-1326 の
   racing キット部品（DataTable／DetailPanel／Chip）を埋め込む
   （B-1325 のアート主導の型）。所有馬一覧、行選択で詳細パネル連動。
   コマンド「レース登録」で出馬表へ。
3. **出馬表**（`screens/entries.tscn`）: 中山11R 春風ステークス
   （芝1800m）8頭立て。同じく全面アート＋キット部品。
   「レース映像」でレースへ、「戻る」で牧場へ。
4. **レース**（`race.gd`）: 横視点 2.5D。競馬場アートを遠景
   （空＋スタンド）／芝／手前ラチの3層に分解してパララックス。
   馬は疾走イラストを局所テクスチャ分離で切り抜き、馬体色調と
   勝負服・鞍下の色差し替えで8頭分（`prep_assets.py`）。
   ギャロップの上下動＋体の傾き、速度に応じた残像／土煙、
   先頭追従カメラ（残り400mから寄る）、ゴール前の
   スローモーション＋フラッシュ／シェイク。シム（脚質・疲労・
   順位）と実況同期は B-1329 の資産を再利用し、字幕は維持。
   ライブ順位パネルには残り距離と馬身差併記。
5. **結果**（`result.gd`）: 着順表（キットの DataTable、タイム／
   着差つき）＋勝ち馬の疾走カットを大きく表示＋ファンファーレ。

画面遷移は UZUUIJuice.transition で統一し、各画面に出現アニメ・
フォーカスの burst・押下 flash・塵モートの fx 層を配線。

## 音（Godot 版と同一素材）

- 実況ボイス29本: `audio/voice/`（対応表は同フォルダの `README.md`）。
  局面イベント→該当ボイスをキュー再生する仕組みは `commentary.gd`。
  Voice バス専用、BGM とは分離（`default_bus_layout.tres`）。
  発火は全て `event_log` に記録され、ヘッドレス検証の対象になる。
- ファンファーレ: `audio/fanfare.mp3`（レース開始前と結果画面）。
- BGM: `audio/bgm_hero.mp3`（Suno「The Hero's Journey」、
  タイトル／牧場／出馬表でループ、レース中は停止）。

## 素材の加工

`prep_assets.py` は支給アート（`~/workspace/starhorse-art/`）から
`art/` のテクスチャを作る一回限りの加工スクリプト（PIL／numpy／
scipy はここだけ）。馬の切り抜きは B-1324 と同じ局所テクスチャ
分離（脚下部が暗いので分離軸は色でなく局所 std）。パララックス層は
帯状の切り分け＋左右端クロスフェードでタイリング可能化し、手前
ラチは緑優位キーで芝を透明化した。

## 動かし方

```sh
# spec から画面シーンを生成（specs/*.json を変えたら再実行。
# 新規アートの .import が要るので先に --import を一度通す）
../../../bin/godot.linuxbsd.editor.x86_64 --headless --path . --import
python3 make_specs.py
python3 ../../uzu.py ui . --spec res://specs/title.json
python3 ../../uzu.py ui . --spec res://specs/farm.json
python3 ../../uzu.py ui . --spec res://specs/entries.json

# 通常実行（リポジトリのエディタバイナリで）
../../../bin/godot.linuxbsd.editor.x86_64 --path .
```

生成シーン（screens/*.tscn、各約18MB）は .gitignore 対象で
コミットしない。上記の手順で再生成する。

## 検証

```sh
python3 verify_race.py     # ヘッドレス自動プレイ: 完走＋着差＋実況の発火列が局面順か
python3 capture.py         # 全画面の撮影（shots/ へ、レース中 fps 実測つき）
python3 capture_video.py   # 一連の流れを動画に（shots/motion_race.mp4、約22秒）
```

`verify_race.py` は固定シード（1329）・30倍速で1レースを回し、
全馬完走・順位確定・着差文字列と、実況19本の発火順（局面順）を
JSON で照合する。
