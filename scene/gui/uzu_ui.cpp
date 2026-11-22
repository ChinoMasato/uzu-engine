/**************************************************************************/
/*  uzu_ui.cpp                                                            */
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

#include "uzu_ui.h"

#include "core/config/engine.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "scene/gui/box_container.h"
#include "scene/gui/button.h"
#include "scene/gui/item_list.h"
#include "scene/gui/label.h"
#include "scene/gui/margin_container.h"
#include "scene/gui/panel_container.h"
#include "scene/gui/progress_bar.h"
#include "scene/gui/tab_container.h"
#include "scene/gui/texture_rect.h"
#include "scene/gui/uzu_ui_juice.h"
#include "scene/resources/font.h"
#include "scene/resources/image_texture.h"
#include "scene/resources/material.h"
#include "scene/resources/shader.h"
#include "scene/resources/style_box.h"
#include "scene/resources/style_box_flat.h"
#include "scene/resources/style_box_line.h"
#include "scene/resources/style_box_texture.h"
#include "scene/resources/theme.h"
#include "scene/scene_string_names.h"
#include "scene/theme/theme_db.h"

namespace {

Color color_of(const Variant &p_v, const Color &p_default) {
	if (p_v.get_type() == Variant::COLOR) {
		return p_v;
	}
	if (p_v.get_type() == Variant::STRING && Color::html_is_valid(p_v)) {
		return Color::html(p_v);
	}
	return p_default;
}

// Signed distance from p to a rounded rectangle centered at c with half size h and radius r.
float rounded_rect_distance(const Vector2 &p, const Vector2 &c, const Vector2 &h, float r) {
	const Vector2 q = (p - c).abs() - h + Vector2(r, r);
	return Vector2(MAX(q.x, 0.0f), MAX(q.y, 0.0f)).length() + MIN(MAX(q.x, q.y), 0.0f) - r;
}

Dictionary defaults() {
	Dictionary d;
	d["accent"] = Color::html("#d9a441");
	d["text"] = Color::html("#f4ead2");
	d["font_size"] = 18;
	Dictionary panel;
	panel["top"] = Color::html("#1d2740ee");
	panel["bottom"] = Color::html("#10162add");
	panel["radius"] = 12;
	panel["border_width"] = 2;
	panel["shadow"] = 8;
	panel["padding"] = 12; // The layout scale (B-1314): spacing steps only.
	d["panel"] = panel;
	Dictionary button;
	button["top"] = Color::html("#34416a");
	button["bottom"] = Color::html("#253050");
	button["hover"] = Color::html("#46598f");
	button["pressed"] = Color::html("#1a2238");
	button["radius"] = 8;
	button["border_width"] = 1;
	button["shadow"] = 4; // Elevation level 1 (B-1314).
	button["padding"] = 8;
	d["button"] = button;
	Dictionary bar;
	bar["bg"] = Color(0, 0, 0, 0.5);
	bar["radius"] = 6;
	d["bar"] = bar;
	return d;
}

Dictionary merged(const Dictionary &p_base, const Variant &p_over) {
	Dictionary out = p_base.duplicate();
	if (p_over.get_type() == Variant::DICTIONARY) {
		const Dictionary over = p_over;
		for (const Variant &k : over.keys()) {
			out[k] = over[k];
		}
	}
	return out;
}

// ---------------------------------------------------------------------------
// B-1312: the type scale.
//
// Five named text steps on one modular scale, ratio 1.25 (the major third):
// body is the theme's base font size, heading / title / display step up by
// the ratio, caption steps down. 1.25 is the smallest classic ratio that
// keeps five steps clearly apart at game-UI sizes — at 1.125 the steps blur
// together under ~20 px, at 1.5 the display step outgrows HUD panels. Each
// step also fixes its line spacing (looser for small text, tighter for
// display), its letter spacing (a few px of tracking on the steps read at a
// glance) and a decoration preset (outline + shadow) for the steps that sit
// on art. create_theme / create_world_theme register each step as a Label
// type variation, so a label picks its step by name; the JSON builder
// (ai_loop/ui_tool.gd, "text_style") resolves to the same variation names.

const char *TYPE_STEPS[] = { "display", "title", "heading", "body", "caption" };

String type_variation_name(const String &p_step) {
	return "UZU" + p_step.capitalize() + "Label";
}

bool is_type_step(const String &p_step) {
	for (const char *step : TYPE_STEPS) {
		if (p_step == step) {
			return true;
		}
	}
	return false;
}

// The scale for one base size. Step dictionaries: "size", "line_spacing",
// "letter_spacing" (px of glyph tracking, applied through a FontVariation),
// "outline_size" and "shadow_offset" (the decoration preset; its colors are
// derived from the theme's text color when the scale is applied) and
// "variation" (the Label type variation carrying the step).
Dictionary type_scale_for(int p_base_size) {
	const int base = CLAMP(p_base_size, 8, 96);
	auto step = [&](const char *p_name, double p_factor, double p_line_factor, double p_track_factor, double p_outline_factor, int p_outline_max, const Vector2i &p_shadow) {
		Dictionary d;
		const int size = MAX(1, int(Math::round(base * p_factor)));
		d["size"] = size;
		d["line_spacing"] = int(Math::round(size * p_line_factor));
		d["letter_spacing"] = int(Math::round(size * p_track_factor));
		d["outline_size"] = CLAMP(int(Math::round(size * p_outline_factor)), 0, p_outline_max);
		d["shadow_offset"] = p_shadow;
		d["variation"] = type_variation_name(p_name);
		return d;
	};
	Dictionary scale;
	scale["display"] = step("display", 1.953125, 0.12, 0.05, 0.10, 6, Vector2i(2, 3)); // 1.25^3
	scale["title"] = step("title", 1.5625, 0.15, 0.04, 0.07, 4, Vector2i(1, 2)); // 1.25^2
	scale["heading"] = step("heading", 1.25, 0.20, 0.02, 0.0, 0, Vector2i(0, 1));
	scale["body"] = step("body", 1.0, 0.30, 0.0, 0.0, 0, Vector2i());
	scale["caption"] = step("caption", 0.8, 0.30, 0.05, 0.0, 0, Vector2i()); // 1 / 1.25
	return scale;
}

// Registers the type scale on a theme: one Label type variation per step,
// carrying the step's size, line spacing, color, decoration preset and —
// when the step has tracking and a font is at hand — a FontVariation with
// the letter spacing. The scale itself is stored in the theme's meta, so
// tools can read the numbers back off any theme.
void apply_type_scale(const Ref<Theme> &p_theme, int p_base_size, const Color &p_text, const Ref<Font> &p_font) {
	const Dictionary scale = type_scale_for(p_base_size);
	// The decoration shade: dark on light text, light on dark text, so the
	// outline and shadow always read against the glyphs themselves.
	const Color shade = p_text.get_luminance() > 0.5f ? Color(0, 0, 0) : Color(1, 1, 1);
	for (const char *name : TYPE_STEPS) {
		const Dictionary s = scale[name];
		const String variation = s["variation"];
		p_theme->set_type_variation(variation, "Label");
		p_theme->set_font_size("font_size", variation, int(s["size"]));
		p_theme->set_constant("line_spacing", variation, int(s["line_spacing"]));
		// Notes sit one step back from the text they annotate.
		p_theme->set_color("font_color", variation, String(name) == "caption" ? Color(p_text, 0.7f) : p_text);
		const int outline = int(s["outline_size"]);
		p_theme->set_constant("outline_size", variation, outline);
		if (outline > 0) {
			p_theme->set_color("font_outline_color", variation, Color(shade, String(name) == "display" ? 0.85f : 0.8f));
		}
		const Vector2i shadow = s["shadow_offset"];
		p_theme->set_constant("shadow_offset_x", variation, shadow.x);
		p_theme->set_constant("shadow_offset_y", variation, shadow.y);
		if (shadow != Vector2i()) {
			p_theme->set_color("font_shadow_color", variation, Color(shade, String(name) == "heading" ? 0.3f : 0.42f));
		}
		const int tracking = int(s["letter_spacing"]);
		if (tracking > 0 && p_font.is_valid()) {
			Ref<FontVariation> spaced;
			spaced.instantiate();
			spaced->set_base_font(p_font);
			spaced->set_spacing(TextServer::SPACING_GLYPH, tracking);
			p_theme->set_font("font", variation, spaced);
		}
	}
	p_theme->set_meta("uzu_type_scale", scale);
}

// ---------------------------------------------------------------------------
// B-1314: the layout scale.
//
// Spacing, corner radii and shadows come from fixed scales, never from
// numbers invented per part (audit item 6: the kit's paddings were
// 14 / 10 / 6 and its shadows 6 / 3, a fresh guess in every part). The
// spacing scale is the gate's set (B-1310): tight steps through the sizes
// parts are actually spaced by, then the wide steps a HUD needs. Shadows
// are five elevation levels; a level is a triple of size, drop and
// opacity — the size is also the blur reach, because both panel and
// frame drawing soften the shadow over its own size, and the drop is a
// fixed 0.35 of the size. The scale rides in every theme's "uzu_layout"
// meta (the "uzu_type_scale" pattern of B-1312) and is readable through
// UZUUI::get_layout_scale(), so tools work from the same numbers.

const int SPACING_SCALE[] = { 0, 4, 8, 12, 16, 24, 32, 48, 64 };
const int RADIUS_SCALE[] = { 0, 2, 4, 6, 8, 12, 16, 24, 32 };
const int ELEVATION_SIZE[] = { 0, 4, 8, 12, 16 };
const float ELEVATION_ALPHA[] = { 0.0f, 0.45f, 0.45f, 0.5f, 0.5f };
const float ELEVATION_DROP = 0.35f; // The shadow's downward drop, per px of size.

// Snapping: the nearest step, ties to the smaller step (the kit's
// existing convention, from snap_radius below) — except shadows, where
// ties go to the larger step so a shadow never thins into invisibility.
int snap_spacing(int p_value) {
	int best = SPACING_SCALE[0];
	for (int v : SPACING_SCALE) {
		if (Math::abs(v - p_value) < Math::abs(best - p_value)) {
			best = v;
		}
	}
	return best;
}

int snap_shadow_size(int p_value) {
	int best = ELEVATION_SIZE[0];
	for (int v : ELEVATION_SIZE) {
		if (Math::abs(v - p_value) <= Math::abs(best - p_value)) {
			best = v;
		}
	}
	return best;
}

int elevation_of_size(int p_size) {
	for (int i = 0; i < 5; i++) {
		if (ELEVATION_SIZE[i] == p_size) {
			return i;
		}
	}
	return 0;
}

// Named spacing steps, for specs that would rather say "m" than 12 (the
// JSON builder accepts the same names; see ai_loop/ui_tool.gd).
int spacing_step_value(const String &p_name) {
	if (p_name == "xs") {
		return 4;
	}
	if (p_name == "s") {
		return 8;
	}
	if (p_name == "m") {
		return 12;
	}
	if (p_name == "l") {
		return 16;
	}
	if (p_name == "xl") {
		return 24;
	}
	if (p_name == "xxl") {
		return 32;
	}
	return -1;
}

Dictionary layout_scale() {
	Dictionary d;
	Array spacing;
	for (int v : SPACING_SCALE) {
		spacing.push_back(v);
	}
	d["spacing"] = spacing;
	Array radius;
	for (int v : RADIUS_SCALE) {
		radius.push_back(v);
	}
	d["radius"] = radius;
	Dictionary steps;
	for (const char *name : { "xs", "s", "m", "l", "xl", "xxl" }) {
		steps[name] = spacing_step_value(name);
	}
	d["spacing_steps"] = steps;
	Dictionary elevation;
	for (int i = 0; i < 5; i++) {
		Dictionary level;
		level["shadow"] = ELEVATION_SIZE[i];
		level["offset_y"] = int(Math::round(ELEVATION_SIZE[i] * ELEVATION_DROP));
		level["alpha"] = ELEVATION_ALPHA[i];
		elevation[itos(i)] = level;
	}
	d["elevation"] = elevation;
	return d;
}

// ---------------------------------------------------------------------------
// B-1313: full theme coverage and visible focus.
//
// The helpers below style the standard controls the first themes left to
// the default Godot look (CheckBox, OptionButton, sliders, LineEdit,
// SpinBox, scroll bars, PopupMenu, Tree) and give every focusable part a
// focus ring that can actually be seen. Icons are drawn procedurally, the
// same way the kit draws its panels: no image assets.

// The gate's radius scale (B-1310); flat boxes snap to it so the new parts
// do not add off-scale values of their own.
int snap_radius(int p_radius) {
	int best = RADIUS_SCALE[0];
	for (int v : RADIUS_SCALE) {
		if (Math::abs(v - p_radius) < Math::abs(best - p_radius)) {
			best = v;
		}
	}
	return best;
}

// A style's content padding, on the spacing scale: a px number (snapped)
// or a step name ("xs".."xxl"). p_default is the caller's own default,
// already on the scale.
float style_padding(const Dictionary &p_style, int p_default) {
	if (!p_style.has("padding")) {
		return p_default;
	}
	const Variant v = p_style["padding"];
	if (v.get_type() == Variant::STRING) {
		const int step = spacing_step_value(v);
		return step >= 0 ? step : p_default;
	}
	return snap_spacing(int(Math::round(double(v))));
}

// A style's shadow, as an elevation step: an explicit "shadow" size
// (snapped to a level) wins; otherwise "elevation" names the level;
// otherwise the caller's default size. The alpha is the level's.
struct ShadowSpec {
	int size = 0;
	float alpha = 0.0f;
};

ShadowSpec style_shadow(const Dictionary &p_style, int p_default_size) {
	int size = p_default_size;
	if (p_style.has("shadow")) {
		size = snap_shadow_size(int(p_style.get("shadow", p_default_size)));
	} else if (p_style.has("elevation")) {
		size = ELEVATION_SIZE[CLAMP(int(p_style.get("elevation", 0)), 0, 4)];
	}
	ShadowSpec out;
	out.size = size;
	out.alpha = ELEVATION_ALPHA[elevation_of_size(size)];
	return out;
}

Ref<StyleBoxFlat> flat_box(const Color &p_bg, int p_radius, float p_padding, const Color &p_border = Color(0, 0, 0, 0), int p_border_width = 0) {
	Ref<StyleBoxFlat> sb;
	sb.instantiate();
	sb->set_bg_color(p_bg);
	if (p_border_width > 0) {
		sb->set_border_width_all(p_border_width);
		sb->set_border_color(p_border);
	}
	sb->set_corner_radius_all(snap_radius(p_radius));
	sb->set_content_margin_all(p_padding);
	return sb;
}

// The focus ring: no fill, an accent border, expanded just outside the
// control's own rect so it reads as an outline, never as a second panel.
Ref<StyleBoxFlat> focus_box(const Color &p_accent, int p_radius) {
	Ref<StyleBoxFlat> sb;
	sb.instantiate();
	sb->set_draw_center(false);
	sb->set_content_margin_all(0); // No content padding: without this the
	// box reports its border width (2) as the margin, off the spacing scale.
	sb->set_border_width_all(2);
	sb->set_border_color(p_accent);
	sb->set_corner_radius_all(snap_radius(p_radius));
	sb->set_expand_margin_all(2);
	return sb;
}

Ref<StyleBoxEmpty> empty_box() {
	Ref<StyleBoxEmpty> sb;
	sb.instantiate();
	return sb;
}

float segment_distance(const Vector2 &p, const Vector2 &p_a, const Vector2 &p_b) {
	const Vector2 ab = p_b - p_a;
	const float t = CLAMP((p - p_a).dot(ab) / MAX(ab.length_squared(), 0.001f), 0.0f, 1.0f);
	return (p_a + ab * t - p).length();
}

bool point_in_triangle(const Vector2 &p, const Vector2 &p_a, const Vector2 &p_b, const Vector2 &p_c) {
	auto sign = [](const Vector2 &u, const Vector2 &v, const Vector2 &w) {
		return (u.x - w.x) * (v.y - w.y) - (v.x - w.x) * (u.y - w.y);
	};
	const float d1 = sign(p, p_a, p_b);
	const float d2 = sign(p, p_b, p_c);
	const float d3 = sign(p, p_c, p_a);
	const bool neg = d1 < 0.0f || d2 < 0.0f || d3 < 0.0f;
	const bool pos = d1 > 0.0f || d2 > 0.0f || d3 > 0.0f;
	return !(neg && pos);
}

// A check box / radio icon: a small framed square (or ring) in the field
// colors, with the mark in the accent when on. Disabled variants are the
// same drawing at low contrast, made by the caller passing dim colors.
Ref<ImageTexture> make_check_icon(bool p_on, bool p_radio, const Color &p_bg, const Color &p_border, const Color &p_mark) {
	const int s = 18;
	Ref<Image> img = Image::create_empty(s, s, false, Image::FORMAT_RGBA8);
	const Vector2 c(s * 0.5f, s * 0.5f);
	for (int y = 0; y < s; y++) {
		for (int x = 0; x < s; x++) {
			const Vector2 p(x + 0.5f, y + 0.5f);
			const float d = p_radio ? (p - c).length() - 7.5f : rounded_rect_distance(p, c, Vector2(7.5f, 7.5f), 3.0f);
			Color col(0, 0, 0, 0);
			if (d <= 0.0f) {
				col = d > -2.0f ? p_border : p_bg;
			}
			if (p_on) {
				if (p_radio) {
					if ((p - c).length() <= 3.4f) {
						col = p_mark;
					}
				} else if (segment_distance(p, Vector2(4.5f, 9.5f), Vector2(7.8f, 12.8f)) < 1.7f || segment_distance(p, Vector2(7.8f, 12.8f), Vector2(13.5f, 5.0f)) < 1.7f) {
					col = p_mark;
				}
			}
			img->set_pixel(x, y, col);
		}
	}
	return ImageTexture::create_from_image(img);
}

// A bare check mark (PopupMenu / Tree checked items carry no box).
Ref<ImageTexture> make_mark_icon(const Color &p_mark) {
	const int s = 14;
	Ref<Image> img = Image::create_empty(s, s, false, Image::FORMAT_RGBA8);
	for (int y = 0; y < s; y++) {
		for (int x = 0; x < s; x++) {
			const Vector2 p(x + 0.5f, y + 0.5f);
			const bool on = segment_distance(p, Vector2(2.5f, 7.5f), Vector2(5.6f, 10.6f)) < 1.6f || segment_distance(p, Vector2(5.6f, 10.6f), Vector2(11.5f, 3.5f)) < 1.6f;
			img->set_pixel(x, y, on ? p_mark : Color(0, 0, 0, 0));
		}
	}
	return ImageTexture::create_from_image(img);
}

// A triangle arrow: 0 = down, 1 = up, 2 = right, 3 = left.
Ref<ImageTexture> make_arrow_icon(int p_dir, const Color &p_color) {
	const int s = 12;
	Ref<Image> img = Image::create_empty(s, s, false, Image::FORMAT_RGBA8);
	Vector2 a, b, c;
	switch (p_dir) {
		case 1:
			a = Vector2(2, 8), b = Vector2(10, 8), c = Vector2(6, 3);
			break;
		case 2:
			a = Vector2(4, 2), b = Vector2(4, 10), c = Vector2(9, 6);
			break;
		case 3:
			a = Vector2(8, 2), b = Vector2(8, 10), c = Vector2(3, 6);
			break;
		default:
			a = Vector2(2, 4), b = Vector2(10, 4), c = Vector2(6, 9);
			break;
	}
	for (int y = 0; y < s; y++) {
		for (int x = 0; x < s; x++) {
			img->set_pixel(x, y, point_in_triangle(Vector2(x + 0.5f, y + 0.5f), a, b, c) ? p_color : Color(0, 0, 0, 0));
		}
	}
	return ImageTexture::create_from_image(img);
}

// The slider knob: a filled disc with a rim, lit from above.
Ref<ImageTexture> make_grabber_icon(const Color &p_fill, const Color &p_rim) {
	const int s = 18;
	Ref<Image> img = Image::create_empty(s, s, false, Image::FORMAT_RGBA8);
	const Vector2 c(s * 0.5f, s * 0.5f);
	for (int y = 0; y < s; y++) {
		for (int x = 0; x < s; x++) {
			const Vector2 p(x + 0.5f, y + 0.5f);
			const float d = (p - c).length() - 7.5f;
			Color col(0, 0, 0, 0);
			if (d <= 0.0f) {
				col = d > -2.0f ? p_rim : p_fill.lightened(0.12f * (1.0f - p.y / s));
			}
			img->set_pixel(x, y, col);
		}
	}
	return ImageTexture::create_from_image(img);
}

Ref<ImageTexture> make_tick_icon(bool p_vertical, const Color &p_color) {
	const int w = p_vertical ? 6 : 12;
	const int h = p_vertical ? 12 : 6;
	Ref<Image> img = Image::create_empty(w, h, false, Image::FORMAT_RGBA8);
	for (int y = 0; y < h; y++) {
		for (int x = 0; x < w; x++) {
			const bool on = p_vertical ? (x >= 2 && x < 4) : (y >= 2 && y < 4);
			img->set_pixel(x, y, on ? p_color : Color(0, 0, 0, 0));
		}
	}
	return ImageTexture::create_from_image(img);
}

Ref<ImageTexture> make_cross_icon(const Color &p_color) {
	const int s = 12;
	Ref<Image> img = Image::create_empty(s, s, false, Image::FORMAT_RGBA8);
	for (int y = 0; y < s; y++) {
		for (int x = 0; x < s; x++) {
			const Vector2 p(x + 0.5f, y + 0.5f);
			const bool on = segment_distance(p, Vector2(3, 3), Vector2(9, 9)) < 1.3f || segment_distance(p, Vector2(9, 3), Vector2(3, 9)) < 1.3f;
			img->set_pixel(x, y, on ? p_color : Color(0, 0, 0, 0));
		}
	}
	return ImageTexture::create_from_image(img);
}

Ref<ImageTexture> make_empty_icon() {
	return ImageTexture::create_from_image(Image::create_empty(16, 16, false, Image::FORMAT_RGBA8));
}

// Styles every standard control create_theme / create_world_theme used to
// leave at the default Godot look, from boxes and colors the caller built
// in its own idiom (procedural panels for create_theme, world frames for
// create_world_theme). p_button_* are the caller's button state boxes,
// p_panel_box its panel box, p_field_box its sunken input-field box.
void style_extended_controls(const Ref<Theme> &p_theme,
		const Ref<StyleBox> &p_panel_box, const Ref<StyleBox> &p_field_box,
		const Ref<StyleBox> &p_button_normal, const Ref<StyleBox> &p_button_hover,
		const Ref<StyleBox> &p_button_pressed, const Ref<StyleBox> &p_button_disabled,
		const Color &p_accent, const Color &p_text, const Color &p_field_bg, int p_radius) {
	const Color dim = Color(p_text, 0.45f);
	const Color faint = Color(p_text, 0.08f);
	const Ref<StyleBox> focus = focus_box(p_accent, p_radius);
	const Ref<StyleBox> focus_small = focus_box(p_accent, 4);
	const Ref<ImageTexture> no_icon = make_empty_icon();

	// CheckBox: the icon carries the look (a framed box / ring drawn
	// above); the control's own boxes stay empty except for a faint hover
	// wash and the focus ring.
	p_theme->set_stylebox("normal", "CheckBox", empty_box());
	p_theme->set_stylebox("pressed", "CheckBox", empty_box());
	p_theme->set_stylebox("disabled", "CheckBox", empty_box());
	p_theme->set_stylebox("hover", "CheckBox", flat_box(Color(p_accent, 0.14f), 4, 0));
	p_theme->set_stylebox("hover_pressed", "CheckBox", flat_box(Color(p_accent, 0.22f), 4, 0));
	p_theme->set_stylebox("focus", "CheckBox", focus_small);
	const Color box_bg = p_field_bg.lightened(0.08f);
	p_theme->set_icon("checked", "CheckBox", make_check_icon(true, false, box_bg, p_accent, p_accent));
	p_theme->set_icon("unchecked", "CheckBox", make_check_icon(false, false, box_bg, Color(p_text, 0.7f), p_accent));
	p_theme->set_icon("checked_disabled", "CheckBox", make_check_icon(true, false, box_bg, dim, dim));
	p_theme->set_icon("unchecked_disabled", "CheckBox", make_check_icon(false, false, box_bg, dim, dim));
	p_theme->set_icon("radio_checked", "CheckBox", make_check_icon(true, true, box_bg, p_accent, p_accent));
	p_theme->set_icon("radio_unchecked", "CheckBox", make_check_icon(false, true, box_bg, Color(p_text, 0.7f), p_accent));
	p_theme->set_icon("radio_checked_disabled", "CheckBox", make_check_icon(true, true, box_bg, dim, dim));
	p_theme->set_icon("radio_unchecked_disabled", "CheckBox", make_check_icon(false, true, box_bg, dim, dim));
	for (const char *name : { "font_color", "font_pressed_color", "font_hover_color", "font_hover_pressed_color", "font_focus_color" }) {
		p_theme->set_color(name, "CheckBox", p_text);
	}
	p_theme->set_color("font_disabled_color", "CheckBox", dim);
	p_theme->set_constant("h_separation", "CheckBox", 4);

	// OptionButton: a button with a drawn arrow.
	p_theme->set_stylebox("normal", "OptionButton", p_button_normal);
	p_theme->set_stylebox("hover", "OptionButton", p_button_hover);
	p_theme->set_stylebox("pressed", "OptionButton", p_button_pressed);
	p_theme->set_stylebox("disabled", "OptionButton", p_button_disabled);
	p_theme->set_stylebox("normal_mirrored", "OptionButton", p_button_normal);
	p_theme->set_stylebox("hover_mirrored", "OptionButton", p_button_hover);
	p_theme->set_stylebox("pressed_mirrored", "OptionButton", p_button_pressed);
	p_theme->set_stylebox("disabled_mirrored", "OptionButton", p_button_disabled);
	p_theme->set_stylebox("focus", "OptionButton", focus);
	p_theme->set_icon("arrow", "OptionButton", make_arrow_icon(0, p_text));
	for (const char *name : { "font_color", "font_pressed_color", "font_hover_color", "font_hover_pressed_color", "font_focus_color" }) {
		p_theme->set_color(name, "OptionButton", p_text);
	}
	p_theme->set_color("font_disabled_color", "OptionButton", dim);
	p_theme->set_constant("h_separation", "OptionButton", 4);
	p_theme->set_constant("arrow_margin", "OptionButton", 4);

	// Sliders: a groove in the field color, the travelled part in the
	// accent, a drawn knob.
	const Ref<StyleBox> groove = flat_box(p_field_bg, 4, 0, Color(p_accent, 0.4f), 1);
	const Ref<StyleBox> groove_fill = flat_box(p_accent, 4, 0);
	const Ref<StyleBox> groove_fill_hi = flat_box(p_accent.lightened(0.2f), 4, 0);
	for (const char *cls : { "HSlider", "VSlider" }) {
		p_theme->set_stylebox("slider", cls, groove);
		p_theme->set_stylebox("grabber_area", cls, groove_fill);
		p_theme->set_stylebox("grabber_area_highlight", cls, groove_fill_hi);
		p_theme->set_icon("grabber", cls, make_grabber_icon(p_accent, p_text));
		p_theme->set_icon("grabber_highlight", cls, make_grabber_icon(p_accent.lightened(0.25f), p_text));
		p_theme->set_icon("grabber_disabled", cls, make_grabber_icon(Color(p_accent, 0.4f), dim));
		p_theme->set_icon("tick", cls, make_tick_icon(cls[0] == 'H', Color(p_text, 0.6f)));
	}

	// LineEdit: the sunken field box, the accent caret and selection, a
	// drawn clear button. (SpinBox embeds a LineEdit, so it inherits the
	// field; its own arrows and button backgrounds are set below.)
	p_theme->set_stylebox("normal", "LineEdit", p_field_box);
	p_theme->set_stylebox("read_only", "LineEdit", flat_box(Color(p_field_bg, 0.6f), p_radius, 8, Color(p_accent, 0.25f), 1));
	p_theme->set_stylebox("focus", "LineEdit", focus);
	p_theme->set_color("font_color", "LineEdit", p_text);
	p_theme->set_color("font_selected_color", "LineEdit", p_text);
	p_theme->set_color("font_uneditable_color", "LineEdit", dim);
	p_theme->set_color("font_placeholder_color", "LineEdit", Color(p_text, 0.4f));
	p_theme->set_color("caret_color", "LineEdit", p_accent);
	p_theme->set_color("selection_color", "LineEdit", Color(p_accent, 0.45f));
	p_theme->set_color("clear_button_color", "LineEdit", p_text);
	p_theme->set_color("clear_button_color_pressed", "LineEdit", p_accent);
	p_theme->set_icon("clear", "LineEdit", make_cross_icon(p_text));

	// SpinBox: drawn up/down arrows over faint button backgrounds.
	p_theme->set_icon("up", "SpinBox", make_arrow_icon(1, p_text));
	p_theme->set_icon("up_hover", "SpinBox", make_arrow_icon(1, p_accent));
	p_theme->set_icon("up_pressed", "SpinBox", make_arrow_icon(1, p_accent));
	p_theme->set_icon("up_disabled", "SpinBox", make_arrow_icon(1, dim));
	p_theme->set_icon("down", "SpinBox", make_arrow_icon(0, p_text));
	p_theme->set_icon("down_hover", "SpinBox", make_arrow_icon(0, p_accent));
	p_theme->set_icon("down_pressed", "SpinBox", make_arrow_icon(0, p_accent));
	p_theme->set_icon("down_disabled", "SpinBox", make_arrow_icon(0, dim));
	p_theme->set_icon("updown", "SpinBox", no_icon);
	const Ref<StyleBox> spin_hover = flat_box(Color(p_accent, 0.25f), 4, 0);
	const Ref<StyleBox> spin_pressed = flat_box(Color(p_accent, 0.45f), 4, 0);
	p_theme->set_stylebox("up_background", "SpinBox", empty_box());
	p_theme->set_stylebox("up_background_hovered", "SpinBox", spin_hover);
	p_theme->set_stylebox("up_background_pressed", "SpinBox", spin_pressed);
	p_theme->set_stylebox("up_background_disabled", "SpinBox", empty_box());
	p_theme->set_stylebox("down_background", "SpinBox", empty_box());
	p_theme->set_stylebox("down_background_hovered", "SpinBox", spin_hover);
	p_theme->set_stylebox("down_background_pressed", "SpinBox", spin_pressed);
	p_theme->set_stylebox("down_background_disabled", "SpinBox", empty_box());
	p_theme->set_stylebox("field_and_buttons_separator", "SpinBox", empty_box());
	p_theme->set_stylebox("up_down_buttons_separator", "SpinBox", empty_box());
	p_theme->set_color("up_icon_modulate", "SpinBox", Color(1, 1, 1));
	p_theme->set_color("down_icon_modulate", "SpinBox", Color(1, 1, 1));
	p_theme->set_constant("buttons_width", "SpinBox", 16);

	// Scroll bars: a dark groove and a solid grabber that brightens.
	const Ref<StyleBox> scroll_groove = flat_box(p_field_bg.darkened(0.25f), 4, 0);
	const Ref<StyleBox> grabber = flat_box(p_accent.darkened(0.15f), 4, 0);
	const Ref<StyleBox> grabber_hi = flat_box(p_accent.lightened(0.15f), 4, 0);
	const Ref<StyleBox> grabber_pressed = flat_box(p_accent.darkened(0.35f), 4, 0);
	for (const char *cls : { "HScrollBar", "VScrollBar" }) {
		p_theme->set_stylebox("scroll", cls, scroll_groove);
		p_theme->set_stylebox("scroll_focus", cls, focus_small);
		p_theme->set_stylebox("grabber", cls, grabber);
		p_theme->set_stylebox("grabber_highlight", cls, grabber_hi);
		p_theme->set_stylebox("grabber_pressed", cls, grabber_pressed);
		for (const char *icon : { "increment", "increment_highlight", "increment_pressed", "decrement", "decrement_highlight", "decrement_pressed" }) {
			p_theme->set_icon(icon, cls, no_icon);
		}
	}

	// PopupMenu: the panel box, an accent wash under the hovered item, a
	// hairline separator, drawn check / radio / submenu marks.
	p_theme->set_stylebox("panel", "PopupMenu", p_panel_box);
	p_theme->set_stylebox("hover", "PopupMenu", flat_box(Color(p_accent, 0.35f), 4, 4));
	Ref<StyleBoxLine> separator;
	separator.instantiate();
	separator->set_color(Color(p_text, 0.3f));
	separator->set_thickness(1);
	separator->set_content_margin_all(0); // Same reason as the focus ring:
	// the line otherwise reports half its thickness as a content margin.
	p_theme->set_stylebox("separator", "PopupMenu", separator);
	p_theme->set_stylebox("labeled_separator_left", "PopupMenu", separator);
	p_theme->set_stylebox("labeled_separator_right", "PopupMenu", separator);
	p_theme->set_icon("checked", "PopupMenu", make_mark_icon(p_accent));
	p_theme->set_icon("checked_disabled", "PopupMenu", make_mark_icon(dim));
	p_theme->set_icon("unchecked", "PopupMenu", no_icon);
	p_theme->set_icon("unchecked_disabled", "PopupMenu", no_icon);
	p_theme->set_icon("indeterminate", "PopupMenu", make_mark_icon(p_text));
	p_theme->set_icon("indeterminate_disabled", "PopupMenu", make_mark_icon(dim));
	p_theme->set_icon("radio_checked", "PopupMenu", make_check_icon(true, true, Color(0, 0, 0, 0), p_accent, p_accent));
	p_theme->set_icon("radio_checked_disabled", "PopupMenu", make_check_icon(true, true, Color(0, 0, 0, 0), dim, dim));
	p_theme->set_icon("radio_unchecked", "PopupMenu", make_check_icon(false, true, Color(0, 0, 0, 0), Color(p_text, 0.7f), p_accent));
	p_theme->set_icon("radio_unchecked_disabled", "PopupMenu", make_check_icon(false, true, Color(0, 0, 0, 0), dim, dim));
	p_theme->set_icon("submenu", "PopupMenu", make_arrow_icon(2, p_text));
	p_theme->set_icon("submenu_mirrored", "PopupMenu", make_arrow_icon(3, p_text));
	p_theme->set_color("font_color", "PopupMenu", p_text);
	p_theme->set_color("font_hover_color", "PopupMenu", p_text);
	p_theme->set_color("font_disabled_color", "PopupMenu", dim);
	p_theme->set_color("font_accelerator_color", "PopupMenu", Color(p_text, 0.6f));
	p_theme->set_color("font_separator_color", "PopupMenu", p_accent);
	p_theme->set_constant("h_separation", "PopupMenu", 4);
	p_theme->set_constant("v_separation", "PopupMenu", 4);

	// Tree: the panel box, accent selection, drawn fold arrows and check
	// marks, guide lines in a quiet text tint.
	p_theme->set_stylebox("panel", "Tree", p_panel_box);
	p_theme->set_stylebox("focus", "Tree", focus_small);
	p_theme->set_stylebox("cursor", "Tree", focus_small);
	p_theme->set_stylebox("cursor_unfocused", "Tree", flat_box(Color(0, 0, 0, 0), 4, 0, Color(p_accent, 0.4f), 1));
	const Ref<StyleBox> row_selected = flat_box(Color(p_accent, 0.35f), 4, 4);
	p_theme->set_stylebox("selected", "Tree", row_selected);
	p_theme->set_stylebox("selected_focus", "Tree", row_selected);
	p_theme->set_stylebox("hovered", "Tree", flat_box(faint, 4, 4));
	p_theme->set_stylebox("hovered_dimmed", "Tree", flat_box(Color(p_text, 0.04f), 4, 4));
	const Ref<StyleBox> row_hover_selected = flat_box(Color(p_accent, 0.45f), 4, 4);
	p_theme->set_stylebox("hovered_selected", "Tree", row_hover_selected);
	p_theme->set_stylebox("hovered_selected_focus", "Tree", row_hover_selected);
	p_theme->set_stylebox("button_hover", "Tree", p_button_hover);
	p_theme->set_stylebox("button_pressed", "Tree", p_button_pressed);
	p_theme->set_stylebox("title_button_normal", "Tree", p_button_normal);
	p_theme->set_stylebox("title_button_pressed", "Tree", p_button_pressed);
	p_theme->set_stylebox("title_button_hover", "Tree", p_button_hover);
	p_theme->set_stylebox("custom_button", "Tree", p_button_normal);
	p_theme->set_stylebox("custom_button_pressed", "Tree", p_button_pressed);
	p_theme->set_stylebox("custom_button_hover", "Tree", p_button_hover);
	p_theme->set_icon("arrow", "Tree", make_arrow_icon(0, p_text));
	p_theme->set_icon("arrow_collapsed", "Tree", make_arrow_icon(2, p_text));
	p_theme->set_icon("arrow_collapsed_mirrored", "Tree", make_arrow_icon(3, p_text));
	p_theme->set_icon("select_arrow", "Tree", make_arrow_icon(0, p_text));
	p_theme->set_icon("checked", "Tree", make_check_icon(true, false, box_bg, p_accent, p_accent));
	p_theme->set_icon("checked_disabled", "Tree", make_check_icon(true, false, box_bg, dim, dim));
	p_theme->set_icon("unchecked", "Tree", make_check_icon(false, false, box_bg, Color(p_text, 0.7f), p_accent));
	p_theme->set_icon("unchecked_disabled", "Tree", make_check_icon(false, false, box_bg, dim, dim));
	p_theme->set_icon("indeterminate", "Tree", make_mark_icon(p_text));
	p_theme->set_icon("indeterminate_disabled", "Tree", make_mark_icon(dim));
	p_theme->set_icon("updown", "Tree", no_icon);
	p_theme->set_color("font_color", "Tree", p_text);
	p_theme->set_color("font_hovered_color", "Tree", p_text);
	p_theme->set_color("font_hovered_dimmed_color", "Tree", Color(p_text, 0.7f));
	p_theme->set_color("font_hovered_selected_color", "Tree", p_text);
	p_theme->set_color("font_selected_color", "Tree", p_text);
	p_theme->set_color("font_disabled_color", "Tree", dim);
	p_theme->set_color("title_button_color", "Tree", p_text);
	p_theme->set_color("guide_color", "Tree", Color(p_text, 0.25f));
	p_theme->set_color("relationship_line_color", "Tree", Color(p_text, 0.3f));
	p_theme->set_color("parent_hl_line_color", "Tree", Color(p_accent, 0.5f));
	p_theme->set_color("children_hl_line_color", "Tree", Color(p_accent, 0.5f));
	p_theme->set_color("drop_on_item_color", "Tree", p_accent);
	p_theme->set_color("drop_position_color", "Tree", p_accent);
	p_theme->set_constant("h_separation", "Tree", 4);
	p_theme->set_constant("v_separation", "Tree", 4);
	p_theme->set_constant("draw_guides", "Tree", 1);
}

} // namespace

