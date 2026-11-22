/**************************************************************************/
/*  test_uzu_ui_juice.cpp                                                 */
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

TEST_FORCE_LINK(test_uzu_ui_juice)

#include "scene/gui/button.h"
#include "scene/gui/label.h"
#include "scene/gui/panel.h"
#include "scene/gui/progress_bar.h"
#include "scene/gui/uzu_ui_juice.h"

namespace TestUZUUIJuice {

static bool log_has(const String &p_event, const String &p_phase, const String &p_target = String()) {
	const Array log = UZUUIJuice::get_event_log();
	for (int i = 0; i < log.size(); i++) {
		const Dictionary e = log[i];
		if (String(e["event"]) == p_event && String(e["phase"]) == p_phase && (p_target.is_empty() || String(e["target"]) == p_target)) {
			return true;
		}
	}
	return false;
}

static String log_last_preset() {
	const Array log = UZUUIJuice::get_event_log();
	if (log.is_empty()) {
		return String();
	}
	return String(Dictionary(log[log.size() - 1])["preset"]);
}

TEST_CASE("[UZUUIJuice] The motion vocabulary: names and preset data") {
	const PackedStringArray names = UZUUIJuice::get_preset_names();
	CHECK(names.size() == 5);
	for (const char *name : { "anticipation", "overshoot", "ease_in", "bounce", "step" }) {
		CHECK(names.has(name));
		const Dictionary preset = UZUUIJuice::get_preset(name);
		CHECK(String(preset["name"]) == name);
		CHECK(double(preset["duration"]) > 0.0);
	}
	const Array levels = UZUUIJuice::get_preset("overshoot")["overshoot_by_level"];
	REQUIRE(levels.size() == 3);
	CHECK(double(levels[0]) < double(levels[1]));
	CHECK(double(levels[1]) < double(levels[2]));
	CHECK(int(UZUUIJuice::get_preset("step")["steps"]) == 4);
	CHECK(UZUUIJuice::get_preset("warp").is_empty());
}

TEST_CASE("[UZUUIJuice] Curves: exact ends, and each vocabulary word behaves like itself") {
	for (const String &preset : UZUUIJuice::get_preset_names()) {
		CHECK_MESSAGE(UZUUIJuice::motion_value(preset, 0.0) == doctest::Approx(0.0), preset);
		CHECK_MESSAGE(UZUUIJuice::motion_value(preset, 1.0) == doctest::Approx(1.0), preset);
	}
	// Overshoot passes the goal and comes back; strength scales the pass.
	CHECK(UZUUIJuice::motion_value("overshoot", 0.7) > 1.0);
	CHECK(UZUUIJuice::motion_value("overshoot", 0.7, 2.0) > UZUUIJuice::motion_value("overshoot", 0.7, 1.0));
	CHECK(UZUUIJuice::overshoot_value(0.7, 3) > UZUUIJuice::overshoot_value(0.7, 2));
	CHECK(UZUUIJuice::overshoot_value(0.7, 2) > UZUUIJuice::overshoot_value(0.7, 1));
	CHECK(UZUUIJuice::overshoot_value(0.7, 0) == doctest::Approx(UZUUIJuice::overshoot_value(0.7, 1)));
	CHECK(UZUUIJuice::overshoot_value(0.7, 9) == doctest::Approx(UZUUIJuice::overshoot_value(0.7, 3)));
	// Ease-in (the article's slow-in) brakes into the target: fast first,
	// monotone, and it never passes the goal.
	CHECK(UZUUIJuice::motion_value("ease_in", 0.5) == doctest::Approx(0.875));
	double prev = 0.0;
	for (int i = 1; i <= 10; i++) {
		const double v = UZUUIJuice::motion_value("ease_in", i / 10.0);
		CHECK(v >= prev);
		CHECK(v <= 1.0);
		prev = v;
	}
	// Anticipation dips below zero first, crosses zero at the end of its
	// phase, then runs the main move.
	CHECK(UZUUIJuice::motion_value("anticipation", 0.15) < 0.0);
	CHECK(UZUUIJuice::motion_value("anticipation", 0.15) == doctest::Approx(-0.18));
	CHECK(UZUUIJuice::motion_value("anticipation", 0.3) == doctest::Approx(0.0));
	CHECK(UZUUIJuice::motion_value("anticipation", 0.65) > 0.0);
	// Bounce touches the goal at the end of the first fall and settles.
	CHECK(UZUUIJuice::motion_value("bounce", 1.0 / 2.75) == doctest::Approx(1.0));
	CHECK(UZUUIJuice::motion_value("bounce", 0.5) > 0.75);
	CHECK(UZUUIJuice::motion_value("bounce", 0.5) < 1.0);
	// Step holds frames: nothing moves between the held values.
	CHECK(UZUUIJuice::motion_value("step", 0.3) == doctest::Approx(0.25));
	CHECK(UZUUIJuice::motion_value("step", 0.49) == doctest::Approx(0.25));
	CHECK(UZUUIJuice::motion_value("step", 0.99) == doctest::Approx(0.75));
}

TEST_CASE("[SceneTree][UZUUIJuice] Open: grows through the overshoot and restores the scale exactly") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	Panel *panel = memnew(Panel);
	panel->set_name("Dialog");
	panel->set_scale(Vector2(1.5, 1.5));
	panel->set_visible(false);
	UZUUIJuice::open_panel(panel, "overshoot", 0.2);
	CHECK(panel->is_visible());
	CHECK(UZUUIJuice::is_animating(panel));
	UZUUIJuice::apply_animations(0.14); // t = 0.7: past the goal.
	CHECK(panel->get_scale().x > 1.5);
	UZUUIJuice::apply_animations(0.1); // Past the end.
	CHECK_FALSE(UZUUIJuice::is_animating(panel));
	CHECK(panel->get_scale() == Vector2(1.5, 1.5));
	CHECK(panel->is_visible());
	CHECK(log_has("open", "start", "Dialog"));
	CHECK(log_has("open", "end", "Dialog"));
	memdelete(panel);
}

