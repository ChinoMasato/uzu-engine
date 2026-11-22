extends Control
## B-1314 showcase: every standard control in one screen, styled by one
## UZUUI theme (the default theme, or a world theme named on the command
## line after "--"). Captured with --write-movie; see ../README notes in
## ai_loop/iterations/2026-11-22-B-1314-muse.md.

func _label(text: String) -> Label:
	var l := Label.new()
	l.text = text
	return l


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var world := args[0] if args.size() > 0 else "wafu"
	if world == "default":
		theme = UZUUI.create_theme({})
	else:
		theme = UZUUI.create_world_theme(world)

	var bg := ColorRect.new()
	bg.color = Color(0.11, 0.12, 0.15)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 24)
	margin.add_theme_constant_override("margin_top", 24)
	margin.add_theme_constant_override("margin_right", 24)
	margin.add_theme_constant_override("margin_bottom", 24)
	add_child(margin)

	var root := HBoxContainer.new()
	root.add_theme_constant_override("separation", 24)
	margin.add_child(root)

	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 16)
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(col)

	# Rows 1-3 sit inside the world panel, as they would on a real
	# settings screen (the wafu text color is dark because it is read on
	# parchment).
	var top_panel := PanelContainer.new()
	col.add_child(top_panel)
	var top := VBoxContainer.new()
	top.add_theme_constant_override("separation", 16)
	top_panel.add_child(top)

	# Row 1: buttons and toggles.
	var row1 := HBoxContainer.new()
	row1.add_theme_constant_override("separation", 16)
	top.add_child(row1)
	var button := Button.new()
	button.text = "Button"
	row1.add_child(button)
	var check_on := CheckBox.new()
	check_on.text = "CheckBox on"
	check_on.button_pressed = true
	row1.add_child(check_on)
	var check_off := CheckBox.new()
	check_off.text = "CheckBox off"
	row1.add_child(check_off)
	var radio := CheckBox.new()
	radio.text = "Radio"
	radio.toggle_mode = true
	radio.button_pressed = true
	row1.add_child(radio)
	var option := OptionButton.new()
	option.add_item("Option A")
	option.add_item("Option B")
	option.add_item("Option C")
	option.select(0)
	row1.add_child(option)
	# Keyboard focus made visible: the Button holds it.
	button.grab_focus()

	# Row 2: text and number entry.
	var row2 := HBoxContainer.new()
	row2.add_theme_constant_override("separation", 16)
	top.add_child(row2)
	var line := LineEdit.new()
	line.text = "LineEdit sample"
	line.custom_minimum_size = Vector2(260, 0)
	row2.add_child(line)
	var spin := SpinBox.new()
	spin.min_value = 0
	spin.max_value = 100
	spin.value = 42
	spin.custom_minimum_size = Vector2(140, 0)
	row2.add_child(spin)
	var bar := ProgressBar.new()
	bar.min_value = 0
	bar.max_value = 100
	bar.value = 65
	bar.custom_minimum_size = Vector2(200, 20)
	bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row2.add_child(bar)

	# Row 3: slider and horizontal scroll bar.
	var row3 := VBoxContainer.new()
	row3.add_theme_constant_override("separation", 12)
	top.add_child(row3)
	var hslider := HSlider.new()
	hslider.min_value = 0
	hslider.max_value = 100
	hslider.value = 60
	hslider.custom_minimum_size = Vector2(0, 24)
	row3.add_child(hslider)
	var hscroll := HScrollBar.new()
	hscroll.min_value = 0
	hscroll.max_value = 100
	hscroll.page = 25
	hscroll.value = 25
	hscroll.custom_minimum_size = Vector2(0, 16)
	row3.add_child(hscroll)

	# Row 4: tree and list side by side, inside the world panel.
	var panel := PanelContainer.new()
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(panel)
	var row4 := HBoxContainer.new()
	row4.add_theme_constant_override("separation", 16)
	panel.add_child(row4)
	var tree := Tree.new()
	tree.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var troot := tree.create_item()
	troot.set_text(0, "Root")
	var item_a := tree.create_item(troot)
	item_a.set_text(0, "Item A (selected)")
	var item_b := tree.create_item(troot)
	item_b.set_text(0, "Item B")
	var nested := tree.create_item(item_b)
	nested.set_text(0, "Nested item")
	row4.add_child(tree)
	var list := ItemList.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_item("Sword")
	list.add_item("Shield")
	list.add_item("Potion")
	list.select(1)
	row4.add_child(list)
	item_a.select(0)

	# Right column: vertical slider and scroll bar.
	var side := VBoxContainer.new()
	side.add_theme_constant_override("separation", 12)
	root.add_child(side)
	var vslider := VSlider.new()
	vslider.min_value = 0
	vslider.max_value = 100
	vslider.value = 40
	vslider.custom_minimum_size = Vector2(24, 220)
	side.add_child(vslider)
	var vscroll := VScrollBar.new()
	vscroll.min_value = 0
	vscroll.max_value = 100
	vscroll.page = 25
	vscroll.value = 30
	vscroll.custom_minimum_size = Vector2(16, 220)
	side.add_child(vscroll)
	side.add_child(_label("VSlider / VScrollBar"))

	# A popped-up menu, so the PopupMenu styling is in the shot too.
	var menu := PopupMenu.new()
	menu.add_check_item("Show grid")
	menu.add_item("Reset view")
	menu.add_separator()
	menu.add_item("Quit")
	menu.set_item_checked(0, true)
	add_child(menu)
	menu.popup(Rect2i(36, 400, 240, 0))