namespace {

// draw_panel with the shadow's opacity as a parameter: the public
// function keeps the opacity panels have always had (0.45), the style
// layer passes the elevation level's (B-1314).
Ref<Image> draw_panel_impl(int p_radius, const Color &p_top, const Color &p_bottom, const Color &p_border, int p_border_width, int p_shadow, float p_shadow_alpha) {
	const int radius = CLAMP(p_radius, 0, 64);
	const int border = CLAMP(p_border_width, 0, 16);
	const int shadow = CLAMP(p_shadow, 0, 32);
	// The rectangle sits in the middle, with room for the shadow around it and a stretchable
	// middle of 8 px; the corners are what the 9-slice keeps.
	const int corner = MAX(radius, border) + 1;
	const int w = 2 * (shadow + corner) + 8;
	const int h = w;
	const Vector2 center(w * 0.5f, h * 0.5f);
	const Vector2 half(w * 0.5f - shadow, h * 0.5f - shadow);
	const float drop = shadow * 0.35f; // The shadow falls a little downward.
	Ref<Image> img = Image::create_empty(w, h, false, Image::FORMAT_RGBA8);
	for (int y = 0; y < h; y++) {
		for (int x = 0; x < w; x++) {
			const Vector2 p(x + 0.5f, y + 0.5f);
			const float d = rounded_rect_distance(p, center, half, radius);
			const float inside = CLAMP(0.5f - d, 0.0f, 1.0f); // Anti-aliased edge.
			// Fill: a vertical gradient over the rectangle; the border near the edge.
			const float t = CLAMP((p.y - (center.y - half.y)) / (2.0f * half.y), 0.0f, 1.0f);
			Color c = p_top.lerp(p_bottom, t);
			if (border > 0) {
				const float in_border = CLAMP(d + border + 0.5f, 0.0f, 1.0f);
				c = c.lerp(p_border, in_border * p_border.a);
				c.a = MAX(c.a, in_border * p_border.a);
			}
			c.a *= inside;
			// Shadow: soft, behind and below the rectangle.
			if (shadow > 0 && inside < 1.0f) {
				const float ds = rounded_rect_distance(p - Vector2(0, drop), center, half, radius);
				const float s = 1.0f - CLAMP(ds / shadow, 0.0f, 1.0f);
				const float sa = p_shadow_alpha * s * s;
				// Over-composite the fill onto the shadow.
				const float a = c.a + sa * (1.0f - c.a);
				if (a > 0.0f) {
					c = Color((c.r * c.a) / a, (c.g * c.a) / a, (c.b * c.a) / a, a);
				}
			}
			img->set_pixel(x, y, c);
		}
	}
	return img;
}

} // namespace

