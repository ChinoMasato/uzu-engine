class_name ResultScreen
extends Control
## The result screen (B-1330): the finishing order as a kit DataTable
## over the racecourse art, the winner's gallop cut large on the left,
## and the fanfare as the celebration (the same clip that opens the
## race -- the only fanfare in the shared material). Built in code
## because the table's rows are the race's own results; every part is
## a UZUUI kit call, dressed by the racing world theme main.gd sets.

signal back_to_farm
signal rematch

const FONT := preload("res://art/game_font_jp.ttf")

var _fanfare: AudioStreamPlayer


func _ready() -> void:
	_fanfare = AudioStreamPlayer.new()
	_fanfare.bus = "BGM"
	_fanfare.stream = load("res://audio/fanfare.mp3")
	add_child(_fanfare)


## Builds the screen for one finished race. `results` is the array
## race.gd emits: runner dicts in finishing order, each with gate /
## horse / draw / finish_t / margin.
func show_results(results: Array) -> void:
	for child in get_children():
		if child != _fanfare:
			child.queue_free()
	var bg := TextureRect.new()
	bg.texture = load("res://art/racecourse_art.jpg")
	bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var shade := TextureRect.new()
	shade.texture = load("res://art/shade.png")
	shade.stretch_mode = TextureRect.STRETCH_SCALE
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(shade)

	var winner: Dictionary = results[0]
	var wgate := int(winner["gate"])
	var title := Label.new()
	title.text = "レース結果 — %s" % StarHorseData.RACE_NAME
	title.position = Vector2(36, 26)
	title.add_theme_font_size_override("font_size", 34)
	title.add_theme_color_override("font_color", Color.WHITE)
	title.add_theme_color_override("font_outline_color", Color(0.08, 0.16, 0.05, 0.95))
	title.add_theme_constant_override("outline_size", 10)
	add_child(title)

	# The winner, large: the same gallop cut the race ran with.
	var cut := TextureRect.new()
	cut.texture = load("res://art/horse_var%d.png" % (wgate - 1))
	cut.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	cut.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	cut.position = Vector2(8, 210)
	cut.size = Vector2(600, 304)
	add_child(cut)
	var win_label := Label.new()
	win_label.text = "1着  %d番 %s" % [wgate, str(winner["horse"]["name"])]
	win_label.position = Vector2(36, 128)
	win_label.add_theme_font_size_override("font_size", 30)
	win_label.add_theme_color_override("font_color", Color("#f2d492"))
	win_label.add_theme_color_override("font_outline_color", Color(0.08, 0.16, 0.05, 0.95))
	win_label.add_theme_constant_override("outline_size", 8)
	add_child(win_label)
	var win_sub := Label.new()
	win_sub.text = "%s騎手  タイム %s" % [str(winner["draw"]["jockey"]), str(winner["margin"])]
	win_sub.position = Vector2(36, 168)
	win_sub.add_theme_font_size_override("font_size", 19)
	win_sub.add_theme_color_override("font_color", Color.WHITE)
	win_sub.add_theme_color_override("font_outline_color", Color(0.08, 0.16, 0.05, 0.9))
	win_sub.add_theme_constant_override("outline_size", 6)
	add_child(win_sub)

	# The finishing order, as a kit table.
	var columns := [
		{"title": "着順", "width": 52, "align": "center"},
		{"title": "枠", "width": 40, "align": "center"},
		{"title": "馬名", "width": 160},
		{"title": "騎手", "width": 118},
		{"title": "タイム／差", "width": 104, "align": "right"},
	]
	var rows := []
	for i in range(results.size()):
		var r: Dictionary = results[i]
		var gate := int(r["gate"])
		rows.append([
			{"align": "center", "text": str(i + 1)},
			{"chip": StarHorseData.FRAME_COLORS[gate - 1], "text": str(gate)},
			str(r["horse"]["name"]),
			str(r["draw"]["jockey"]),
			{"align": "right", "text": str(r["margin"])},
		])
	var table := UZUUI.make_data_table(columns, rows, {"row_height": 44})
	table.position = Vector2(622, 108)
	table.size = Vector2(506, 420)
	add_child(table)
	UZUUI.select_table_row(table, 0)

	var back := Button.new()
	back.text = "牧場へ戻る"
	back.position = Vector2(622, 556)
	back.size = Vector2(240, 58)
	back.add_theme_font_size_override("font_size", 22)
	back.pressed.connect(func() -> void: back_to_farm.emit())
	add_child(back)
	var again := Button.new()
	again.text = "もう一度レース"
	again.position = Vector2(886, 556)
	again.size = Vector2(240, 58)
	again.add_theme_font_size_override("font_size", 22)
	again.pressed.connect(func() -> void: rematch.emit())
	add_child(again)
	_fanfare.play()
