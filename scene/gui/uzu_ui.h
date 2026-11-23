/**************************************************************************/
/*  uzu_ui.h                                                              */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#pragma once

#include "core/io/image.h"
#include "core/object/object.h"
#include "core/variant/dictionary.h"
#include "core/variant/typed_array.h"
#include "scene/main/node.h"

class Control;
class ShaderMaterial;
class StyleBox;
class Theme;

// U.ZU UI kit (BACKLOG B-1302, Phase 13 rich UI): panels drawn procedurally (a vertical
// gradient, rounded corners, a border and a soft shadow, in one 9-slice image), a theme
// that styles every common control with them, and constructors for the usual parts
// (panel, button, bar, tabs, list, dialog), so an agent gets a finished look without
// drawing assets. ai_loop/ui_tool.gd (B-1301) builds screens with it.
class UZUUI : public Object {
	GDCLASS(UZUUI, Object);

protected:
	static void _bind_methods();

public:
	// A panel style. Keys: "bg" (a color, or "top"/"bottom" for a gradient), "radius",
	// "border", "border_width", "shadow" (px) or "elevation" (a layout-scale level),
	// "padding" (px or a spacing step name). Colors are Color or "#rrggbb[aa]".
	// Lengths snap to the layout scale (see get_layout_scale).
	static Ref<StyleBox> create_panel_style(const Dictionary &p_style);
	// The 9-slice image behind a panel style (exposed for tests and tools).
	static Ref<Image> draw_panel(int p_radius, const Color &p_top, const Color &p_bottom, const Color &p_border, int p_border_width, int p_shadow);
	// A theme for every common control. Keys (all optional): "accent", "text", "font"
	// (a Font), "font_size", and "panel", "button", "bar" (style dictionaries as above;
	// buttons also take "hover" and "pressed" colors).
	static Ref<Theme> create_theme(const Dictionary &p_options = Dictionary());
	static Dictionary get_theme_defaults();
	// The layout scale (B-1314): the spacing steps, corner radii and
	// elevation levels every length in a theme comes from. "spacing" and
	// "radius" are Arrays of px; "spacing_steps" maps the step names
	// ("xs", "s", "m", "l", "xl", "xxl") specs can use instead of numbers;
	// "elevation" maps a level ("0".."4") to its shadow triple {"shadow",
	// "offset_y", "alpha"}. Style dictionaries take "elevation" next to
	// "shadow", and a "padding" step name next to a number; off-scale
	// numbers snap to the nearest step. The same Dictionary is stored in
	// every theme's "uzu_layout" meta.
	static Dictionary get_layout_scale();
	// The type scale (B-1312): five named text steps — display, title, heading,
	// body, caption — derived from one base size (the theme's "font_size") by a
	// fixed ratio of 1.25. Each step is a Dictionary {"size", "line_spacing",
	// "letter_spacing", "outline_size", "shadow_offset", "variation"}; every
	// theme carries the steps as Label type variations under the "variation"
	// names, and the same Dictionary is stored in the theme's "uzu_type_scale"
	// meta. "letter_spacing" is px of glyph tracking (a FontVariation on the
	// variation), "outline_size"/"shadow_offset" are the step's decoration
	// preset (colors derive from the theme's text color).
	static Dictionary get_type_scale(int p_base_size);
	// A label in one step of the type scale: the theme it ends up under gives
	// it the step's size, spacing and decoration. An unknown step is "body".
	static Control *make_label(const String &p_text, const String &p_step = "body");

	// World UI (B-1307): textured game frames instead of plain app panels. A frame style:
	// "material" (wood, metal, parchment, stone, glass, halftone, grime, flat), "shape"
	// (rounded, chamfer, skew, pixel), "base" and "edge" colors, "accent" (ornaments and
	// glow), "radius", "border_width", "shadow" (px) or "elevation" (a layout-scale
	// level), "ornament" (none, rivets, nails, brackets, diamonds), "padding" (px or a
	// spacing step name), "seed", "scale" (1 or 2: generate at twice the resolution, for
	// high-DPI), "inner_shadow" / "highlight" / "glow" (0..1 depth layers over the
	// material, B-1318; all off by default except the glow of glass), "gradient_to" /
	// "gradient_dir" (a colour run under the material, B-1321; the axis it runs along
	// stretches instead of tiling), "gradient_stops" (the run's remaining stops as an
	// Array of colours, for three stops and more, B-1322; "gradient_dir" also takes
	// "radial", centred by "gradient_center" and reaching the last stop at
	// "gradient_radius"), "halftone_cells" / "halftone_dot" (the halftone
	// print's pitch in cells per tile and its ink colour, B-1321). Lengths snap to
	// the layout scale (see get_layout_scale). The middle of
	// the image repeats, so the texture keeps its scale at any size.
	static Ref<Image> draw_frame(const Dictionary &p_style);
	static Ref<StyleBox> create_frame_style(const Dictionary &p_style);
	// World themes: fantasy, wafu, sf, horror, persona, pixel, racing, sim. One name switches the
	// frames, colors and parts; p_overrides changes any option of the world.
	static PackedStringArray get_world_names();
	static Dictionary get_world_options(const String &p_world);
	static Ref<Theme> create_world_theme(const String &p_world, const Dictionary &p_overrides = Dictionary());
	// How the world moves (for open/hover animation): {"duration", "transition", "ease",
	// "overshoot", "steps"}; read by UI motion (B-1304).
	static Dictionary get_world_motion(const String &p_world);

