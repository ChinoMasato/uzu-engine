# moonpost — 月夜の郵便屋さん（B-1005 イメージ先行サンプル）

仕様イラスト1枚から作った小さな 2.5D 配達ゲーム。月夜の村の通りを歩き、
赤・青・緑の郵便受け3つに手紙を届けるとクリア。

## 遊び方
- 移動: WASD／矢印キー（通りの中だけ歩ける）
- 配達: 郵便受けの近くで E／Space

## 構成
- `spec.png` — 仕様イラスト（ChatGPT 生成、1672x941）
- `image_scene/` — B-1221 が生成した雛形（Backdrop＋帯状カード17枚、参照カメラ、歩行検証つき）
- `spec_registry.json` — B-1222 レジストリ（要素9件を登録、validate 通過）
- `elements.json` — レジストリへ流し込む要素表（image_bbox は working pixels = 768x432 基準）
- `main.tscn` / `main.gd` — ゲーム本体（雛形シーン＋Player＋郵便受け3つ＋HUD）
- `sfx_deliver.wav` / `sfx_clear.wav` — エンジンの sfx プリセット（coin／powerup）で生成
- `verify_playthrough.py` — aiplayer 完走検証（B-313 の play log 記録つき）
- `play_log.jsonl` — 検証ランの操作ログ（uzu-play-log/1）
- `spec_diff_verdict.json` — B-1223 の判定結果

## 検証の再実行
```
GODOT=<editor binary> python3 ai_loop/uzu.py image-scene ai_loop/samples/moonpost --image ai_loop/samples/moonpost/spec.png
GODOT=<editor binary> python3 ai_loop/samples/moonpost/verify_playthrough.py
GODOT=<editor binary> python3 ai_loop/uzu.py spec-diff ai_loop/samples/moonpost --registry spec_registry.json
GODOT=<editor binary> python3 ai_loop/uzu.py collision-check ai_loop/samples/moonpost --scene res://main.tscn
python3 ai_loop/uzu.py audio-check ai_loop/samples/moonpost/sfx_deliver.wav
```

## チェック結果（2026-11-28）
- 完走検証: 全9項目 pass（到達3/3、配達 0→3、クリア、play log の再構成 ok）
- spec-diff: 構図 0.828（基準0.3）／色 0.291（基準0.32）pass、カード16件・意味要素9件 pass。
  自動検出の glow 候補6件中4件が fail のため総合 ok=false（→ BACKLOG B-1227）
- collision-check: ok（警告3件: プレイヤー見た目メッシュ、前景カード同士の微小な重なり2件）
- audio-check: 2音とも全項目 pass
- feel-report: playthrough モードは hikari 固定のため実行不可（→ B-1113）。
  probe-selftest は hitstop／shake を検出、slowmo／kick は演出チャンネルなしのため未検出
- 雛形の歩行検証: 到達 3/5（前景カード列が通りを塞ぐ → B-1229）

道具の不便は全て BACKLOG へ還した（B-1225〜B-1229、B-1113、B-320）。
詳細は ai_loop/iterations/2026-11-28-B-1005-lead.md。