Ref<Image> UZUUI::draw_panel(int p_radius, const Color &p_top, const Color &p_bottom, const Color &p_border, int p_border_width, int p_shadow) {
	return draw_panel_impl(p_radius, p_top, p_bottom, p_border, p_border_width, p_shadow, 0.45f);
}

Ref<StyleBox> UZUUI::create_panel_style(const Dictionary &p_style) {
	const Color bg = color_of(p_style.get("bg", Variant()), Color(0.08, 0.1, 0.17, 0.87));
	const Color top = color_of(p_style.get("top", Variant()), bg);
	const Color bottom = color_of(p_style.get("bottom", Variant()), p_style.has("top") ? top : bg);
	// Every length the style emits is on the layout scale (B-1314): the
	// radius snaps to the radius scale, the shadow is an elevation step,
	// the padding a spacing step (a number, snapped, or a step name).
	const int radius = snap_radius(int(p_style.get("radius", 8)));
	const int border_width = p_style.get("border_width", p_style.has("border") ? 2 : 0);
	const Color border = color_of(p_style.get("border", Variant()), Color(0, 0, 0, 0));
	const ShadowSpec shadow = style_shadow(p_style, 0);
	const float padding = style_padding(p_style, 8);
	Ref<Image> img = draw_panel_impl(radius, top, bottom, border, border_width, shadow.size, shadow.alpha);
	Ref<StyleBoxTexture> sb;
	sb.instantiate();
	sb->set_texture(ImageTexture::create_from_image(img));
	const int s = shadow.size;
	const int corner = MAX(radius, CLAMP(border_width, 0, 16)) + 1;
	sb->set_texture_margin_all(s + corner);
	sb->set_expand_margin_all(s); // The shadow is drawn outside the control's rect.
	sb->set_content_margin_all(padding);
	return sb;
}