	// Game parts, styled by the theme's type variations (UZUGauge, UZUTalk, UZUNameTag,
	// UZUSlot, UZURibbon, UZUSeparator), so they change with the world.
	static Control *make_gauge(double p_value, double p_max = 100.0, int p_segments = 10);
	static Control *make_talk_window(const String &p_speaker, const String &p_text);
	static Control *make_item_slot(const String &p_label = String(), int p_count = 0);
	static Control *make_ribbon(const String &p_text);
	static Control *make_separator();

	// Data parts (B-1326), styled by the theme's UZUStatBar / UZUChip /
	// UZUTableHeader / UZUTableRow variations, so they change with the
	// world like every other part. The vocabulary of the data-dense
	// screens (racing, simulation): a labelled bar with its number, a
	// status chip, a selectable table and the detail panel that
	// follows the selection.
	// A caption, a smooth bar and its value in one row. Options:
	// "caption_width" / "value_width" (px), "bar_height" (px), "fill"
	// (a colour overriding the theme's bar fill for this bar only).
	// Children: "Caption", "Bar" (ProgressBar), "Value".
	static Control *make_stat_bar(const String &p_caption, double p_value, double p_max = 100.0, const Dictionary &p_options = Dictionary());
	// A small pill: an accent caption and a value, with an optional
	// "delta" note (its colour overridable by "delta_color").
	// Children: "Box/Caption", "Box/Value", "Box/Delta".
	static Control *make_status_chip(const String &p_caption, const String &p_value, const Dictionary &p_options = Dictionary());
	// A table from column and row data. Columns: Dictionaries
	// {"title", "width", "align" (left|center|right), "expand"}.
	// A column's width is its cells' minimum width; a row also
	// spends 4 px of separation between cells and 8 px of margin at
	// both ends, so a table of fixed columns fits when the widths
	// plus those add up to the table's width (an "expand" column
	// absorbs whatever is left instead).
	// Cells: a String (plain text) or a Dictionary -- {"text",
	// "color", "align"} for text, {"bar", "max", "fill"} for a mini
	// stat bar, {"face" (0..4), "text", "color"} for a condition face
	// with its word, {"image" (a Texture2D)} for a picture, {"chip"
	// (a colour), "text"} for a coloured number chip. Rows are
	// toggle Buttons in one group (children "Row0", "Row1", ...),
	// each carrying its row Array as "row_data" metadata; connecting
	// a row's "pressed" signal is the selection hook. Options:
	// "row_height" (px).
	static Control *make_data_table(const Array &p_columns, const Array &p_rows, const Dictionary &p_options = Dictionary());
	// Presses one row of a table made by make_data_table (the group
	// releases the others) and returns the row, or null.
	static Control *select_table_row(Control *p_table, int p_index);
	// The detail panel that follows a table's selection: a title, a
	// portrait and two stacks ("Rows", "Bars") that set_detail_panel
	// refills. Options: "portrait_height" (px), "key_width" (px),
	// "bar_caption_width" (px), "data" (an initial data Dictionary).
	static Control *make_detail_panel(const Dictionary &p_options = Dictionary());
	// Refills a detail panel. Data: {"title", "portrait" (a
	// Texture2D or null), "rows" (an Array of {"key", "value",
	// "color"} Dictionaries or [key, value] Arrays), "bars" (an
	// Array of {"caption", "value", "max", "fill"} Dictionaries)}.
	static void set_detail_panel(Control *p_panel, const Dictionary &p_data);

	// The moving decoration of a world's frames (B-1307 stage 2): a canvas shader that
	// glints, pulses, flickers or flows over the frame (never over the text). Null for an
	// unknown world.
	static Ref<ShaderMaterial> create_world_material(const String &p_world);

