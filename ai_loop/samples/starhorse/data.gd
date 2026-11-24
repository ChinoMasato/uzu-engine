class_name StarHorseData
extends RefCounted
## Canonical data of the sample (B-1329): the eight owned horses, the
## race draw, and the detail-panel records for the kit's DataTable /
## DetailPanel parts. make_specs.py mirrors the draw into
## specs/entries.json -- keep the two in sync.

## Running styles: 逃げ front-runner / 先行 stalker / 差し closer /
## 追込 deep closer. The race sim (race.gd) paces by style, and the
## commentary picks its win line from the winner's style.
const HORSES := [
	{"name": "サンライズエース", "age": 3, "sex": "牡", "speed": 92, "stamina": 78,
		"form": "絶好調", "stable": "美浦", "face": 0, "style": "先行",
		"record": "12戦 5勝", "weight_kg": 480, "next": "日本ダービー"},
	{"name": "ミライノカゼ", "age": 4, "sex": "牝", "speed": 85, "stamina": 88,
		"form": "好調", "stable": "美浦", "face": 1, "style": "差し",
		"record": "15戦 4勝", "weight_kg": 452, "next": "安田記念"},
	{"name": "ホワイトオーシャン", "age": 5, "sex": "牡", "speed": 90, "stamina": 95,
		"form": "絶好調", "stable": "栗東", "face": 2, "style": "先行",
		"record": "18戦 7勝", "weight_kg": 512, "next": "春風ステークス"},
	{"name": "レッドヴァルキリー", "age": 3, "sex": "牝", "speed": 78, "stamina": 72,
		"form": "好調", "stable": "美浦", "face": 3, "style": "逃げ",
		"record": "8戦 3勝", "weight_kg": 446, "next": "桜花賞"},
	{"name": "キングスパーク", "age": 6, "sex": "牡", "speed": 88, "stamina": 65,
		"form": "普通", "stable": "栗東", "face": 4, "style": "先行",
		"record": "24戦 6勝", "weight_kg": 498, "next": "春風ステークス"},
	{"name": "ブルームスター", "age": 2, "sex": "牝", "speed": 72, "stamina": 80,
		"form": "絶好調", "stable": "美浦", "face": 5, "style": "追込",
		"record": "3戦 1勝", "weight_kg": 430, "next": "未定"},
	{"name": "シルバーグローリー", "age": 4, "sex": "牡", "speed": 83, "stamina": 90,
		"form": "好調", "stable": "栗東", "face": 6, "style": "差し",
		"record": "14戦 5勝", "weight_kg": 486, "next": "青葉賞"},
	{"name": "ハヤテノツバサ", "age": 3, "sex": "牡", "speed": 95, "stamina": 60,
		"form": "普通", "stable": "美浦", "face": 7, "style": "逃げ",
		"record": "9戦 2勝", "weight_kg": 468, "next": "皐月賞"},
]

## The draw of the sample race (gate order). JRA frame colours double
## as the silk colours of the 2D race view.
const FRAME_COLORS := ["#f5f5f5", "#26221f", "#e60012", "#0055c4",
		"#f7d117", "#009944", "#f08300", "#ee86a8"]
const DRAW := [
	{"horse": 0, "jockey": "佐々木蓮", "burden": 56, "odds": 8.4, "popularity": 4},
	{"horse": 3, "jockey": "山田悠真", "burden": 54, "odds": 9.7, "popularity": 5},
	{"horse": 2, "jockey": "小林直樹", "burden": 57, "odds": 3.1, "popularity": 1},
	{"horse": 5, "jockey": "鈴木健吾", "burden": 54, "odds": 26.4, "popularity": 8},
	{"horse": 4, "jockey": "中村恵太", "burden": 58, "odds": 18.9, "popularity": 7},
	{"horse": 1, "jockey": "高橋宗一郎", "burden": 55, "odds": 6.2, "popularity": 3},
	{"horse": 7, "jockey": "井上翔太", "burden": 56, "odds": 12.6, "popularity": 6},
	{"horse": 6, "jockey": "田村亮太", "burden": 57, "odds": 4.8, "popularity": 2},
]

const RACE_NAME := "春風ステークス"
const RACE_DISTANCE := 1800


static func farm_record(i: int) -> Dictionary:
	var h: Dictionary = HORSES[i]
	return {
		"title": h["name"],
		"portrait": load("res://art/face_%d.png" % int(h["face"])),
		"rows": [["年齢", "%d歳 %s" % [int(h["age"]), h["sex"]]],
			["戦績", h["record"]], ["馬体重", "%dkg" % int(h["weight_kg"])],
			["厩舎", h["stable"]], ["調子", h["form"]], ["次走", h["next"]]],
		"bars": [{"caption": "スピード", "value": int(h["speed"])},
			{"caption": "スタミナ", "fill": "#3f9fd8", "value": int(h["stamina"])}],
	}


static func entries_record(gate: int) -> Dictionary:
	var d: Dictionary = DRAW[gate - 1]
	var h: Dictionary = HORSES[int(d["horse"])]
	return {
		"title": h["name"],
		"portrait": load("res://art/face_%d.png" % int(h["face"])),
		"rows": [["枠・馬番", "%d枠 %d番" % [gate, gate]],
			["性齢", "%s%d" % [h["sex"], int(h["age"])]],
			["騎手", d["jockey"]], ["負担重量", "%dkg" % int(d["burden"])],
			["オッズ", "%.1f" % float(d["odds"])], ["人気", "%d番人気" % int(d["popularity"])]],
		"bars": [{"caption": "スピード", "value": int(h["speed"])},
			{"caption": "スタミナ", "fill": "#3f9fd8", "value": int(h["stamina"])}],
	}