Dictionary UZUUI::get_theme_defaults() {
	return defaults();
}

Dictionary UZUUI::get_layout_scale() {
	return layout_scale();
}

Dictionary UZUUI::get_type_scale(int p_base_size) {
	return type_scale_for(p_base_size);
}

Ref<Theme> UZUUI::create_theme(const Dictionary &p_options) {
	const Dictionary o = merged(defaults(), p_options);
	const Color accent = color_of(o["accent"], Color::html("#d9a441"));
	const Color text = color_of(o["text"], Color::html("#f4ead2"));
	Ref<Theme> theme;
	theme.instantiate();
	theme->set_default_font_size(o["font_size"]);
	const Ref<Font> font = o.get("font", Variant());
	if (font.is_valid()) {
		theme->set_default_font(font);
	}
	// The type scale (B-1312): the base size is the theme's font size, so
	// the existing single "font_size" option keeps its meaning and the
	// steps follow it. Letter spacing wraps the caller's font, or the
	// fallback font when the theme relies on the default.
	Ref<Font> scale_font = font;
	if (scale_font.is_null() && ThemeDB::get_singleton()) {
		scale_font = ThemeDB::get_singleton()->get_fallback_font();
	}
	apply_type_scale(theme, int(o.get("font_size", 18)), text, scale_font);
	// The layout scale (B-1314) rides along the same way, so a tool
	// holding any theme can read the numbers its spacing came from.
	theme->set_meta("uzu_layout", layout_scale());
	// Panels: PanelContainer, TabContainer pages, lists, tooltips.
	Dictionary panel = merged(Dictionary(defaults()["panel"]), o["panel"]);
	if (!panel.has("border")) {
		panel["border"] = accent;
	}
	const Ref<StyleBox> panel_style = create_panel_style(panel);
	theme->set_stylebox("panel", "PanelContainer", panel_style);
	theme->set_stylebox("panel", "TabContainer", panel_style);
	theme->set_stylebox("panel", "ItemList", panel_style);
	Dictionary tip = panel.duplicate();
	tip["padding"] = 8;
	tip["shadow"] = 4;
	theme->set_stylebox("panel", "TooltipPanel", create_panel_style(tip));
	// Buttons: normal, hover, pressed, disabled.
	Dictionary button = merged(Dictionary(defaults()["button"]), o["button"]);
	if (!button.has("border")) {
		button["border"] = accent;
	}
	const Ref<StyleBox> btn_normal = create_panel_style(button);
	theme->set_stylebox("normal", "Button", btn_normal);
	Dictionary state = button.duplicate();
	state["top"] = color_of(button["hover"], Color::html("#46598f"));
	state["bottom"] = Color(state["top"]).darkened(0.15);
	const Ref<StyleBox> btn_hover = create_panel_style(state);
	theme->set_stylebox("hover", "Button", btn_hover);
	state["top"] = color_of(button["pressed"], Color::html("#1a2238"));
	state["bottom"] = state["top"];
	state["shadow"] = 0;
	const Ref<StyleBox> btn_pressed = create_panel_style(state);
	theme->set_stylebox("pressed", "Button", btn_pressed);
	state["top"] = Color(color_of(button["top"], Color::html("#34416a"))).darkened(0.4);
	state["bottom"] = state["top"];
	state["border"] = Color(accent, 0.3);
	const Ref<StyleBox> btn_disabled = create_panel_style(state);
	theme->set_stylebox("disabled", "Button", btn_disabled);
	Ref<StyleBoxEmpty> none;
	none.instantiate();
	// Focus is a visible accent ring, not an empty box (B-1313): keyboard
	// and gamepad users must be able to see the focused part.
	theme->set_stylebox("focus", "Button", focus_box(accent, int(button.get("radius", 8))));
	// Tabs: the selected tab joins the page; the others are darker.
	Dictionary tab = button.duplicate();
	tab["shadow"] = 0;
	tab["padding"] = 8;
	theme->set_stylebox("tab_selected", "TabContainer", create_panel_style(tab));
	tab["top"] = Color(color_of(button["top"], Color::html("#34416a"))).darkened(0.35);
	tab["bottom"] = tab["top"];
	theme->set_stylebox("tab_unselected", "TabContainer", create_panel_style(tab));
	tab["top"] = color_of(button["hover"], Color::html("#46598f"));
	tab["bottom"] = tab["top"];
	theme->set_stylebox("tab_hovered", "TabContainer", create_panel_style(tab));
	theme->set_stylebox("tabbar_background", "TabContainer", none);
	// Bars and list selection.
	const Dictionary bar = merged(Dictionary(defaults()["bar"]), o["bar"]);
	Ref<StyleBoxFlat> bar_bg;
	bar_bg.instantiate();
	bar_bg->set_bg_color(color_of(bar["bg"], Color(0, 0, 0, 0.5)));
	bar_bg->set_corner_radius_all(snap_radius(int(bar.get("radius", 6))));
	theme->set_stylebox("background", "ProgressBar", bar_bg);
	Ref<StyleBoxFlat> fill = bar_bg->duplicate();
	fill->set_bg_color(color_of(bar.get("fill", Variant()), accent));
	theme->set_stylebox("fill", "ProgressBar", fill);
	Ref<StyleBoxFlat> selected = bar_bg->duplicate();
	selected->set_bg_color(Color(accent, 0.35));
	theme->set_stylebox("selected", "ItemList", selected);
	theme->set_stylebox("selected_focus", "ItemList", selected);
	// The list cursor and focus are outlines in the accent, not empty
	// boxes (B-1313).
	theme->set_stylebox("cursor", "ItemList", flat_box(Color(0, 0, 0, 0), 4, 0, accent, 1));
	theme->set_stylebox("cursor_unfocused", "ItemList", flat_box(Color(0, 0, 0, 0), 4, 0, Color(accent, 0.4), 1));
	theme->set_stylebox("focus", "ItemList", focus_box(accent, int(panel.get("radius", 12))));
	// Text.
	for (const char *cls : { "Label", "Button", "ProgressBar", "TooltipLabel", "ItemList" }) {
		theme->set_color("font_color", cls, text);
	}
	theme->set_color("default_color", "RichTextLabel", text);
	for (const char *name : { "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color" }) {
		theme->set_color(name, "Button", text);
	}
	theme->set_color("font_disabled_color", "Button", Color(text, 0.4));
	theme->set_color("font_selected_color", "TabContainer", text);
	theme->set_color("font_hovered_color", "TabContainer", text);
	theme->set_color("font_unselected_color", "TabContainer", Color(text, 0.65));
	theme->set_color("font_selected_color", "ItemList", text);
	theme->set_color("font_hovered_color", "ItemList", text);
	theme->set_constant("separation", "VBoxContainer", 8);
	theme->set_constant("separation", "HBoxContainer", 8); // Was 10, off the spacing scale.
	// Every remaining standard control (B-1313): the input field is the
	// panel sunk — its gradient flipped and darkened, no shadow.
	Dictionary field = panel.duplicate();
	field["top"] = color_of(panel["bottom"], Color::html("#10162a")).darkened(0.1);
	field["bottom"] = color_of(panel["bottom"], Color::html("#10162a")).darkened(0.25);
	field["padding"] = 8;
	field["shadow"] = 0;
	const Color field_bg = color_of(field["bottom"], Color::html("#10162a"));
	style_extended_controls(theme, panel_style, create_panel_style(field), btn_normal, btn_hover, btn_pressed, btn_disabled,
			accent, text, field_bg, int(button.get("radius", 8)));
	return theme;
}

