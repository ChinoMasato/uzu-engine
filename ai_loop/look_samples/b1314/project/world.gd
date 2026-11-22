extends Control
## B-1314 world-UI sample: the same layout as the B-1311 wafu sample
## (status panel with gauges and slots, a ribbon, a menu, a talk window),
## re-shot after the layout-scale migration to confirm the migration did
## not break the look. Captured with --write-movie.

func _place(c: Control, x: float, y: float, w: float, h: float) -> void:
	c.position = Vector2(x, y)
	c.size = Vector2(w, h)
	add_child(c)


func _ready() -> void:
	theme = UZUUI.create_world_theme("wafu")

	var bg := ColorRect.new()
	bg.color = Color(0.32, 0.32, 0.33)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Status panel, top-left.
	var status := PanelContainer.new()
	var sbox := VBoxContainer.new()
	sbox.add_theme_constant_override("separation", 8)
	status.add_child(sbox)
	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 8)
	var mina := Label.new()
	mina.text = "ミナ"
	mina.theme_type_variation = "UZUTitleLabel"
	name_row.add_child(mina)
	var lv := Label.new()
	lv.text = "Lv.7"
	lv.theme_type_variation = "UZUTitleLabel"
	name_row.add_child(lv)
	sbox.add_child(name_row)
	for row in [["HP", 65.0], ["MP", 40.0]]:
		var r := HBoxContainer.new()
		r.add_theme_constant_override("separation", 8)
		var l := Label.new()
		l.text = row[0]
		l.custom_minimum_size = Vector2(36, 0)
		r.add_child(l)
		var g := UZUUI.make_gauge(row[1], 100.0, 20)
		g.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		r.add_child(g)
		sbox.add_child(r)
	sbox.add_child(UZUUI.make_separator())
	var slots := HBoxContainer.new()
	slots.add_theme_constant_override("separation", 8)
	slots.add_child(UZUUI.make_item_slot("灯", 1))
	slots.add_child(UZUUI.make_item_slot("鍵"))
	slots.add_child(UZUUI.make_item_slot("薬", 3))
	slots.add_child(UZUUI.make_item_slot(""))
	sbox.add_child(slots)
	_place(status, 24, 36, 340, 228)

	# Ribbon, top-center.
	_place(UZUUI.make_ribbon("灯りの欠片"), 372, 36, 408, 64)

	# Menu, top-right.
	var menu := PanelContainer.new()
	var mbox := VBoxContainer.new()
	mbox.add_theme_constant_override("separation", 8)
	menu.add_child(mbox)
	for text in ["どうぐ", "そうび", "セーブ"]:
		var b := Button.new()
		b.text = text
		b.custom_minimum_size = Vector2(0, 52)
		mbox.add_child(b)
	_place(menu, 952, 36, 176, 228)

	# Talk window along the bottom.
	var talk := UZUUI.make_talk_window("村の長老", "祠のランタンが消えてしまった。夕暮れまでに、灯りの欠片を三つ集めてきておくれ。")
	talk.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	talk.offset_left = 40
	talk.offset_right = -40
	talk.offset_top = -140
	talk.offset_bottom = -24
	add_child(talk)

	var motion := UZUUIWorld.new()
	motion.world = "wafu"
	add_child(motion)
