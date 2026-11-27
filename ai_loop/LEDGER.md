# LEDGER — 検証ループの実行記録

失敗も消さない。1イテレーション = 1行ブロック。

## 2026-11-17 プロジェクト開始

- フォーク点: Godot master @ 203bf0a（4.8 beta）。ブランチ `ai-native` を作成。
- 環境実測: clone 約2分／477MB。SCons は venv（~/workspace/.venv-build）に導入。
- ビルドプローブ: template_release で4分間に178オブジェクト（約44個/分）。全対象は約2,000ファイル、フルビルド推定1〜1.5時間。
- ベースラインビルド（template_release, tests=yes）をバックグラウンドで開始。結果は完了時にここへ追記する。

## 2026-11-17 — B-004 マルチエージェント開発基盤（Muse、VM）
- 千野の決定: コード開発の主ツールを Claude Code とし、複数 AI エージェントで並行開発できる構成にする。
- 追加: CLAUDE.md（AGENTS.md を @import）、ai_loop/MULTI_AGENT.md、ai_loop/CLAIMS.md、ai_loop/iterations/、agent_start.sh／build_locked.sh（flock 直列化）／agent_finish.sh。
- 実証: agent_start.sh で B-999 テスト用 worktree＋ブランチの作成・削除を確認。スクリプトは bash -n pass。
- この VM にも Claude Code 2.1.325 を導入（~/workspace/tools/claude-code）。初回利用時の Anthropic サインインは千野側の操作が必要。
- ベースラインビルド（B-001）は継続中につき、本件はコード変更なし・運用ファイルのみ。

## 2026-11-17 — GitHub へ展開（A案: 正式フォーク）
- 千野が GitHub で godotengine/godot をフォーク（ChinoMasato/godot、master はフォーク点 203bf0a のまま）。
- Muse の GitHub App にはフォーク作成権限がなかったため、フォーク作成は千野が Web で実施。push はデバイス認証で発行した GitHub CLI トークンで Muse 環境から実行し、push 完了後にトークンファイルは破棄した。
- ai-native を push し、リモート HEAD がローカル HEAD（29765fe）と一致することを ls-remote で確認済み。以後の正は GitHub 側リポジトリとする。

## 2026-11-17 — Codex 対応（千野の指示）
- Codex でもそのまま作業できるよう入口を明示: AGENTS.md 冒頭に「Start here」節を追加（BRIEFING → MULTI_AGENT → BACKLOG の必読順と、ツール別入口: Claude Code=CLAUDE.md／Codex=AGENTS.md）。
- .codex/config.toml を追加（プロジェクト既定値: sandbox_mode=workspace-write、approval_policy=on-request。規則ではなく既定値）。
- BRIEFING.md にツール別入口の注記を追加。規則自体は従来どおり全ツール共通。

## 2026-11-17 — 三者連携基盤（千野の指示）
- 連携窓口を ai_loop/COORDINATION.md に一本化（状況ボード＋質問節＋役割定義）。開始時に読み、終了時に自分の行を更新する運用。正式決定はオーナー承認→リードがLEDGERへ反映した時点で確定、と明記。
- MULTI_AGENT.md に連携節を追加、AGENTS.md と BRIEFING.md の必読リストに COORDINATION.md を追加。
- 背景: Claude Code セッションと Codex が稼働開始し、質問（B-001採用可否・作業ブランチ・分担案）と push 403 の報告がオーナー経由で届いたため、中継を不要にする仕組みとして整備。未決事項は COORDINATION.md の Q1/Q2 に集約。

## 2026-11-17 — Q1 決定（オーナー承認）と B-001 ベースライン採用
- 決定1（B-001）: Claude Code（ローカル）が取得したベースラインを正式採用する。報告値: フルビルド 15分54秒、単体テスト 1431件中 1430 pass、fail 1件は環境起因（Claude Code の報告）。エンジン側コミット ff5246b は運用ファイルのみでコード差分がないため、この結果は現行ツリーに適用できる。詳細記録（ビルド設定・マシン環境・fail 1件のテスト名と根拠）は Claude Code が追って記録し、リードが ai-native へ取り込む。Muse の VM ビルドは本決定により停止した（オブジェクト 2,111 個は保持、増分再開可能。VM 側のテスト結果は得られていない）。
- 決定2（作業ブランチ）: Claude セッション専用ブランチ claude/uzu-engine-briefing-rrno7b を許可。ai-native へのマージはリード経由。
- 決定3（分担）: Claude Code = B-002 → B-003、Codex = B-101 を承認。B-002/B-003 に限り ai_loop/ と version.py へのリード権限を Claude Code へ委譲。B-003 は互換影響の事前調査・報告が条件。
- 連携: 以後の push・マージは保持したデバイス認証トークンでリード（Muse）が随時実施する（オーナー承認済み）。

## 2026-11-17 — B-001 ベースライン確立（Claude Code、クラウド）
- オーナー判断で本結果を正式なベースラインとして採用（Muse 側のビルドは停止）。詳細: ai_loop/iterations/2026-11-17-B-001-claude.md
- ビルド設定: AGENTS.md の規定どおり `scons platform=linuxbsd target=template_release tests=yes accesskit=no arch=x86_64`（並列数だけ -j4。4コアのため）。対象 ai-native @ 3d70ab368。
- マシン: Claude Code クラウドコンテナ（gVisor）、Xeon 2.10GHz × 4コア、RAM 15GB、Ubuntu 24.04.5、gcc 13.3.0、Python 3.13.18、SCons 4.11.1、zstandard 0.25.0。
- 所要時間: フルビルド 15分54秒（2,665 ファイル、exit 0）、単体テスト約31秒。
- テスト: 総数 1431／pass 1430／fail 1／skip 3（assertion 423591 中 1000 が fail）。
- fail: `[IP] resolve_hostname`（tests/core/io/test_ip.cpp:44）、localhost の IPv6 解決が空になる。環境起因と判断した根拠: コンテナの /etc/hosts に `::1 localhost` が無く、getent でも Python の getaddrinfo でも AF_INET6 の localhost を引けない。`::1 localhost` を一時的に足すと全 1431 件 pass、fail 0 になる（そのあと元に戻した）。コード起因の失敗は 0 件。

## 2026-11-17 — リード統合: Claude ブランチを ai-native へマージ
- claude/uzu-engine-briefing-rrno7b（3bb7ea0）を ai-native へ fast-forward マージ。内容: B-001 詳細記録（LEDGER 本編＋iterations）、B-002 measure.sh（リードがレビュー: flock 直列化・失敗時も記録・doctest 集計のパースを確認、bash -n pass）、B-003 事前調査（コード変更なし）。
- Q1 の条件（ベースライン詳細記録）はこれで充足。B-001 は正式に完了。
- B-003 の実装は Q3（COORDINATION.md）のオーナー決定待ち: short_name の扱い（案A: name のみ変更／案B: 両方変更）、判定条件の差し替え、measure.sh の TZ 既定。

## 2026-11-17 — Q3 決定（オーナー承認）: B-003 は案Aパッケージ
- B-003 の範囲を version.py の name のみに確定（short_name は "godot" のまま、互換維持）。BACKLOG の判定を「起動ヘッダの U.ZU Engine 表示＋全テスト pass」に差し替え（--version は名前を含まないため）。
- measure.sh の日付は TZ=Asia/Tokyo を既定化（リードが適用、bash -n pass）。
- B-003 の実装は Claude Code が担当ブランチで実施し、検証（起動ヘッダ＋全テスト）つきで申告する。