namespace {

const int FRAME_TILE = 256; // The repeating middle of a frame image. At 128 the
// repeat period across a wide panel was still short enough to read as a
// pattern; 256 with multi-octave noise keeps the period below perception
// on talk-window-sized panels (B-1311).

// Periodic value noise: the lattice wraps at p_cells_x × p_cells_y cells
// across the tile, so the value repeats exactly every p_tile px on both
// axes and a tiled frame has no seams.
float value_noise(float p_x, float p_y, int p_tile, int p_cells_x, int p_cells_y, uint32_t p_seed) {
	const float fx = p_x * p_cells_x / p_tile;
	const float fy = p_y * p_cells_y / p_tile;
	const int x0 = int(Math::floor(fx));
	const int y0 = int(Math::floor(fy));
	auto lattice = [&](int x, int y) {
		const int wx = ((x % p_cells_x) + p_cells_x) % p_cells_x;
		const int wy = ((y % p_cells_y) + p_cells_y) % p_cells_y;
		const uint32_t h = (uint32_t(wx) * 73856093u) ^ (uint32_t(wy) * 19349663u) ^ (p_seed * 83492791u);
		return float((h * 2654435761u) >> 8) / float(1 << 24);
	};
	const float tx = fx - x0;
	const float ty = fy - y0;
	const float sx = tx * tx * (3.0f - 2.0f * tx);
	const float sy = ty * ty * (3.0f - 2.0f * ty);
	return Math::lerp(Math::lerp(lattice(x0, y0), lattice(x0 + 1, y0), sx), Math::lerp(lattice(x0, y0 + 1), lattice(x0 + 1, y0 + 1), sx), sy);
}

// Fractal noise: octaves of value noise whose cell counts double from
// p_cells_x/p_cells_y. Every count stays an integer, so the sum keeps the
// exact tile period. The result is normalized to [0, 1].
float fbm_noise(float p_x, float p_y, int p_tile, int p_cells_x, int p_cells_y, uint32_t p_seed, int p_octaves = 4) {
	float sum = 0.0f;
	float amp = 0.5f;
	float norm = 0.0f;
	int cx = p_cells_x;
	int cy = p_cells_y;
	for (int i = 0; i < p_octaves; i++) {
		sum += amp * value_noise(p_x, p_y, p_tile, cx, cy, p_seed + uint32_t(i) * 131u);
		norm += amp;
		amp *= 0.5f;
		cx *= 2;
		cy *= 2;
	}
	return sum / norm;
}

// Domain-warped fbm: the sample point is pushed around by another fbm
// field, which bends the regular lattice shapes into organic ones. Both
// fields share the tile period, so the warped result still tiles exactly.
float fbm_warped(float p_x, float p_y, int p_tile, int p_cells, uint32_t p_seed, float p_warp) {
	const float qx = fbm_noise(p_x, p_y, p_tile, p_cells, p_cells, p_seed + 101u, 3);
	const float qy = fbm_noise(p_x, p_y, p_tile, p_cells, p_cells, p_seed + 202u, 3);
	return fbm_noise(p_x + (qx - 0.5f) * 2.0f * p_warp, p_y + (qy - 0.5f) * 2.0f * p_warp, p_tile, p_cells, p_cells, p_seed, 4);
}

float frame_distance(const String &p_shape, const Vector2 &p, const Vector2 &c, const Vector2 &h, float r) {
	if (p_shape == "chamfer") {
		const Vector2 q = (p - c).abs();
		return MAX(MAX(q.x - h.x, q.y - h.y), (q.x + q.y - (h.x + h.y - r)) * 0.7071f);
	}
	if (p_shape == "skew") {
		// A parallelogram leaning right: x shifts with height.
		const Vector2 q(p.x - (p.y - c.y) * 0.25f, p.y);
		return rounded_rect_distance(q, c, Vector2(h.x - h.y * 0.25f, h.y), 0.0f);
	}
	if (p_shape == "pixel") {
		const Vector2 q = (p - c).abs() - h;
		return MAX(q.x, q.y); // Hard corners (notched below).
	}
	return rounded_rect_distance(p, c, h, r);
}

// Every layer is built from the periodic fbm above, in three scales —
// broad swells, a mid texture and a fine grain — so no single period is
// left for the eye to catch when the tile repeats (B-1311). p_tile is
// the tile size in px (FRAME_TILE × the generation scale) and p_scale
// the generation scale itself; lengths below are in scale-1 px.
Color material_color(const String &p_material, const Color &p_base, float x, float y, float d, uint32_t seed, int p_tile, int p_scale) {
	const float warp = p_tile * 0.125f;
	const float grain = value_noise(x, y, p_tile, 128, 128, seed + 7);
	Color c = p_base;
	if (p_material == "wood") {
		// Rings bent by a warped field, a broad mottle over them, fine grain last.
		const float bend = fbm_warped(x, y, p_tile, 3, seed + 5, warp);
		const float ring = 0.5f + 0.5f * Math::sin((y + (bend - 0.5f) * p_tile * 0.35f) * (Math::TAU / (8.0f * p_scale)));
		const float mottle = fbm_noise(x, y, p_tile, 4, 4, seed + 9);
		c = c.darkened(0.22f * ring + 0.10f * mottle + 0.05f * grain);
	} else if (p_material == "metal") {
		// Brushed: noise stretched thin along x, a broad mottle and grain over it.
		const float streak = fbm_noise(x, y, p_tile, 2, 96, seed + 3, 3);
		const float mottle = fbm_noise(x, y, p_tile, 4, 4, seed + 9, 3);
		c = c.lightened(0.10f * streak).darkened(0.06f * mottle + 0.05f * grain);
	} else if (p_material == "parchment") {
		// Calm, like real paper: broad soft swells, a warped mid drift, a
		// whisper of fiber and fine grain, all at low contrast. Every
		// component wraps with the tile, so the repeat is seamless; the
		// multi-octave build keeps any one period from standing out.
		const float swell = fbm_noise(x, y, p_tile, 3, 3, seed + 11, 3);
		const float drift = fbm_warped(x, y, p_tile, 6, seed + 23, warp);
		const float fiber = fbm_noise(x, y, p_tile, 96, 12, seed + 31, 2);
		c = c.darkened(0.045f * swell + 0.030f * drift + 0.008f * fiber + 0.012f * grain);
		c = c.darkened(0.35f * CLAMP(1.0f + d / (10.0f * p_scale), 0.0f, 1.0f)); // Burnt edges.
	} else if (p_material == "stone") {
		const float n = fbm_warped(x, y, p_tile, 5, seed, warp);
		c = c.darkened(0.22f * n).lightened(0.05f * grain);
		const float crack = fbm_noise(x, y, p_tile, 5, 5, seed + 41, 3);
		if (Math::abs(crack - 0.5f) < 0.03f) {
			c = c.darkened(0.35f); // Cracks along a warped contour.
		}
	} else if (p_material == "glass") {
		// Scan lines whose period divides the tile, and a faint sheen.
		const float line = 0.5f + 0.5f * Math::sin(y * (Math::TAU / (4.0f * p_scale)));
		const float sheen = fbm_noise(x, y, p_tile, 3, 3, seed + 3, 2);
		c.a *= 0.92f + 0.08f * line;
		c = c.darkened(0.05f * sheen);
	} else if (p_material == "halftone") {
		// Dots on a grid whose cell divides the tile; the radius grows
		// down one tile period and wraps with the tile.
		const float cell = p_tile / 32.0f;
		const Vector2 g(Math::fposmod(x, cell) - cell * 0.5f, Math::fposmod(y, cell) - cell * 0.5f);
		const float ly = Math::fposmod(y, float(p_tile));
		const float rad = (1.0f + 1.6f * CLAMP((ly - 4.0f * p_scale) / (40.0f * p_scale), 0.0f, 1.0f)) * p_scale;
		if (g.length() < rad) {
			c = c.darkened(0.3f);
		}
	} else if (p_material == "grime") {
		const float n = fbm_warped(x, y, p_tile, 4, seed, warp);
		c = c.darkened(0.45f * n * n + 0.12f * grain);
		const float scratch = fbm_noise(x, y, p_tile, 6, 6, seed + 53, 3);
		if (Math::abs(scratch - 0.5f) < 0.02f) {
			c = c.lightened(0.15f); // Scratches along a warped contour.
		}
	}
	return c;
}

} // namespace

namespace {

// draw_frame with the soft shadow's opacity as a parameter: the public
// function keeps the opacity frames have always had (0.5), the style
// layer passes the elevation level's (B-1314). The hard offset shadow of
// the halftone / pixel materials keeps its own 0.85 — that flatness is
// the material's trait, not an elevation value.
Ref<Image> draw_frame_impl(const Dictionary &p_style, float p_shadow_alpha) {
	const String material = p_style.get("material", "flat");
	const String shape = p_style.get("shape", "rounded");
	const Color base = color_of(p_style.get("base", Variant()), Color(0.12, 0.14, 0.22, 0.94));
	const Color edge = color_of(p_style.get("edge", Variant()), base.darkened(0.5));
	const Color accent = color_of(p_style.get("accent", Variant()), Color::html("#d9a441"));
	const String ornament = p_style.get("ornament", "none");
	const bool pixel = shape == "pixel";
	// Generation resolution scale (B-1311): 2 renders every length at
	// twice the px, so frames stay sharp where the UI is scaled up
	// (high-DPI); the default 1 keeps the old sizes.
	const int scale = CLAMP(int(p_style.get("scale", 1)), 1, 2);
	const int tile = FRAME_TILE * scale;
	const int radius = CLAMP(int(p_style.get("radius", pixel ? 0 : 8)), 0, 48) * scale;
	const int bw = CLAMP(int(p_style.get("border_width", 3)), 0, 16) * scale;
	const int shadow = CLAMP(int(p_style.get("shadow", 6)), 0, 32) * scale;
	const uint32_t seed = uint32_t(int(p_style.get("seed", 1)));
	const int orn = ornament == "none" ? 0 : 10 * scale;
	// Depth layers over the material (B-1318), each a 0..1 strength in
	// the style: "inner_shadow" shades the surface just inside the rim,
	// "highlight" is the rim light from the top left, "glow" bleeds the
	// accent color in from the edge. The defaults keep every existing
	// frame's look — all off, except the glow glass has always had.
	const float inner_shadow = CLAMP(float(p_style.get("inner_shadow", 0.0)), 0.0f, 1.0f);
	const float highlight = CLAMP(float(p_style.get("highlight", 0.0)), 0.0f, 1.0f);
	const float glow = CLAMP(float(p_style.get("glow", material == "glass" ? 0.35f : 0.0f)), 0.0f, 1.0f);
	// For skew the 9-slice middle is half a tile wide (create_frame_style),
	// so an fbm material must repeat at that period or the tiled middle
	// prints the seam as a pattern jump. Halftone is exempt: its dot
	// cell (tile / 32) divides the half tile exactly.
	const int mat_tile = shape == "skew" && material != "halftone" ? tile / 2 : tile;
	// The corner the 9-slice keeps must contain the whole ornament: an
	// ornament sits bw + 3 in from the frame edge and reaches orn px
	// further. Before B-1311 the corner only reserved MAX(radius, bw*2,
	// orn), so the outer part of every ornament fell into the edge strips
	// the 9-slice tiles, and printed as rows of dots across wide panels.
	const int orn_extent = orn > 0 ? bw + 3 * scale + orn : 0;
	const int corner = MAX(MAX(radius, bw * 2), orn_extent) + 2 * scale + (shape == "skew" ? 8 * scale : 0);
	const int w = 2 * (shadow + corner) + tile;
	const int h = w;
	const Vector2 center(w * 0.5f, h * 0.5f);
	const Vector2 half(w * 0.5f - shadow, h * 0.5f - shadow);
	const bool hard_shadow = material == "halftone" || pixel;
	Ref<Image> img = Image::create_empty(w, h, false, Image::FORMAT_RGBA8);
	for (int y = 0; y < h; y++) {
		for (int x = 0; x < w; x++) {
			const Vector2 p(x + 0.5f, y + 0.5f);
			float d = frame_distance(shape, p, center, half, radius);
			if (pixel) {
				// A stepped corner: the one-pixel notch of pixel-art frames, no anti-aliasing.
				const Vector2 q = (p - center).abs();
				if (q.x > half.x - 2 && q.y > half.y - 2) {
					d = 1.0f;
				}
			}
			const float inside = pixel ? (d <= 0.0f ? 1.0f : 0.0f) : CLAMP(0.5f - d, 0.0f, 1.0f);
			Color c = material_color(material, base, p.x, p.y, d, seed, mat_tile, scale);
			// Bevel: light from the top, dark at the bottom, just inside the border.
			if (d > -(bw * 2.0f + 2.0f * scale) && d < -bw && !pixel) {
				c = (p.y < center.y) ? c.lightened(0.18f) : c.darkened(0.18f);
			}
			if (bw > 0) {
				const float in_border = pixel ? (d > -bw ? 1.0f : 0.0f) : CLAMP(d + bw + 0.5f, 0.0f, 1.0f);
				Color e = edge;
				if (material == "glass") {
					e = accent; // A lit edge.
				}
				c = c.lerp(e, in_border);
				// Rim highlight (B-1318): the border catches the light
				// from the top left, so the frame reads as a raised
				// surface instead of a flat print. The SDF gradient
				// points out of the frame; the light is its up/left part.
				if (highlight > 0.0f && !pixel) {
					const float gx = frame_distance(shape, p + Vector2(1, 0), center, half, radius) - frame_distance(shape, p - Vector2(1, 0), center, half, radius);
					const float gy = frame_distance(shape, p + Vector2(0, 1), center, half, radius) - frame_distance(shape, p - Vector2(0, 1), center, half, radius);
					const Vector2 n = Vector2(gx, gy).normalized();
					const float light = CLAMP(-n.y * 0.7f - n.x * 0.45f, 0.0f, 1.0f);
					c = c.lightened(highlight * 0.38f * light * in_border);
				}
			}
			// Depth layers over the interior (B-1318): the accent glow
			// bleeding in from the edge and the inner shadow, the soft
			// shade the rim casts on the surface just inside it. Both
			// fall off within a few px, so the middle of a wide panel
			// keeps the plain material.
			if (d < 0.0f) {
				if (glow > 0.0f) {
					c = c.lerp(accent, glow * Math::exp(d / (3.0f * scale))); // Glow just inside the edge.
				}
				if (inner_shadow > 0.0f) {
					c = c.darkened(inner_shadow * 0.55f * Math::exp(d / (7.0f * scale)));
				}
			}
			// Corner ornaments, in the corner squares the 9-slice keeps
			// (the corner above reserves their full extent, B-1311).
			if (orn > 0 && inside > 0.0f) {
				const Vector2 q = (p - center).abs();
				const Vector2 k = Vector2(half.x, half.y) - q; // Distance in from each side.
				const float kx = k.x - bw - 3.0f * scale;
				const float ky = k.y - bw - 3.0f * scale;
				if (kx >= 0.0f && ky >= 0.0f && kx < orn && ky < orn) {
					// Shape tests in scale-1 units, so scale 2 draws the same ornament at twice the px.
					const float ux = kx / scale;
					const float uy = ky / scale;
					bool mark = false;
					if (ornament == "rivets" || ornament == "nails") {
						mark = Vector2(ux - 3.0f, uy - 3.0f).length() < (ornament == "rivets" ? 2.6f : 1.6f);
					} else if (ornament == "brackets") {
						mark = (ux < 2.0f && uy < 10.0f) || (uy < 2.0f && ux < 10.0f);
					} else if (ornament == "diamonds") {
						mark = Math::abs(ux - 4.0f) + Math::abs(uy - 4.0f) < 3.5f;
					}
					if (mark) {
						c = ornament == "nails" ? Color(0.15, 0.12, 0.1) : accent.lightened(ornament == "rivets" ? 0.2f : 0.0f);
						c.a = 1.0f;
					}
				}
			}
			c.a *= inside;
			if (shadow > 0 && inside < 1.0f) {
				float sa;
				if (hard_shadow) {
					// A solid offset block, the comic/pixel way.
					sa = frame_distance(shape, p - Vector2(shadow * 0.6f, shadow * 0.6f), center, half, radius) <= 0.0f ? 0.85f : 0.0f;
				} else {
					const float ds = frame_distance(shape, p - Vector2(0, shadow * 0.35f), center, half, radius);
					const float t = 1.0f - CLAMP(ds / shadow, 0.0f, 1.0f);
					sa = p_shadow_alpha * t * t;
				}
				const float a = c.a + sa * (1.0f - c.a);
				if (a > 0.0f) {
					c = Color((c.r * c.a) / a, (c.g * c.a) / a, (c.b * c.a) / a, a);
				}
			}
			img->set_pixel(x, y, c);
		}
	}
	return img;
}

} // namespace

