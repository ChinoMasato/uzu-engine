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
#include "scene/resources/style_box_flat.h"
#include "scene/resources/style_box_texture.h"
#include "scene/resources/theme.h"
#include "scene/scene_string_names.h"

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
	panel["padding"] = 14;
	d["panel"] = panel;
	Dictionary button;
	button["top"] = Color::html("#34416a");
	button["bottom"] = Color::html("#253050");
	button["hover"] = Color::html("#46598f");
	button["pressed"] = Color::html("#1a2238");
	button["radius"] = 8;
	button["border_width"] = 1;
	button["shadow"] = 3;
	button["padding"] = 10;
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

} // namespace

Ref<Image> UZUUI::draw_panel(int p_radius, const Color &p_top, const Color &p_bottom, const Color &p_border, int p_border_width, int p_shadow) {
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
				const float sa = 0.45f * s * s;
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

Ref<StyleBox> UZUUI::create_panel_style(const Dictionary &p_style) {
	const Color bg = color_of(p_style.get("bg", Variant()), Color(0.08, 0.1, 0.17, 0.87));
	const Color top = color_of(p_style.get("top", Variant()), bg);
	const Color bottom = color_of(p_style.get("bottom", Variant()), p_style.has("top") ? top : bg);
	const int radius = p_style.get("radius", 10);
	const int border_width = p_style.get("border_width", p_style.has("border") ? 2 : 0);
	const Color border = color_of(p_style.get("border", Variant()), Color(0, 0, 0, 0));
	const int shadow = p_style.get("shadow", 0);
	const float padding = p_style.get("padding", 10);
	Ref<Image> img = draw_panel(radius, top, bottom, border, border_width, shadow);
	Ref<StyleBoxTexture> sb;
	sb.instantiate();
	sb->set_texture(ImageTexture::create_from_image(img));
	const int s = CLAMP(shadow, 0, 32);
	const int corner = MAX(CLAMP(radius, 0, 64), CLAMP(border_width, 0, 16)) + 1;
	sb->set_texture_margin_all(s + corner);
	sb->set_expand_margin_all(s); // The shadow is drawn outside the control's rect.
	sb->set_content_margin_all(padding);
	return sb;
}

Dictionary UZUUI::get_theme_defaults() {
	return defaults();
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
	theme->set_stylebox("normal", "Button", create_panel_style(button));
	Dictionary state = button.duplicate();
	state["top"] = color_of(button["hover"], Color::html("#46598f"));
	state["bottom"] = Color(state["top"]).darkened(0.15);
	theme->set_stylebox("hover", "Button", create_panel_style(state));
	state["top"] = color_of(button["pressed"], Color::html("#1a2238"));
	state["bottom"] = state["top"];
	state["shadow"] = 0;
	theme->set_stylebox("pressed", "Button", create_panel_style(state));
	state["top"] = Color(color_of(button["top"], Color::html("#34416a"))).darkened(0.4);
	state["bottom"] = state["top"];
	state["border"] = Color(accent, 0.3);
	theme->set_stylebox("disabled", "Button", create_panel_style(state));
	Ref<StyleBoxEmpty> none;
	none.instantiate();
	theme->set_stylebox("focus", "Button", none);
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
	bar_bg->set_corner_radius_all(bar["radius"]);
	theme->set_stylebox("background", "ProgressBar", bar_bg);
	Ref<StyleBoxFlat> fill = bar_bg->duplicate();
	fill->set_bg_color(color_of(bar.get("fill", Variant()), accent));
	theme->set_stylebox("fill", "ProgressBar", fill);
	Ref<StyleBoxFlat> selected = bar_bg->duplicate();
	selected->set_bg_color(Color(accent, 0.35));
	theme->set_stylebox("selected", "ItemList", selected);
	theme->set_stylebox("selected_focus", "ItemList", selected);
	theme->set_stylebox("cursor", "ItemList", none);
	theme->set_stylebox("cursor_unfocused", "ItemList", none);
	theme->set_stylebox("focus", "ItemList", none);
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
	theme->set_constant("separation", "HBoxContainer", 10);
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

Ref<Image> UZUUI::draw_frame(const Dictionary &p_style) {
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
			Color c = material_color(material, base, p.x, p.y, d, seed, tile, scale);
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
			}
			if (material == "glass" && d < 0.0f) {
				c = c.lerp(accent, 0.35f * Math::exp(d / (3.0f * scale))); // Glow just inside the edge.
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
					sa = 0.5f * t * t;
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

Ref<StyleBox> UZUUI::create_frame_style(const Dictionary &p_style) {
	const Ref<Image> img = draw_frame(p_style);
	Ref<StyleBoxTexture> sb;
	sb.instantiate();
	sb->set_texture(ImageTexture::create_from_image(img));
	const int scale = CLAMP(int(p_style.get("scale", 1)), 1, 2);
	const int margin = (img->get_width() - FRAME_TILE * scale) / 2;
	const int shadow = CLAMP(int(p_style.get("shadow", 6)), 0, 32) * scale;
	sb->set_texture_margin_all(margin);
	sb->set_expand_margin_all(shadow);
	// The middle repeats, so the texture keeps its scale.
	sb->set_h_axis_stretch_mode(StyleBoxTexture::AXIS_STRETCH_MODE_TILE_FIT);
	sb->set_v_axis_stretch_mode(StyleBoxTexture::AXIS_STRETCH_MODE_TILE_FIT);
	sb->set_content_margin_all(float(p_style.get("padding", 14)));
	if (String(p_style.get("shape", "")) == "pixel") {
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
		set(frame, "ornament", "brackets"), set(frame, "radius", 10), set(frame, "border_width", 3), set(frame, "shadow", 8);
		set(button, "material", "parchment"), set(button, "base", "#e8d6a8"), set(button, "edge", "#5a3d22"), set(button, "radius", 6);
		set(o, "text", "#f6e7c8"), set(o, "button_text", "#3a2614"), set(o, "accent", "#e6c36a"), set(o, "fill", "#d94a3a");
	} else if (p_world == "wafu") {
		set(frame, "material", "parchment"), set(frame, "base", "#efe2c4"), set(frame, "edge", "#3b2416"), set(frame, "accent", "#b8322a");
		set(frame, "ornament", "diamonds"), set(frame, "radius", 2), set(frame, "border_width", 3), set(frame, "shadow", 6);
		set(button, "material", "flat"), set(button, "base", "#b8322a"), set(button, "edge", "#3b1410"), set(button, "radius", 2);
		set(o, "text", "#2a1a10"), set(o, "button_text", "#fbf1dc"), set(o, "accent", "#b8322a"), set(o, "fill", "#b8322a");
	} else if (p_world == "sf") {
		set(frame, "material", "glass"), set(frame, "base", "#07141ee6"), set(frame, "edge", "#38e1ff"), set(frame, "accent", "#38e1ff");
		set(frame, "shape", "chamfer"), set(frame, "radius", 12), set(frame, "border_width", 2), set(frame, "shadow", 10);
		set(button, "material", "glass"), set(button, "base", "#0e2a3aee"), set(button, "accent", "#38e1ff"), set(button, "shape", "chamfer"), set(button, "radius", 8);
		set(o, "text", "#d8f6ff"), set(o, "button_text", "#d8f6ff"), set(o, "accent", "#38e1ff"), set(o, "fill", "#38e1ff");
	} else if (p_world == "horror") {
		set(frame, "material", "grime"), set(frame, "base", "#2a1414"), set(frame, "edge", "#090404"), set(frame, "accent", "#8a1010");
		set(frame, "ornament", "nails"), set(frame, "radius", 1), set(frame, "border_width", 3), set(frame, "shadow", 12);
		set(button, "material", "grime"), set(button, "base", "#3a1a1a"), set(button, "edge", "#0b0505"), set(button, "radius", 1);
		set(o, "text", "#e8d8d0"), set(o, "button_text", "#e8d8d0"), set(o, "accent", "#a01818"), set(o, "fill", "#8a1010");
	} else if (p_world == "persona") {
		set(frame, "material", "halftone"), set(frame, "base", "#e8212b"), set(frame, "edge", "#111111"), set(frame, "accent", "#ffffff");
		set(frame, "shape", "skew"), set(frame, "border_width", 4), set(frame, "shadow", 10);
		set(button, "material", "flat"), set(button, "base", "#111111"), set(button, "edge", "#ffffff"), set(button, "shape", "skew"), set(button, "border_width", 3), set(button, "shadow", 6);
		set(o, "text", "#ffffff"), set(o, "button_text", "#ffffff"), set(o, "accent", "#ffe14d"), set(o, "fill", "#ffe14d");
	} else if (p_world == "pixel") {
		set(frame, "material", "flat"), set(frame, "base", "#1b1f3a"), set(frame, "edge", "#f4f4f4"), set(frame, "accent", "#f4b41a");
		set(frame, "shape", "pixel"), set(frame, "border_width", 3), set(frame, "shadow", 4);
		set(button, "material", "flat"), set(button, "base", "#3b4a8c"), set(button, "edge", "#f4f4f4"), set(button, "shape", "pixel"), set(button, "border_width", 3), set(button, "shadow", 3);
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
	theme->set_stylebox("normal", "Button", create_frame_style(button));
	Dictionary state = button.duplicate();
	const Color bbase = color_of(button["base"], Color(0.2, 0.2, 0.3));
	state["base"] = bbase.lightened(0.18);
	theme->set_stylebox("hover", "Button", create_frame_style(state));
	state["base"] = bbase.darkened(0.25);
	state["shadow"] = 0;
	theme->set_stylebox("pressed", "Button", create_frame_style(state));
	state["base"] = Color(bbase.darkened(0.4), 0.7);
	theme->set_stylebox("disabled", "Button", create_frame_style(state));
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
	// Name tag: a small frame of the accent color.
	Dictionary tag = button.duplicate();
	tag["base"] = accent;
	tag["ornament"] = "none";
	tag["padding"] = 6;
	theme->set_type_variation("UZUNameTag", "PanelContainer");
	theme->set_stylebox("panel", "UZUNameTag", create_frame_style(tag));
	theme->set_type_variation("UZUNameTagLabel", "Label");
	theme->set_color("font_color", "UZUNameTagLabel", accent.get_luminance() > 0.55 ? Color(0.08, 0.06, 0.05) : Color(1, 1, 1));
	theme->set_type_variation("UZUTalk", "PanelContainer");
	theme->set_stylebox("panel", "UZUTalk", panel);
	// Item slot: a sunken square.
	Dictionary slot = frame.duplicate();
	slot["base"] = color_of(frame["base"], Color(0.1, 0.1, 0.1)).darkened(0.35);
	slot["ornament"] = "none";
	slot["shadow"] = 0;
	slot["padding"] = 6;
	theme->set_type_variation("UZUSlot", "PanelContainer");
	theme->set_stylebox("panel", "UZUSlot", create_frame_style(slot));
	// Ribbon heading: the accent, wider padding.
	Dictionary ribbon = tag.duplicate();
	ribbon["padding"] = 10;
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
		count->set_text(itos(p_count));
		count->set_horizontal_alignment(HORIZONTAL_ALIGNMENT_RIGHT);
		count->add_theme_font_size_override("font_size", 14);
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
	label->set_theme_type_variation("UZUNameTagLabel");
	label->set_text(p_text);
	label->set_horizontal_alignment(HORIZONTAL_ALIGNMENT_CENTER);
	label->add_theme_font_size_override("font_size", 22);
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
		// The top-level panels open with the world's motion.
		if (open_on_ready && Object::cast_to<PanelContainer>(c) && c->get_parent() == root && c->is_inside_tree()) {
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
	title->set_text(p_title);
	title->add_theme_font_size_override("font_size", 22);
	box->add_child(title);
	Label *text = memnew(Label);
	text->set_name("Text");
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