## 2026-11-17 — AIファースト改善マップを反映（オーナー指示）
- フォーク実物の棚卸しに基づく改善マップを設計書（第2節末「AIファースト改善マップ」）と BACKLOG へ反映。不足は「出力の構造化」「合否判定」「プレイ自己検証」の3点に集約。原則: 追加モード／オプトインのみで既存挙動を変えない。
- Wave 1 として5件を登録: B-104（ベンチ合否）、B-201（構造化エラーログ試験実装）、B-202（GDScriptエラーJSON）、B-203（プロジェクト検証コマンド）、B-303（自己検証プレイ最小版）。残り候補は BACKLOG の保留へ Wave 2 として集約。

## 2026-11-17 — リード統合: B-003 実装を ai-native へマージ
- version.py の name が "U.ZU Engine" になった（short_name は "godot" のまま）。新規テスト tests/core/test_version.cpp（名前と互換を固定する2件）を含む。
- 検証（Claude Code の最終検証をリードが確認）: 最小プロジェクトで `--headless --quit` の起動ヘッダが "U.ZU Engine v4.8.beta..." と表示され exit 0。全テスト 1433 件中 1432 pass（fail は既知の環境起因 [IP] resolve_hostname のみ。::1 追加時は全件 pass）。変更前は新規テストが fail することも確認済み（red→green）。
- BACKLOG の B-001／B-002／B-003 を完了に更新。Phase 0 は完了。
- 申し送り: 起動ヘッダの website（version.py の website = godotengine.org）の扱いは未決定。必要なら別項目としてオーナー判断。

## 2026-11-17 — B-003 追随: website を U.ZU に変更（オーナー指示）
- version.py の website を https://godotengine.org から https://u-zu.co.jp へ変更（起動ヘッダと About 表示に出る URL）。docs 欄（ドキュメントへの参照）は本家ドキュメントを指すため据え置き。
- tests/core/test_version.cpp に website を固定するテストを1件追加（合計3件）。ヘッダ表示の再検証は次の増分ビルド（Claude Code のループ）で併せて確認する。

## 2026-11-17 — リード統合: Phase 4・Phase 7・A-1・A-3 を ai-native へ（PR #3 相当）
- Claude Code のブランチ（2584812）を ai-native へ fast-forward 統合。オーナーが Q4〜Q7 で直接承認した一連の作業: Phase 7 ルック（B-701〜B-713、B-703b を除く全部。UZULook クラスと look_preset_3d、エディタの U.ZU メニューと構図ガイド、look.sh／palette_check.py／サンプルシーン）、Phase 4（B-401 engine.sh、B-402 MCP サーバー）、A-1（ヘッドレス描画スクリーンショット＋画像差分）、A-4（クラウド環境セットアップ）。
- A-3（= B-102 として完走）: core/io/ip.cpp に RFC 6761 の localhost フォールバック（システム解決が空返しのときだけ loopback を返す。オーナーが案a を選択）。tests/core/io/test_ip.cpp にテスト追加。これでベースライン以来の既知 fail は解消方向。
- 検証状態: Claude Code の申告で全テスト 1476 件 pass（従来 1433＋新規 43）。エディタ側コードは Claude の環境で editor ビルド＋起動確認済み（従来の標準ビルド=template では editor/ がコンパイル対象外だった点が A-2 の動機）。
- A-2 をリードが実施: 標準ループビルドを editor に変更（build_locked.sh／measure.sh は TARGET 環境変数、既定 editor。template_release は実行時・書き出し確認用に温存）。AGENTS.md の Build／Test 節も更新。
- Codex の B-101 はドラフト（fce3e6b）のまま未完（エンジン検証と完了申告待ち）。統合対象外。
- 残: B-703b（UZUPostEffect）が Phase 7 の最後の1件。Phase 2 の Wave 1（B-201〜B-203）と B-104、B-303 は未着手。

## 2026-11-18 — リード統合: WIN-GPU の残りと B-101。影の対策を B-714 として決定
- agent/win-gpu-claude-local の未統合分2件（Windows GPU 道具 shoot_gpu.py／frame_time.gd／look_variant.gd と WIN-GPU 記録）を ai-native へ統合（README の競合は両節を残して解消）。同ブランチの他のコミット（B-703b、B-201〜B-203、B-104、B-301〜B-305、B-502、B-503 draft、B-601、B-103）は Claude Code（クラウド）が ai-native へ直接反映済みだったもの。
- B-101（Codex）を統合: tests/doctest_json.py（doctest XML→JSON）。Codex の実エンジン検証は editor ビルドで 1481 pass／0 fail／3 skip、JSON 一覧と集計の一致を確認。リード側でも変換器の単体テスト10件が pass することを確認した。CLAIMS の競合は行を併せて解消。
- 影の判断（オーナーから委任、WIN-GPU の RTX 4050 実測に基づく）: 「高」の light_angular_distance 0.5→0.25＋影フィルタ High を採用（粒 4.93→1.37、+0.74 ms）。TAA は不採用。B-703b は変更なし。実施は B-714 として BACKLOG に登録（値のテスト更新＋GPU 再計測が判定）。
- 申し送り: テスト総数が環境で異なる（クラウド 1477／Windows 1475／Codex 1481）。Windows との差2件は未特定（全件一覧はオーナー PC の gpu_shots/out/test_cases_windows.txt）。--headless --import の segfault が1回だけ発生（6回再試行で再現せず）。いずれも監視事項。
- 状態メモ: ai-native は Claude Code（クラウド）の直接 push で前進している（B-306、B-504〜B-507、B-801、B-802 を含む）。その運用方針の記録はブランチ側の転記で届いたため、オーナー本人への確認を別途行う。

## 2026-11-18 — 運用方針の確定: 検証済み作業は ai-native へ直接反映
- オーナーがリードとのチャットで明示的に確認: Claude Code は検証（ビルド＋全テスト pass）を通した作業を ai-native へ直接反映してよい（PR・リード統合を待たない）。記録（iterations／CLAIMS）は従来どおり。
- リード（Muse）の役割は、事後レビュー、台帳（LEDGER／BACKLOG／COORDINATION）の整合、判断事項（例: B-714 の影対策）に移る。ブランチ経由で届いた作業（Codex の B-101、ローカルの GPU 確認）は従来どおりリードが統合する。

## 2026-11-18 — Wave 3 を登録（AI 開発特化の次の一手）
- オーナーの問いへのリードの整理を BACKLOG と COORDINATION（Q11）に反映。登録: B-307 状態ハッシュ、B-308 失敗パケット、B-309 セーブステート、B-204 プロジェクトマップ、B-205 UID 修復、B-105 テスト影響選択。推しは検証3点セット（B-307〜309）。Wave 3 候補（リファクタ API 化、意味的 diff、性能予算、要約モード）は保留に集約。

## 2026-11-18 — HD-2D 系テクニックを登録（B-715〜B-722）と B-714 の補記
- オーナーの問いへのリードの整理を BACKLOG（Phase 7 の続き）と COORDINATION（Q12）に反映。推しはチルトシフト DOF（B-715）、Lit スプライト（B-716）、HD-2D ワンクリックプリセット（B-722）。
- 訂正: B-714 は LEDGER 記録時に BACKLOG への転記が漏れていた（アンカー文字列の不一致で置換が効いていなかった）。本日補記した。

## 2026-11-18 — 着手順を提示（リード）
- Phase 8 の完了（B-801〜B-805）を確認。オーナーの「進めて」を受けて、COORDINATION に着手順メモを置いた: B-714 → HD-2D 系（B-715→716→717→722）→ Wave 3（B-307→309→308）→ 隙間で B-105／B-204／B-205。

