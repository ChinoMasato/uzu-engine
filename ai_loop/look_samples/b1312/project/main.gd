extends Control
## B-1312 showcase: the type scale as a specimen sheet — every step
## (display / title / heading / body / caption) in one screen, styled by
## one UZUUI world theme (named on the command line after "--", default
## "wafu"). Each row is tagged with its step name in the caption step.
## Captured with --write-movie; see ai_loop/iterations/2026-11-22-B-1312-muse.md.

const SAMPLES := {
	"display": "Hikari no Kakera",
	"title": "Chapter One - The Village of Lamps",
	"heading": "Quest log: three shards for the shrine",
	"body": "The lantern at the shrine has gone out. Gather the three shards of light scattered around the village and bring them back before dusk, while the paths are still safe to walk.",
	"caption": "Version 1.2 - the game autosaves at the shrine.",
}


func _row(step: String) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 24)
	var tag := UZUUI.make_label(step, "caption")
	tag.custom_minimum_size = Vector2(90, 0)
	row.add_child(tag)
	var sample := UZUUI.make_label(SAMPLES[step], step)
	sample.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if step == "body":
		sample.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(sample)
	return row


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var world := args[0] if args.size() > 0 else "wafu"
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

	# The steps sit inside the world panel, as they would on a real title
	# or menu screen (the wafu text color is dark because it is read on
	# parchment).
	var panel := PanelContainer.new()
	margin.add_child(panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 28)
	panel.add_child(col)
	for step in ["display", "title", "heading", "body", "caption"]:
		col.add_child(_row(step))
