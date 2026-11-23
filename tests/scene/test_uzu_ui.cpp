/**************************************************************************/
/*  test_uzu_ui.cpp                                                       */
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

#include "tests/test_macros.h"

TEST_FORCE_LINK(test_uzu_ui)

#include "scene/gui/box_container.h"
#include "scene/gui/button.h"
#include "scene/gui/item_list.h"
#include "scene/gui/label.h"
#include "scene/gui/panel_container.h"
#include "scene/gui/progress_bar.h"
#include "scene/gui/tab_container.h"
#include "scene/gui/uzu_touch.h"
#include "scene/gui/uzu_ui.h"
#include "scene/gui/uzu_ui_juice.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"
#include "scene/resources/image_texture.h"
#include "scene/resources/material.h"
#include "scene/resources/style_box.h"
#include "scene/resources/style_box_flat.h"
#include "scene/resources/style_box_texture.h"
#include "scene/resources/theme.h"
#include "scene/scene_string_names.h"

namespace TestUZUUI {

// The panel is an 8-bit image: compare colors to within one step or so.
static bool close(const Color &p_a, const Color &p_b) {
	return Math::abs(p_a.r - p_b.r) < 0.01f && Math::abs(p_a.g - p_b.g) < 0.01f && Math::abs(p_a.b - p_b.b) < 0.01f;
}

TEST_CASE("[SceneTree][UZUUI] A procedural panel: gradient, rounded corners, border, shadow") {
	const Color top(0.2, 0.3, 0.6);
	const Color bottom(0.05, 0.05, 0.15);
	const Color border(0.9, 0.7, 0.2);
	const Ref<Image> img = UZUUI::draw_panel(12, top, bottom, border, 2, 8);
	REQUIRE(img.is_valid());
	const int w = img->get_width();
	const int h = img->get_height();
	CHECK(w == 2 * (8 + 13) + 8);
	CHECK(h == w);
	// The middle: opaque, between the two gradient colors, lighter above than below.
	const Color mid = img->get_pixel(w / 2, h / 2);
	CHECK(mid.a > 0.99f);
	CHECK(img->get_pixel(w / 2, 8 + 4).get_luminance() > img->get_pixel(w / 2, h - 8 - 4).get_luminance());
	// The border: on the straight edge, the border color.
	const Color edge = img->get_pixel(w / 2, 8);
	CHECK(close(edge, border));
	CHECK(edge.a > 0.9f);
	// The rounded corner: the very corner of the rectangle is not filled (only shadow).
	const Color corner = img->get_pixel(8, 8);
	CHECK(corner.a < 0.5f);
	// The shadow: soft and semi-transparent outside, stronger below than above, gone at the image edge.
	CHECK(img->get_pixel(w / 2, h - 5).a > img->get_pixel(w / 2, 4).a);
	CHECK(img->get_pixel(w / 2, h - 5).a < 0.45f);
	CHECK(img->get_pixel(0, 0).a < 0.02f);
	// No shadow, no border: nothing outside the rectangle, and the edge is the fill.
	const Ref<Image> plain = UZUUI::draw_panel(0, top, top, Color(0, 0, 0, 0), 0, 0);
	CHECK(close(plain->get_pixel(0, 0), top));
	CHECK(plain->get_pixel(0, 0).a > 0.99f);
}

TEST_CASE("[SceneTree][UZUUI] Panel styles and the theme") {
	Dictionary style;
	style["top"] = "#334466";
	style["bottom"] = "#112233";
	style["radius"] = 10;
	style["border"] = "#d9a441";
	style["shadow"] = 6;
	style["padding"] = 14;
	Ref<StyleBoxTexture> sb = UZUUI::create_panel_style(style);
	REQUIRE(sb.is_valid());
	CHECK(sb->get_texture().is_valid());
	// The style's lengths snap to the layout scale (B-1314): radius
	// 10 -> 8, shadow 6 -> 8 (elevation level 2), padding 14 -> 12.
	CHECK(sb->get_texture_margin(SIDE_LEFT) == doctest::Approx(8 + 9));
	CHECK(sb->get_expand_margin(SIDE_BOTTOM) == doctest::Approx(8)); // The shadow is outside the rect.
	CHECK(sb->get_content_margin(SIDE_TOP) == doctest::Approx(12));

	Dictionary options;
	options["accent"] = "#40c0a0";
	options["font_size"] = 22;
	const Ref<Theme> theme = UZUUI::create_theme(options);
	REQUIRE(theme.is_valid());
	CHECK(theme->get_default_font_size() == 22);
	for (const char *item : { "panel/PanelContainer", "panel/TabContainer", "panel/ItemList", "panel/TooltipPanel", "normal/Button", "hover/Button",
				 "pressed/Button", "disabled/Button", "tab_selected/TabContainer", "tab_unselected/TabContainer", "background/ProgressBar", "fill/ProgressBar", "selected/ItemList" }) {
		const String s = item;
		CHECK_MESSAGE(theme->has_stylebox(s.get_slicec('/', 0), s.get_slicec('/', 1)), item);
	}
	// The accent colors the bar fill.
	Ref<StyleBoxFlat> fill = theme->get_stylebox("fill", "ProgressBar");
	REQUIRE(fill.is_valid());
	CHECK(fill->get_bg_color().is_equal_approx(Color::html("#40c0a0")));
	CHECK(UZUUI::get_theme_defaults().has("panel"));
}

TEST_CASE("[SceneTree][UZUUI] Theme completeness: every standard control styled, focus visible") {
	// B-1313: the B-1310 gate's coverage list. Every type must carry at
	// least one stylebox of the theme itself (not the default Godot look),
	// the parts that take focus must carry a focus box that is not
	// StyleBoxEmpty, and the drawn parts (check marks, arrows, knobs)
	// must carry the theme's own icons.
	auto check_complete = [](const Ref<Theme> &theme) {
		for (const char *cls : { "PanelContainer", "Button", "CheckBox", "OptionButton", "HSlider", "VSlider", "LineEdit", "SpinBox", "HScrollBar", "VScrollBar", "PopupMenu", "Tree", "TabContainer", "ItemList", "ProgressBar", "TooltipPanel" }) {
			List<StringName> boxes;
			theme->get_stylebox_list(cls, &boxes);
			CHECK_MESSAGE(boxes.size() > 0, cls);
		}
		// The state boxes each part is drawn with.
		for (const char *item : { "normal/CheckBox", "hover/CheckBox", "hover_pressed/CheckBox", "normal/OptionButton", "hover/OptionButton", "pressed/OptionButton", "disabled/OptionButton",
					 "slider/HSlider", "grabber_area/HSlider", "grabber_area_highlight/HSlider", "slider/VSlider", "grabber_area/VSlider",
					 "normal/LineEdit", "read_only/LineEdit", "up_background_hovered/SpinBox", "up_background_pressed/SpinBox", "down_background_hovered/SpinBox",
					 "scroll/HScrollBar", "grabber/HScrollBar", "grabber_highlight/HScrollBar", "grabber_pressed/HScrollBar",
					 "scroll/VScrollBar", "grabber/VScrollBar", "grabber_highlight/VScrollBar", "grabber_pressed/VScrollBar",
					 "panel/PopupMenu", "hover/PopupMenu", "separator/PopupMenu",
					 "panel/Tree", "selected/Tree", "selected_focus/Tree", "hovered/Tree" }) {
			const String s = item;
			CHECK_MESSAGE(theme->has_stylebox(s.get_slicec('/', 0), s.get_slicec('/', 1)), item);
		}
		// Focus is a real, visible box on every focusable part.
		for (const char *cls : { "Button", "CheckBox", "OptionButton", "LineEdit", "Tree", "ItemList" }) {
			REQUIRE_MESSAGE(theme->has_stylebox("focus", cls), cls);
			const Ref<StyleBox> focus = theme->get_stylebox("focus", cls);
			CHECK_MESSAGE(Object::cast_to<StyleBoxEmpty>(focus.ptr()) == nullptr, cls);
		}
		for (const char *cls : { "HScrollBar", "VScrollBar" }) {
			const Ref<StyleBox> focus = theme->get_stylebox("scroll_focus", cls);
			CHECK_MESSAGE(Object::cast_to<StyleBoxEmpty>(focus.ptr()) == nullptr, cls);
		}
		// The Button focus: a real box, not the normal box reused (the
		// gate requires it to be distinguishable). Most worlds get the
		// accent ring -- an unfilled border; a world whose buttons
		// invert (persona, B-1320) gets the flipped frame instead.
		const Ref<StyleBox> focus_btn = theme->get_stylebox("focus", "Button");
		REQUIRE(focus_btn.is_valid());
		CHECK(focus_btn != theme->get_stylebox("normal", "Button"));
		Ref<StyleBoxFlat> ring = focus_btn;
		if (ring.is_valid()) {
			CHECK_FALSE(ring->is_draw_center_enabled());
			CHECK(ring->get_border_width(SIDE_LEFT) == 2);
		}
		// Drawn icons: check marks, arrows, knobs, ticks.
		for (const char *item : { "checked/CheckBox", "unchecked/CheckBox", "radio_checked/CheckBox", "radio_unchecked/CheckBox",
					 "arrow/OptionButton", "grabber/HSlider", "grabber_highlight/HSlider", "grabber_disabled/HSlider", "tick/HSlider",
					 "grabber/VSlider", "tick/VSlider", "clear/LineEdit", "up/SpinBox", "down/SpinBox",
					 "checked/PopupMenu", "submenu/PopupMenu", "arrow/Tree", "arrow_collapsed/Tree", "checked/Tree", "unchecked/Tree" }) {
			const String s = item;
			CHECK_MESSAGE(theme->has_icon(s.get_slicec('/', 0), s.get_slicec('/', 1)), item);
		}
		// The check mark is really drawn: the checked icon has accent
		// pixels the unchecked one does not.
		const Ref<Texture2D> checked = theme->get_icon("checked", "CheckBox");
		const Ref<Texture2D> unchecked = theme->get_icon("unchecked", "CheckBox");
		REQUIRE(checked.is_valid());
		REQUIRE(unchecked.is_valid());
		CHECK(checked->get_image()->get_data() != unchecked->get_image()->get_data());
	};
	check_complete(UZUUI::create_theme(Dictionary()));
	for (const String &world : UZUUI::get_world_names()) {
		check_complete(UZUUI::create_world_theme(world));
	}
}

TEST_CASE("[SceneTree][UZUUI] Type scale: five steps on every theme, decoration presets") {
	// B-1312: the scale itself — five steps, strictly growing, each step
	// the one below times the 1.25 ratio (within integer rounding), and
	// body is the base size the caller asked for.
	const Dictionary scale = UZUUI::get_type_scale(18);
	int prev = 0;
	for (const char *name : { "caption", "body", "heading", "title", "display" }) {
		const Dictionary s = scale[name];
		const int size = int(s["size"]);
		CHECK(size > prev);
		if (prev > 0) {
			CHECK(double(size) / prev > 1.15);
			CHECK(double(size) / prev < 1.35);
		}
		prev = size;
		CHECK(String(s["variation"]) == "UZU" + String(name).capitalize() + "Label");
	}
	CHECK(int(Dictionary(scale["body"])["size"]) == 18);
	CHECK(int(Dictionary(scale["body"])["line_spacing"]) >= 3); // Body text breathes.
	CHECK(int(Dictionary(scale["display"])["letter_spacing"]) > 0); // Display is tracked.
	CHECK(int(Dictionary(scale["display"])["outline_size"]) > 0);
	CHECK(int(Dictionary(scale["body"])["outline_size"]) == 0);

	// Every theme carries all five steps as Label variations whose items
	// match the scale, and the scale rides along in the theme's meta.
	auto check_theme = [](const Ref<Theme> &theme, int base) {
		REQUIRE(theme->has_meta("uzu_type_scale"));
		const Dictionary s = theme->get_meta("uzu_type_scale");
		for (const char *name : { "display", "title", "heading", "body", "caption" }) {
			const Dictionary step = s[name];
			const String variation = step["variation"];
			CHECK(theme->get_font_size("font_size", variation) == int(step["size"]));
			CHECK(theme->get_constant("line_spacing", variation) == int(step["line_spacing"]));
		}
		CHECK(int(Dictionary(s["body"])["size"]) == base);
		// Decoration presets: display and title are outlined and shadowed,
		// body is plain, and captions sit back (dimmer than body text).
		CHECK(theme->get_constant("outline_size", "UZUDisplayLabel") > 0);
		CHECK(theme->get_constant("outline_size", "UZUTitleLabel") > 0);
		CHECK(theme->get_constant("outline_size", "UZUBodyLabel") == 0);
		CHECK(theme->get_constant("shadow_offset_y", "UZUDisplayLabel") > 0);
		CHECK(theme->get_constant("shadow_offset_y", "UZUBodyLabel") == 0);
		CHECK(theme->get_color("font_color", "UZUCaptionLabel").a < theme->get_color("font_color", "UZUBodyLabel").a);
		// Tracked steps carry a spaced font (the letter spacing is real,
		// not just a number in the scale).
		if (int(Dictionary(s["display"])["letter_spacing"]) > 0) {
			CHECK(theme->has_font("font", "UZUDisplayLabel"));
		}
	};
	check_theme(UZUUI::create_theme(Dictionary()), 18);
	Dictionary big;
	big["font_size"] = 20; // The existing single size option is the scale's base.
	check_theme(UZUUI::create_theme(big), 20);
	for (const String &world : UZUUI::get_world_names()) {
		check_theme(UZUUI::create_world_theme(world), world == "pixel" ? 16 : 19);
	}
	// make_label picks the step's variation; the default step is body.
	Control *title = UZUUI::make_label("Title", "title");
	CHECK(Object::cast_to<Label>(title)->get_theme_type_variation() == "UZUTitleLabel");
	Control *plain = UZUUI::make_label("Plain");
	CHECK(Object::cast_to<Label>(plain)->get_theme_type_variation() == "UZUBodyLabel");
	memdelete(title);
	memdelete(plain);
}

TEST_CASE("[SceneTree][UZUUI] Layout scale: spacing, radius and elevation on every theme") {
	// B-1314: the scale itself — the gate's spacing set (B-1310), five
	// elevation levels whose sizes strictly grow, and the step names.
	const Dictionary layout = UZUUI::get_layout_scale();
	const Array spacing = layout["spacing"];
	REQUIRE(spacing.size() == 9);
	CHECK(int(spacing[0]) == 0);
	for (int i = 1; i < spacing.size(); i++) {
		CHECK(int(spacing[i]) > int(spacing[i - 1]));
	}
	const Dictionary elevation = layout["elevation"];
	REQUIRE(elevation.size() == 5);
	int prev_size = -1;
	for (int i = 0; i < 5; i++) {
		const Dictionary level = elevation[itos(i)];
		const int size = int(level["shadow"]);
		CHECK(size > prev_size);
		prev_size = size;
		CHECK(int(level["offset_y"]) == int(Math::round(size * 0.35)));
		CHECK(double(level["alpha"]) >= 0.0);
		CHECK(double(level["alpha"]) <= 1.0);
	}
	CHECK(int(Dictionary(layout["spacing_steps"])["m"]) == 12);
	CHECK(int(Dictionary(layout["spacing_steps"])["xs"]) == 4);

	auto in_scale = [](const Array &p_scale, int p_value) {
		for (int i = 0; i < p_scale.size(); i++) {
			if (int(p_scale[i]) == p_value) {
				return true;
			}
		}
		return false;
	};
	const Array radii = layout["radius"];
	Array shadow_sizes;
	for (int i = 0; i < 5; i++) {
		shadow_sizes.push_back(int(Dictionary(elevation[itos(i)])["shadow"]));
	}

	// Every length a theme carries is on the scale: content margins and
	// separations on the spacing steps, flat corner radii on the radius
	// steps, expand margins (the baked shadow) and flat shadow sizes on
	// the elevation sizes. This is the gate's scale check (B-1310),
	// pinned at the source for every theme the kit ships.
	auto check_theme = [&](const Ref<Theme> &theme) {
		REQUIRE(theme.is_valid());
		CHECK(theme->get_meta("uzu_layout") == layout);
		for (const char *cls : { "PanelContainer", "Button", "CheckBox", "OptionButton", "HSlider", "VSlider", "LineEdit", "SpinBox", "HScrollBar", "VScrollBar", "PopupMenu", "Tree", "TabContainer", "ItemList", "ProgressBar", "TooltipPanel", "Label", "RichTextLabel", "UZUNameTag", "UZUTalk", "UZUSlot", "UZURibbon", "UZUGauge", "VBoxContainer", "HBoxContainer" }) {
			List<StringName> boxes;
			theme->get_stylebox_list(cls, &boxes);
			for (const StringName &name : boxes) {
				const Ref<StyleBox> sb = theme->get_stylebox(name, cls);
				const String where = String(cls) + "." + String(name);
				for (int side = 0; side < 4; side++) {
					const float m = sb->get_margin(Side(side));
					const bool margin_ok = m == Math::floor(m) && in_scale(spacing, int(m));
					CHECK_MESSAGE(margin_ok, where, " content_margin ", m);
				}
				if (const StyleBoxTexture *tex = Object::cast_to<StyleBoxTexture>(sb.ptr())) {
					for (int side = 0; side < 4; side++) {
						const float e = tex->get_expand_margin(Side(side));
						CHECK_MESSAGE(in_scale(shadow_sizes, int(e)), where, " expand_margin ", e);
					}
				}
				if (const StyleBoxFlat *flat = Object::cast_to<StyleBoxFlat>(sb.ptr())) {
					for (int corner = 0; corner < 4; corner++) {
						CHECK_MESSAGE(in_scale(radii, flat->get_corner_radius(Corner(corner))), where, " corner_radius");
					}
					CHECK_MESSAGE(in_scale(shadow_sizes, flat->get_shadow_size()), where, " shadow_size");
				}
			}
			List<StringName> constants;
			theme->get_constant_list(cls, &constants);
			for (const StringName &name : constants) {
				const String n = name;
				if (n.contains("separation") || n.contains("margin")) {
					CHECK_MESSAGE(in_scale(spacing, theme->get_constant(name, cls)), cls, ".", n);
				}
			}
		}
	};
	check_theme(UZUUI::create_theme(Dictionary()));
	for (const String &world : UZUUI::get_world_names()) {
		check_theme(UZUUI::create_world_theme(world));
	}

	// The theme defaults and the world options state on-scale numbers.
	const Dictionary defaults = UZUUI::get_theme_defaults();
	for (const char *section : { "panel", "button" }) {
		const Dictionary sec = defaults[section];
		CHECK(in_scale(spacing, int(sec["padding"])));
		CHECK(in_scale(shadow_sizes, int(sec["shadow"])));
		CHECK(in_scale(radii, int(sec["radius"])));
	}
	for (const String &world : UZUUI::get_world_names()) {
		const Dictionary o = UZUUI::get_world_options(world);
		for (const char *section : { "frame", "button" }) {
			const Dictionary sec = o[section];
			if (sec.has("radius")) {
				CHECK_MESSAGE(in_scale(radii, int(sec["radius"])), world, " ", section, " radius");
			}
			if (sec.has("shadow")) {
				CHECK_MESSAGE(in_scale(shadow_sizes, int(sec["shadow"])), world, " ", section, " shadow");
			}
		}
	}

	// Styles resolve through the scale: "elevation" names a level, an
	// explicit "shadow" snaps to one, "padding" takes a step name.
	Dictionary by_level;
	by_level["elevation"] = 3;
	Ref<StyleBoxTexture> panel_sb = UZUUI::create_panel_style(by_level);
	REQUIRE(panel_sb.is_valid());
	CHECK(panel_sb->get_expand_margin(SIDE_LEFT) == doctest::Approx(12));
	Dictionary by_shadow;
	by_shadow["shadow"] = 10;
	panel_sb = UZUUI::create_panel_style(by_shadow);
	CHECK(panel_sb->get_expand_margin(SIDE_LEFT) == doctest::Approx(12));
	Dictionary by_name;
	by_name["padding"] = "l";
	panel_sb = UZUUI::create_panel_style(by_name);
	CHECK(panel_sb->get_content_margin(SIDE_LEFT) == doctest::Approx(16));
	Ref<StyleBoxTexture> frame_sb = UZUUI::create_frame_style(by_level);
	REQUIRE(frame_sb.is_valid());
	CHECK(frame_sb->get_expand_margin(SIDE_LEFT) == doctest::Approx(12));
	Dictionary frame_default;
	frame_sb = UZUUI::create_frame_style(frame_default);
	CHECK(frame_sb->get_expand_margin(SIDE_LEFT) == doctest::Approx(8)); // The kit default is level 2.
	CHECK(frame_sb->get_content_margin(SIDE_LEFT) == doctest::Approx(12));

	// The made parts speak the scale too: the talk window's name tag is
	// inset by a spacing step, and its overlap is one step (negative —
	// the tag sits on the window's edge by design).
	Control *talk = UZUUI::make_talk_window("Elder", "Bring three shards.");
	Control *tag_margin = Object::cast_to<Control>(talk->get_node(NodePath("TagMargin")));
	REQUIRE(tag_margin != nullptr);
	CHECK(tag_margin->get_theme_constant("margin_left", "MarginContainer") == 24);
	CHECK(talk->get_theme_constant("separation", "VBoxContainer") == -8);
	memdelete(talk);
}

TEST_CASE("[SceneTree][UZUUI] Parts") {
	Control *button = UZUUI::make_button("Start");
	CHECK(Object::cast_to<Button>(button)->get_text() == "Start");
	Control *bar = UZUUI::make_bar(30, 60);
	CHECK(Object::cast_to<ProgressBar>(bar)->get_value() == doctest::Approx(30));
	CHECK(Object::cast_to<ProgressBar>(bar)->get_max() == doctest::Approx(60));
	Control *tabs = UZUUI::make_tabs({ "Items", "Skills", "Map" });
	CHECK(Object::cast_to<TabContainer>(tabs)->get_tab_count() == 3);
	CHECK(Object::cast_to<TabContainer>(tabs)->get_tab_title(1) == "Skills");
	Control *list = UZUUI::make_list({ "Sword", "Shield" });
	CHECK(Object::cast_to<ItemList>(list)->get_item_count() == 2);
	Control *dialog = UZUUI::make_dialog("Elder", "Bring three shards.", { "Accept", "Later" });
	REQUIRE(Object::cast_to<PanelContainer>(dialog) != nullptr);
	CHECK(Object::cast_to<Label>(dialog->get_node(NodePath("Content/Title")))->get_text() == "Elder");
	CHECK(dialog->get_node(NodePath("Content/Buttons/Accept")) != nullptr);
	CHECK(dialog->get_node(NodePath("Content/Buttons/Later")) != nullptr);
	Control *wrapped = UZUUI::make_panel(UZUUI::make_button("Inside"));
	CHECK(wrapped->get_child_count() == 1);
	for (Control *c : { button, bar, tabs, list, dialog, wrapped }) {
		memdelete(c);
	}
}

TEST_CASE("[SceneTree][UZUUI] World frames: texture that repeats, shapes, ornaments") {
	Dictionary wood;
	wood["material"] = "wood";
	wood["base"] = "#6b4a2e";
	wood["edge"] = "#2e1d10";
	wood["accent"] = "#e6c36a";
	wood["ornament"] = "brackets";
	wood["radius"] = 10;
	wood["border_width"] = 3;
	wood["shadow"] = 8;
	const Ref<Image> img = UZUUI::draw_frame(wood);
	const int w = img->get_width();
	// The margin the 9-slice keeps, read off the style the frame makes;
	// the middle between the margins is the tile that repeats.
	Ref<StyleBoxTexture> wood_sb = UZUUI::create_frame_style(wood);
	REQUIRE(wood_sb.is_valid());
	const int m = int(wood_sb->get_texture_margin(SIDE_LEFT));
	const int tile = w - 2 * m;
	REQUIRE(tile > 0);
	// The middle repeats every tile px: the row through the middle matches itself one tile on.
	const int y = w / 2;
	for (int x = m; x < m + 4; x++) {
		CHECK(close(img->get_pixel(x, y), img->get_pixel(x + tile, y)));
	}
	// The wood is not flat: the middle has some variation.
	float lo = 1.0f, hi = 0.0f;
	for (int x = m; x < m + tile; x++) {
		const float l = img->get_pixel(x, y).get_luminance();
		lo = MIN(lo, l);
		hi = MAX(hi, l);
	}
	CHECK(hi - lo > 0.03f);
	// A bracket ornament in the accent color sits in the top-left corner.
	bool gold = false;
	for (int yy = 8; yy < m; yy++) {
		for (int x = 8; x < m; x++) {
			gold = gold || close(img->get_pixel(x, yy), Color::html("#e6c36a"));
		}
	}
	CHECK(gold);

	// Pixel frames: no half-transparent edge pixels inside the frame's own area.
	Dictionary pixel;
	pixel["shape"] = "pixel";
	pixel["shadow"] = 0;
	pixel["base"] = "#1b1f3a";
	pixel["edge"] = "#f4f4f4";
	const Ref<Image> px = UZUUI::draw_frame(pixel);
	int partial = 0;
	for (int yy = 0; yy < px->get_height(); yy++) {
		for (int x = 0; x < px->get_width(); x++) {
			const float a = px->get_pixel(x, yy).a;
			partial += a > 0.02f && a < 0.98f;
		}
	}
	CHECK(partial == 0);
	CHECK(px->get_pixel(0, 0).a < 0.02f); // The notched corner.

	// Glass: the edge glows in the accent color, brighter near the edge than in the middle.
	Dictionary glass;
	glass["material"] = "glass";
	glass["base"] = "#07141e";
	glass["accent"] = "#38e1ff";
	glass["shape"] = "chamfer";
	glass["shadow"] = 0;
	const Ref<Image> gl = UZUUI::draw_frame(glass);
	const int gm = gl->get_width() / 2;
	CHECK(gl->get_pixel(gm, 4).b > gl->get_pixel(gm, gm).b);
	CHECK(gl->get_pixel(0, 0).a < 0.02f); // The cut corner.
}

TEST_CASE("[SceneTree][UZUUI] Parchment: calm over a wide panel, no printed pattern") {
	// The wafu frame is parchment. Its middle tile repeats across panels
	// as wide as a talk window, so what matters is the tile itself: a
	// gentle large-scale variation (not flat), at low contrast, with no
	// busy small grain — a small, strong pattern is what read as cheap
	// print in the owner's playtest (2026-11-21).
	const Dictionary frame = UZUUI::get_world_options("wafu")["frame"];
	const Ref<Image> img = UZUUI::draw_frame(frame);
	REQUIRE(img.is_valid());
	Ref<StyleBoxTexture> sb = UZUUI::create_frame_style(frame);
	REQUIRE(sb.is_valid());
	const int w = img->get_width();
	const int m = int(sb->get_texture_margin(SIDE_LEFT));
	const int tile = w - 2 * m;
	REQUIRE(tile >= 96); // A wide repeat period is the point of the fix.
	const int y = w / 2;
	// Wrap continuity: in the tiled render the tile's last column sits
	// next to its first column, so the two must meet without a cliff.
	// (Comparing pixel(x) with pixel(x + tile) instead would conflate
	// the frame's own burnt-edge darkening, which lives in the margin
	// and is drawn once, not tiled.)
	CHECK(Math::abs(img->get_pixel(m + tile - 1, y).get_luminance() - img->get_pixel(m, y).get_luminance()) < 0.03f);
	CHECK(Math::abs(img->get_pixel(y, m + tile - 1).get_luminance() - img->get_pixel(y, m).get_luminance()) < 0.03f);
	// The tile's luminance: some variation, but low contrast, and smooth
	// from one pixel to the next (swells, not grain).
	float lo = 1.0f, hi = 0.0f, steps = 0.0f;
	int n_steps = 0;
	for (int yy = y - 8; yy <= y + 8; yy += 8) {
		float prev = -1.0f;
		for (int x = m; x < m + tile; x++) {
			const float l = img->get_pixel(x, yy).get_luminance();
			lo = MIN(lo, l);
			hi = MAX(hi, l);
			if (yy == y && prev >= 0.0f) {
				steps += Math::abs(l - prev);
				n_steps++;
			}
			prev = l;
		}
	}
	CHECK(hi - lo > 0.015f); // Not flat: the paper has a tone of its own.
	CHECK(hi - lo < 0.12f); // Low contrast: no pattern shouts.
	REQUIRE(n_steps > 0);
	CHECK(steps / n_steps < 0.01f); // Smooth: neighbouring pixels barely differ.
}

TEST_CASE("[SceneTree][UZUUI] Ornaments stay inside the 9-slice corner squares") {
	// Regression (B-1311): the corner the 9-slice keeps used to reserve
	// only MAX(radius, bw*2, orn) px, while an ornament reaches
	// bw + 3 + orn px in from the frame edge. The outer part fell into
	// the edge strips — the regions the 9-slice tiles — and printed as
	// rows of dots across wide panels (the wafu talk window in the
	// owner's playtest, 2026-11-21). For every ornament, at both
	// generation scales, every pixel painted in the ornament's color
	// must lie in one of the four corner squares.
	struct Case {
		const char *ornament;
		Color color;
	};
	const Case cases[] = {
		{ "rivets", Color::html("#e6c36a").lightened(0.2f) },
		{ "nails", Color(0.15f, 0.12f, 0.1f) },
		{ "brackets", Color::html("#e6c36a") },
		{ "diamonds", Color::html("#e6c36a") },
	};
	for (const Case &cse : cases) {
		for (int scale = 1; scale <= 2; scale++) {
			Dictionary style;
			style["material"] = "flat";
			style["base"] = "#30507a";
			style["edge"] = "#101820";
			style["accent"] = "#e6c36a";
			style["ornament"] = cse.ornament;
			style["radius"] = 2;
			style["border_width"] = 3;
			style["shadow"] = 6;
			style["scale"] = scale;
			const Ref<Image> img = UZUUI::draw_frame(style);
			REQUIRE(img.is_valid());
			Ref<StyleBoxTexture> sb = UZUUI::create_frame_style(style);
			REQUIRE(sb.is_valid());
			const int w = img->get_width();
			const int h = img->get_height();
			const int m = int(sb->get_texture_margin(SIDE_LEFT));
			int found = 0;
			int leaked = 0;
			for (int y = 0; y < h; y++) {
				for (int x = 0; x < w; x++) {
					if (!close(img->get_pixel(x, y), cse.color)) {
						continue;
					}
					found++;
					const bool corner_x = x < m || x >= w - m;
					const bool corner_y = y < m || y >= h - m;
					if (!(corner_x && corner_y)) {
						leaked++;
					}
				}
			}
			CHECK(found > 0); // The ornament is drawn at all.
			CHECK(leaked == 0);
		}
	}
	// The wafu frame itself: its diamonds are the accent color, and the
	// parchment under them never reaches that color.
	const Dictionary frame = UZUUI::get_world_options("wafu")["frame"];
	const Ref<Image> img = UZUUI::draw_frame(frame);
	REQUIRE(img.is_valid());
	Ref<StyleBoxTexture> sb = UZUUI::create_frame_style(frame);
	REQUIRE(sb.is_valid());
	const int w = img->get_width();
	const int h = img->get_height();
	const int m = int(sb->get_texture_margin(SIDE_LEFT));
	const Color accent = Color::html("#b8322a");
	int leaked = 0;
	for (int y = 0; y < h; y++) {
		for (int x = 0; x < w; x++) {
			if (!close(img->get_pixel(x, y), accent)) {
				continue;
			}
			const bool corner_x = x < m || x >= w - m;
			const bool corner_y = y < m || y >= h - m;
			if (!(corner_x && corner_y)) {
				leaked++;
			}
		}
	}
	CHECK(leaked == 0);
}

TEST_CASE("[SceneTree][UZUUI] Frame materials: exact tile period, bounded values") {
	// The materials are fbm-based (B-1311): whatever the layer mix, the
	// tile must repeat exactly (pixel(x) == pixel(x + tile)) or the
	// tiled render shows the period as a pattern. (The pre-B-1311 metal
	// streaks, sampled at x*0.25, had a period of four tiles and failed
	// exactly this.) Every material must also actually vary — a flat
	// tile is the other failure mode.
	const char *materials[] = { "wood", "metal", "parchment", "stone", "glass", "halftone", "grime" };
	for (const char *mat : materials) {
		Dictionary style;
		style["material"] = mat;
		style["base"] = "#7a6a55";
		style["edge"] = "#201812";
		style["accent"] = "#e6c36a";
		// A wide corner keeps the checked region clear of the frame-space
		// effects (bevel, burnt edges, edge glow) that are not tile-periodic.
		style["radius"] = 24;
		style["border_width"] = 0;
		style["shadow"] = 0;
		const Ref<Image> img = UZUUI::draw_frame(style);
		REQUIRE_MESSAGE(img.is_valid(), mat);
		Ref<StyleBoxTexture> sb = UZUUI::create_frame_style(style);
		REQUIRE_MESSAGE(sb.is_valid(), mat);
		const int w = img->get_width();
		const int m = int(sb->get_texture_margin(SIDE_LEFT));
		const int tile = w - 2 * m;
		CHECK_MESSAGE(tile >= 256, mat); // The B-1311 tile size.
		for (int y : { w / 3, w / 2, 2 * w / 3 }) {
			for (int x = m; x < m + 16; x++) {
				CHECK_MESSAGE(close(img->get_pixel(x, y), img->get_pixel(x + tile, y)), mat);
			}
		}
		// Variation across the tile (alpha for glass, whose texture
		// lives in the scan lines and so varies along y, not x). The
		// sampling step is 3 so it cannot sync with the 4 px scan lines.
		float lo = 1.0f, hi = 0.0f;
		for (int y = m; y < m + tile; y += 3) {
			for (int x = m; x < m + tile; x += 3) {
				const Color px = img->get_pixel(x, y);
				const float v = String(mat) == "glass" ? px.a : px.get_luminance();
				lo = MIN(lo, v);
				hi = MAX(hi, v);
			}
		}
		CHECK_MESSAGE(hi - lo > 0.01f, mat);
	}
	// The fbm value range, on parchment: it only ever darkens the base,
	// by a bounded amount — no layer may blow out or go muddy.
	Dictionary parch;
	parch["material"] = "parchment";
	parch["base"] = "#efe2c4";
	parch["edge"] = "#3b2416";
	parch["radius"] = 24;
	parch["border_width"] = 0;
	parch["shadow"] = 0;
	const Ref<Image> img = UZUUI::draw_frame(parch);
	REQUIRE(img.is_valid());
	Ref<StyleBoxTexture> sb = UZUUI::create_frame_style(parch);
	const int w = img->get_width();
	const int m = int(sb->get_texture_margin(SIDE_LEFT));
	const int tile = w - 2 * m;
	const Color base = Color::html("#efe2c4");
	for (int y = m; y < m + tile; y += 17) {
		for (int x = m; x < m + tile; x += 17) {
			const Color px = img->get_pixel(x, y);
			CHECK(px.r <= base.r + 0.01f);
			CHECK(px.g <= base.g + 0.01f);
			CHECK(px.b <= base.b + 0.01f);
			CHECK(px.r >= base.r * 0.85f);
			CHECK(px.g >= base.g * 0.85f);
			CHECK(px.b >= base.b * 0.85f);
		}
	}
}

TEST_CASE("[SceneTree][UZUUI] Frame generation scale: twice the px, same design") {
	const Dictionary frame = UZUUI::get_world_options("wafu")["frame"];
	const Ref<Image> img1 = UZUUI::draw_frame(frame);
	Dictionary frame2 = frame.duplicate();
	frame2["scale"] = 2;
	const Ref<Image> img2 = UZUUI::draw_frame(frame2);
	REQUIRE(img1.is_valid());
	REQUIRE(img2.is_valid());
	CHECK(img2->get_width() == 2 * img1->get_width());
	CHECK(img2->get_height() == 2 * img1->get_height());
	Ref<StyleBoxTexture> sb1 = UZUUI::create_frame_style(frame);
	Ref<StyleBoxTexture> sb2 = UZUUI::create_frame_style(frame2);
	REQUIRE(sb1.is_valid());
	REQUIRE(sb2.is_valid());
	CHECK(int(sb2->get_texture_margin(SIDE_LEFT)) == 2 * int(sb1->get_texture_margin(SIDE_LEFT)));
	// The default is scale 1: an explicit 1 draws the identical image.
	Dictionary frame1 = frame.duplicate();
	frame1["scale"] = 1;
	const Ref<Image> img1b = UZUUI::draw_frame(frame1);
	REQUIRE(img1b.is_valid());
	CHECK(img1b->get_width() == img1->get_width());
	CHECK(close(img1b->get_pixel(40, 40), img1->get_pixel(40, 40)));
}

TEST_CASE("[SceneTree][UZUUI] Frame depth layers: inner shadow, rim highlight, glow") {
	// The B-1318 layers over the material. A plain frame on mid gray,
	// so lightening and darkening both have room to show; shadow 0
	// keeps the geometry simple: the shape spans the whole image.
	Dictionary plain;
	plain["material"] = "flat";
	plain["base"] = "#808080";
	plain["edge"] = "#404040";
	plain["accent"] = "#ff2818";
	plain["radius"] = 8;
	plain["border_width"] = 4;
	plain["shadow"] = 0;
	const Ref<Image> base_img = UZUUI::draw_frame(plain);
	REQUIRE(base_img.is_valid());
	const int w = base_img->get_width();
	const int c = w / 2;

	// All layers at 0 draw the identical image as no keys at all:
	// the defaults change nothing that already exists.
	Dictionary zeroed = plain.duplicate();
	zeroed["inner_shadow"] = 0.0;
	zeroed["highlight"] = 0.0;
	zeroed["glow"] = 0.0;
	const Ref<Image> zero_img = UZUUI::draw_frame(zeroed);
	REQUIRE(zero_img.is_valid());
	for (int y = 0; y < w; y += 7) {
		for (int x = 0; x < w; x += 7) {
			CHECK(close(zero_img->get_pixel(x, y), base_img->get_pixel(x, y)));
		}
	}

	// Inner shadow: the surface just inside the rim is darker, and
	// only there — the middle of the panel is untouched.
	Dictionary shaded = plain.duplicate();
	shaded["inner_shadow"] = 1.0;
	const Ref<Image> shaded_img = UZUUI::draw_frame(shaded);
	REQUIRE(shaded_img.is_valid());
	CHECK(shaded_img->get_pixel(c, 7).get_luminance() < base_img->get_pixel(c, 7).get_luminance() - 0.05f);
	CHECK(close(shaded_img->get_pixel(c, c), base_img->get_pixel(c, c)));

	// Rim highlight: the top border catches more light than the
	// bottom border. Without the layer the two are the same.
	Dictionary lit = plain.duplicate();
	lit["highlight"] = 1.0;
	const Ref<Image> lit_img = UZUUI::draw_frame(lit);
	REQUIRE(lit_img.is_valid());
	CHECK(lit_img->get_pixel(c, 2).get_luminance() > lit_img->get_pixel(c, w - 3).get_luminance() + 0.03f);
	CHECK(close(base_img->get_pixel(c, 2), base_img->get_pixel(c, w - 3)));

	// Glow on a material that never had one: the accent bleeds in
	// from the edge, so a pixel just inside it leans toward the accent.
	Dictionary glowing = plain.duplicate();
	glowing["glow"] = 1.0;
	const Ref<Image> glow_img = UZUUI::draw_frame(glowing);
	REQUIRE(glow_img.is_valid());
	const Color g = glow_img->get_pixel(c, 6);
	CHECK(g.r > g.b + 0.05f);
	CHECK(Math::abs(base_img->get_pixel(c, 6).r - base_img->get_pixel(c, 6).b) < 0.01f);
}

TEST_CASE("[SceneTree][UZUUI] Skew frames: no wedge at the tile seams") {
	// Regression (B-1317's persona shot, fixed in B-1318): a skew
	// panel's middle is a parallelogram band 3/4 of the texture wide,
	// shifting with height. Sliced at a full tile, the band did not
	// cover the sliced middle at every row, and tiling it across a
	// wide panel left a transparent wedge at every seam. The slice
	// is now half a tile wide, which the band covers at every row —
	// and the edge strips' middles lie inside the band too.
	for (int scale = 1; scale <= 2; scale++) {
		Dictionary frame = UZUUI::get_world_options("persona")["frame"];
		frame["scale"] = scale;
		const Ref<Image> img = UZUUI::draw_frame(frame);
		REQUIRE(img.is_valid());
		Ref<StyleBoxTexture> sb = UZUUI::create_frame_style(frame);
		REQUIRE(sb.is_valid());
		const int w = img->get_width();
		const int h = img->get_height();
		const int mx = int(sb->get_texture_margin(SIDE_LEFT));
		const int my = int(sb->get_texture_margin(SIDE_TOP));
		const int shadow = 12 * scale;
		CHECK(w - 2 * mx == 128 * scale); // The half-tile middle.
		// The middle itself is fully opaque: tiled across a panel of
		// any width (900 px and beyond), the center cannot open up.
		int holes = 0;
		for (int y = my; y < h - my; y++) {
			for (int x = mx; x < w - mx; x++) {
				holes += img->get_pixel(x, y).a <= 0.98f ? 1 : 0;
			}
		}
		CHECK(holes == 0);
		// No row of the middle band has a gap either: between the
		// first and last opaque pixel of a row, everything is opaque,
		// so the strips and the tiled middle meet without a wedge.
		int gaps = 0;
		for (int y = my; y < h - my; y++) {
			int first = -1;
			int last = -1;
			for (int x = 0; x < w; x++) {
				if (img->get_pixel(x, y).a > 0.98f) {
					if (first < 0) {
						first = x;
					}
					last = x;
				}
			}
			REQUIRE(first >= 0);
			for (int x = first; x <= last; x++) {
				gaps += img->get_pixel(x, y).a <= 0.98f ? 1 : 0;
			}
		}
		CHECK(gaps == 0);
		// The top and bottom strips are covered over the middle's
		// columns too (their rows just inside the shape's edge).
		int strip_holes = 0;
		for (int y = shadow + 2 * scale; y <= my; y++) {
			for (int x = mx; x < w - mx; x++) {
				strip_holes += img->get_pixel(x, y).a <= 0.98f ? 1 : 0;
				strip_holes += img->get_pixel(x, h - 1 - y).a <= 0.98f ? 1 : 0;
			}
		}
		CHECK(strip_holes == 0);
	}
	// An fbm material on a skew frame repeats at the sliced period,
	// so the pattern is seamless across the same seams: deep inside
	// the frame, one middle-width along is the same pixel.
	Dictionary wood;
	wood["material"] = "wood";
	wood["base"] = "#6b4a2e";
	wood["edge"] = "#2e1d10";
	wood["accent"] = "#e6c36a";
	wood["shape"] = "skew";
	wood["radius"] = 8;
	wood["border_width"] = 3;
	wood["shadow"] = 8;
	const Ref<Image> wimg = UZUUI::draw_frame(wood);
	REQUIRE(wimg.is_valid());
	Ref<StyleBoxTexture> wsb = UZUUI::create_frame_style(wood);
	REQUIRE(wsb.is_valid());
	const int ww = wimg->get_width();
	const int wmx = int(wsb->get_texture_margin(SIDE_LEFT));
	const int mid = ww / 2;
	for (int x = wmx; x < wmx + 8; x++) {
		CHECK(close(wimg->get_pixel(x, mid), wimg->get_pixel(x + (ww - 2 * wmx), mid)));
	}
}

// Maps one destination pixel inside an axis' middle region back to a
// source pixel, following StyleBoxTexture's stretch modes (B-1319's
// 9-slice simulation; the corner and edge regions map 1:1).
static int slice_map_axis(int p_dst, int p_src_lo, int p_src_len, int p_dst_len, StyleBoxTexture::AxisStretchMode p_mode) {
	switch (p_mode) {
		case StyleBoxTexture::AXIS_STRETCH_MODE_TILE:
			return p_src_lo + (p_dst % p_src_len);
		case StyleBoxTexture::AXIS_STRETCH_MODE_TILE_FIT: {
			const int tiles = MAX(1, int(Math::ceil(double(p_dst_len) / double(p_src_len))));
			const double tile_dst = double(p_dst_len) / tiles;
			const double local = (p_dst + 0.5) - Math::floor((p_dst + 0.5) / tile_dst) * tile_dst;
			return p_src_lo + MIN(int(local / tile_dst * p_src_len), p_src_len - 1);
		}
		default: // AXIS_STRETCH_MODE_STRETCH
			return p_src_lo + MIN(int((p_dst + 0.5) * double(p_src_len) / double(p_dst_len)), p_src_len - 1);
	}
}

static Color slice_sample(const Ref<Image> &p_img, const Ref<StyleBoxTexture> &p_sb, int p_dest_w, int p_dest_h, int x, int y) {
	auto axis = [](int p, int p_dest, float p_m_lo, float p_m_hi, int p_src_size, StyleBoxTexture::AxisStretchMode p_mode) {
		const int lo = int(p_m_lo);
		const int hi = int(p_m_hi);
		if (p < lo) {
			return p;
		}
		if (p >= p_dest - hi) {
			return p_src_size - (p_dest - p);
		}
		return slice_map_axis(p - lo, lo, p_src_size - lo - hi, p_dest - lo - hi, p_mode);
	};
	const int sx = axis(x, p_dest_w, p_sb->get_texture_margin(SIDE_LEFT), p_sb->get_texture_margin(SIDE_RIGHT), p_img->get_width(), p_sb->get_h_axis_stretch_mode());
	const int sy = axis(y, p_dest_h, p_sb->get_texture_margin(SIDE_TOP), p_sb->get_texture_margin(SIDE_BOTTOM), p_img->get_height(), p_sb->get_v_axis_stretch_mode());
	return p_img->get_pixel(sx, sy);
}

TEST_CASE("[SceneTree][UZUUI] Skew frames: the bottom edge is one continuous band (B-1319)") {
	// Regression (owner feedback on B-1315's persona talk shot): at
	// talk-window size the panel's bottom strip drew as a second
	// band, offset ~26 px from the body above it. The middle band was
	// tiled vertically, so a panel shorter than the frame texture
	// clipped the band's rows; the bottom strip still showed the
	// texture's last rows, and the lean jumped at the seam by
	// slope × the skipped rows. Simulate the 9-slice draw from the
	// style's own texture, margins and stretch modes, and require
	// the silhouette's edges to move continuously at any height —
	// an edge may lean, it may never jump.
	Dictionary frame = UZUUI::get_world_options("persona")["frame"];
	const Ref<Image> img = UZUUI::draw_frame(frame);
	REQUIRE(img.is_valid());
	Ref<StyleBoxTexture> sb = UZUUI::create_frame_style(frame);
	REQUIRE(sb.is_valid());
	CHECK(sb->get_v_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
	const int expand = int(sb->get_expand_margin(SIDE_LEFT));
	const Size2 sizes[] = { Size2(1056, 190), Size2(1056, 120), Size2(700, 600) };
	for (const Size2 &panel : sizes) {
		const int dw = int(panel.x) + 2 * expand;
		const int dh = int(panel.y) + 2 * expand;
		int prev_first = -1;
		int prev_last = -1;
		int max_step = 0;
		int rows = 0;
		for (int y = 0; y < dh; y++) {
			int first = -1;
			int last = -1;
			for (int x = 0; x < dw; x++) {
				// The frame body only: the shadow the same texture
				// carries tops out at 0.85, below this threshold.
				if (slice_sample(img, sb, dw, dh, x, y).a > 0.98f) {
					if (first < 0) {
						first = x;
					}
					last = x;
				}
			}
			if (first < 0) {
				continue;
			}
			rows++;
			if (prev_first >= 0) {
				max_step = MAX(max_step, MAX(Math::abs(first - prev_first), Math::abs(last - prev_last)));
			}
			prev_first = first;
			prev_last = last;
		}
		CHECK(rows > 0);
		// The lean moves an edge 0.25 px per row; sampling and the
		// anti-aliased rim account for a couple of px — never the
		// 26 px seam jump of the bug.
		CHECK(max_step <= 3);
	}
}

TEST_CASE("[SceneTree][UZUUI] World material: the decoration stays on the frame body (B-1319)") {
	// The glint used to mix toward white over the whole stylebox
	// texture, drop shadow included, so a persona window's shadow
	// read as a pale smudge on the background. The shader now masks
	// the effect by the sampled alpha; each world sets the range so
	// its frame body clears it and its shadow (0.85 hard, 0.5 soft)
	// does not.
	for (const String &w : UZUUI::get_world_names()) {
		const Ref<ShaderMaterial> m = UZUUI::create_world_material(w);
		REQUIRE(m.is_valid());
		const float lo = float(m->get_shader_parameter("mask_lo"));
		const float hi = float(m->get_shader_parameter("mask_hi"));
		CHECK(lo > 0.5f); // Above every soft shadow.
		CHECK(hi > lo);
		CHECK(hi <= 1.0f);
	}
	// Persona's hard shadow is 0.85: the mask must start above it,
	// and the opaque body (1.0) must clear it fully.
	const Ref<ShaderMaterial> persona = UZUUI::create_world_material("persona");
	REQUIRE(persona.is_valid());
	CHECK(float(persona->get_shader_parameter("mask_lo")) > 0.85f);
	CHECK(float(persona->get_shader_parameter("mask_hi")) < 1.0f);
	// SF's glass body is ~0.86: its mask must top out below that, or
	// the scan lines would be masked off the frame they decorate.
	const Ref<ShaderMaterial> sf = UZUUI::create_world_material("sf");
	REQUIRE(sf.is_valid());
	CHECK(float(sf->get_shader_parameter("mask_hi")) < 0.86f);
	// The mechanism itself: the mask multiplies the effect.
	CHECK(persona->get_shader()->get_code().contains("smoothstep(mask_lo, mask_hi, c.a)"));
}

TEST_CASE("[SceneTree][UZUUI] Backdrops: every world composes, none is flat (B-1319)") {
	for (const String &w : UZUUI::get_world_names()) {
		const Dictionary o = UZUUI::get_backdrop_options(w);
		REQUIRE(!o.is_empty());
		const Ref<Image> img = UZUUI::draw_backdrop(o);
		REQUIRE(img.is_valid());
		REQUIRE(img->get_width() == 1152);
		REQUIRE(img->get_height() == 648);
		// Not a flat fill: the luminance varies across the canvas.
		double mean = 0.0;
		double sq = 0.0;
		int n = 0;
		for (int y = 0; y < img->get_height(); y += 9) {
			for (int x = 0; x < img->get_width(); x += 9) {
				const Color c = img->get_pixel(x, y);
				const double lum = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
				mean += lum;
				sq += lum * lum;
				n++;
			}
		}
		mean /= n;
		const double sd = Math::sqrt(MAX(0.0, sq / n - mean * mean));
		// A flat fill scores exactly 0; dark worlds (horror, pixel)
		// compose at low absolute luminance and measure 0.0036-0.005.
		CHECK(sd > 0.002);
		// The vignette holds the corners down: the same composition
		// without it (same seed, same mottle) is brighter in the
		// corner block — an exact comparison, no noise allowance.
		Dictionary plain_style = o.duplicate();
		plain_style.erase("vignette");
		const Ref<Image> plain = UZUUI::draw_backdrop(plain_style);
		REQUIRE(plain.is_valid());
		auto block_lum = [](const Ref<Image> &p_img, int cx, int cy) {
			double s = 0.0;
			for (int y = cy - 4; y <= cy + 4; y++) {
				for (int x = cx - 4; x <= cx + 4; x++) {
					const Color c = p_img->get_pixel(x, y);
					s += 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
				}
			}
			return s / 81.0;
		};
		CHECK(block_lum(img, 10, 10) < block_lum(plain, 10, 10) * 0.98);
		CHECK(block_lum(img, 1141, 637) < block_lum(plain, 1141, 637) * 0.98);
	}
	// Persona's composition is its graphic band: a real red swath.
	const Ref<Image> persona = UZUUI::draw_backdrop(UZUUI::get_backdrop_options("persona"));
	REQUIRE(persona.is_valid());
	int red = 0;
	for (int y = 0; y < persona->get_height(); y += 3) {
		for (int x = 0; x < persona->get_width(); x += 3) {
			const Color c = persona->get_pixel(x, y);
			red += (c.r > 0.5f && c.g < 0.2f) ? 1 : 0;
		}
	}
	CHECK(red > 2000);
	// Wafu has no band: its texture is the mottle and the glow, so
	// red-band pixels are absent there.
	const Ref<Image> wafu = UZUUI::draw_backdrop(UZUUI::get_backdrop_options("wafu"));
	REQUIRE(wafu.is_valid());
	int wafu_red = 0;
	for (int y = 0; y < wafu->get_height(); y += 3) {
		for (int x = 0; x < wafu->get_width(); x += 3) {
			const Color c = wafu->get_pixel(x, y);
			wafu_red += (c.r > 0.5f && c.g < 0.2f) ? 1 : 0;
		}
	}
	CHECK(wafu_red == 0);
	CHECK(UZUUI::get_backdrop_options("steampunk").is_empty());
	CHECK(UZUUI::make_backdrop("steampunk") == nullptr);
	Control *bd = UZUUI::make_backdrop("persona");
	REQUIRE(bd != nullptr);
	CHECK(bd->get_mouse_filter() == Control::MOUSE_FILTER_IGNORE);
	memdelete(bd);
}

TEST_CASE("[SceneTree][UZUUI] Backdrop accents and persona button inversion (B-1320)") {
	// The counter-slash: at the canvas centre the persona backdrop is
	// band2's deep red, where the main band does not reach.
	const Ref<Image> persona = UZUUI::draw_backdrop(UZUUI::get_backdrop_options("persona"));
	REQUIRE(persona.is_valid());
	const Color mid = persona->get_pixel(576, 220);
	CHECK(mid.r > 0.4f);
	CHECK(mid.g < 0.05f);
	CHECK(mid.b < 0.1f);
	// The sparkles: near-white pixels in the upper field, in a region
	// the band's white rule cannot reach (on the right it stays low).
	int whites = 0;
	for (int y = 20; y < 194; y += 2) {
		for (int x = 400; x < 1094; x += 2) {
			const Color c = persona->get_pixel(x, y);
			whites += (c.r > 0.9f && c.g > 0.9f && c.b > 0.9f) ? 1 : 0;
		}
	}
	CHECK(whites > 30);
	// The second glow is a real light: the same style without it is
	// black at its centre.
	Dictionary g;
	g["base"] = "#000000";
	g["mottle"] = 0.0;
	g["glow2"] = "#ffffff";
	g["glow2_pos"] = Vector2(0.5, 0.5);
	g["glow2_strength"] = 1.0;
	const Ref<Image> lit = UZUUI::draw_backdrop(g);
	REQUIRE(lit.is_valid());
	CHECK(lit->get_pixel(576, 324).r > 0.2f);
	g.erase("glow2");
	const Ref<Image> unlit = UZUUI::draw_backdrop(g);
	REQUIRE(unlit.is_valid());
	CHECK(unlit->get_pixel(576, 324).r < 0.01f);
	// Persona buttons invert on hover and focus: the hover frame's
	// centre is the signal red, and the focus box is that same frame,
	// not the accent ring. Wafu keeps the ring.
	const Ref<Theme> ptheme = UZUUI::create_world_theme("persona");
	REQUIRE(ptheme.is_valid());
	const Ref<StyleBoxTexture> hover = ptheme->get_stylebox("hover", "Button");
	REQUIRE(hover.is_valid());
	const Ref<ImageTexture> htex = hover->get_texture();
	REQUIRE(htex.is_valid());
	const Ref<Image> himg = htex->get_image();
	REQUIRE(himg.is_valid());
	const Color hc = himg->get_pixel(himg->get_width() / 2, himg->get_height() / 2);
	CHECK(hc.r > 0.5f);
	CHECK(hc.g < 0.2f);
	CHECK(ptheme->get_stylebox("focus", "Button")->get_class() == "StyleBoxTexture");
	CHECK(ptheme->get_color("font_hover_color", "Button") == Color(1, 1, 1));
	const Ref<Theme> wtheme = UZUUI::create_world_theme("wafu");
	REQUIRE(wtheme.is_valid());
	CHECK(wtheme->get_stylebox("focus", "Button")->get_class() == "StyleBoxFlat");
}

TEST_CASE("[SceneTree][UZUUI] Halftone print and gradients (B-1321)") {
	// The mean spacing of the ink runs along a row: the print's pitch
	// as drawn, in px.
	auto dot_spacing = [](const Ref<Image> &p_img, int y, int x0, int x1, float ink_r) {
		Vector<float> centers;
		int run_start = -1;
		for (int x = x0; x <= x1; x++) {
			const bool ink = p_img->get_pixel(x, y).r < ink_r;
			if (ink && run_start < 0) {
				run_start = x;
			}
			if (!ink && run_start >= 0) {
				centers.push_back((run_start + x - 1) * 0.5f);
				run_start = -1;
			}
		}
		if (centers.size() < 4) {
			return -1.0f;
		}
		float sum = 0.0f;
		for (int i = 1; i < centers.size(); i++) {
			sum += centers[i] - centers[i - 1];
		}
		return sum / float(centers.size() - 1);
	};
	// A halftone frame with the print spelled out: pitch and ink are
	// the style's, not constants.
	Dictionary print;
	print["material"] = "halftone";
	print["base"] = "#e60012";
	print["halftone_dot"] = "#7d000d";
	print["border_width"] = 0;
	print["shadow"] = 0;
	print["halftone_cells"] = 64;
	const Ref<Image> fine = UZUUI::draw_frame(print);
	REQUIRE(fine.is_valid());
	// The pitch follows the style: 64 cells per 256 tile is a 4 px
	// cell, half the legacy print's 8. (The threshold reads the ink's
	// core: at this pitch the dots nearly touch along a centre row,
	// and their anti-aliased rims bridge the gap.)
	CHECK(dot_spacing(fine, 138, 40, 236, 0.55f) == doctest::Approx(4.0).epsilon(0.08));
	Dictionary legacy = print.duplicate();
	legacy["halftone_cells"] = 32;
	const Ref<Image> coarse = UZUUI::draw_frame(legacy);
	REQUIRE(coarse.is_valid());
	CHECK(dot_spacing(coarse, 138, 40, 236, 0.55f) == doctest::Approx(8.0).epsilon(0.08));
	// The ink is the named shade: at a dot centre the pixel is the
	// maroon itself — a red, not a black hole.
	const Color dot = fine->get_pixel(138, 138);
	CHECK(dot.r == doctest::Approx(0.49).epsilon(0.04));
	CHECK(dot.g < 0.05f);
	CHECK(dot.r > 0.3f);
	// The rim is anti-aliased: along the row some pixel sits strictly
	// between ink and ground (the old print stepped in one px).
	bool edge_found = false;
	for (int x = 40; x < 236; x++) {
		const float r = fine->get_pixel(x, 138).r;
		edge_found |= r > 0.58f && r < 0.84f;
	}
	CHECK(edge_found);
	// Persona's preset carries the reworked print, and its frame's
	// centre — the pixel the gate samples — is a maroon dot.
	const Dictionary pframe = Dictionary(UZUUI::get_world_options("persona")["frame"]);
	CHECK(int(pframe["halftone_cells"]) == 64);
	CHECK(pframe.has("halftone_dot"));
	const Ref<Image> pimg = UZUUI::draw_frame(pframe);
	REQUIRE(pimg.is_valid());
	const Color pc = pimg->get_pixel(pimg->get_width() / 2, pimg->get_height() / 2);
	CHECK(pc.r > 0.35f);
	CHECK(pc.r < 0.65f);
	CHECK(pc.g < 0.06f);
	const Dictionary pback = UZUUI::get_backdrop_options("persona");
	CHECK(int(pback["halftone_cells"]) == 64);
	CHECK(pback.has("halftone_dot"));
	// B-1322: the ground's run became a radial multi-stop ramp and
	// the band's a three-stop one; the keys are the stops forms now.
	CHECK(pback.has("gradient_stops"));
	CHECK(pback.has("band_gradient_stops"));
	// A frame gradient runs under the material: the flat frame's top
	// sits near the base, its bottom near the named colour, and
	// without the key the two ends are identical.
	Dictionary grad;
	grad["material"] = "flat";
	grad["base"] = "#404040";
	grad["gradient_to"] = "#d9d9d9";
	grad["border_width"] = 0;
	grad["shadow"] = 0;
	const Ref<Image> gimg = UZUUI::draw_frame(grad);
	REQUIRE(gimg.is_valid());
	const int mid_x = gimg->get_width() / 2;
	CHECK(gimg->get_pixel(mid_x, 20).r < 0.35f);
	CHECK(gimg->get_pixel(mid_x, gimg->get_height() - 21).r > 0.75f);
	Dictionary flat = grad.duplicate();
	flat.erase("gradient_to");
	const Ref<Image> fimg = UZUUI::draw_frame(flat);
	REQUIRE(fimg.is_valid());
	CHECK(fimg->get_pixel(mid_x, 20).r == doctest::Approx(fimg->get_pixel(mid_x, fimg->get_height() - 21).r));
	// The gradient's axis stretches in the stylebox (it must span the
	// panel once); a halftone frame without one keeps its native
	// vertical tiling (this style is not skew).
	const Ref<StyleBoxTexture> gbox = UZUUI::create_frame_style(grad);
	REQUIRE(gbox.is_valid());
	CHECK(gbox->get_v_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
	Dictionary ht_grad = print.duplicate();
	ht_grad["gradient_to"] = "#c40010";
	const Ref<StyleBoxTexture> hgbox = UZUUI::create_frame_style(ht_grad);
	REQUIRE(hgbox.is_valid());
	CHECK(hgbox->get_v_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
	CHECK(hgbox->get_h_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_TILE);
	const Ref<StyleBoxTexture> hbox = UZUUI::create_frame_style(print);
	REQUIRE(hbox.is_valid());
	CHECK(hbox->get_v_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_TILE);
	// Backdrop gradients: the ground runs base -> gradient_to, and
	// the band runs along its own width.
	Dictionary bd;
	bd["size"] = Vector2i(240, 240);
	bd["base"] = "#000000";
	bd["gradient_to"] = "#ffffff";
	bd["mottle"] = 0.0;
	const Ref<Image> bdimg = UZUUI::draw_backdrop(bd);
	REQUIRE(bdimg.is_valid());
	CHECK(bdimg->get_pixel(120, 12).r < 0.12f);
	CHECK(bdimg->get_pixel(120, 228).r > 0.88f);
	Dictionary band;
	band["size"] = Vector2i(240, 240);
	band["base"] = "#000000";
	band["mottle"] = 0.0;
	band["band"] = "#ff0000";
	band["band_gradient_to"] = "#0000ff";
	band["band_y"] = 0.5;
	band["band_h"] = 100;
	band["band_slope"] = 0.0;
	const Ref<Image> bandimg = UZUUI::draw_backdrop(band);
	REQUIRE(bandimg.is_valid());
	const Color btop = bandimg->get_pixel(120, 80);
	CHECK(btop.r > 0.8f);
	CHECK(btop.b < 0.25f);
	const Color bbot = bandimg->get_pixel(120, 160);
	CHECK(bbot.b > 0.8f);
	CHECK(bbot.r < 0.25f);
}

TEST_CASE("[SceneTree][UZUUI] Gradient ramps, radial runs and frame lighting (B-1322)") {
	// A multi-stop frame ramp: black -> white -> black down the tile.
	// The middle row must sit near the middle stop, not on the
	// two-stop lerp's line (which would read ~0.5 at a quarter height
	// on its way up and never come back down).
	Dictionary ramp;
	ramp["material"] = "flat";
	ramp["base"] = "#000000";
	Array stops;
	stops.push_back("#ffffff");
	stops.push_back("#000000");
	ramp["gradient_stops"] = stops;
	ramp["border_width"] = 0;
	ramp["shadow"] = 0;
	const Ref<Image> rimg = UZUUI::draw_frame(ramp);
	REQUIRE(rimg.is_valid());
	const int rx = rimg->get_width() / 2;
	const int rh = rimg->get_height();
	CHECK(rimg->get_pixel(rx, 8).r < 0.15f); // The base, at the top.
	CHECK(rimg->get_pixel(rx, rh / 2).r > 0.85f); // The middle stop, hit at the middle.
	CHECK(rimg->get_pixel(rx, rh - 9).r < 0.15f); // And back down to the last stop.
	// The ramp's axis stretches in the stylebox, like a two-stop run's.
	const Ref<StyleBoxTexture> rbox = UZUUI::create_frame_style(ramp);
	REQUIRE(rbox.is_valid());
	CHECK(rbox->get_v_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
	// A radial backdrop run: the centre holds the base, the far
	// corner reaches the last stop, and the centre can sit off-middle
	// (the key light's corner).
	Dictionary rad;
	rad["size"] = Vector2i(240, 240);
	rad["base"] = "#000000";
	Array rstops;
	rstops.push_back("#666666");
	rstops.push_back("#ffffff");
	rad["gradient_stops"] = rstops;
	rad["gradient_dir"] = "radial";
	rad["gradient_center"] = Vector2(0.25, 0.25);
	rad["gradient_radius"] = 0.8;
	rad["mottle"] = 0.0;
	const Ref<Image> radimg = UZUUI::draw_backdrop(rad);
	REQUIRE(radimg.is_valid());
	CHECK(radimg->get_pixel(60, 60).r < 0.1f); // At the centre: the base.
	CHECK(radimg->get_pixel(120, 60).r > 0.15f); // Partway out (t=0.31): on the first run, 0.25.
	CHECK(radimg->get_pixel(120, 60).r < 0.4f);
	CHECK(radimg->get_pixel(232, 232).r > 0.9f); // The far corner: the last stop.
	// A radial frame run stretches both axes (it is positional in
	// both); the halftone print keeps its native horizontal tiling.
	Dictionary frad = ramp.duplicate();
	frad.erase("gradient_stops");
	frad["gradient_to"] = "#ffffff";
	frad["gradient_dir"] = "radial";
	const Ref<StyleBoxTexture> frbox = UZUUI::create_frame_style(frad);
	REQUIRE(frbox.is_valid());
	CHECK(frbox->get_h_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
	CHECK(frbox->get_v_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
	// The band's own ramp: three stops across its width — the lit
	// catch under the upper edge, then the shade.
	Dictionary band;
	band["size"] = Vector2i(240, 240);
	band["base"] = "#000000";
	band["mottle"] = 0.0;
	band["band"] = "#400000";
	Array bstops;
	bstops.push_back("#ff0000");
	bstops.push_back("#000040");
	band["band_gradient_stops"] = bstops;
	band["band_y"] = 0.5;
	band["band_h"] = 100;
	band["band_slope"] = 0.0;
	const Ref<Image> bandimg = UZUUI::draw_backdrop(band);
	REQUIRE(bandimg.is_valid());
	CHECK(bandimg->get_pixel(120, 80).r == doctest::Approx(0.4).epsilon(0.08)); // Near the top edge (t=0.1): the band colour rising to the bright stop.
	CHECK(bandimg->get_pixel(120, 120).r > 0.9f); // The bright stop at the band's middle.
	const Color bbot = bandimg->get_pixel(120, 168);
	CHECK(bbot.b > 0.2f); // The last stop shades the lower edge.
	CHECK(bbot.r < 0.1f);
	// Persona's presets carry the new runs.
	const Dictionary pframe = Dictionary(UZUUI::get_world_options("persona")["frame"]);
	CHECK(pframe.has("gradient_stops"));
	CHECK(Array(pframe["gradient_stops"]).size() == 3);
	const Dictionary pback = UZUUI::get_backdrop_options("persona");
	CHECK(String(pback["gradient_dir"]) == "radial");
	CHECK(Array(pback["gradient_stops"]).size() == 2);
	CHECK(Array(pback["band_gradient_stops"]).size() == 2);
	// The frame lighting (the shader pass): every world names the
	// three uniforms inside their ranges, persona lights all three,
	// and pixel — flat by design — lights none.
	for (const String &w : UZUUI::get_world_names()) {
		const Ref<ShaderMaterial> m = UZUUI::create_world_material(w);
		REQUIRE(m.is_valid());
		for (const char *key : { "sweep", "rim", "bloom" }) {
			const float v = float(m->get_shader_parameter(key));
			CHECK(v >= 0.0f);
			CHECK(v <= 1.0f);
		}
	}
	const Ref<ShaderMaterial> persona = UZUUI::create_world_material("persona");
	REQUIRE(persona.is_valid());
	CHECK(float(persona->get_shader_parameter("sweep")) > 0.0f);
	CHECK(float(persona->get_shader_parameter("rim")) > 0.0f);
	CHECK(float(persona->get_shader_parameter("bloom")) > 0.0f);
	const Ref<ShaderMaterial> pixel = UZUUI::create_world_material("pixel");
	REQUIRE(pixel.is_valid());
	CHECK(float(pixel->get_shader_parameter("sweep")) == 0.0f);
	CHECK(float(pixel->get_shader_parameter("rim")) == 0.0f);
	CHECK(float(pixel->get_shader_parameter("bloom")) == 0.0f);
	// The mechanisms themselves, pinned in the shader source.
	const String code = persona->get_shader()->get_code();
	CHECK(code.contains("uniform float sweep"));
	CHECK(code.contains("uniform float rim"));
	CHECK(code.contains("uniform float bloom"));
	CHECK(code.contains("a_r - a_l")); // The rim reads the silhouette's gradient.
}

TEST_CASE("[SceneTree][UZUUI] World themes and game parts") {
	const PackedStringArray worlds = UZUUI::get_world_names();
	CHECK(worlds.size() == 6);
	for (const String &world : worlds) {
		const Ref<Theme> theme = UZUUI::create_world_theme(world);
		REQUIRE_MESSAGE(theme.is_valid(), world);
		for (const char *variation : { "UZUGauge", "UZUTalk", "UZUNameTag", "UZUSlot", "UZURibbon" }) {
			CHECK_MESSAGE(theme->is_type_variation(variation, String(variation) == "UZUGauge" ? "ProgressBar" : "PanelContainer"), world);
		}
		CHECK(String(theme->get_meta("uzu_world")) == world);
		CHECK(Dictionary(theme->get_meta("uzu_motion")).has("duration"));
	}
	// Different worlds, different frames.
	const Ref<StyleBoxTexture> fantasy = UZUUI::create_world_theme("fantasy")->get_stylebox("panel", "PanelContainer");
	const Ref<StyleBoxTexture> sf = UZUUI::create_world_theme("sf")->get_stylebox("panel", "PanelContainer");
	REQUIRE(fantasy.is_valid());
	REQUIRE(sf.is_valid());
	CHECK(fantasy->get_texture()->get_image()->get_data() != sf->get_texture()->get_image()->get_data());
	CHECK(fantasy->get_h_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_TILE_FIT);
	// Motion follows the world: persona snaps with a big overshoot, pixel steps, sf has none.
	CHECK(double(UZUUI::get_world_motion("persona")["overshoot"]) > double(UZUUI::get_world_motion("fantasy")["overshoot"]));
	CHECK(int(UZUUI::get_world_motion("pixel")["steps"]) > 0);
	CHECK(double(UZUUI::get_world_motion("sf")["overshoot"]) == doctest::Approx(0.0));
	ERR_PRINT_OFF;
	CHECK(UZUUI::create_world_theme("steampunk").is_null());
	ERR_PRINT_ON;

	Control *gauge = UZUUI::make_gauge(30, 60, 12);
	CHECK(gauge->get_theme_type_variation() == "UZUGauge");
	CHECK(gauge->get_custom_minimum_size().x == doctest::Approx(144));
	Control *talk = UZUUI::make_talk_window("Elder", "Bring three shards.");
	CHECK(Object::cast_to<Label>(talk->get_node(NodePath("TagMargin/NameTag/Speaker")))->get_text() == "Elder");
	CHECK(Object::cast_to<Label>(talk->get_node(NodePath("Window/Body/Line")))->get_text() == "Bring three shards.");
	CHECK(Object::cast_to<Label>(talk->get_node(NodePath("Window/Body/Next")))->get_text() == String::utf8("▼"));
	Control *slot = UZUUI::make_item_slot("Key", 3);
	CHECK(Object::cast_to<Label>(slot->get_node(NodePath("Box/Count")))->get_text() == "3");
	CHECK(slot->get_theme_type_variation() == "UZUSlot");
	Control *ribbon = UZUUI::make_ribbon("Chapter 1");
	CHECK(Object::cast_to<Label>(ribbon->get_node(NodePath("Title")))->get_text() == "Chapter 1");
	Control *sep = UZUUI::make_separator();
	CHECK(sep->get_custom_minimum_size().y == doctest::Approx(12));
	for (Control *c : { gauge, talk, slot, ribbon, sep }) {
		memdelete(c);
	}
}

TEST_CASE("[SceneTree][UZUUI] World motion: moving frames, opening, hover, ambient sway") {
	// Each world has its own moving decoration; an unknown one has none.
	int modes = 0;
	int last = -1;
	for (const String &w : UZUUI::get_world_names()) {
		const Ref<ShaderMaterial> m = UZUUI::create_world_material(w);
		REQUIRE_MESSAGE(m.is_valid(), w);
		CHECK(m->get_shader()->get_code().contains("TIME"));
		const int mode = m->get_shader_parameter("mode");
		modes += mode != last;
		last = mode;
	}
	CHECK(modes >= 4);
	ERR_PRINT_OFF;
	CHECK(UZUUI::create_world_material("steampunk").is_null());
	ERR_PRINT_ON;

	Control *screen = memnew(Control);
	screen->set_theme(UZUUI::create_world_theme("fantasy"));
	SceneTree::get_singleton()->get_root()->add_child(screen);
	screen->set_size(Size2(1280, 720));
	Control *panel = UZUUI::make_panel(UZUUI::make_button("Go"));
	screen->add_child(panel);
	Control *ribbon = UZUUI::make_ribbon("Title");
	screen->add_child(ribbon);
	Control *talk = UZUUI::make_talk_window("Elder", "Hello.");
	screen->add_child(talk);
	UZUUIWorld *world = memnew(UZUUIWorld);
	world->set_world("fantasy");
	screen->add_child(world);
	UZUUIJuice::clear_event_log();

	const Dictionary stats = world->decorate();
	CHECK(int(stats["panels"]) >= 3); // The panel, the ribbon, and the talk window's frames.
	CHECK(int(stats["buttons"]) == 1);
	CHECK(int(stats["ribbons"]) == 1);
	CHECK(int(stats["next_marks"]) == 1);
	CHECK(int(stats["opened"]) >= 3);
	CHECK(Ref<ShaderMaterial>(panel->get_material()).is_valid());
	Control *button = Object::cast_to<Control>(panel->get_child(0));
	CHECK(Ref<ShaderMaterial>(button->get_material()).is_valid());
	// The text is not drawn with the frame's material.
	Control *line = Object::cast_to<Control>(talk->get_node(NodePath("Window/Body/Line")));
	CHECK(line->get_material().is_null());
	CHECK_FALSE(line->get_use_parent_material());
	// Opening was logged by UZUUIJuice (self-verifying play can see it).
	int opens = 0;
	for (const Variant &e : UZUUIJuice::get_event_log()) {
		opens += String(Dictionary(e)["event"]).contains("open");
	}
	CHECK(opens >= 3);
	// Hover makes the button swell.
	UZUUIJuice::clear_event_log();
	button->emit_signal(SceneStringName(mouse_entered));
	CHECK(UZUUIJuice::is_animating(button));
	// Ambient motion: the ribbon sways, the next mark blinks.
	world->advance(0.5);
	CHECK(Math::abs(ribbon->get_rotation_degrees()) > 0.01);
	Control *next = Object::cast_to<Control>(talk->get_node(NodePath("Window/Body/Next")));
	const float a1 = next->get_self_modulate().a;
	world->advance(0.3);
	CHECK(next->get_self_modulate().a != doctest::Approx(a1));
	CHECK(double(world->get_stats()["time"]) == doctest::Approx(0.8));
	UZUUIJuice::cancel_all();
	memdelete(screen);
}

TEST_CASE("[SceneTree][UZUUI] World motion: a spec's named motion plays on decorate (B-1317)") {
	Control *screen = memnew(Control);
	screen->set_theme(UZUUI::create_world_theme("wafu"));
	SceneTree::get_singleton()->get_root()->add_child(screen);
	screen->set_size(Size2(1280, 720));
	Control *panel = UZUUI::make_panel();
	Dictionary spec;
	spec["preset"] = "appear";
	panel->set_meta("uzu_motion", spec);
	screen->add_child(panel);
	UZUUIWorld *world = memnew(UZUUIWorld);
	world->set_world("wafu");
	screen->add_child(world);
	const Dictionary stats = world->decorate();
	CHECK(int(stats["motions"]) == 1);
	CHECK(UZUUIJuice::is_animating(panel));
	// The named preset played, not the default opening.
	CHECK(String(UZUUIJuice::get_animation_state(panel)["motion"]) == "appear");
	UZUUIJuice::cancel_all();
	memdelete(screen);
}

namespace {

// The quality gate's contrast (B-1310), mirrored for the property tests:
// WCAG luminance, a translucent colour composited over black and white,
// the worse ratio wins.
float test_wcag_luminance(const Color &p_c) {
	auto lin = [](float v) {
		return v <= 0.04045f ? v / 12.92f : Math::pow((v + 0.055f) / 1.055f, 2.4f);
	};
	return 0.2126f * lin(p_c.r) + 0.7152f * lin(p_c.g) + 0.0722f * lin(p_c.b);
}

float test_gate_contrast(const Color &p_fg, const Color &p_bg) {
	float worst = 1e9f;
	for (int i = 0; i < 2; i++) {
		const Color base = i == 0 ? Color(0, 0, 0) : Color(1, 1, 1);
		auto over = [&](const Color &c) {
			return Color(c.r * c.a + base.r * (1.0f - c.a), c.g * c.a + base.g * (1.0f - c.a), c.b * c.a + base.b * (1.0f - c.a));
		};
		const float back = test_wcag_luminance(over(p_bg));
		const float fore = test_wcag_luminance(over(p_fg));
		worst = MIN(worst, (MAX(fore, back) + 0.05f) / (MIN(fore, back) + 0.05f));
	}
	return worst;
}

// The panel fill the way the gate's probe samples it: the centre of the
// panel stylebox's texture (or the flat box's colour).
Color test_panel_fill(const Ref<Theme> &p_theme) {
	const Ref<StyleBox> sb = p_theme->get_stylebox("panel", "PanelContainer");
	const Ref<StyleBoxTexture> tex = sb;
	if (tex.is_valid() && tex->get_texture().is_valid()) {
		const Ref<Image> img = tex->get_texture()->get_image();
		return img->get_pixel(img->get_width() / 2, img->get_height() / 2);
	}
	const Ref<StyleBoxFlat> flat = sb;
	REQUIRE(flat.is_valid());
	return flat->get_bg_color();
}

} // namespace

TEST_CASE("[SceneTree][UZUUI] Slider groove: solved contrast on every theme (B-1315)") {
	// The B-1313 styling left the groove within a contrast of 1.0-1.8 of
	// the panel in most themes; the gate now scores the groove against
	// the panel and the fill against the groove at 2.0 each, and the
	// theme builder solves the groove colour to pass. Pin both ratios
	// for the default theme and every world.
	PackedStringArray names;
	names.push_back("default");
	for (const String &world : UZUUI::get_world_names()) {
		names.push_back(world);
	}
	for (const String &name : names) {
		const Ref<Theme> theme = name == "default" ? UZUUI::create_theme({}) : UZUUI::create_world_theme(name);
		REQUIRE_MESSAGE(theme.is_valid(), name);
		const Ref<StyleBoxFlat> groove = theme->get_stylebox("slider", "HSlider");
		const Ref<StyleBoxFlat> fill = theme->get_stylebox("grabber_area", "HSlider");
		REQUIRE_MESSAGE(groove.is_valid(), name);
		REQUIRE_MESSAGE(fill.is_valid(), name);
		const Color panel = test_panel_fill(theme);
		CHECK_MESSAGE(test_gate_contrast(groove->get_bg_color(), panel) >= 2.0f, name);
		CHECK_MESSAGE(test_gate_contrast(fill->get_bg_color(), groove->get_bg_color()) >= 2.0f, name);
	}
	// Persona's body text: the reference red passes the gate's 4.5 where
	// the earlier red scored 4.48.
	const Ref<Theme> persona = UZUUI::create_world_theme("persona");
	const Color text = persona->get_color("font_color", "Label");
	CHECK(test_gate_contrast(text, test_panel_fill(persona)) >= 4.5f);
	// And its halftone frame tiles at native size across the width, never
	// rescaled (the TILE_FIT rescale beat against the dot grid into a
	// moire). The vertical axis is the exception since B-1319: a skew
	// frame stretches it, because a tiled vertical band cuts the slanted
	// bottom strip mid-slope and the seam showed as a doubled bottom edge
	// (see the B-1319 continuity test below).
	const Dictionary frame = Dictionary(UZUUI::get_world_options("persona")["frame"]);
	const Ref<StyleBoxTexture> frame_box = UZUUI::create_frame_style(frame);
	REQUIRE(frame_box.is_valid());
	CHECK(frame_box->get_h_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_TILE);
	CHECK(frame_box->get_v_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
	const Dictionary wood = Dictionary(UZUUI::get_world_options("fantasy")["frame"]);
	const Ref<StyleBoxTexture> wood_box = UZUUI::create_frame_style(wood);
	REQUIRE(wood_box.is_valid());
	CHECK(wood_box->get_h_axis_stretch_mode() == StyleBoxTexture::AXIS_STRETCH_MODE_TILE_FIT);
	// The skew slant as a number layouts can use (B-1315): persona's
	// edge travels a quarter of its tile height; wafu does not lean.
	const Dictionary margins = UZUUI::get_skew_safe_margins(frame);
	CHECK(double(margins["slope"]) == doctest::Approx(0.25));
	const Ref<Image> frame_img = UZUUI::draw_frame(frame);
	CHECK(double(margins["travel"]) == doctest::Approx(0.25 * frame_img->get_height()));
	const Dictionary wafu_frame = Dictionary(UZUUI::get_world_options("wafu")["frame"]);
	CHECK(double(UZUUI::get_skew_safe_margins(wafu_frame)["travel"]) == doctest::Approx(0.0));
	// The talk window in a skew world: the text block is inset past the
	// slant -- the widest on-scale side margins, and a deeper top margin
	// so the block starts below the rows where the parallelogram's right
	// edge sits furthest left (B-1315 containment).
	const Ref<StyleBox> talk_box = persona->get_stylebox("panel", "UZUTalk");
	REQUIRE(talk_box.is_valid());
	CHECK(talk_box->get_margin(SIDE_LEFT) == 64);
	CHECK(talk_box->get_margin(SIDE_RIGHT) == 64);
	CHECK(talk_box->get_margin(SIDE_TOP) == 32);
	const Ref<Theme> wafu_theme = UZUUI::create_world_theme("wafu");
	const Ref<StyleBox> wafu_talk_box = wafu_theme->get_stylebox("panel", "UZUTalk");
	REQUIRE(wafu_talk_box.is_valid());
	CHECK(wafu_talk_box->get_margin(SIDE_LEFT) < 64); // No skew, no widening.
	// The name tag in a skew world falls back to a chamfer (its frame's
	// travel is wider than the tag itself): the stylebox is sliced
	// uniformly, not with the skew half-tile slice.
	const Ref<StyleBoxTexture> tag_box = persona->get_stylebox("panel", "UZUNameTag");
	REQUIRE(tag_box.is_valid());
	CHECK(tag_box->get_texture_margin(SIDE_LEFT) == tag_box->get_texture_margin(SIDE_TOP));
	// An OptionButton in a skew world: its label starts inside the
	// shape, past the top-left notch (a deeper left margin).
	const Ref<StyleBox> option_box = persona->get_stylebox("normal", "OptionButton");
	REQUIRE(option_box.is_valid());
	CHECK(option_box->get_margin(SIDE_LEFT) == 64);
	const Ref<StyleBox> wafu_option_box = wafu_theme->get_stylebox("normal", "OptionButton");
	REQUIRE(wafu_option_box.is_valid());
	CHECK(wafu_option_box->get_margin(SIDE_LEFT) < 64);
}

TEST_CASE("[SceneTree][UZUUI] Touch parts: stick value and theme styling (B-1315)") {
	Control *screen = memnew(Control);
	SceneTree::get_singleton()->get_root()->add_child(screen);
	screen->set_size(Size2(640, 480));
	UZUTouchStick *stick = Object::cast_to<UZUTouchStick>(UZUUI::make_touch_stick());
	REQUIRE(stick != nullptr);
	CHECK(stick->get_custom_minimum_size() == Size2(168, 168));
	screen->add_child(stick);
	stick->set_size(Size2(168, 168));
	// A drag to the right: past the deadzone, short of the rim.
	stick->press_at(Vector2(84, 84) + Vector2(60, 0));
	CHECK(stick->get_value().x == doctest::Approx(0.70).epsilon(0.05));
	CHECK(stick->get_value().y == doctest::Approx(0.0));
	CHECK(stick->get_knob_offset().x == doctest::Approx(60.0));
	// A small drag stays inside the deadzone.
	stick->drag_to(Vector2(84, 84) + Vector2(4, 0));
	CHECK(stick->get_value() == Vector2());
	// Release centres everything.
	stick->release();
	CHECK(stick->get_value() == Vector2());
	CHECK(stick->get_knob_offset() == Vector2());
	// A set value clamps to the unit circle.
	stick->set_value(Vector2(2, 0));
	CHECK(stick->get_value() == Vector2(1, 0));
	// The pad button is a Button under its own variation.
	Button *pad = Object::cast_to<Button>(UZUUI::make_touch_button("OK"));
	REQUIRE(pad != nullptr);
	CHECK(pad->get_theme_type_variation() == "UZUTouchButton");
	CHECK(pad->get_text() == "OK");
	memdelete(pad);
	memdelete(screen);
	// Every theme styles both parts.
	PackedStringArray names;
	names.push_back("default");
	for (const String &world : UZUUI::get_world_names()) {
		names.push_back(world);
	}
	for (const String &name : names) {
		const Ref<Theme> theme = name == "default" ? UZUUI::create_theme({}) : UZUUI::create_world_theme(name);
		REQUIRE_MESSAGE(theme.is_valid(), name);
		CHECK_MESSAGE(theme->is_type_variation("UZUTouchButton", "Button"), name);
		for (const char *color : { "base_color", "ring_color", "knob_color", "knob_ring_color" }) {
			CHECK_MESSAGE(theme->has_color(color, "UZUTouchStick"), name);
		}
		const Ref<StyleBox> normal = theme->get_stylebox("normal", "UZUTouchButton");
		REQUIRE_MESSAGE(normal.is_valid(), name);
		CHECK_MESSAGE(!normal->is_class("StyleBoxEmpty"), name);
		const Ref<StyleBox> focus = theme->get_stylebox("focus", "UZUTouchButton");
		REQUIRE_MESSAGE(focus.is_valid(), name);
		CHECK_MESSAGE(!focus->is_class("StyleBoxEmpty"), name);
	}
}

} // namespace TestUZUUI