## 2026-11-18 — Phase 9（U.ZU Picture）を登録。Q13 に回答
- ローカル（Windows／RTX 4050）の試作ブランチ agent/picture-claude-local を ai-native へ統合（GDScript 試作一式、GPU 確認済み、絵は含まず）。
- BACKLOG に Phase 9 を新設: B-903 マップ取り込み（先頭）、B-901 UZUPicture ノード、B-902 PBR 生成、B-904 エージェントコマンド。優先度は現キューの核の後（リード決定、COORDINATION Q13 回答）。
- 方針決定: 推定モデルはエンジンに同梱しない（外部コマンドの口のみ）。分担は C++ 化＝クラウド、GPU 確認＝ローカル。
- なお B-714 はクラウドが実施済み（記録 2026-11-18-B-714-claude.md）。GPU 再計測はローカル待ち。

## 2026-11-18 — リード統合: B-714 GPU 確認、B-105、B-803 補完、B-005
- agent/b714gpu-claude-local を統合: B-714 の GPU 再計測で粒 −72%（7.05→1.99、B-703b 有効時）・+0.71 ms を確認し、B-714 を完了にした。shadow_grain.py を道具に追加。
- agent/b-105-codex を統合: テスト影響選択（tests/select_tests.py）。単体テストはリード側でも pass。BACKLOG の B-105 を完了に。
- agent/b-803-codex を統合: クラウド実装済みの B-803 への Codex の補完（フレームベンチの MCP 公開と不完全な計測の拒否）。mcp_server.py の競合は両方の道具登録を残して解消。Codex が重複に気づいて自実装を取り消した経緯も記録に残っている。
- agent/b-005-codex を統合: オーナー直接依頼のロゴ／アイデンティティ（misc/logo/uzu/、エディタのブランド画像、About の表示とロゴアニメーション、test_pck_packer のロゴサイズ依存の修正）。コードの競合はなく、運用ファイルのみ解消。見た目の最終確認はエディタ実機でオーナーへ。
- 直接反映側では HD-2D の核（B-715〜B-718、B-722）が反映済み（画像はオーナー判断待ち）。

## 2026-11-18 — HD2D の GPU 確認を統合、不具合2件を B-723／B-724 として決定
- agent/hd2dgpu-claude-local を統合（記録、比較画像 hd2d_gpu_*.png、hd2d_gpu.py 等）。全テストは Windows で 1485 pass／0 fail（クラウド 1491 との差3件は未調査のまま）。
- 重さ: ルック「高」4.26 ms → hd2d 適用で 5.88 ms（チルトシフト 0.7〜1.2 ms、粒子はほぼ0）。
- 不具合1（B-716 輪郭）: シェーダーが sprite_texture を repeat で読み、透明な最上段の上に最下段（靴）の輪郭が出る。対策は sampler への repeat_disable（normal_texture も同様）とリードが決定し B-723 に登録。
- 不具合2（B-722）: --no-camera では太陽回転が if (camera) の中にあるため実行されず、夕方に人物が逆光で真っ黒。対策は「リグなしでも現在のカメラ基準で回す。カメラが無ければ回さず結果 JSON で知らせる」と決定し B-724 に登録。

## 2026-11-18 — B-106 上流追随マージの予行演習を登録
- 振り返り（同日）で「勝ち筋の判定は追随マージのコスト」と整理したことを受け、オーナー指示でキューに追加。着手順は不具合修正（B-723／B-724）の次。
- 事前計測: フォーク点からの変更は追加208／既存変更37ファイル。実質的なコード変更は約15ファイルに収まっており、追加型の規律が競合面を小さく保っている。

## 2026-11-18 — B-107 GitHub Actions 検証基盤を登録
- オーナー指示でキューに追加（B-106 の直前）。公開フォークの無料ランナー（4コア／16GB）で editor ビルド＋全テストを自動化する。見込み: コールド約40分、増分10〜20分。
- あわせて記録: Xserver は共用 Web ホスティングのためビルドには使わない（オーナーとの確認事項として COORDINATION に明記）。

## 2026-11-18 — B-108 起動直後のアイコンちらつきを診断・登録
- オーナー報告「起動するとタスクバーに一瞬 Godot のアイコンが出てから U.ZU に切り替わる」。原因: exe 埋め込みアイコン（platform/windows/godot.ico／godot_console.ico）は B-005 の差し替え対象外で Godot のまま。起動直後は埋め込み、初期化後は実行時アイコン（差し替え済み）が表示されるため切り替わる。
- 対策（公式アイコンから .ico を生成して差し替え）を B-108 として登録。小さい修正群（B-723／B-724）と並べて実施する。

## 2026-11-18 — エディタ GUI 方針をオーナーが決定
- 「AI での開発に特化したいのでエディタ画面は不要」というオーナーの方針を、リード整理の形（GUI は作らない／バイナリはヘッドレス基盤として残す／コードは削除しない）で確定。AGENTS.md の Hard rules と COORDINATION の Q14 に記録。
- Q6 の保留だった UI 配置の問いは「UI は作らない」で解消。

## 2026-11-18 — B-723／B-724 完了（GPU 再確認に合格、リードが取り込み）
- ローカル（RTX 4050）が ai-native 8df1b69 で再確認: 全テスト 1490 pass／0 fail／3 skip。B-723 は3人とも頭上の横線が消滅、B-724 は --no-camera の夕方で太陽がカメラ背後に回り顔と服が読める。重さ hd2d 6.12ms／--no-camera 5.54ms（前回とほぼ同じ）、やり直し0回。記録と画像をブランチ agent/b723gpu-claude-local から取り込み、BACKLOG の両項目を完了にした。
- テスト総数の環境差について進展: 今回クラウド 1496 との差6件は **UDSServer のテストのみ**と特定された（件数自体は回により 3〜6 で変動）。監視は継続するが、差の居場所は掴めた。
- 残る小件（記録のみ）: 人物の胴中央の縦の暗い帯（自分の影の可能性）。再現条件が分かったら別途扱う。

## 2026-11-18 — 胴の縦の暗い帯の原因を特定、B-725 として修正を決定
- ローカルが切り分け: 原因は B-716 の BlobShadow（Decal）が人物の板自体にも投影されていたこと（全レイヤー対象＋高さ1m の箱）。影設定・画面効果は無関係と実測で除外。Hero2 の顔の影は Hero3 の実影で仕様どおり。
- リード決定: 推し案（Lit スプライトを専用レイヤーに置き、Decal の cull_mask から外す）を採用し B-725 に登録。高さを縮める別案は地面の凹凸で影が切れる恐れがあるため不採用。記録のみだった小件はこれで正式な修正項目になった。

## 2026-11-18 — B-108 完了（Windows アイコン、オーナー実機確認）
- Codex の agent/b-005-codex-windows を統合: platform/windows/godot.ico と godot_console.ico を U.ZU アイコンに差し替え（生成スクリプト misc/logo/uzu/windows_icons.py を同梱）。あわせて SCsub に .ico へのビルド依存が追加され、アイコン変更時にリソースが再ビルドされるようになった。
- 検証: オーナーが実機で「アイコン直ってます」と確認（統合前のローカルビルド）。これで ai-native から再ビルドしても Godot のアイコンに戻らない。
- 申し送り: 同ブランチの窓口行に「B-720 の GPU 確認はデバイス喪失で一部保留（別ブランチ）」とある。B-720 の完了判定はその回収後に行う。

## 2026-11-18 — PR #4（B-904）と PR #5（B-725）を処理
- PR #4（B-904、Codex）: Picture の試作コマンドを共通 CLI（uzu.py picture）に接続。Windows で回帰16件＋実 Vulkan での検出→採用→撮影を確認済み。競合なしでマージし、B-904 を完了にした。
- PR #5（B-725、Codex）: 人物をレイヤー20に置き Decal の cull_mask から外す修正。新規の影は item_rect × pixel_size から足元へ配置。全テスト 1501 pass（Codex 計測）。ドラフトだったが GPU 再確認が終わったため、リードが ready 化してマージ、B-725 を完了にした。
- ただし B-725 の GPU 再確認（ローカル）は分割判定: 帯は消えた（30.5 → 5.4、合格）が、地面の丸い影は「一度も出ていなかった」ことが判明。保存済みシーンへの再適用で Decal の大きさ・位置が古い値のまま残るのが原因（B-716 の配置に由来する既存の欠陥）。切り分けて B-726 に登録した。
- Phase 9 の B-903／B-901 はクラウドの直接反映で完了済みだったこともあわせて確認した。

