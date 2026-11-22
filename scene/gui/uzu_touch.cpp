/**************************************************************************/
/*  uzu_touch.cpp                                                         */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,   */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,       */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "uzu_touch.h"

#include "core/input/input.h"
#include "core/input/input_enums.h"
#include "core/input/input_event.h"
#include "core/object/class_db.h"

namespace {

// The stick's geometry comes from its rect: the disc fills the shorter
// side, the knob travels to 6 px inside the rim and is 0.4 of the disc.
float stick_radius(const Size2 &p_size) {
	return MIN(p_size.x, p_size.y) * 0.5f;
}

} // namespace

UZUTouchStick::UZUTouchStick() {
	set_custom_minimum_size(Size2(168, 168));
	set_mouse_filter(MOUSE_FILTER_STOP);
	set_process(true); // The mouse-release-outside guard in _notification.
}

void UZUTouchStick::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_value", "value"), &UZUTouchStick::set_value);
	ClassDB::bind_method(D_METHOD("get_value"), &UZUTouchStick::get_value);
	ClassDB::bind_method(D_METHOD("set_deadzone", "deadzone"), &UZUTouchStick::set_deadzone);
	ClassDB::bind_method(D_METHOD("get_deadzone"), &UZUTouchStick::get_deadzone);
	ClassDB::bind_method(D_METHOD("get_knob_offset"), &UZUTouchStick::get_knob_offset);
	ClassDB::bind_method(D_METHOD("press_at", "local_position"), &UZUTouchStick::press_at);
	ClassDB::bind_method(D_METHOD("drag_to", "local_position"), &UZUTouchStick::drag_to);
	ClassDB::bind_method(D_METHOD("release"), &UZUTouchStick::release);
	ADD_PROPERTY(PropertyInfo(Variant::VECTOR2, "value"), "set_value", "get_value");
	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "deadzone", PROPERTY_HINT_RANGE, "0,0.9,0.01"), "set_deadzone", "get_deadzone");
	ADD_SIGNAL(MethodInfo("value_changed", PropertyInfo(Variant::VECTOR2, "value")));
	ADD_SIGNAL(MethodInfo("released"));
}

void UZUTouchStick::set_value(const Vector2 &p_value) {
	value = p_value.length() > 1.0f ? p_value.normalized() : p_value;
	knob_offset = value * MAX(stick_radius(get_size()) - 6.0f, 0.0f);
	queue_redraw();
}

Vector2 UZUTouchStick::get_value() const {
	return value;
}

void UZUTouchStick::set_deadzone(float p_deadzone) {
	deadzone = CLAMP(p_deadzone, 0.0f, 0.9f);
}

float UZUTouchStick::get_deadzone() const {
	return deadzone;
}

Vector2 UZUTouchStick::get_knob_offset() const {
	return knob_offset;
}

void UZUTouchStick::_apply_pointer(const Vector2 &p_local) {
	const float travel = MAX(stick_radius(get_size()) - 6.0f, 1.0f);
	Vector2 off = p_local - get_size() * 0.5f;
	if (off.length() > travel) {
		off = off.normalized() * travel;
	}
	knob_offset = off;
	const Vector2 v = off / travel;
	if (v.length() < deadzone) {
		value = Vector2();
	} else {
		const float m = CLAMP((v.length() - deadzone) / (1.0f - deadzone), 0.0f, 1.0f);
		value = v.normalized() * m;
	}
	emit_signal("value_changed", value);
	queue_redraw();
}

void UZUTouchStick::_release() {
	if (drag == -1 && value == Vector2() && knob_offset == Vector2()) {
		return;
	}
	drag = -1;
	value = Vector2();
	knob_offset = Vector2();
	emit_signal("value_changed", value);
	emit_signal("released");
	queue_redraw();
}

void UZUTouchStick::press_at(const Vector2 &p_local) {
	if (drag == -1) {
		drag = -2;
	}
	_apply_pointer(p_local);
}

void UZUTouchStick::drag_to(const Vector2 &p_local) {
	if (drag != -1) {
		_apply_pointer(p_local);
	}
}

void UZUTouchStick::release() {
	_release();
}

void UZUTouchStick::gui_input(const Ref<InputEvent> &p_event) {
	InputEventScreenTouch *touch = Object::cast_to<InputEventScreenTouch>(p_event.ptr());
	if (touch) {
		if (touch->is_pressed() && drag == -1) {
			drag = touch->get_index();
			_apply_pointer(touch->get_position());
			accept_event();
		} else if (!touch->is_pressed() && touch->get_index() == drag) {
			_release();
			accept_event();
		}
		return;
	}
	InputEventScreenDrag *drag_event = Object::cast_to<InputEventScreenDrag>(p_event.ptr());
	if (drag_event) {
		if (drag_event->get_index() == drag) {
			_apply_pointer(drag_event->get_position());
			accept_event();
		}
		return;
	}
	InputEventMouseButton *button = Object::cast_to<InputEventMouseButton>(p_event.ptr());
	if (button && button->get_button_index() == MouseButton::LEFT) {
		if (button->is_pressed() && drag == -1) {
			drag = -2;
			_apply_pointer(button->get_position());
			accept_event();
		} else if (!button->is_pressed() && drag == -2) {
			_release();
			accept_event();
		}
		return;
	}
	InputEventMouseMotion *motion = Object::cast_to<InputEventMouseMotion>(p_event.ptr());
	if (motion && drag == -2) {
		_apply_pointer(motion->get_position());
		accept_event();
	}
}

void UZUTouchStick::_notification(int p_what) {
	switch (p_what) {
		case NOTIFICATION_PROCESS: {
			// A mouse release outside the control never reaches gui_input;
			// do not leave the stick held.
			if (drag == -2 && !Input::get_singleton()->is_mouse_button_pressed(MouseButton::LEFT)) {
				_release();
			}
		} break;
		case NOTIFICATION_EXIT_TREE: {
			_release();
		} break;
		case NOTIFICATION_DRAW: {
			const Size2 size = get_size();
			const Vector2 center = size * 0.5f;
			const float radius = stick_radius(size);
			if (radius <= 2.0f) {
				break;
			}
			const Color base = get_theme_color("base_color", "UZUTouchStick");
			const Color ring = get_theme_color("ring_color", "UZUTouchStick");
			const Color knob = get_theme_color("knob_color", "UZUTouchStick");
			const Color knob_ring = get_theme_color("knob_ring_color", "UZUTouchStick");
			draw_circle(center, radius, base);
			draw_arc(center, radius - 1.5f, 0.0f, Math::TAU, 64, ring, 3.0f, true);
			const Vector2 knob_center = center + knob_offset;
			const float knob_radius = radius * 0.4f;
			draw_circle(knob_center, knob_radius, knob);
			draw_arc(knob_center, knob_radius - 1.0f, 0.0f, Math::TAU, 48, knob_ring, 2.0f, true);
		} break;
	}
}