TEST_CASE("[SceneTree][UZUUIJuice] Close with anticipation: swells first, then hides, scale restored") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	Panel *panel = memnew(Panel);
	panel->set_name("Dialog");
	UZUUIJuice::close_panel(panel, "anticipation", 0.3);
	UZUUIJuice::apply_animations(0.045); // t = 0.15: the dip is -0.18, so the close is at 1.18x.
	CHECK(panel->get_scale().x > 1.1);
	CHECK(panel->is_visible());
	UZUUIJuice::apply_animations(0.3);
	CHECK_FALSE(panel->is_visible());
	CHECK(panel->get_scale() == Vector2(1, 1));
	CHECK(log_has("close", "start", "Dialog"));
	CHECK(log_has("close", "end", "Dialog"));
	memdelete(panel);
}

TEST_CASE("[SceneTree][UZUUIJuice] Hover pulse swells and lands exactly; cancel restores at once") {
	UZUUIJuice::cancel_all();
	Button *button = memnew(Button);
	button->set_scale(Vector2(2, 2));
	UZUUIJuice::hover_pulse(button, 1.0, 0.2);
	UZUUIJuice::apply_animations(0.1); // Half-way: the full +10%.
	CHECK(button->get_scale().x == doctest::Approx(2.2));
	UZUUIJuice::apply_animations(0.1);
	CHECK(button->get_scale() == Vector2(2, 2));
	UZUUIJuice::hover_pulse(button, 1.0, 0.2);
	UZUUIJuice::apply_animations(0.1);
	UZUUIJuice::cancel(button);
	CHECK(button->get_scale() == Vector2(2, 2));
	CHECK_FALSE(UZUUIJuice::is_animating(button));
	memdelete(button);
}

