/**************************************************************************/
/*  uzu_ui_juice.h                                                        */
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

#include "core/object/object.h"
#include "core/variant/array.h"
#include "core/variant/dictionary.h"

class Control;

// UI motion (BACKLOG B-1304, Phase 13 rich UI): the movements that make a UI
// feel like a game -- panels that open with a bounce, dialogs that swell a
// breath before they close, numbers that count up -- behind static calls in
// the same style as UZUJuice (B-1101): a runtime node is created in the scene
// tree on first use and advances the animations, and every animation is a
// pure state value (elapsed / duration through a named curve), so the whole
// thing is unit-testable without a scene tree or real time.
//
// The motion vocabulary comes from gameanimation.info, "UI no komakai ugoki"
// (shared by the owner, 2026-11-19): anticipation (a small move opposite to
// the main one first), overshoot (past the goal, then back, with strength
// levels), ease-in (a mechanical, braking stop) and bounce. A fifth curve,
// "step", quantizes time for the pixel world of UZUUI (B-1307). Which curve a
// world uses is UZUUI::get_world_motion(); apply_world_motion() reads it, so
// the look and the motion of a world stay in one place.
class UZUUIJuice : public Object {
	GDCLASS(UZUUIJuice, Object);

protected:
	static void _bind_methods();

public:
	// The named motion curves: "anticipation", "overshoot", "ease_in",
	// "bounce", "step".
	static PackedStringArray get_preset_names();
	// One curve as data: {"name", "duration", "strength"} (overshoot also
	// carries "overshoot_by_level", the back constants of levels 1..3).
	// An empty dictionary for an unknown name.
	static Dictionary get_preset(const String &p_preset);
	// The curve itself: progress (0..1, may dip below 0 for anticipation or
	// rise above 1 for overshoot and bounce) at time p_t (0..1). p_strength
	// scales the anticipation dip and the overshoot (1 is the classic back
	// constant 1.70158). Pure math; both ends are exact (0 at 0, 1 at 1).
	static double motion_value(const String &p_preset, double p_t, double p_strength = 1.0);
	// The overshoot curve at a strength level (1 soft, 2 classic, 3 sharp --
	// the persona world's snap). Pure math.
	static double overshoot_value(double p_t, int p_level = 2);

	// Opens p_control (shows it and grows it from nothing through the
	// curve). The control's own scale and pivot are restored exactly when
	// the animation ends.
	static void open_panel(Control *p_control, const String &p_preset = "overshoot", double p_duration = 0.25, double p_strength = 1.0);
	// Closes p_control (shrinks it through the curve, then hides it). With
	// the default "anticipation" curve it first swells a little, exactly
	// the dialog close of the reference article.
	static void close_panel(Control *p_control, const String &p_preset = "anticipation", double p_duration = 0.22, double p_strength = 1.0);
	// A one-shot swell for hover and presses: up by 10% * p_strength and
	// back, ending at exactly the captured scale.
	static void hover_pulse(Control *p_control, double p_strength = 1.0, double p_duration = 0.18);
	// Counts a Label's text (or a Range's value) from p_from to p_to
	// through the curve; the final value is exact.
	static void count_up(Control *p_control, int64_t p_from, int64_t p_to, double p_duration = 0.6, const String &p_preset = "ease_in", double p_strength = 1.0);
	// The minimal screen transition: p_from fades out and hides while
	// p_to fades in, both through the curve. Returns false if either
	// control is missing.
	static bool transition(Control *p_from, Control *p_to, double p_duration = 0.3, const String &p_preset = "ease_in", double p_strength = 1.0);
	// Opens (or closes) p_control with the motion of a UZUUI world
	// (B-1307): the duration, overshoot and steps of
	// UZUUI::get_world_motion() become the curve. Returns false for an
	// unknown world.
	static bool apply_world_motion(Control *p_control, const String &p_world, bool p_open = true);

	// The motion presets (B-1317): what a control does, as opposed to the
	// curves above, which are how it moves. "appear" (fade in while
	// growing through the curve), "disappear" (fade and shrink out, then
	// hide), "hover" (a swell and a brighten, back to the exact start),
	// "press" (a dip below the base scale and back), "value_change" (a
	// Range's value -- a gauge, a bar -- or a Label's number, interpolated
	// from where it is to a target through the curve).
	static PackedStringArray get_motion_names();
	// Plays one motion preset on p_control, in one call. p_options:
	// "world" (a UZUUI world name: duration, curve, strength and steps
	// come from UZUUI::get_world_motion(), so persona is fast with a big
	// overshoot and pixel steps frame by frame; value_change takes twice
	// the world's duration), "curve" (a curve name, overriding the
	// world's), "duration", "strength", "steps", and "to" / "from" (the
	// value_change endpoints; "from" defaults to the current value, "to"
	// to a Range's max). Returns false for an unknown motion, world or
	// curve, and for value_change on a control holding no value.
	static bool play_motion(Control *p_control, const String &p_motion, const Dictionary &p_options = Dictionary());
	// The running animation of p_control as data, for probes and tests:
	// {"animating", "motion", "curve", "elapsed", "duration", "progress",
	// "value"} -- progress is the (possibly step-quantized) time 0..1 and
	// value the curve at it; the driven state itself (scale, modulate) is
	// read from the control. Just {"animating": false} when idle.
	static Dictionary get_animation_state(Control *p_control);
	// Sets the animation's clock to p_time seconds and applies that exact
	// state at once; at or past the duration the animation finishes, with
	// the exact end state. Returns false when p_control is not animating.
	static bool seek_animation(Control *p_control, double p_time);

	static bool is_animating(Control *p_control);
	static int get_active_animation_count();
	// Stops the control's animation, restoring exactly what was captured.
	static void cancel(Control *p_control);
	static void cancel_all();

	// The event log, for self-verifying play (B-303 style): one dictionary
	// per animation start and finish, {"event", "phase", "preset",
	// "target"}. Capped at the newest 256 entries.
	static Array get_event_log();
	static void clear_event_log();

	// Advances every running animation by p_dt seconds. Called by the
	// runtime node each frame; tests call it directly with fixed steps.
	static void apply_animations(double p_dt);
	// Creates the runtime node in the scene tree if there is none yet.
	// Safe to call without a running scene tree (it does nothing then).
	static void ensure_runtime();
};