## 2026-11-18 — Phase 10 サンプルゲーム『灯りの欠片』を登録
- オーナー指示「U.ZU Engine の機能をすべて生かしたサンプルゲームを作って出したい」を受け、Phase 10（B-1001 本体／B-1002 自己検証と橋の実証／B-1003 Web 公開）を新設した。
- 題材は HD-2D の村で灯りの欠片を集める5分級のミニゲーム。全機能の対応表は B-1001 に明記（HD-2D 一式、Picture、自己検証プレイ、状態ハッシュ、テレメトリ、橋、構造化ログ、プロジェクト検証）。
- これは判定マイルストーン②（公開→遊ばれる→感想の循環）の実証にもなる。

## 2026-11-18 — 記録ブランチ群の取り込みと B-106 予行結果の確定（リード）
- testgap を取り込み: テスト総数の環境差は **Linux が UDSServer の6件を多く実行する（UNIX_ENABLED のみ）** と確定し、長く残っていた未特定事項を閉じた。差分ツール ai_loop/test_cases_diff.py と Windows のテスト一覧も同梱。
- gpuflake を取り込み: ローカル GPU のデバイス喪失はマシン全体の NVIDIA 障害で、エンジンの不具合ではなかった。GPU 道具に1回の再試行を追加。
- b108check を取り込み: B-108 は実機起動でも最初から U.ZU アイコンと確認。あわせて macOS の icns が Godot のまま残っていると判明し、B-109 として登録した。
- b-720-codex-gpu（風揺れの GPU 再確認道具と結果）と b-903-codex-map（試作取り込みの正確性補完＋テスト）を取り込んだ。
- agent/b-108-codex は **統合しない**: B-108 の並行実装だが、統合済みの版（b-005-codex-windows）がオーナー実機確認＋ローカル再確認まで済んでおり、未検証の別アイコンに差し替える理由がないため見送りとして記録する。
- B-106 予行の結果を確定として記録する: 上流51コミット・65ファイルに対し **競合0件**（自動マージ1秒未満）、両側変更は editor_help.cpp の1件だけで別箇所のため両立、ビルド成功・全テスト 1498 件 pass。追加型の規律が追随コストをほぼゼロにしていることが予行で実証された。本番（4.8 RC／正式版）も同じ手順。
- B-107: リポジトリ変数 DISABLE_GODOT_CI=true をリードが API で設定し、検証ワークフロー（uzu_verify.yml）が動く状態にした。初回実行の結果と red→green の確認は実施セッション側で完了させる。

## 2026-11-18 — B-107 完了と B-726 エンジン側の統合（リード）
- B-107 を完了にした: 検証ワークフロー（uzu_verify.yml）は green 2回（ai-native 4.2分、agent/hikari-muse 3.0分。どちらもキャッシュあり）に加え、意図的に落とすテストだけを入れた使い捨てブランチ agent/ci-red-check で **red を正しく検出**（2.8分で failure）した。red→green の判定を満たしたのでブランチは削除した。キャッシュが効く push では 3〜4分で検証が回ることが分かった。
- B-726 のエンジン側を実装・統合した（agent/b-726-muse、Actions green 2.7分）: add_blob_shadow が既存の BlobShadow を再計算して直す形にし、保存済み影の古い形状が再適用で直るようにした。項目自体は、hd2d 見本の保存済み影の作り直しと GPU 再確認（ローカル）が残るため未完了のまま。

## 2026-11-18 — B-902 完了（リード）
- B-902（画像からの PBR 生成 `UZUPBRFromImage`）を実装し ai-native へ統合した: 試作 pbr_tool.gd の計算と Poly Haven 実スキャン合わせの種類表を C++ 静的 API へ移植し、ai_loop コマンド `picture.py pbrmake` を追加。検証は Actions で green（全テスト 1513 件 pass、うち新規7件）。途中の失敗3回（Math::absf／MAXF と class_db.h／予測値2件の較正）も含め記録は iterations/2026-11-18-B-902-muse.md。
- これで Phase 9（U.ZU Picture）は全項目完了。エンジン側の未完了は B-109（macOS icns）と B-726 の見本再保存＋GPU 再確認（ローカル）、B-501（itch 実証、オーナー作業）、Phase 10 の B-1001〜1003（サンプルゲーム検証はこの VM のビルド完了待ち）。

## 2026-11-18 — B-726 完了の締めと B-902 追補（リード）
- B-726: ローカル GPU 再確認の記録・画像はローカルセッションが ai-native へ統合済み（e165e44）。リード側の締めとして BACKLOG を完了にし、本項を追記した。判定の詳細は iterations/2026-11-18-B-726-GPU-claude-local.md。
- B-902 追補: クラウドセッションの重複実装からの指摘（ぼかしの縮小が点サンプリングで、規則模様の目地に同期して光推定が外れる）を正と判断し、縮小を区画の平均に変更した（agent/b-902-blurfix-muse、Actions green、新規回帰テスト1件＝規則格子を光と誤認しないこと）。実測の裏付け（本当の法線との誤差 10.00°→9.54°）は iterations/2026-11-18-B-902-dup-claude.md。
- B-109: 実装はクラウドセッションが反映済み。残りは macOS 実機での表示確認のみ。B-110: ワークフロー変更の差分を ai_loop/uzu_verify_artifact.patch に置き、push 代行をクラウドセッションへ依頼した（COORDINATION）。
- B-1001: サンプルゲーム『灯りの欠片』を ai-native へ統合し、実エンジンでの完走を検証した（タイトル→収集3つ→点火→クリア、cleared=true、スクリプトエラー0件、スクショ4枚）。検証で main.gd の存在しない API 呼び出し（surface_material_override → set_surface_override_material、4箇所）を捕まえて修正。描画確認は Compatibility まで、Forward+ のルックは GPU 実機で別途。記録 iterations/2026-11-18-B-1001-muse.md。
- B-110: 完了。ローカル（WSL）が実行 44326635731（7ad07707a）の artifact をダウンロードして起動確認（--headless --version → 4.8.beta.custom_build.7ad07707a、終了コード 0）。判定を満たした。重複ブランチ agent/b110push-claude-local は統合不要（リード判断。同名ブランチはリモートに無く、ローカル側のみ）。
- B-727: GPU 確認（ローカル、RTX 4050）が合格。3 描画方式すべてでシェーダーの誤り 0、深さの色・泡・映り込み・屈折の正しさと、水の重さ（1080p で +0.6〜1.4 ms）を確認。見た目の直し4点（ノイズの格子、反射の階段、泡の角、下端の線）を B-728 として登録した。GPU 記録ファイル（iterations/2026-11-19-B-727-GPU-claude-local.md、look_samples/compare/b727_gpu_*、ai_loop/windows/water_gpu.py）はローカルブランチ agent/b727gpu-claude-local にあり、ai-native への反映はローカル待ち。
- 運用: オーナー指示（2026-11-19）でリード判断の範囲を COORDINATION 運用ルール6に明記した。
- B-310／B-311: 完了（B-1002 の検証が発見した道具側の穴）。B-310 = AI プレイヤーの press が InputEventAction も送る（_unhandled_input で読むゲームが反応するように）。B-311 = aiplayer／selfplay がコピー直後にインポートする（.godot なしではフォント等の preload が parse error になっていた）。どちらも aiplayer self-test pass。
- B-1002: 完了。『灯りの欠片』を AI プレイヤーの閉ループ操作で2回完走し機械判定（チェックポイント順序 start→shard_1→shard_2→shard_3→lantern_lit、最終状態 shards=3／cleared=true、開始ハッシュの決定性）。橋モックへ公開（g_0001／b_0002、公開前チェックがライセンス不足を検出→add-notices で解消）→感想取り込みで課題 F-001 と贈り物ファイルを生成。ゲーム側は uzu_state 宣言と移動の物理ステップ化を実施。記録: iterations/2026-11-19-B-1002-muse.md、検証レポートは ai_loop/samples/hikari/verify_report.json。
- 方向追加（2026-11-19 オーナー指示）: Phase 13 リッチ UI（B-1301〜1306）、Phase 14 オンライン対応／Cloudflare 無料枠（B-1401〜1406）、Phase 15 マップ自動生成（B-1501〜1508）を登録。iconicllc.jp の技術分析からは B-1210（KTX2）、B-1211（実天候 Open-Meteo）、B-1108（オーディオスプライト）、B-1405（配信テンプレート）を取り込んだ。
- 『灯りの欠片』Web 版: iOS Safari で 3D が描画されない問題に、プロジェクトへ rendering_method.web=gl_compatibility を追加（Web 書き出しが Forward+ で動いていたのが原因候補。デスクトップ検証は常に Compatibility だった）。オーナーの再確認待ち（B-1003）。
- B-1101: 完了。UZUJuice 基盤（静的 API＋自動生成ランタイム）と時間効果（ヒットストップ／スローモーション、壁時計の状態機械、重なり時はヒットストップ優先→スロー再開→元の速度へ復帰）。CI 全テスト 1528 pass（新規5件）。記録: iterations/2026-11-19-B-1101-muse.md（Godot 4.8 master の API 注意5点を含む）。
- 項目追加（2026-11-19）: B-1212 ピクセルアート描画プリセット（オーナー共有の描画ルールを AGENTS.md にも記載）、B-729 水面の平面反射、B-1213 滝キット、B-1214 ライトシャフト＋水中プリセット（AI 生成シーンの映像表現から）。
- B-1102: 完了。UZUJuice シェイク（trauma 方式、決定的ノイズ、カメラの元オフセットを退避・復元）。CI 全テスト 1531 pass。記録: iterations/2026-11-19-B-1102-muse.md。
- B-1103: 完了。UZUJuice フラッシュ（modulate／オーバーレイ、正確な復元）＋スカッシュ＆ストレッチ（バネ積分）。CI 全テスト 1534 pass。記録: iterations/2026-11-19-B-1103-muse.md。
- B-1215: 登録（オーナーの原則「常にどこかが動いているとリッチ」から、常時モーションキット＋動きの監査）。