TEST_CASE("[SceneTree][UZUUIJuice] Count up: labels and ranges follow the curve and land exactly") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	Label *label = memnew(Label);
	label->set_name("Score");
	UZUUIJuice::count_up(label, 0, 100, 0.6, "ease_in");
	UZUUIJuice::apply_animations(0.3); // t = 0.5, ease-in is 0.875.
	CHECK(label->get_text() == "88");
	UZUUIJuice::apply_animations(0.3);
	CHECK(label->get_text() == "100");
	CHECK(log_has("count_up", "end", "Score"));
	ProgressBar *bar = memnew(ProgressBar);
	bar->set_min(0);
	bar->set_max(2000);
	bar->set_value(0);
	UZUUIJuice::count_up(bar, 0, 1000, 0.6, "overshoot");
	UZUUIJuice::apply_animations(0.42); // t = 0.7: the overshoot counts past the goal.
	CHECK(bar->get_value() > 1000);
	UZUUIJuice::apply_animations(0.3);
	CHECK(bar->get_value() == doctest::Approx(1000));
	memdelete(label);
	memdelete(bar);
}

TEST_CASE("[SceneTree][UZUUIJuice] Transition: the old screen fades out and hides, the new one fades in") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	Panel *from = memnew(Panel);
	from->set_name("Title");
	Panel *to = memnew(Panel);
	to->set_name("Game");
	to->set_visible(false);
	CHECK(UZUUIJuice::transition(from, to, 0.3, "ease_in"));
	CHECK(to->is_visible());
	UZUUIJuice::apply_animations(0.15);
	CHECK(from->get_modulate().a < 1.0f);
	CHECK(to->get_modulate().a > 0.0f);
	UZUUIJuice::apply_animations(0.2);
	CHECK_FALSE(from->is_visible());
	CHECK(from->get_modulate().a == doctest::Approx(1.0));
	CHECK(to->is_visible());
	CHECK(to->get_modulate().a == doctest::Approx(1.0));
	CHECK(log_has("transition", "start", "Title"));
	CHECK(log_has("transition", "end", "Title"));
	memdelete(from);
	memdelete(to);
}

TEST_CASE("[SceneTree][UZUUIJuice] World motion: the world's curve, duration and steps drive the animation") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	Panel *panel = memnew(Panel);
	CHECK(UZUUIJuice::apply_world_motion(panel, "persona"));
	CHECK(log_last_preset() == "overshoot"); // Persona snaps with a big overshoot.
	UZUUIJuice::apply_animations(0.2); // Persona's duration is 0.18.
	CHECK_FALSE(UZUUIJuice::is_animating(panel));
	CHECK(panel->get_scale() == Vector2(1, 1));
	CHECK(UZUUIJuice::apply_world_motion(panel, "pixel"));
	CHECK(log_last_preset() == "step");
	UZUUIJuice::apply_animations(0.05); // t = 0.25 of 0.2 s, held by the steps and the curve.
	CHECK(panel->get_scale().x == doctest::Approx(0.25));
	UZUUIJuice::apply_animations(0.2);
	CHECK_FALSE(UZUUIJuice::is_animating(panel));
	CHECK(UZUUIJuice::apply_world_motion(panel, "sf"));
	CHECK(log_last_preset() == "ease_in"); // SF brakes mechanically, no overshoot.
	UZUUIJuice::cancel_all();
	CHECK_FALSE(UZUUIJuice::apply_world_motion(panel, "steampunk"));
	memdelete(panel);
}

TEST_CASE("[UZUUIJuice] Motion presets: the five names of B-1317") {
	const PackedStringArray names = UZUUIJuice::get_motion_names();
	CHECK(names.size() == 5);
	CHECK(names.has("appear"));
	CHECK(names.has("disappear"));
	CHECK(names.has("hover"));
	CHECK(names.has("press"));
	CHECK(names.has("value_change"));
}

