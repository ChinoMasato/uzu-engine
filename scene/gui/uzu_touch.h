/**************************************************************************/
/*  uzu_touch.h                                                           */
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

#pragma once

#include "scene/gui/control.h"

// Touch parts of the UZUUI kit (BACKLOG B-1315): a virtual stick that a game
// drops on touch layouts instead of hand-drawing its own (the audit found
// the sample's home-made touch UI bypassing the world themes). The stick is
// drawn from theme colours under the "UZUTouchStick" type variation, so a
// world theme restyles it like every other part. It reports an analog value
// and nothing else -- feeding engine input actions from the value is the
// game's job, so the same part serves any control scheme.
//
// The pointer surface is public (press_at / drag_to / release) as well as
// wired to gui_input: an AI player or a test can drive the stick exactly
// the way a finger does, in local coordinates.
class UZUTouchStick : public Control {
	GDCLASS(UZUTouchStick, Control);

	Vector2 value;
	float deadzone = 0.22f;
	int drag = -1; // -1 idle, -2 mouse, >= 0 a touch index.
	Vector2 knob_offset;

	void _apply_pointer(const Vector2 &p_local);
	void _release();

protected:
	static void _bind_methods();
	void _notification(int p_what);
	virtual void gui_input(const Ref<InputEvent> &p_event) override;

public:
	UZUTouchStick();

	void set_value(const Vector2 &p_value);
	Vector2 get_value() const;
	void set_deadzone(float p_deadzone);
	float get_deadzone() const;
	// Where the knob sits, in px from the centre (the drawn state, for
	// tests and AI verification).
	Vector2 get_knob_offset() const;

	void press_at(const Vector2 &p_local);
	void drag_to(const Vector2 &p_local);
	void release();
};