- 2026-11-19: B-1104（粒子バースト＋カメラキック）を ai-native へ統合。CI 全テスト 1537 pass。CI は4周: テスト API 名（get_one_shot／delay_usec）→ CPUParticles の世代 API（Parameter enum／set_mesh）→ 全テスト pass 後の終了時クラッシュ（静的キャッシュしたテクスチャがサーバー解体後に破棄）を順に修正。

- 2026-11-19: B-1106（impact プリセット）を ai-native へ統合。CI 全テスト 1540 pass。過程で本物のバグを発見: AudioServer のない環境で UZUSfx::generate が AudioStreamWAV::set_data の null 参照で落ちる → generate にガードを追加（UZUSfx 側の修正として同梱）。

- 2026-11-19: B-1107（『灯りの欠片』への juice 組み込み）を完了。欠片収集で impact(pickup)、ランタン点火で impact＋kick＋バースト。AI プレイヤー検証2回とも juice 発火記録 [pickup×3, lantern] を確認し全判定合格（verify_report.json）。Phase 11 は B-1108（クラウド担当）を除き完了。

- 2026-11-19: 滞留ブランチ5件を ai-native へ統合（オーナー指示）: B-727 GPU 記録、B-314 ログ照合（Codex）、B-728 水の見た目修正（Codex）、B-1201 Blender ブリッジ（Codex）、UZUWorldGen（ローカル、Phase 15 の B-1501／1502／1503／1505／1506 を充足）。競合は台帳と uzu.py の道具追加のみで union 解消。統合後 CI 全テスト 1548 pass（クラウドの B-1302 込み）。

- 2026-11-19: B-110 の独立検証記録（Codex）を ai-native へ統合（agent/b-110-codex、記録ファイルのみ）。Debian 13 x86-64 で Actions 実行 44326635731（7ad07707a）の artifact（78,858,399 bytes、SHA-256 一致）をダウンロードし、再ビルドせず起動確認（--headless --version → 4.8.beta.custom_build.7ad07707a、終了コード 0、sample_game の headless 起動も終了コード 0）。全単体テスト 1515 pass／0 fail／3 skip。B-110 の判定（配布バイナリの起動確認）を別環境からの独立検証として補強する。記録: iterations/2026-11-18-B-110-codex.md。

- 2026-11-19: B-727 の GPU 比較手順（Codex、agent/b-727-codex）を ai-native へ統合。water_gpu.py はローカルの GPU 確認版（3レンダラー対応、32481012858）を採用し、Codex 版は置き換え済みのため取り込まず。water_gpu.md は現行 CLI（GODOT 環境変数、--renderers／--cases）に合わせて更新。検証記録: iterations/2026-11-18-B-727-codex.md（ソフトウェア Vulkan で3条件成功、配布バイナリで全1515件 pass）。

- 2026-11-19: B-403 機能カタログを ai-native へ統合（agent/b-403-lead）。道具の定義そのものから生成するカタログ193件（cli 12／command 69／mcp 70／preset 6／script 22／class 14）、`uzu.py catalog` と MCP catalog_search で検索可能。突合テスト含む Python テスト15件 pass、C++ 変更なし（全テストは CI で担保）。あわせてオーナー指摘「モデルのクオリティがゲームの見た目のクオリティになってしまう」を受け B-1219（モデル品質の底上げ）を Phase 12 に登録し、判定の数値化を COORDINATION 運用ルール7に追加。

- 2026-11-19: lantern_ui 見本（Codex、agent/b-1307-codex）を ai-native へ統合し、B-1309 として登録。当初 B-1307 と名乗っていた番号衝突をリードが付け直し。生成画像は Codex 生成（オーナー確認済み）。オーナー指示によりプルリクエストは使わない運用を COORDINATION ルール8に明記（PR #10 はこの統合で解消）。

- 2026-11-19: B-404 エージェント能力に適応するインターフェースを ai-native へ統合（agent/b-404-lead）。能力プロファイル（UZU_AGENT_CAPS／JSON、語彙は blender／browser／gpu／image_gen、未知の能力はエラー）、カタログ197件に required_capabilities／fallback を付与し不足能力つきで表示、texture-route で生成画像→B-902 と手続きプリセット（B-1209）の振り分けを実証。Python テスト 40件 pass、C++ 変更なし。

- 2026-11-19: B-406 会話・クエストのデータ道具を ai-native へ統合（Codex、agent/b-406-codex）。会話グラフを JSON で宣言し `uzu.py dialogue` と MCP `dialogue_validate` で検証（未到達ノード、分岐漏れ、フラグの読み書き不整合、表示テキストの文字数）。見本（灯りの欠片、6ノード・7状態）で診断 0、選択肢を外すと分岐漏れと未到達ノードを検出。Python テスト 23件 pass、エンジン全テスト 1560 pass（Actions の確認済み editor を SHA-256 照合で使用）、`uzu.py selftest all` pass。カタログは 200件に再生成（dialogue 3件を追加）。統合時の競合は CLAIMS.md／catalog.json／mcp_server.py の両側追加のみで、両方残す形で解消（catalog.json は make_catalog.py で再生成）。記録: iterations/2026-11-19-B-406-codex.md。ブランチ先端の CI run 44533292748 は success。