Ref<Image> UZUUI::draw_frame(const Dictionary &p_style) {
	return draw_frame_impl(p_style, 0.5f);
}

Ref<StyleBox> UZUUI::create_frame_style(const Dictionary &p_style) {
	// Every length the style emits is on the layout scale (B-1314), the
	// same discipline as create_panel_style: the shadow resolves to an
	// elevation step (the kit default is level 2), the radius snaps, the
	// padding is a spacing step. The resolved values go into the style
	// the frame is drawn from, so the drawing and the margins agree.
	Dictionary style = p_style.duplicate();
	const ShadowSpec shadow = style_shadow(style, ELEVATION_SIZE[2]);
	style["shadow"] = shadow.size;
	if (style.has("radius")) {
		style["radius"] = snap_radius(int(style["radius"]));
	}
	const Ref<Image> img = draw_frame_impl(style, shadow.alpha);
	Ref<StyleBoxTexture> sb;
	sb.instantiate();
	sb->set_texture(ImageTexture::create_from_image(img));
	const int scale = CLAMP(int(style.get("scale", 1)), 1, 2);
	const int margin = (img->get_width() - FRAME_TILE * scale) / 2;
	if (String(style.get("shape", "")) == "skew") {
		// A parallelogram's cross-section is 3/4 of the texture width
		// and shifts by a quarter of the height across the middle, so a
		// full-tile middle is not covered by the shape at every row:
		// tiled across a wide panel it left a transparent wedge at
		// every seam (B-1317's persona shot, fixed in B-1318). A
		// half-tile middle lies inside the band at every row — and so
		// do the middles of all four edge strips — so no wedge can
		// form. The fbm materials repeat at the same half period
		// (draw_frame_impl), so the pattern stays seamless too.
		const int margin_x = (img->get_width() - FRAME_TILE * scale / 2) / 2;
		sb->set_texture_margin(SIDE_LEFT, margin_x);
		sb->set_texture_margin(SIDE_RIGHT, margin_x);
		sb->set_texture_margin(SIDE_TOP, margin);
		sb->set_texture_margin(SIDE_BOTTOM, margin);
	} else {
		sb->set_texture_margin_all(margin);
	}
	sb->set_expand_margin_all(shadow.size * scale);
	// The middle repeats, so the texture keeps its scale.
	sb->set_h_axis_stretch_mode(StyleBoxTexture::AXIS_STRETCH_MODE_TILE_FIT);
	sb->set_v_axis_stretch_mode(StyleBoxTexture::AXIS_STRETCH_MODE_TILE_FIT);
	sb->set_content_margin_all(style_padding(style, 12));
	if (String(style.get("shape", "")) == "pixel") {
		sb->set_texture(ImageTexture::create_from_image(img));
	}
	return sb;
}

PackedStringArray UZUUI::get_world_names() {
	return PackedStringArray({ "fantasy", "wafu", "sf", "horror", "persona", "pixel" });
}

Dictionary UZUUI::get_world_options(const String &p_world) {
	Dictionary frame;
	Dictionary button;
	Dictionary o;
	auto set = [](Dictionary &d, const char *k, const Variant &v) { d[k] = v; };
	if (p_world == "fantasy") {
		set(frame, "material", "wood"), set(frame, "base", "#6b4a2e"), set(frame, "edge", "#2e1d10"), set(frame, "accent", "#e6c36a");
		set(frame, "ornament", "brackets"), set(frame, "radius", 8), set(frame, "border_width", 3), set(frame, "shadow", 8);
		set(frame, "inner_shadow", 0.45), set(frame, "highlight", 0.35);
		set(button, "material", "parchment"), set(button, "base", "#e8d6a8"), set(button, "edge", "#5a3d22"), set(button, "radius", 6);
		set(o, "text", "#f6e7c8"), set(o, "button_text", "#3a2614"), set(o, "accent", "#e6c36a"), set(o, "fill", "#d94a3a");
	} else if (p_world == "wafu") {
		set(frame, "material", "parchment"), set(frame, "base", "#efe2c4"), set(frame, "edge", "#3b2416"), set(frame, "accent", "#b8322a");
		set(frame, "ornament", "diamonds"), set(frame, "radius", 2), set(frame, "border_width", 3), set(frame, "shadow", 8);
		set(frame, "inner_shadow", 0.3), set(frame, "highlight", 0.2);
		set(button, "material", "flat"), set(button, "base", "#b8322a"), set(button, "edge", "#3b1410"), set(button, "radius", 2);
		set(o, "text", "#2a1a10"), set(o, "button_text", "#fbf1dc"), set(o, "accent", "#b8322a"), set(o, "fill", "#b8322a");
	} else if (p_world == "sf") {
		set(frame, "material", "glass"), set(frame, "base", "#07141ee6"), set(frame, "edge", "#38e1ff"), set(frame, "accent", "#38e1ff");
		set(frame, "shape", "chamfer"), set(frame, "radius", 12), set(frame, "border_width", 2), set(frame, "shadow", 12);
		set(button, "material", "glass"), set(button, "base", "#0e2a3aee"), set(button, "accent", "#38e1ff"), set(button, "shape", "chamfer"), set(button, "radius", 8);
		set(o, "text", "#d8f6ff"), set(o, "button_text", "#d8f6ff"), set(o, "accent", "#38e1ff"), set(o, "fill", "#38e1ff");
	} else if (p_world == "horror") {
		set(frame, "material", "grime"), set(frame, "base", "#2a1414"), set(frame, "edge", "#090404"), set(frame, "accent", "#8a1010");
		set(frame, "ornament", "nails"), set(frame, "radius", 0), set(frame, "border_width", 3), set(frame, "shadow", 12);
		set(frame, "inner_shadow", 0.5);
		set(button, "material", "grime"), set(button, "base", "#3a1a1a"), set(button, "edge", "#0b0505"), set(button, "radius", 0);
		set(o, "text", "#e8d8d0"), set(o, "button_text", "#e8d8d0"), set(o, "accent", "#a01818"), set(o, "fill", "#8a1010");
	} else if (p_world == "persona") {
		set(frame, "material", "halftone"), set(frame, "base", "#e8212b"), set(frame, "edge", "#111111"), set(frame, "accent", "#ffffff");
		set(frame, "shape", "skew"), set(frame, "border_width", 4), set(frame, "shadow", 12);
		set(frame, "inner_shadow", 0.3), set(frame, "highlight", 0.3);
		set(button, "material", "flat"), set(button, "base", "#111111"), set(button, "edge", "#ffffff"), set(button, "shape", "skew"), set(button, "border_width", 3), set(button, "shadow", 8);
		set(o, "text", "#ffffff"), set(o, "button_text", "#ffffff"), set(o, "accent", "#ffe14d"), set(o, "fill", "#ffe14d");
	} else if (p_world == "pixel") {
		set(frame, "material", "flat"), set(frame, "base", "#1b1f3a"), set(frame, "edge", "#f4f4f4"), set(frame, "accent", "#f4b41a");
		set(frame, "shape", "pixel"), set(frame, "border_width", 3), set(frame, "shadow", 4);
		set(button, "material", "flat"), set(button, "base", "#3b4a8c"), set(button, "edge", "#f4f4f4"), set(button, "shape", "pixel"), set(button, "border_width", 3), set(button, "shadow", 4);
		set(o, "text", "#f4f4f4"), set(o, "button_text", "#f4f4f4"), set(o, "accent", "#f4b41a"), set(o, "fill", "#5bd46a");
	} else {
		ERR_FAIL_V_MSG(Dictionary(), vformat("UZUUI: unknown world \"%s\" (see get_world_names).", p_world));
	}
	o["world"] = p_world;
	o["frame"] = frame;
	o["button"] = button;
	o["font_size"] = p_world == "pixel" ? 16 : 19;
	return o;
}

Dictionary UZUUI::get_world_motion(const String &p_world) {
	// Motion follows the world (gameanimation.info): sharp overshoot for persona, mechanical
	// ease-in for sf, soft overshoot for fantasy and wafu, stepped frames for pixel.
	Dictionary m;
	m["duration"] = 0.25;
	m["transition"] = "back";
	m["ease"] = "out";
	m["overshoot"] = 1.2;
	m["steps"] = 0;
	if (p_world == "persona") {
		m["duration"] = 0.18, m["overshoot"] = 2.6;
	} else if (p_world == "sf") {
		m["transition"] = "expo", m["ease"] = "in_out", m["overshoot"] = 0.0, m["duration"] = 0.3;
	} else if (p_world == "horror") {
		m["transition"] = "sine", m["ease"] = "in_out", m["overshoot"] = 0.0, m["duration"] = 0.6;
	} else if (p_world == "pixel") {
		m["transition"] = "linear", m["overshoot"] = 0.0, m["steps"] = 4, m["duration"] = 0.2;
	} else if (p_world == "wafu") {
		m["transition"] = "quart", m["ease"] = "out", m["overshoot"] = 0.0, m["duration"] = 0.35;
	}
	return m;
}