TEST_CASE("[SceneTree][UZUUIJuice] Appear (persona): fades and grows in, overshoots, lands exact") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	Panel *panel = memnew(Panel);
	panel->set_name("Quest");
	panel->set_visible(false);
	Dictionary options;
	options["world"] = "persona";
	CHECK(UZUUIJuice::play_motion(panel, "appear", options));
	CHECK(panel->is_visible());
	// t = 0: the start state -- shrunk to the floor and fully transparent.
	Dictionary state = UZUUIJuice::get_animation_state(panel);
	CHECK(bool(state["animating"]));
	CHECK(String(state["motion"]) == "appear");
	CHECK(String(state["curve"]) == "overshoot"); // Persona's snap.
	CHECK(double(state["duration"]) == doctest::Approx(0.18)); // Persona's fast duration.
	CHECK(double(state["progress"]) == doctest::Approx(0.0));
	CHECK(panel->get_scale().x == doctest::Approx(0.02));
	CHECK(panel->get_modulate().a == doctest::Approx(0.0));
	// Mid-way (t = 0.7): persona's big overshoot carries the scale past 1.
	CHECK(UZUUIJuice::seek_animation(panel, 0.18 * 0.7));
	CHECK(panel->get_scale().x > 1.0);
	CHECK(panel->get_modulate().a == doctest::Approx(1.0));
	state = UZUUIJuice::get_animation_state(panel);
	CHECK(double(state["value"]) > 1.0); // The curve itself is past the goal.
	// The end state is exact and the animation is gone.
	CHECK(UZUUIJuice::seek_animation(panel, 0.18));
	CHECK_FALSE(UZUUIJuice::is_animating(panel));
	CHECK(panel->get_scale() == Vector2(1, 1));
	CHECK(panel->get_modulate() == Color(1, 1, 1, 1));
	CHECK(panel->is_visible());
	CHECK(log_has("appear", "start", "Quest"));
	CHECK(log_has("appear", "end", "Quest"));
	memdelete(panel);
}

TEST_CASE("[SceneTree][UZUUIJuice] Appear (pixel): the steps hold the scale at frame values") {
	UZUUIJuice::cancel_all();
	Panel *panel = memnew(Panel);
	Dictionary options;
	options["world"] = "pixel";
	CHECK(UZUUIJuice::play_motion(panel, "appear", options));
	CHECK(UZUUIJuice::seek_animation(panel, 0.05)); // t = 0.25 of 0.2 s.
	CHECK(panel->get_scale().x == doctest::Approx(0.25));
	CHECK(panel->get_modulate().a == doctest::Approx(0.25f));
	CHECK(UZUUIJuice::seek_animation(panel, 0.09)); // t = 0.45: still the same held frame.
	CHECK(panel->get_scale().x == doctest::Approx(0.25));
	CHECK(UZUUIJuice::seek_animation(panel, 0.2));
	CHECK_FALSE(UZUUIJuice::is_animating(panel));
	CHECK(panel->get_scale() == Vector2(1, 1));
	memdelete(panel);
}

TEST_CASE("[SceneTree][UZUUIJuice] Disappear: fades and shrinks out, then hides, state restored") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	Panel *panel = memnew(Panel);
	panel->set_name("Quest");
	Dictionary options;
	options["world"] = "wafu";
	CHECK(UZUUIJuice::play_motion(panel, "disappear", options));
	CHECK(UZUUIJuice::seek_animation(panel, 0.35 * 0.5)); // Wafu's duration, half-way.
	CHECK(panel->is_visible());
	CHECK(panel->get_modulate().a < 1.0f);
	CHECK(panel->get_modulate().a > 0.0f);
	CHECK(panel->get_scale().x < 1.0);
	CHECK(UZUUIJuice::seek_animation(panel, 0.35));
	CHECK_FALSE(panel->is_visible());
	CHECK(panel->get_scale() == Vector2(1, 1));
	CHECK(panel->get_modulate() == Color(1, 1, 1, 1));
	CHECK(log_has("disappear", "end", "Quest"));
	memdelete(panel);
}

TEST_CASE("[SceneTree][UZUUIJuice] Press: dips below the base scale and returns exactly") {
	UZUUIJuice::cancel_all();
	Button *button = memnew(Button);
	button->set_scale(Vector2(2, 2));
	CHECK(UZUUIJuice::play_motion(button, "press"));
	CHECK(UZUUIJuice::seek_animation(button, 0.09)); // Half of the 0.18 s default.
	CHECK(button->get_scale().x == doctest::Approx(2.0 * 0.88));
	CHECK(UZUUIJuice::seek_animation(button, 0.18));
	CHECK(button->get_scale() == Vector2(2, 2));
	memdelete(button);
}