- 2026-11-20: B-111 検証高速化を ai-native へ統合（agent/b-111-lead）。ccache 4.14.3 を導入し、editor オブジェクト188個の再ビルドが新規 worktree でも 997秒→17秒（約−98%）になることを統計で裏付け。SCons がコンパイラ子プロセスへ CCACHE_DIR／HOME を渡さない落とし穴は ccache.conf の cache_dir 固定で回避。ai_loop/verify_changed.py（差分→影響テスト選択、全件フォールバック付き）を常用の検証入口にした。フルビルド全体の短縮率は未実測。

- 2026-11-20: B-1108 オーディオスプライトを ai-native へ統合（agent/b-1108-lead）。UZUSfx のプリセットを既定50msの無音ギャップで連結した単一 WAV とマニフェスト（名前→開始／長さ）を生成し、区間再生ヘルパーと CLI／MCP（sfx_sprite）を追加。生成とマニフェストは同一の区間計算から出すためずれず、決定的。全テスト 1559/1561（fail は既知の環境起因2件）。テストが未初期化メモリでギャップが無音にならない実バグ等3件を捕まえて修正。

- 2026-11-20: B-1219 第1段（建物）の Blender ベイク工程を ai-native へ統合（agent/b-1219-lead）。`uzu.py building` で spec から家／店舗を生成（開口は形状で作る）、手続きテクスチャを 2048 ベイク→1024 で GLB 化。見本5棟でベイク欠落率 0.009〜0.146%、稜線保存率 1.0、同一 spec の GLB が md5 一致。エンジン内レシピ（クラウド、第1段）と合わせて建物の両ルートが揃った。残りは第2段（品質指標の B-1204 組み込み、WorldGen 本体の家置き換え、ORM／AO、内部フェースカリング）と岩・自然物。

- 2026-11-20: B-1109 VFX レシピを ai-native へ統合（agent/b-1109-lead）。新規クラス UZUVfx がレシピ（Dictionary／JSON）から複合エフェクトを生成・追跡する。見本 explosion／laser を同梱し、全テスト 1572 pass。**Phase 11（UZUJuice）はこれで全項目完了**。

- 2026-11-20: B-1306 と B-1004 を ai-native へ統合（agent/b-1306-lead）。『灯りの欠片』の UI を wafu 世界観テーマで作り直し（宣言的タイトル、ゲージ HUD、会話枠）、仮想スティックとインタラクトボタンのタッチ操作を追加。完走検証は同一ハッシュで pass、UI レポートで text_overflow 3件→0件。

- 2026-11-20: B-1508 を ai-native へ統合（agent/b-1508-lead）。『灯りの欠片』の村を UZUWorldGen 生成（Land＋Pond＋City の合成、ground オプション新設、ベンチ当たり追加）に置き換え、完走検証と歩行検証（5/5）が通ることを確認。map_tool の NavigationMesh 保存は実測で問題なしと切り分け。

- 2026-11-20: B-1509 生成仕様の4点セットを ai-native へ統合（agent/b-1509-lead）。生成の記録を scene_spec／region_graph／asset_registry／validation_report に揃える仕組みが入り、観測できた事実と補完した推論が区別して残るようになった。

- 2026-11-20: B-1510 地域グラフ歩行検証を ai-native へ統合（agent/b-1510-lead）。生成マップの全経路を AI が実歩行して合否を出す仕組みが入った。見本の村では基礎スラブの縁が徒歩進入を阻むことが実歩行の証拠で判明（B-1508 の生成側の課題として記録）。

- 2026-11-20: B-1511 保存物の再読監査を ai-native へ統合（agent/b-1511-lead）。**Phase 15（マップ自動生成）はこれで全項目完了**。監査は初回から実物の問題を2件発見した（生成器の自己申告の二重割り算 B-1512、MultiMesh の load fidelity B-1513）。

- 2026-11-20: B-1512 を ai-native へ統合（agent/b-1512-lead）。再読監査が見つけた生成器の自己申告バグ（二重割り算）を修正し、registry の数値が監査の実測と一致するようになった。

- 2026-11-20: B-1221 イメージ先行フローを ai-native へ統合（agent/b-1221-lead）。仕様イラスト1枚から歩けるシーン雛形（レイヤー配置・歩行域・当たり／インタラクト候補・基準カメラ）を spec として生成できるようになった。残りは B-1222（仕様画像レジストリ）と B-1223（仕様差分検証）。

- 2026-11-20: B-1220 アニメーション生成を ai-native へ統合（Codex、agent/b-1220-codex）。`uzu.py anim`／MCP `animation_motion` でリグ付きモデルへ待機・歩行・走行の手続きモーションを付与し、`animation_align` で連番スプライトのフレーム整列。見本で3クリップ生成・ループ継ぎ目差分 0、歩行 75フレームで 1.875 m を確認。Python テスト 89件 pass（本 VM でも tests.test_animation 4件 OK）、エンジン全テスト 1576 pass（ブランチ先端の CI run 44668679444 は success、ネイティブ差分なしのため確認済み editor を SHA-256 照合で使用）。カタログは 224件に再生成（anim 追加、再生成しても差分なし）。

- 2026-11-20: B-1219 第2段を ai-native へ統合（agent/b-1219-s2-lead）。スタイル定義のデータ化により、様式追加がコード変更なしで可能になった（alpine 実証）。ORM/AO ベイク、内部フェースカリング、瓦インスタンシング、岩レシピまで完了し B-1219 は完了。

- 2026-11-20: B-1111 音の機械チェックを ai-native へ統合（agent/b-1111-lead）。AI が聞けない音を波形の数値で検査できるようになった（クリッピング・無音・ループ継ぎ目・スプライト整合）。B-1108 の耳確認の宿題のうち機械で見られる部分はこれでカバー。

- 2026-11-20: B-1223 仕様差分検証を ai-native へ統合（agent/b-1223-lead）。仕様画像と画面の差分を構図・色調・要素単位で機械判定できるようになり、イメージ先行フローの「寄せる」作業がループに乗った。残りは B-1222（仕様画像レジストリ）。