Ref<Theme> UZUUI::create_world_theme(const String &p_world, const Dictionary &p_overrides) {
	Dictionary o = get_world_options(p_world);
	ERR_FAIL_COND_V(o.is_empty(), Ref<Theme>());
	for (const Variant &k : p_overrides.keys()) {
		o[k] = p_overrides[k];
	}
	Dictionary base_options;
	base_options["accent"] = o["accent"];
	base_options["text"] = o["text"];
	base_options["font_size"] = o["font_size"];
	if (o.has("font")) {
		base_options["font"] = o["font"];
	}
	Dictionary bar;
	bar["fill"] = o["fill"];
	base_options["bar"] = bar;
	Ref<Theme> theme = create_theme(base_options);
	const Dictionary frame = o["frame"];
	const Dictionary button = o["button"];
	const Ref<StyleBox> panel = create_frame_style(frame);
	for (const char *cls : { "PanelContainer", "TabContainer", "ItemList" }) {
		theme->set_stylebox("panel", cls, panel);
	}
	Dictionary tip = frame.duplicate();
	tip["padding"] = 8;
	tip["ornament"] = "none";
	theme->set_stylebox("panel", "TooltipPanel", create_frame_style(tip));
	// Buttons: the world's button, lighter on hover, darker and flat when pressed.
	const Ref<StyleBox> wbtn_normal = create_frame_style(button);
	theme->set_stylebox("normal", "Button", wbtn_normal);
	Dictionary state = button.duplicate();
	const Color bbase = color_of(button["base"], Color(0.2, 0.2, 0.3));
	state["base"] = bbase.lightened(0.18);
	const Ref<StyleBox> wbtn_hover = create_frame_style(state);
	theme->set_stylebox("hover", "Button", wbtn_hover);
	state["base"] = bbase.darkened(0.25);
	state["shadow"] = 0;
	const Ref<StyleBox> wbtn_pressed = create_frame_style(state);
	theme->set_stylebox("pressed", "Button", wbtn_pressed);
	state["base"] = Color(bbase.darkened(0.4), 0.7);
	const Ref<StyleBox> wbtn_disabled = create_frame_style(state);
	theme->set_stylebox("disabled", "Button", wbtn_disabled);
	const Color btext = color_of(o["button_text"], Color(1, 1, 1));
	for (const char *name : { "font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color" }) {
		theme->set_color(name, "Button", btext);
	}
	// Tabs use the button frames.
	theme->set_stylebox("tab_selected", "TabContainer", create_frame_style(button));
	Dictionary tab_off = button.duplicate();
	tab_off["base"] = Color(bbase.darkened(0.35), 0.9);
	theme->set_stylebox("tab_unselected", "TabContainer", create_frame_style(tab_off));
	theme->set_stylebox("tab_hovered", "TabContainer", create_frame_style(state));
	theme->set_color("font_selected_color", "TabContainer", btext);
	theme->set_color("font_unselected_color", "TabContainer", Color(btext, 0.7));
	theme->set_color("font_hovered_color", "TabContainer", btext);

	// Game parts as type variations of the usual controls.
	const Color accent = color_of(o["accent"], Color::html("#d9a441"));
	const Color text = color_of(o["text"], Color(1, 1, 1));
	// Every remaining standard control, restyled in the world's frames
	// (B-1313; create_theme styled them in the default idiom, the world
	// pass replaces them): the input field is the frame sunk — base
	// darkened, no ornament, no shadow.
	Dictionary field_frame = frame.duplicate();
	field_frame["base"] = color_of(frame["base"], Color(0.1, 0.1, 0.14)).darkened(0.3);
	field_frame["ornament"] = "none";
	field_frame["shadow"] = 0;
	field_frame["padding"] = 8;
	const int button_radius = int(button.get("radius", 8));
	style_extended_controls(theme, panel, create_frame_style(field_frame), wbtn_normal, wbtn_hover, wbtn_pressed, wbtn_disabled,
			accent, text, color_of(field_frame["base"], Color(0.07, 0.07, 0.1)), button_radius);
	theme->set_stylebox("focus", "Button", focus_box(accent, button_radius));
	theme->set_stylebox("focus", "ItemList", focus_box(accent, int(frame.get("radius", 8))));
	theme->set_stylebox("cursor", "ItemList", flat_box(Color(0, 0, 0, 0), 4, 0, accent, 1));
	theme->set_stylebox("cursor_unfocused", "ItemList", flat_box(Color(0, 0, 0, 0), 4, 0, Color(accent, 0.4), 1));
	// Name tag: a small frame of the accent color.
	Dictionary tag = button.duplicate();
	tag["base"] = accent;
	tag["ornament"] = "none";
	tag["padding"] = 4; // Spacing scale (was 6).
	theme->set_type_variation("UZUNameTag", "PanelContainer");
	theme->set_stylebox("panel", "UZUNameTag", create_frame_style(tag));
	theme->set_type_variation("UZUNameTagLabel", "Label");
	theme->set_color("font_color", "UZUNameTagLabel", accent.get_luminance() > 0.55 ? Color(0.08, 0.06, 0.05) : Color(1, 1, 1));
	// The ribbon's label: the title step of the type scale (B-1312), in the
	// name tag's contrast color — it sits on the accent, not on a panel.
	const Dictionary title_step = type_scale_for(int(o["font_size"]))["title"];
	theme->set_type_variation("UZURibbonLabel", "Label");
	theme->set_font_size("font_size", "UZURibbonLabel", int(title_step["size"]));
	theme->set_color("font_color", "UZURibbonLabel", accent.get_luminance() > 0.55 ? Color(0.08, 0.06, 0.05) : Color(1, 1, 1));
	theme->set_type_variation("UZUTalk", "PanelContainer");
	theme->set_stylebox("panel", "UZUTalk", panel);
	// Item slot: a sunken square.
	Dictionary slot = frame.duplicate();
	slot["base"] = color_of(frame["base"], Color(0.1, 0.1, 0.1)).darkened(0.35);
	slot["ornament"] = "none";
	slot["shadow"] = 0;
	slot["padding"] = 4; // Spacing scale (was 6).
	theme->set_type_variation("UZUSlot", "PanelContainer");
	theme->set_stylebox("panel", "UZUSlot", create_frame_style(slot));
	// Ribbon heading: the accent, wider padding.
	Dictionary ribbon = tag.duplicate();
	ribbon["padding"] = 8; // Spacing scale (was 10).
	ribbon["shape"] = String(frame.get("shape", "rounded")) == "pixel" ? "pixel" : "chamfer";
	ribbon["radius"] = 10;
	theme->set_type_variation("UZURibbon", "PanelContainer");
	theme->set_stylebox("panel", "UZURibbon", create_frame_style(ribbon));
	// Segmented gauge: the fill repeats a segment with a gap.
	Ref<Image> seg = Image::create_empty(12, 12, false, Image::FORMAT_RGBA8);
	Ref<Image> seg_bg = Image::create_empty(12, 12, false, Image::FORMAT_RGBA8);
	const Color fill = color_of(o["fill"], accent);
	for (int y = 0; y < 12; y++) {
		for (int x = 0; x < 12; x++) {
			const bool gap = x >= 10;
			const float shade = 1.0f - 0.25f * (y / 11.0f);
			seg->set_pixel(x, y, gap ? Color(0, 0, 0, 0) : Color(fill.r * shade, fill.g * shade, fill.b * shade, 1.0f));
			seg_bg->set_pixel(x, y, gap ? Color(0, 0, 0, 0) : Color(0, 0, 0, 0.55f));
		}
	}
	for (int i = 0; i < 2; i++) {
		Ref<StyleBoxTexture> sb;
		sb.instantiate();
		sb->set_texture(ImageTexture::create_from_image(i == 0 ? seg : seg_bg));
		sb->set_h_axis_stretch_mode(StyleBoxTexture::AXIS_STRETCH_MODE_TILE);
		sb->set_v_axis_stretch_mode(StyleBoxTexture::AXIS_STRETCH_MODE_STRETCH);
		theme->set_stylebox(i == 0 ? "fill" : "background", "UZUGauge", sb);
	}
	theme->set_type_variation("UZUGauge", "ProgressBar");
	// Separator: a line in the accent with a diamond in the middle (drawn by make_separator).
	theme->set_color("font_color", "Label", text);
	theme->set_meta("uzu_world", p_world);
	theme->set_meta("uzu_motion", get_world_motion(p_world));
	return theme;
}

Control *UZUUI::make_gauge(double p_value, double p_max, int p_segments) {
	ProgressBar *bar = memnew(ProgressBar);
	bar->set_name("Gauge");
	bar->set_theme_type_variation("UZUGauge");
	bar->set_max(p_max);
	bar->set_value(p_value);
	bar->set_show_percentage(false);
	// Segments are 12 px wide; the bar is as wide as the segments asked for.
	bar->set_custom_minimum_size(Size2(12 * MAX(p_segments, 1), 14));
	return bar;
}

Control *UZUUI::make_talk_window(const String &p_speaker, const String &p_text) {
	VBoxContainer *root = memnew(VBoxContainer);
	root->set_name("Talk");
	root->add_theme_constant_override("separation", -8); // The name tag overlaps the window's top edge.
	MarginContainer *tag_margin = memnew(MarginContainer);
	tag_margin->set_name("TagMargin");
	tag_margin->add_theme_constant_override("margin_left", 24);
	tag_margin->set_z_index(1);
	tag_margin->set_h_size_flags(Control::SIZE_SHRINK_BEGIN);
	PanelContainer *tag = memnew(PanelContainer);
	tag->set_name("NameTag");
	tag->set_theme_type_variation("UZUNameTag");
	Label *name = memnew(Label);
	name->set_name("Speaker");
	name->set_theme_type_variation("UZUNameTagLabel");
	name->set_text(p_speaker);
	tag->add_child(name);
	tag_margin->add_child(tag);
	root->add_child(tag_margin);
	PanelContainer *window = memnew(PanelContainer);
	window->set_name("Window");
	window->set_theme_type_variation("UZUTalk");
	VBoxContainer *body = memnew(VBoxContainer);
	body->set_name("Body");
	Label *line = memnew(Label);
	line->set_name("Line");
	line->set_theme_type_variation("UZUBodyLabel");
	line->set_text(p_text);
	line->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	line->set_custom_minimum_size(Size2(320, 48));
	body->add_child(line);
	Label *next = memnew(Label);
	next->set_name("Next");
	next->set_text(String::utf8("▼"));
	next->set_horizontal_alignment(HORIZONTAL_ALIGNMENT_RIGHT);
	body->add_child(next);
	window->add_child(body);
	root->add_child(window);
	return root;
}

Control *UZUUI::make_item_slot(const String &p_label, int p_count) {
	PanelContainer *slot = memnew(PanelContainer);
	slot->set_name("Slot");
	slot->set_theme_type_variation("UZUSlot");
	slot->set_custom_minimum_size(Size2(64, 64));
	VBoxContainer *box = memnew(VBoxContainer);
	box->set_name("Box");
	Label *label = memnew(Label);
	label->set_name("Item");
	label->set_text(p_label);
	label->set_horizontal_alignment(HORIZONTAL_ALIGNMENT_CENTER);
	label->set_v_size_flags(Control::SIZE_EXPAND_FILL);
	label->set_vertical_alignment(VERTICAL_ALIGNMENT_CENTER);
	box->add_child(label);
	if (p_count > 0) {
		Label *count = memnew(Label);
		count->set_name("Count");
		count->set_theme_type_variation("UZUCaptionLabel");
		count->set_text(itos(p_count));
		count->set_horizontal_alignment(HORIZONTAL_ALIGNMENT_RIGHT);
		box->add_child(count);
	}
	slot->add_child(box);
	return slot;
}

Control *UZUUI::make_ribbon(const String &p_text) {
	PanelContainer *ribbon = memnew(PanelContainer);
	ribbon->set_name("Ribbon");
	ribbon->set_theme_type_variation("UZURibbon");
	Label *label = memnew(Label);
	label->set_name("Title");
	label->set_theme_type_variation("UZURibbonLabel");
	label->set_text(p_text);
	label->set_horizontal_alignment(HORIZONTAL_ALIGNMENT_CENTER);
	ribbon->add_child(label);
	return ribbon;
}

Control *UZUUI::make_separator() {
	// A thin line that fades at both ends, with a diamond in the middle.
	const int w = 256;
	const int h = 12;
	Ref<Image> img = Image::create_empty(w, h, false, Image::FORMAT_RGBA8);
	for (int y = 0; y < h; y++) {
		for (int x = 0; x < w; x++) {
			const float fade = 1.0f - Math::abs(x - w * 0.5f) / (w * 0.5f);
			const bool line = Math::abs(y - h * 0.5f + 0.5f) < 1.0f;
			const bool diamond = Math::abs(x - w * 0.5f) + Math::abs(y - h * 0.5f + 0.5f) < 5.0f;
			const float a = diamond ? 1.0f : (line ? fade : 0.0f);
			img->set_pixel(x, y, Color(1, 1, 1, a));
		}
	}
	TextureRect *sep = memnew(TextureRect);
	sep->set_name("Separator");
	sep->set_texture(ImageTexture::create_from_image(img));
	sep->set_expand_mode(TextureRect::EXPAND_IGNORE_SIZE);
	sep->set_stretch_mode(TextureRect::STRETCH_SCALE);
	sep->set_custom_minimum_size(Size2(0, 12));
	sep->set_self_modulate(Color(1, 1, 1, 0.8));
	return sep;
}

static const char *WORLD_FRAME_SHADER = R"(
shader_type canvas_item;
// The moving decoration of world UI frames (UZUUI, B-1307): a glint that sweeps across,
// a breathing pulse, a flicker, or scan lines that flow. Only the frame is drawn with
// this material; the text and the parts inside keep their own.
uniform int mode = 1;
uniform vec4 glow_color : source_color = vec4(1.0, 0.9, 0.6, 1.0);
uniform float speed = 0.3;
uniform float strength = 0.22;
uniform float steps = 0.0;
varying vec2 local;

void vertex() {
	local = VERTEX;
}

void fragment() {
	vec4 c = texture(TEXTURE, UV) * COLOR;
	float t = TIME * speed;
	if (steps > 0.0) {
		t = floor(t * steps) / steps; // Stepped, like frame-by-frame pixel art.
	}
	float k = 0.0;
	if (mode == 1) {
		float x = mod(local.x + local.y * 0.6 - t * 900.0, 1800.0);
		k = smoothstep(0.0, 50.0, x) * (1.0 - smoothstep(50.0, 110.0, x));
	} else if (mode == 2) {
		k = 0.5 + 0.5 * sin(t * 6.2831853);
	} else if (mode == 3) {
		float n = fract(sin(floor(t * 14.0) * 91.7) * 4373.1);
		k = n > 0.82 ? 1.0 : 0.0;
	} else if (mode == 4) {
		k = 0.5 + 0.5 * sin((local.y - t * 80.0) * 0.35);
	}
	c.rgb = mix(c.rgb, glow_color.rgb, clamp(k * strength, 0.0, 1.0));
	COLOR = c;
}
)";

Ref<ShaderMaterial> UZUUI::create_world_material(const String &p_world) {
	struct Decor {
		const char *world;
		int mode;
		const char *color;
		float speed, strength, steps;
	};
	static const Decor DECOR[] = {
		{ "fantasy", 1, "#fff1b0", 0.25f, 0.28f, 0.0f }, // A gold glint now and then.
		{ "wafu", 1, "#fff8e6", 0.12f, 0.16f, 0.0f }, // A slow, quiet sheen.
		{ "sf", 4, "#7ff0ff", 1.0f, 0.12f, 0.0f }, // Scan lines flowing down.
		{ "horror", 3, "#000000", 1.0f, 0.45f, 0.0f }, // A failing light.
		{ "persona", 1, "#ffffff", 0.9f, 0.4f, 0.0f }, // A fast white flash.
		{ "pixel", 2, "#ffffff", 0.5f, 0.14f, 4.0f }, // A stepped blink.
	};
	for (const Decor &d : DECOR) {
		if (p_world != d.world) {
			continue;
		}
		Ref<Shader> shader;
		shader.instantiate();
		shader->set_code(WORLD_FRAME_SHADER);
		Ref<ShaderMaterial> m;
		m.instantiate();
		m->set_shader(shader);
		m->set_shader_parameter("mode", d.mode);
		m->set_shader_parameter("glow_color", Color::html(d.color));
		m->set_shader_parameter("speed", d.speed);
		m->set_shader_parameter("strength", d.strength);
		m->set_shader_parameter("steps", d.steps);
		return m;
	}
	ERR_FAIL_V_MSG(Ref<ShaderMaterial>(), vformat("UZUUI: unknown world \"%s\" (see get_world_names).", p_world));
}