TEST_CASE("[SceneTree][UZUUIJuice] Hover through play_motion: swells and brightens, lands exact") {
	UZUUIJuice::cancel_all();
	Button *button = memnew(Button);
	CHECK(UZUUIJuice::play_motion(button, "hover"));
	CHECK(UZUUIJuice::seek_animation(button, 0.09));
	CHECK(button->get_scale().x == doctest::Approx(1.1));
	CHECK(button->get_modulate().r > 1.0f); // The brighten.
	CHECK(UZUUIJuice::seek_animation(button, 0.18));
	CHECK(button->get_scale() == Vector2(1, 1));
	CHECK(button->get_modulate() == Color(1, 1, 1, 1));
	memdelete(button);
}

TEST_CASE("[SceneTree][UZUUIJuice] Value change: a gauge interpolates from its current value") {
	UZUUIJuice::cancel_all();
	UZUUIJuice::clear_event_log();
	ProgressBar *bar = memnew(ProgressBar);
	bar->set_name("Hp");
	bar->set_min(0);
	bar->set_max(100);
	bar->set_value(20);
	Dictionary options;
	options["world"] = "wafu"; // ease_in, no overshoot: the value climbs monotonically.
	options["to"] = 80.0;
	CHECK(UZUUIJuice::play_motion(bar, "value_change", options));
	Dictionary state = UZUUIJuice::get_animation_state(bar);
	CHECK(double(state["duration"]) == doctest::Approx(0.7)); // Twice the world's 0.35.
	double previous = 20.0;
	for (int i = 1; i <= 4; i++) {
		CHECK(UZUUIJuice::seek_animation(bar, 0.7 * i / 5.0));
		CHECK(bar->get_value() > previous);
		previous = bar->get_value();
	}
	// t = 0.5 exactly: ease_in is 0.875, so 20 + 60 * 0.875.
	CHECK(UZUUIJuice::seek_animation(bar, 0.35));
	CHECK(bar->get_value() == doctest::Approx(72.5));
	CHECK(UZUUIJuice::seek_animation(bar, 0.7));
	CHECK(bar->get_value() == doctest::Approx(80.0));
	CHECK_FALSE(UZUUIJuice::is_animating(bar));
	CHECK(log_has("value_change", "end", "Hp"));
	memdelete(bar);
}

TEST_CASE("[SceneTree][UZUUIJuice] Value change: persona overshoots the target, then lands on it") {
	UZUUIJuice::cancel_all();
	ProgressBar *bar = memnew(ProgressBar);
	bar->set_min(0);
	bar->set_max(200);
	bar->set_value(0);
	Dictionary options;
	options["world"] = "persona";
	options["to"] = 100.0;
	CHECK(UZUUIJuice::play_motion(bar, "value_change", options));
	CHECK(UZUUIJuice::seek_animation(bar, 0.36 * 0.7)); // t = 0.7 of the doubled duration.
	CHECK(bar->get_value() > 100.0);
	CHECK(UZUUIJuice::seek_animation(bar, 0.36));
	CHECK(bar->get_value() == doctest::Approx(100.0));
	memdelete(bar);
}

TEST_CASE("[SceneTree][UZUUIJuice] Play motion refuses unknown names, worlds and curves") {
	UZUUIJuice::cancel_all();
	Panel *panel = memnew(Panel);
	CHECK_FALSE(UZUUIJuice::play_motion(panel, "explode"));
	Dictionary bad_world;
	bad_world["world"] = "steampunk";
	CHECK_FALSE(UZUUIJuice::play_motion(panel, "appear", bad_world));
	Dictionary bad_curve;
	bad_curve["curve"] = "wobble";
	CHECK_FALSE(UZUUIJuice::play_motion(panel, "appear", bad_curve));
	CHECK_FALSE(UZUUIJuice::play_motion(panel, "value_change")); // A panel holds no value.
	CHECK_FALSE(UZUUIJuice::is_animating(panel));
	CHECK_FALSE(UZUUIJuice::seek_animation(panel, 0.1));
	CHECK_FALSE(bool(UZUUIJuice::get_animation_state(panel)["animating"]));
	memdelete(panel);
}

} // namespace TestUZUUIJuice