- 2026-11-20: B-1224 当たり判定の機械チェックを ai-native へ統合（agent/b-1224-lead）。静的検査で B-1510 の進入不能 finding を精密化（阻害箇所は南縁の 0.31m 段差と特定）。イメージ先行フローのチェック道具（B-1223／B-1224）が揃い、B-1005 の依存は B-1112 のみになった。
- 2026-11-20 B-1112 手触りの代理指標を統合（リード）。feel_probe＋feel_report＋uzu.py feel-report。hikari の収集は遅延1物理フレーム・flash 実測約120ms（要求どおり）、juice 無効版では全チャネル0の数値差を確認。エンジン1574/1576（既知UDP2件）、Python 全pass、C++変更なし。カタログ238件
- 2026-11-20 『灯りの欠片』Web 版の軽量化（リード）: Web 書き出し時のみ 3D 解像度スケール 0.7＋太陽の影距離 70m に制限（main.gd _web_perf_tuning、editor 実行では無効）。切り分けで判明: _ready での directional_shadow_atlas_set_size はロックステップ検証を壊すため不採用。完走検証 pass×2、Web 再書き出し・再配置済み（u-zu.co.jp/hikari-20261120/）
- 2026-11-21 『灯りの欠片』実プレイFB修正を統合（agent/hikari-fix-20261120）: ①エンジン UZUPicture が書き出し版で res:// 画像を読めないバグを修正（ResourceLoader 優先＋ファイル読込フォールバック、新規テスト込み、全テスト 1575/1577・既知UDP2件のみ）②クリアパネルが左上に半分はみ出す配置バグ（position=-size/2）をオフセット中心合わせに修正（オーナーのスクショの正体は会話窓ではなくクリアパネルだった）③タイトルに開始プロンプトの明示＋点滅と、スレッド読み込み＋「読み込み中…」表示。完走検証 pass
- 2026-11-21 『灯りの欠片』実プレイFB修正 第2弾を統合（agent/hikari-fix2-20261121）: ①開始時のひっかかり: 世界生成を段階実行化＋生成世界まるごとの事前ベイク同梱（baked_village.scn 3.8MB、指紋不一致時は段階生成にフォールバック）。実測 押下→操作可能 758ms→191ms、最長フレーム 704ms→98ms、開始ハッシュは全方式一致。事前計算の原則は BRIEFING に明記済み（同日オーナー方針）②フォント欠け13文字を特定しサブセット再生成（197→614グリフ）、check_font_coverage.py で再発防止 ③UZUUI 羊皮紙の32pxタイル繰り返しを128px＋低コントラスト合成に変更（scene/gui/uzu_ui.cpp、性質テスト追加）。エンジン 1576/1578（既知UDP2件）。あわせて CLAIMS.md に残っていた旧コンフリクトマーカー（B-1111/B-1112/B-1224 行）を解消
- 2026-11-21 B-1003 完了: オーナーが iPhone 実機で Web 版（u-zu.co.jp/hikari-20261120/）をプレイしクリアまで到達（スクショ確認）。Phase 10 はこれで全項目完了（実 itch 公開は B-501 に残る）

- 2026-11-21 B-1504〜B-1507 の LEDGER 追記（リード、台帳の締め）: 2026-11-19 に ai-native へ反映済みだったが LEDGER への転記が漏れていたため補記。B-1504 村同士を道で結ぶ（最小全域木＋A*、全区間の連結を単体テストで確認、全テスト 1560 pass、記録 iterations/2026-11-19-B-1504-claude.md）。B-1505／B-1506 は UZUWorldGen として統合（modules/uzu_worldgen、CI 全テスト 1548 pass）。B-1507 街にベンチと NavigationMesh（建物・木・街灯・ベンチ・噴水を除外、places_connected）＋歩行の自己検証 uzu.py map walk／MCP map_walk、6つの街で全目的地に到着、全テスト 1561 pass、記録 iterations/2026-11-19-B-1507-claude.md。BACKLOG・CLAIMS は完了済み。Phase 15 の完了自体は B-1511 の項に記録済み。

- 2026-11-22 B-1310 UI品質ゲート完了（リード統合）: agent/b-1310-muse を統合。`uzu.py ui-quality` が AAA水準5項目（繰り返し指数／コントラスト／状態完全性／被覆率／スケール適合）を合否 JSON で返す。現行 wafu は fail（繰り返し 0.52、被覆率 0.375、フォーカス不可視、余白・影のオフスケール多数）＝監査の欠陥を検出漏れなく捕捉。以後の UI 改善（B-1311〜B-1315）の判定はこのゲートで行う。

- 2026-11-22 B-1310 修正（リード、CI 復旧）: 統合直後の uzu_verify run #44955489719 が Agent tool self-tests で failure（ui_quality.py とテストが numpy を import するがランナーに無く ModuleNotFoundError）。ワークフロー変更ではなく本体側で直した: 自己相関の FFT を標準ライブラリ実装へフォールバック化（numpy がある場合は従来の高速経路、無い場合は純 Python FFT で同じ値を計算。実測で両経路の差 0.00000 を確認）。テストの合成画像生成も random＋PIL 化。numpy 遮断のシミュレーションでゲートが完走し、現行 wafu は従来どおり fail（繰り返し指数 0.5205）になることを確認。

- 2026-11-22 B-1310 修正その2（リード、CI 復旧）: numpy 修正直後の uzu_verify run #44957378060 が再び Agent tool self-tests で failure（tests/test_ui_quality.py の RepetitionTest 2件が `from PIL import Image` で ModuleNotFoundError。ランナーに Pillow が無い）。ワークフロー変更ではなく本体側で直した: PIL 依存の合成画像テスト2件を PIL 不在時は skip する形にし、ui font subset の skip（fonttools/brotli 不在時）と同じ扱いにした。PIL がある環境では 13件すべて実行され pass、PIL 遮断のシミュレーションでは 11件 pass＋2件 skip で exit 0 を確認。`uzu.py ui-quality` 本体の texture_repetition は従来どおり PIL を使う（スクリーンショット解析の実行時依存であり、CI の self-test では呼ばれない）。

- 2026-11-22 B-1311 枠テクスチャの高品質化 完了（リード統合）: agent/b-1311-muse を統合。装飾漏れは角マージン確保量の不足（4px）が原因と特定し構造修正（漏れ実測 16/64px → 0px）。素材生成は fbm＋ドメインワープ＋タイル256px＋3層構成へ、生成スケール scale 1/2 を追加。全テスト 1579/1581。ゲートの繰り返し指数は見本画面の切り出しでは切り分け不能だったため、空パネルで測る手順を B-1315 で整備する留保つきで締める。

- 2026-11-22 B-1313 テーマ完全性とフォーカス 完了（リード統合）: agent/b-1313-muse を統合。未被覆10種すべてに両テーマでスタイル付け、フォーカスはアクセント2pxリングに置換。ゲート被覆率 1.0・状態完全性 pass、全テスト 1580/1582。弱点（スライダー溝の低コントラスト）は B-1315 へ。

- 2026-11-22 B-1312 タイポグラフィ体系 完了（リード統合）: agent/b-1312-muse を統合。タイプスケール5段（比率1.25、基準＝既存 font_size で互換）、字間・行間・縁取り／影プリセット、JSON の text_style 対応。全テスト 1581/1583、ゲート既存 pass 項目を維持。

- 2026-11-22 B-1314 レイアウト／エレベーション体系 完了（リード統合）: agent/b-1314-muse を統合。余白・角丸・影をスケール化（spacing/radius/elevation L0〜L4、get_layout_scale＋テーマ meta）、JSON のステップ名参照に対応。全7テーマでゲートのスケール適合 pass、全テスト 1582/1584。persona の contrast fail は B-1315 へ。

- 2026-11-22 B-1316 フォントのロケール検証 完了（リード統合）: agent/b-1316-muse を統合。uzu.py font-locale-check（句読点インク上端／本文帯 ≤0.5 で pass）。実測で配布フォント・JP は pass、TC は fail。見本フォント規約を look_samples/README.md に新設。カタログ 243 件。

- 2026-11-22 B-1317 UIモーション 完了（リード統合）: agent/b-1317-muse を統合。UZUUIJuice にプリセット5種の統一口と seek/state の検証口を追加、世界観差（persona のオーバーシュート等）をテストで固定。全テスト 1592/1594。persona の skew パネル中央の楔抜けは B-1318 で直す。

- 2026-11-22 B-1318 素材の階層化＋skew楔抜け修正 完了（リード統合）: agent/b-1318-muse を統合。draw_frame に inner_shadow／highlight／glow の3層（既定は従来一致）、skew は半タイルスライスで楔抜けを解消。全テスト 1594/1596。次は最終項目 B-1315（実証画面・ゲート全項目 pass）。

