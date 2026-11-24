class_name Commentary
extends Node
## Race commentary player (B-1329): the comparison point against the
## Godot original. The race sim reports phase events; this node maps
## each event to one of the 29 voice clips (the mapping table of
## audio/voice/README.md), queues them, and plays them back in order on
## the dedicated "Voice" bus so they never fight the BGM.
##
## Every trigger is recorded in `event_log` ({seq, phase, voice, t}) at
## trigger time -- the headless verifier checks that log, not the audio
## hardware, so the firing order is testable on any machine. Playback
## advances on the player's `finished` signal, with a watchdog that
## force-advances after the clip's length (+margin) so a dummy audio
## driver can never stall the queue. In `fast` mode (headless verify) a
## clip counts as 0.12 s.

signal line_changed(text: String)

const LINES := {
	"01_pre_gatein": "各馬、ゲートインが完了しました。まもなく発走です。",
	"02_pre_ready": "スタートの時を待ちます。全馬、態勢が整いました。",
	"03_start": "スタートしました！ 各馬、一斉に飛び出しました！",
	"04_start_clean": "綺麗なスタートを切りました！",
	"05_start_late": "あっと、出遅れた馬がいます！",
	"06_early_lead_battle": "先行争いが激しくなっています。ハナを切るのはどの馬か！",
	"07_early_leader": "先頭に立って、レースを引っ張ります。",
	"08_early_stretched": "集団は縦長になってきました。",
	"09_early_holdback": "後方でじっくりと脚をためています。",
	"10_mid_frontside": "向こう正面に入りました。ペースはやや速めです。",
	"11_mid_settled": "隊列はほぼ固まりました。各馬、虎視眈々と上位を狙います。",
	"12_mid_corner": "3コーナーから4コーナーへ。そろそろ動きが出てきそうです。",
	"13_final_straight": "さあ、最終コーナーを回って直線に入りました！",
	"14_final_leader": "先頭はまだ譲りません！ 後続が一斉に襲いかかります！",
	"15_final_outside": "外から一気に伸びてきた！ これは凄い脚です！",
	"16_final_inside": "内を突いて抜け出してきました！",
	"17_final_200m": "残り200メートル！ 先頭争いは横一線です！",
	"18_final_100m": "残り100メートル！ 勝負はまだ分かりません！",
	"19_goal_win": "ゴールイン！ 見事な勝利です！",
	"20_goal_push": "抜けた、抜けたー！ そのまま押し切りました！",
	"21_goal_close": "大接戦のゴール！ 勝ったのは果たしてどの馬か！",
	"22_goal_photo": "写真判定にもつれ込む大接戦でした！",
	"23_win_frontrun": "逃げ切り勝ちです！ 最後まで先頭を譲りませんでした！",
	"24_win_stalker": "差し切り勝ち！ 直線で一気に差し切りました！",
	"25_win_closer": "豪快な追い込みが決まりました！ 後方から全てを飲み込みました！",
	"26_win_runaway": "大差での圧勝です！ 文句なしの内容でした！",
	"27_upset": "これは大波乱の予感です！",
	"28_crowd": "スタンドが大きく沸いています！",
	"29_closing": "素晴らしいレースでした。勝ち馬に大きな拍手を送りましょう。",
}

var fast := false
var event_log: Array = []

var _player: AudioStreamPlayer
var _queue: Array = []
var _playing_id := ""
var _playing_for := 0.0
var _seq := 0


func _ready() -> void:
	_player = AudioStreamPlayer.new()
	_player.bus = "Voice"
	add_child(_player)
	_player.finished.connect(_on_clip_finished)


## Trigger one commentary line for a race phase. `t` is the race clock
## (seconds since the gate opened, negative during the pre-race).
func say(phase: String, voice_id: String, t: float) -> void:
	_seq += 1
	event_log.append({"seq": _seq, "phase": phase, "voice": voice_id, "t": snappedf(t, 0.01)})
	_queue.append(voice_id)
	if _playing_id == "":
		_play_next()


func is_speaking() -> bool:
	return _playing_id != "" or not _queue.is_empty()


func _process(delta: float) -> void:
	if _playing_id == "":
		return
	_playing_for += delta
	var limit := 0.12 if fast else _clip_length(_playing_id) + 0.35
	if _playing_for >= limit:
		_play_next()


func _on_clip_finished() -> void:
	if not fast:
		_play_next()


func _clip_length(voice_id: String) -> float:
	var stream := _player.stream
	if stream != null:
		return stream.get_length()
	return 2.0


func _play_next() -> void:
	_playing_for = 0.0
	if _queue.is_empty():
		_playing_id = ""
		_player.stop()
		line_changed.emit("")
		return
	_playing_id = str(_queue.pop_front())
	var path := "res://audio/voice/%s.wav" % _playing_id
	if ResourceLoader.exists(path):
		_player.stream = load(path)
		_player.play()
	line_changed.emit(LINES.get(_playing_id, ""))