	// A screen's backdrop (B-1319): a generated background composition,
	// so a showcase or menu never floats its frames over a flat color.
	// A backdrop style: "size" (Vector2i, default 1152×648), "base",
	// "mottle" (0..1 fbm variation over the base), "band" (a diagonal
	// band's color; absent = no band), "band_y" (0..1 center), "band_h"
	// (px), "band_halftone" (dots on the band), "band_slope" (the
	// band's rise per px, default 0.22), "band2" (a second band's
	// color, drawn over the first) with "band2_y" / "band2_h" /
	// "band2_slope" / "band2_halftone", "line" (a thin line
	// color along the band's upper edge), "glow" (a soft radial glow's
	// color), "glow_pos" (0..1), "glow_strength", a second glow
	// "glow2" / "glow2_pos" / "glow2_strength", "stars" (a count of
	// four-point sparkles scattered over the upper field, B-1320) and
	// "star" (their color), "vignette" (0..1
	// edge darkening), "seed", "gradient_to" / "gradient_dir" (a colour
	// run under the ground, B-1321) with "gradient_stops" /
	// "gradient_center" / "gradient_radius" (multi-stop and radial
	// runs, B-1322), "band_gradient_to" / "band_gradient_stops" (the
	// band's own run across its width) and "halftone_cells" /
	// "halftone_dot" (the
	// bands' print). get_backdrop_options returns a world's
	// composition; make_backdrop builds it as a full-rect TextureRect
	// (mouse-transparent, aspect-covered) ready to add first in a screen.
	static Ref<Image> draw_backdrop(const Dictionary &p_style);
	static Dictionary get_backdrop_options(const String &p_world);
	static Control *make_backdrop(const String &p_world);

	// The skew frame's slant, for layouts that must stay inside the
	// parallelogram (B-1315): {"slope", "travel"} -- across the frame
	// tile the edge travels travel px horizontally, so content whose
	// bottom row sits at fraction f of the panel height needs travel*f
	// of extra left inset (and travel*(1-f') on the right at its top
	// row f'). Zeroes for any other shape.
	static Dictionary get_skew_safe_margins(const Dictionary &p_style);

	// Touch parts (B-1315), styled by the theme's "UZUTouchStick" colours
	// and "UZUTouchButton" variation, so a touch layout follows the world
	// like every other part instead of being hand-drawn per game.
	static Control *make_touch_stick();
	static Control *make_touch_button(const String &p_text);

	// Parts. Each returns a new Control, not yet added anywhere.
	static Control *make_panel(Control *p_content = nullptr);
	static Control *make_button(const String &p_text);
	static Control *make_bar(double p_value, double p_max = 100.0);
	static Control *make_tabs(const PackedStringArray &p_titles);
	static Control *make_list(const PackedStringArray &p_items);
	static Control *make_dialog(const String &p_title, const String &p_text, const PackedStringArray &p_buttons);
};

// The motion of a world UI (B-1307 stage 2), as a node saved with the screen. When the
// screen starts it gives the frames (panels, buttons, tabs) the world's moving decoration,
// opens the top-level panels with the world's motion (UZUUIJuice), plays the motion a
// spec named for a control (its "uzu_motion" metadata, B-1317), makes buttons swell on
// hover, and while it runs it sways ribbons and blinks the talk window's next mark. So a
// world UI is never still. Its counts are in get_stats() for self-verifying play.
class UZUUIWorld : public Node {
	GDCLASS(UZUUIWorld, Node);

	String world = "fantasy";
	bool open_on_ready = true;
	bool hover = true;
	bool ambient = true;
	double time = 0.0;
	Dictionary stats;
	Vector<ObjectID> ribbons;
	Vector<ObjectID> next_marks;

	void _on_hover(ObjectID p_control);

protected:
	static void _bind_methods();
	void _notification(int p_what);

public:
	void set_world(const String &p_world);
	String get_world() const;
	void set_open_on_ready(bool p_enable);
	bool is_open_on_ready() const;
	void set_hover(bool p_enable);
	bool is_hover() const;
	void set_ambient(bool p_enable);
	bool is_ambient() const;

	// Decorates the parent Control's tree now (also done when the node becomes ready).
	// Returns {"panels", "buttons", "opened", "motions", "ribbons", "next_marks"};
	// "motions" counts the controls whose "uzu_motion" metadata (the "motion"
	// key of ai_loop/ui_tool.gd, B-1317) was played with this world's motion.
	Dictionary decorate();
	// Advances the ambient motion (ribbon sway, next-mark blink) by p_delta seconds;
	// called every frame, and directly by tests.
	void advance(double p_delta);
	Dictionary get_stats() const;
};