void UZUUIWorld::set_world(const String &p_world) {
	world = p_world;
}
String UZUUIWorld::get_world() const {
	return world;
}
void UZUUIWorld::set_open_on_ready(bool p_enable) {
	open_on_ready = p_enable;
}
bool UZUUIWorld::is_open_on_ready() const {
	return open_on_ready;
}
void UZUUIWorld::set_hover(bool p_enable) {
	hover = p_enable;
}
bool UZUUIWorld::is_hover() const {
	return hover;
}
void UZUUIWorld::set_ambient(bool p_enable) {
	ambient = p_enable;
}
bool UZUUIWorld::is_ambient() const {
	return ambient;
}

void UZUUIWorld::_on_hover(ObjectID p_control) {
	Control *c = ObjectDB::get_instance<Control>(p_control);
	if (c) {
		const Dictionary motion = UZUUI::get_world_motion(world);
		UZUUIJuice::hover_pulse(c, CLAMP(double(motion.get("overshoot", 1.2)) * 0.5, 0.3, 1.5));
	}
}

Dictionary UZUUIWorld::decorate() {
	Control *root = Object::cast_to<Control>(get_parent());
	ERR_FAIL_NULL_V_MSG(root, Dictionary(), "UZUUIWorld: the parent must be a Control (the screen).");
	const Ref<ShaderMaterial> material = UZUUI::create_world_material(world);
	ERR_FAIL_COND_V(material.is_null(), Dictionary());
	int panels = 0;
	int buttons = 0;
	int opened = 0;
	int motions = 0;
	ribbons.clear();
	next_marks.clear();
	TypedArray<Node> all = root->find_children("*", "Control", true, false);
	for (const Variant &v : all) {
		Control *c = Object::cast_to<Control>(v);
		if (!c) {
			continue;
		}
		const bool framed = Object::cast_to<PanelContainer>(c) || Object::cast_to<TabContainer>(c) || Object::cast_to<BaseButton>(c);
		if (framed && c->get_material().is_null()) {
			c->set_material(material); // The children keep their own materials (use_parent_material is off).
			panels += Object::cast_to<BaseButton>(c) ? 0 : 1;
		}
		if (BaseButton *b = Object::cast_to<BaseButton>(c)) {
			buttons++;
			const Callable cb = callable_mp(this, &UZUUIWorld::_on_hover).bind(b->get_instance_id());
			if (hover && !b->is_connected(SceneStringName(mouse_entered), cb)) {
				b->connect(SceneStringName(mouse_entered), cb);
			}
		}
		if (c->get_theme_type_variation() == StringName("UZURibbon")) {
			ribbons.push_back(c->get_instance_id());
		}
		if (c->get_name() == StringName("Next") && Object::cast_to<Label>(c)) {
			next_marks.push_back(c->get_instance_id());
		}
		// A motion the spec named for this control (B-1317: the "motion"
		// key of ai_loop/ui_tool.gd, stored as "uzu_motion" metadata)
		// plays with this world's motion, instead of the default opening.
		bool spec_motion = false;
		if (c->has_meta("uzu_motion")) {
			const Dictionary spec = c->get_meta("uzu_motion");
			Dictionary options = spec.duplicate(); // A Dictionary is a reference: erasing from a plain copy would eat the spec (and the stored meta).
			options.erase("preset");
			if (!options.has("world")) {
				options["world"] = world;
			}
			spec_motion = UZUUIJuice::play_motion(c, String(spec.get("preset", "")), options);
			motions += spec_motion ? 1 : 0;
		}
		// The top-level panels open with the world's motion.
		if (open_on_ready && !spec_motion && Object::cast_to<PanelContainer>(c) && c->get_parent() == root && c->is_inside_tree()) {
			opened += UZUUIJuice::apply_world_motion(c, world, true) ? 1 : 0;
		}
	}
	// Talk windows and other made parts are VBoxes holding panels: open those too.
	for (int i = 0; open_on_ready && i < root->get_child_count(); i++) {
		Control *c = Object::cast_to<Control>(root->get_child(i));
		if (c && !Object::cast_to<PanelContainer>(c) && c->is_inside_tree() && c->find_child("Window", false, false)) {
			opened += UZUUIJuice::apply_world_motion(c, world, true) ? 1 : 0;
		}
	}
	stats["world"] = world;
	stats["panels"] = panels;
	stats["buttons"] = buttons;
	stats["opened"] = opened;
	stats["motions"] = motions;
	stats["ribbons"] = ribbons.size();
	stats["next_marks"] = next_marks.size();
	return stats;
}

void UZUUIWorld::advance(double p_delta) {
	time += p_delta;
	const Dictionary motion = UZUUI::get_world_motion(world);
	const int steps = motion.get("steps", 0);
	const double t = steps > 0 ? Math::floor(time * steps * 2.0) / (steps * 2.0) : time;
	for (const ObjectID &id : ribbons) {
		if (Control *r = ObjectDB::get_instance<Control>(id)) {
			r->set_pivot_offset(r->get_size() * 0.5);
			r->set_rotation_degrees(1.2 * Math::sin(t * 1.6)); // A gentle sway.
		}
	}
	for (const ObjectID &id : next_marks) {
		if (Control *m = ObjectDB::get_instance<Control>(id)) {
			m->set_self_modulate(Color(1, 1, 1, 0.35 + 0.65 * (0.5 + 0.5 * Math::cos(t * 5.0)))); // The blinking next mark.
		}
	}
	stats["time"] = time;
}

Dictionary UZUUIWorld::get_stats() const {
	return stats;
}

void UZUUIWorld::_notification(int p_what) {
	switch (p_what) {
		case NOTIFICATION_READY: {
			if (Engine::get_singleton()->is_editor_hint()) {
				return;
			}
			// After the parent's children are ready and laid out.
			callable_mp(this, &UZUUIWorld::decorate).call_deferred();
			set_process(ambient);
		} break;
		case NOTIFICATION_PROCESS: {
			advance(get_process_delta_time());
		} break;
	}
}

void UZUUIWorld::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_world", "world"), &UZUUIWorld::set_world);
	ClassDB::bind_method(D_METHOD("get_world"), &UZUUIWorld::get_world);
	ClassDB::bind_method(D_METHOD("set_open_on_ready", "enable"), &UZUUIWorld::set_open_on_ready);
	ClassDB::bind_method(D_METHOD("is_open_on_ready"), &UZUUIWorld::is_open_on_ready);
	ClassDB::bind_method(D_METHOD("set_hover", "enable"), &UZUUIWorld::set_hover);
	ClassDB::bind_method(D_METHOD("is_hover"), &UZUUIWorld::is_hover);
	ClassDB::bind_method(D_METHOD("set_ambient", "enable"), &UZUUIWorld::set_ambient);
	ClassDB::bind_method(D_METHOD("is_ambient"), &UZUUIWorld::is_ambient);
	ClassDB::bind_method(D_METHOD("decorate"), &UZUUIWorld::decorate);
	ClassDB::bind_method(D_METHOD("advance", "delta"), &UZUUIWorld::advance);
	ClassDB::bind_method(D_METHOD("get_stats"), &UZUUIWorld::get_stats);
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "world", PROPERTY_HINT_ENUM, "fantasy,wafu,sf,horror,persona,pixel"), "set_world", "get_world");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "open_on_ready"), "set_open_on_ready", "is_open_on_ready");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "hover"), "set_hover", "is_hover");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "ambient"), "set_ambient", "is_ambient");
}

Control *UZUUI::make_panel(Control *p_content) {
	PanelContainer *panel = memnew(PanelContainer);
	panel->set_name("Panel");
	if (p_content) {
		panel->add_child(p_content);
	}
	return panel;
}

Control *UZUUI::make_button(const String &p_text) {
	Button *b = memnew(Button);
	b->set_name("Button");
	b->set_text(p_text);
	return b;
}

Control *UZUUI::make_label(const String &p_text, const String &p_step) {
	Label *label = memnew(Label);
	label->set_name("Label");
	label->set_text(p_text);
	if (!is_type_step(p_step)) {
		WARN_PRINT(vformat("UZUUI: unknown type step \"%s\" (display, title, heading, body, caption); using \"body\".", p_step));
	}
	label->set_theme_type_variation(type_variation_name(is_type_step(p_step) ? p_step : "body"));
	return label;
}

Control *UZUUI::make_bar(double p_value, double p_max) {
	ProgressBar *bar = memnew(ProgressBar);
	bar->set_name("Bar");
	bar->set_max(p_max);
	bar->set_value(p_value);
	bar->set_show_percentage(false);
	bar->set_custom_minimum_size(Size2(0, 16));
	return bar;
}

Control *UZUUI::make_tabs(const PackedStringArray &p_titles) {
	TabContainer *tabs = memnew(TabContainer);
	tabs->set_name("Tabs");
	for (const String &title : p_titles) {
		VBoxContainer *page = memnew(VBoxContainer);
		page->set_name(title.validate_node_name());
		tabs->add_child(page, true);
	}
	return tabs;
}

Control *UZUUI::make_list(const PackedStringArray &p_items) {
	ItemList *list = memnew(ItemList);
	list->set_name("List");
	for (const String &item : p_items) {
		list->add_item(item);
	}
	list->set_auto_height(true);
	return list;
}

Control *UZUUI::make_dialog(const String &p_title, const String &p_text, const PackedStringArray &p_buttons) {
	VBoxContainer *box = memnew(VBoxContainer);
	box->set_name("Content");
	Label *title = memnew(Label);
	title->set_name("Title");
	title->set_theme_type_variation("UZUTitleLabel");
	title->set_text(p_title);
	box->add_child(title);
	Label *text = memnew(Label);
	text->set_name("Text");
	text->set_theme_type_variation("UZUBodyLabel");
	text->set_text(p_text);
	text->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
	text->set_custom_minimum_size(Size2(360, 0));
	box->add_child(text);
	HBoxContainer *row = memnew(HBoxContainer);
	row->set_name("Buttons");
	row->set_alignment(BoxContainer::ALIGNMENT_END);
	for (const String &label : p_buttons) {
		Control *b = make_button(label);
		b->set_name(label.validate_node_name());
		row->add_child(b, true);
	}
	box->add_child(row);
	Control *panel = make_panel(box);
	panel->set_name("Dialog");
	return panel;
}

void UZUUI::_bind_methods() {
	ClassDB::bind_static_method("UZUUI", D_METHOD("create_panel_style", "style"), &UZUUI::create_panel_style);
	ClassDB::bind_static_method("UZUUI", D_METHOD("draw_panel", "radius", "top", "bottom", "border", "border_width", "shadow"), &UZUUI::draw_panel);
	ClassDB::bind_static_method("UZUUI", D_METHOD("create_theme", "options"), &UZUUI::create_theme, DEFVAL(Dictionary()));
	ClassDB::bind_static_method("UZUUI", D_METHOD("get_theme_defaults"), &UZUUI::get_theme_defaults);
	ClassDB::bind_static_method("UZUUI", D_METHOD("get_layout_scale"), &UZUUI::get_layout_scale);
	ClassDB::bind_static_method("UZUUI", D_METHOD("get_type_scale", "base_size"), &UZUUI::get_type_scale);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_label", "text", "step"), &UZUUI::make_label, DEFVAL("body"));
	ClassDB::bind_static_method("UZUUI", D_METHOD("draw_frame", "style"), &UZUUI::draw_frame);
	ClassDB::bind_static_method("UZUUI", D_METHOD("create_frame_style", "style"), &UZUUI::create_frame_style);
	ClassDB::bind_static_method("UZUUI", D_METHOD("get_world_names"), &UZUUI::get_world_names);
	ClassDB::bind_static_method("UZUUI", D_METHOD("get_world_options", "world"), &UZUUI::get_world_options);
	ClassDB::bind_static_method("UZUUI", D_METHOD("create_world_theme", "world", "overrides"), &UZUUI::create_world_theme, DEFVAL(Dictionary()));
	ClassDB::bind_static_method("UZUUI", D_METHOD("get_world_motion", "world"), &UZUUI::get_world_motion);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_gauge", "value", "max", "segments"), &UZUUI::make_gauge, DEFVAL(100.0), DEFVAL(10));
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_talk_window", "speaker", "text"), &UZUUI::make_talk_window);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_item_slot", "label", "count"), &UZUUI::make_item_slot, DEFVAL(String()), DEFVAL(0));
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_ribbon", "text"), &UZUUI::make_ribbon);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_separator"), &UZUUI::make_separator);
	ClassDB::bind_static_method("UZUUI", D_METHOD("create_world_material", "world"), &UZUUI::create_world_material);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_panel", "content"), &UZUUI::make_panel, DEFVAL(Variant()));
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_button", "text"), &UZUUI::make_button);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_bar", "value", "max"), &UZUUI::make_bar, DEFVAL(100.0));
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_tabs", "titles"), &UZUUI::make_tabs);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_list", "items"), &UZUUI::make_list);
	ClassDB::bind_static_method("UZUUI", D_METHOD("make_dialog", "title", "text", "buttons"), &UZUUI::make_dialog);
}