- 2026-11-22 B-1315 AAA水準の実証画面 完了（リード統合）: agent/b-1315-muse を統合。persona／wafu ×5画面でゲート全項目 pass（persona 本文コントラスト 4.802、被覆率 1.0）、包含 全10画面 pass（静止時＋peak 位相）。hikari HUD の ■■■ をアイコン化、タッチ UI を部品化、繰り返し測定をシート経路へ作り直し。Phase 13 の UI品質 AAA 化（B-1310〜B-1318）はこれで全項目完了。
- 2026-11-22 B-1319 統合（リード）: 会話窓 skew 底辺の二重帯（9スライス縦軸 TILE が原因）を STRETCH 化で解消、グリントを枠アルファにクリップ、背景構図を UZUUI.draw_backdrop／make_backdrop として部品化し全世界観にプリセット。全テスト 1599/1601、ゲート・包含 pass 維持。
- 2026-11-22 B-1320 統合（リード）: persona 見本のデザイン作り込み（ロゴ級タイトル・色面の X 交差・透かし英字・フォーカス反転）とアニメーション振り付け（スタッガ出現・遷移・アイドル）を実装。動画 motion_persona.mp4 をオーナー確認用に作成。全テスト 1600/1602、ゲート・包含 pass 維持。
- 2026-11-23 B-1321 統合（リード）: グラデーション（frame／backdrop）と細密ハーフトーン（4px・陰色ドット・AA縁）を実装、シート測定の原寸化も修正。3DレンダリングUIの試行（b1321 プロジェクト、撮影＋動画）を作成。全テスト 1601/1603、ゲート・包含 pass 維持。
- 2026-11-23 B-1322 統合（リード）: persona 見本に多段／放射グラデーション、ライティング（sweep／rim／bloom、3D は動的光源）、エフェクト（塵・burst・flash・slash）を投入。バー文字と会話画面の密度、3D 構図も改善。before／after 並置と動画更新。全テスト 1602/1604、ゲート・包含 pass 維持。
- 2026-11-24 B-1323 統合（リード）: fantasy／horror（a班）と sf／pixel（b班）の見本を統合。競合は CLAIMS（両行保持）、main.gd（分岐の合体）、uzu_ui.cpp Decor 表（sf=sweep 0.35 を b から、horror=フリッカ 0.60／rim 0.12 を a から）、containment.json（JSON 合体）で解消。これで6世界観すべての見本が揃った。
- 2026-11-24 B-1324 統合（リード）: アート主導タイトル（arttitle）を統合。素材は ChatGPT 生成の背景アートとキャラ切り抜き（テクスチャ分離の flood fill）。全テスト 1603/1605、包含 31/31、ゲート pass。本統合には、B-1323 統合時のリードの競合解消で main.gd から落ちた閉じ括弧1行の補修を含む（ai-native の見本プロジェクトはその間パースエラーだった。B-1324 担当の検出）。
- 2026-11-24 B-1325 統合（リード）: アート主導を persona の残り4画面（メニュー／設定／会話／HUD）へ拡張。素材の画面別焼き分け、会話のバストアップ、HUD の縁配置。全テスト 1603/1605、包含 35/35、ゲート pass。
- 2026-11-24 B-1326 統合（リード）: 競馬／シムのデータ密度型UI（racing／sim 世界観＋3画面）と部品化（StatBar／Chip／DataTable／DetailPanel）を統合。B-1325 との main.gd 競合は見出しコメントのみで、コードは一般化側に B-1326 のデータ配線が合体した形で解消。全テスト 1604/1606、ゲート racing／sim pass、包含 34/34。
- 2026-11-24 B-1328 統合（リード）: データ画面の仕上げ。表の全列表示（列幅の実測再配分）と sim の焼き込み残片消去＋ラベル再配置。包含 38/38、ゲート無回帰、全テスト 1604/1606。
- 2026-11-24 B-1329 統合（リード）: 『スターホース牧場』U.ZU 版サンプル。B-1326 キットで3画面＋実況29本の局面同期キュー。自動プレイ検証 pass、全テスト 1604/1606。

- 2026-11-25 B-1330 統合: 『スターホース牧場』U.ZU 版の最高品質化（agent/b-1330-muse @7b24f38ea07）。アート主導の全画面（タイトル新設／牧場・出馬表のアート全面化）、レースは横視点 2.5D（3層パララックス＋切り抜き馬＋スロー／シェイク）、結果画面追加。自動プレイ pass、全テスト 1604/1606。成果物は Windows exe（starhorse-uzu-win.zip）。Windows テンプレートはデータ部品入りの新ビルドに差し替え（旧版は .bak-20261125）。
- 2026-11-25: B-1332 統合（リード）: 『スターホース牧場』のレースを実3D化。リグ済み馬 GLB の内蔵 Gallop を速度同期、BoneAttachment3D でジョッキー騎乗、コース・ラチ・ゲート・スタンド・距離標識を3D構築、中継型カメラ。verify pass（シム結果は B-1330 と同一）、全テスト 1604/1606。exe 差し替え済み（73MB）。
- 2026-11-27 B-1331 統合（リード）: map_tool の外部保存に NavigationMesh を含める（agent/b-1331-codex @b15089beaea、worldgen2 ブランチの2行だけを移植）。村の外部保存・再読込 12/12 pass（頂点 3,588・ポリゴン 3,795 が一致、.tscn は ext_resource 参照）。統合前にブランチを fork へ push し uzu_verify run 45898571695 が green（全テスト＋self-test、5m27s）を確認してから統合。ローカル分割実行の 13 fail は環境のソケット制限（ENet／TCP／UDP／UDS の EPERM）で変更（GDScript 2行）と無関係。
- 2026-11-27 B-1327 統合（リード）: エンジン→AI のプロンプト要求プロトコル（agent/b-1327-codex @9ed90e53cd2、Codex）。uzu-prompt-request/1・uzu-prompt-result/1 の仕様（PROMPT_REQUEST.md）、決定的プロンプト合成、uzu.py prompt-request（compose／issue／list／get／submit）、.uzu/prompt-requests への発行・回収。ai_loop の Python・カタログ・文書のみでエンジン本体の変更なし。往復 4/4（素材生成／撮影評価×fixed／design）、新規テスト 9/9 pass。統合後の CI run 45962400694 が success（全テスト 1606 pass、632805 assertions、5m20s）。ブランチに push がなかったため（Codex 側はプロキシで fetch 不可）、ブランチ CI の代わりに ai-native への統合後 CI で確認した。make_catalog.py --check の未登録 2 件（ui_containment_probe、UZUTouchStick）は B-1327 外で着手前から同じ。
- 2026-11-27 台帳の締め（リード、定例チェック）: B-1501／1502／1503／1505／1506 の CLAIMS 行を補記（2026-11-19 の滞留ブランチ整理で統合済み・CI 1548 pass。LEDGER 2026-11-21 の「BACKLOG・CLAIMS は完了済み」はこの5件の CLAIMS 行が未記入だったため訂正）。B-108 の CLAIMS 行も補記（agent/b-005-codex-windows で統合済み）。滞留ブランチの判定: agent/b-108-codex は b-005-codex-windows と重複する別実装（7サイズ .ico が10サイズ版と競合）のため統合しない。agent/worldgen2-claude-local と agent/b-1507-lead はクラウド版 B-1504／B-1507 が ai-native に入っており superseded のため統合しない（後者は記録に明記あり）。agent/b-902-blurfix-muse の内容は ai-native に既に入っている。ワークフロー3件（agent/b110push-claude-local、agent/verify-artifact-codex、agent/windows-artifact-codex）は運用ルールどおり保留（artifact アップロードは ai-native のワークフローに既に入っている）。claude/uzu-engine-briefing-rrno7b の未統合 22コミットはいずれも 2026-11-18/19 の旧作業で、内容は ai-native へ別経路で反映済み（B-1302／1303／1305、B-1504／B-1507、B-1219 第1段など）。2026-11-20 の「専用の統合セッション」は不要になった。CI は green（最新 run 45963182903 success、2026-11-27 08:06:53Z）。
