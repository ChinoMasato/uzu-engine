"""Procedural stereo WAV music generator for U.ZU Engine ai_loop."""

from array import array
import hashlib
import json
import math
import os
import random
import sys
import wave

SAMPLE_RATE = 44100
CHANNELS = 2
BEATS_PER_BAR = 4
CROSSFADE_MS = 50.0

NOTE_OFFSETS = {
    "C": 0,
    "B#": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "FB": 4,
    "F": 5,
    "E#": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
    "CB": 11,
}

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}

PRESETS = {
    "village": {
        "key": "C",
        "mode": "major",
        "bpm": 84,
        "bars": 8,
        "progression": [1, 6, 4, 5],
        "density": 0.55,
        "drum_style": "light",
        "pad": True,
        "bass_pattern": "half",
        "seed_offset": 101,
    },
    "battle": {
        "key": "D",
        "mode": "minor",
        "bpm": 132,
        "bars": 8,
        "progression": [1, 1, 6, 7],
        "density": 0.85,
        "drum_style": "full",
        "pad": False,
        "bass_pattern": "eighth",
        "seed_offset": 202,
    },
    "title": {
        "key": "G",
        "mode": "major",
        "bpm": 72,
        "bars": 8,
        "progression": [1, 4, 6, 5],
        "density": 0.60,
        "drum_style": "none",
        "pad": True,
        "bass_pattern": "half",
        "seed_offset": 303,
    },
}


def note_to_midi(name, default_octave=4) -> int:
    """Convert a note name (e.g. 'C', 'F#3', 'Bb4') to a MIDI note number."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Invalid note name: {name!r}")
    token = name.strip()
    split_idx = 1
    if len(token) > 1 and token[1] in ("#", "b", "B"):
        split_idx = 2
    pitch_part = token[:split_idx].upper()
    if pitch_part not in NOTE_OFFSETS:
        raise ValueError(f"Unknown pitch name: {name!r}")
    oct_part = token[split_idx:]
    octave = int(oct_part) if oct_part else default_octave
    return (octave + 1) * 12 + NOTE_OFFSETS[pitch_part]


def note_freq(midi) -> float:
    """Convert a MIDI note number to frequency in Hz (A4=69=440.0)."""
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def scale_notes(key_midi, mode) -> list[int]:
    """Return one octave of MIDI note numbers for the given key and mode."""
    if mode not in SCALES:
        raise ValueError(f"Unknown mode: {mode!r}")
    return [key_midi + offset for offset in SCALES[mode]]


def chord_notes(key_midi, mode, degree, octave=4, seventh=False) -> list[int]:
    """Build a triad (or 7th chord) on the 1-based scale degree in the given octave."""
    if mode not in SCALES:
        raise ValueError(f"Unknown mode: {mode!r}")
    intervals = SCALES[mode]
    n_deg = len(intervals)
    if degree < 1 or degree > n_deg:
        raise ValueError(f"Degree {degree} out of range 1..{n_deg}")
    base_root = (octave + 1) * 12 + (key_midi % 12)
    idx = degree - 1
    steps = (0, 2, 4, 6) if seventh else (0, 2, 4)
    notes = []
    for step in steps:
        total = idx + step
        oct_shift = total // n_deg
        deg_idx = total % n_deg
        notes.append(base_root + intervals[deg_idx] + oct_shift * 12)
    return notes


def _build_chords(preset, bars=None):
    eff_bars = bars if bars is not None else preset["bars"]
    key_midi = note_to_midi(preset["key"], default_octave=4)
    mode = preset["mode"]
    prog = preset["progression"]
    chords = []
    for bar in range(eff_bars):
        deg = prog[bar % len(prog)]
        chords.append({
            "bar": bar,
            "start_beat": float(bar * BEATS_PER_BAR),
            "dur_beat": float(BEATS_PER_BAR),
            "degree": deg,
            "midis": chord_notes(key_midi, mode, deg, octave=4),
        })
    return chords


def _normalize_chords(chords):
    norm = []
    for i, item in enumerate(chords):
        if isinstance(item, dict):
            midis = list(item.get("midis") or item.get("notes") or [])
            start_beat = float(item.get("start_beat", i * BEATS_PER_BAR))
            dur_beat = float(item.get("dur_beat", BEATS_PER_BAR))
            norm.append({
                "bar": item.get("bar", i),
                "start_beat": start_beat,
                "dur_beat": dur_beat,
                "midis": midis,
            })
        else:
            norm.append({
                "bar": i,
                "start_beat": float(i * BEATS_PER_BAR),
                "dur_beat": float(BEATS_PER_BAR),
                "midis": list(item),
            })
    return norm


def _snap_to_scale(midi, scale_pcs, low_midi=60, high_midi=84):
    best = None
    best_dist = 999
    for candidate in range(low_midi, high_midi + 1):
        if (candidate % 12) in scale_pcs:
            dist = abs(candidate - midi)
            if dist < best_dist:
                best_dist = dist
                best = candidate
    return best if best is not None else max(low_midi, min(high_midi, midi))


def generate_melody(rng, preset, chords) -> list[dict]:
    """Generate a deterministic, motif-driven melody restricted to the preset scale."""
    norm_chords = _normalize_chords(chords)
    if not norm_chords:
        return []
    key_midi = note_to_midi(preset["key"], default_octave=5)
    mode = preset["mode"]
    scale_pcs = set(n % 12 for n in scale_notes(key_midi, mode))
    density = max(0.0, min(1.0, float(preset.get("density", 0.6))))
    bpm = preset.get("bpm", 100)
    drum_style = preset.get("drum_style", "light")

    if drum_style == "full" or bpm >= 120:
        grid = [0.5, 0.25, 0.25, 0.5, 0.5, 0.5, 0.25, 0.25, 0.5, 0.5]
    elif drum_style == "none" or bpm <= 76:
        grid = [1.0, 1.0, 0.5, 0.5, 1.0]
    else:
        grid = [0.5, 0.5, 0.5, 0.5, 1.0, 0.5, 0.5]

    motif_steps = []
    pos = 0.0
    for step in grid:
        if pos >= BEATS_PER_BAR:
            break
        dur = min(step, BEATS_PER_BAR - pos)
        active = rng.random() < (0.35 + 0.60 * density)
        deg_offset = rng.choice([-2, -1, 0, 1, 2, 3, 4])
        motif_steps.append((pos, dur, active, deg_offset))
        pos += dur

    events = []
    n_bars = len(norm_chords)
    last_midi = key_midi + 12

    for bar_idx, ch in enumerate(norm_chords):
        bar_start = ch["start_beat"]
        bar_dur = ch["dur_beat"]
        chord_tones = [m + 12 for m in ch["midis"]] if ch["midis"] else [key_midi + 12]
        is_cadence = (bar_idx % 4 == 3) or (bar_idx == n_bars - 1)

        for step_idx, (rel_pos, dur, active, offset) in enumerate(motif_steps):
            if rel_pos >= bar_dur:
                break
            if is_cadence and rel_pos >= bar_dur - 1.0:
                if step_idx == len(motif_steps) - 1 or rel_pos >= bar_dur - 1.0:
                    target = _snap_to_scale(chord_tones[0], scale_pcs, 64, 84)
                    events.append({
                        "start_beat": bar_start + rel_pos,
                        "dur_beat": max(0.25, bar_dur - rel_pos),
                        "midi": target,
                        "velocity": round(0.72 + 0.1 * rng.random(), 3),
                    })
                    last_midi = target
                    break

            play = active
            if bar_idx % 2 == 1 and rng.random() < 0.25:
                play = rng.random() < density
            if not play:
                continue

            if rel_pos in (0.0, 2.0):
                base_tone = rng.choice(chord_tones)
            else:
                base_tone = last_midi + offset * 2
                if bar_idx % 2 == 1:
                    base_tone += rng.choice([-2, 0, 2])

            midi = _snap_to_scale(base_tone, scale_pcs, 62, 86)
            vel = 0.68 + 0.18 * rng.random()
            if rel_pos == 0.0:
                vel = min(0.95, vel + 0.08)

            ev_dur = min(dur * 0.92, bar_dur - rel_pos)
            events.append({
                "start_beat": bar_start + rel_pos,
                "dur_beat": round(max(0.125, ev_dur), 4),
                "midi": midi,
                "velocity": round(vel, 3),
            })
            last_midi = midi

    return events


def generate_bass(rng, preset, chords) -> list[dict]:
    """Generate a root/fifth bass line following the preset bass_pattern."""
    norm_chords = _normalize_chords(chords)
    pattern = preset.get("bass_pattern", "half")
    step_map = {"half": 2.0, "quarter": 1.0, "eighth": 0.5}
    step = step_map.get(pattern, 1.0)

    events = []
    for ch in norm_chords:
        bar_start = ch["start_beat"]
        bar_dur = ch["dur_beat"]
        chord_midis = ch["midis"]
        root = (chord_midis[0] % 12) + 36 if chord_midis else 36
        fifth = (chord_midis[2] % 12) + 36 if len(chord_midis) >= 3 else root + 7
        if fifth < root:
            fifth += 12

        t = 0.0
        idx = 0
        while t < bar_dur - 1e-6:
            if pattern == "eighth" and idx % 4 == 2 and rng.random() < 0.25:
                midi = root + 12
            elif idx % 2 == 0:
                midi = root
            else:
                midi = fifth if rng.random() < 0.7 else root

            dur = min(step * 0.88, bar_dur - t)
            vel = 0.78 if idx % 2 == 0 else (0.62 + 0.08 * rng.random())
            events.append({
                "start_beat": bar_start + t,
                "dur_beat": round(dur, 4),
                "midi": midi,
                "velocity": round(vel, 3),
            })
            t += step
            idx += 1

    return events


def generate_pad(preset, chords) -> list[dict]:
    """Generate sustained bar-level chord pad events when preset['pad'] is enabled."""
    if not preset.get("pad", True):
        return []
    norm_chords = _normalize_chords(chords)
    thick = preset.get("drum_style") == "none"
    vel = 0.42 if thick else 0.34
    events = []
    for ch in norm_chords:
        midis = list(ch["midis"])
        if thick and midis:
            midis = midis + [midis[0] + 12]
        events.append({
            "start_beat": ch["start_beat"],
            "dur_beat": ch["dur_beat"],
            "midis": midis,
            "velocity": vel,
        })
    return events


def generate_drums(rng, preset) -> list[dict]:
    """Generate drum events ('kick', 'snare', 'hat') according to drum_style."""
    style = preset.get("drum_style", "none")
    if style == "none":
        return []
    bars = preset.get("bars", 8)
    events = []

    for bar in range(bars):
        base = float(bar * BEATS_PER_BAR)
        if style == "light":
            for i in range(8):
                beat = i * 0.5
                if i % 2 == 1 or rng.random() < 0.55:
                    vel = 0.26 if i % 2 == 1 else 0.18
                    events.append({
                        "start_beat": base + beat,
                        "kind": "hat",
                        "velocity": round(vel + 0.04 * rng.random(), 3),
                    })
        elif style == "full":
            for beat in (0.0, 2.0):
                events.append({
                    "start_beat": base + beat,
                    "kind": "kick",
                    "velocity": 0.90,
                })
            if rng.random() < 0.55:
                events.append({
                    "start_beat": base + 2.5,
                    "kind": "kick",
                    "velocity": 0.72,
                })
            for beat in (1.0, 3.0):
                events.append({
                    "start_beat": base + beat,
                    "kind": "snare",
                    "velocity": 0.80,
                })
            if bar % 2 == 1 and rng.random() < 0.6:
                events.append({
                    "start_beat": base + 3.75,
                    "kind": "snare",
                    "velocity": 0.48,
                })
            for i in range(8):
                vel = 0.42 if i % 2 == 0 else 0.30
                events.append({
                    "start_beat": base + i * 0.5,
                    "kind": "hat",
                    "velocity": round(vel + 0.05 * rng.random(), 3),
                })

    events.sort(key=lambda e: e["start_beat"])
    return events


def _infer_beat_sec(events_by_track, seconds):
    bpm = events_by_track.get("bpm") if isinstance(events_by_track, dict) else None
    if bpm:
        return 60.0 / float(bpm)
    max_beat = 0.0
    for track_name in ("melody", "bass", "pad", "drums"):
        for ev in events_by_track.get(track_name, ()):
            end_b = float(ev.get("start_beat", 0.0)) + float(ev.get("dur_beat", 0.5))
            if end_b > max_beat:
                max_beat = end_b
    bars = max(1, int(math.ceil(max_beat / BEATS_PER_BAR)))
    return seconds / float(bars * BEATS_PER_BAR)


def _add_melody_note(buf, total_frames, sr, start_sec, dur_sec, freq, vel):
    atk = min(0.015, dur_sec * 0.2)
    dec = min(0.08, dur_sec * 0.3)
    rel = 0.06
    start_i = max(0, int(start_sec * sr))
    end_i = min(total_frames, int((start_sec + dur_sec + rel) * sr))
    if end_i <= start_i:
        return

    atk_n = max(1, int(atk * sr))
    dec_n = max(1, int(dec * sr))
    note_n = max(1, int(dur_sec * sr))
    rel_n = max(1, int(rel * sr))

    pan_l = 0.56
    pan_r = 0.48
    amp = vel * 0.22
    dp = freq / sr
    dp2 = (2.0 * freq) / sr
    sin = math.sin
    two_pi = 2.0 * math.pi
    p = 0.0
    p2 = 0.0

    for idx in range(start_i, end_i):
        k = idx - start_i
        if k < atk_n:
            env = k / atk_n
        elif k < atk_n + dec_n:
            env = 1.0 - 0.30 * ((k - atk_n) / dec_n)
        elif k < note_n:
            env = 0.70
        else:
            rem = k - note_n
            env = 0.70 * max(0.0, 1.0 - rem / rel_n)

        tri = 1.0 - 4.0 * abs((p % 1.0) - 0.5)
        sig = (tri * 0.82 + sin(two_pi * p2) * 0.18) * env * amp
        j = idx * 2
        buf[j] += sig * pan_l
        buf[j + 1] += sig * pan_r
        p += dp
        p2 += dp2


def _add_bass_note(buf, total_frames, sr, start_sec, dur_sec, freq, vel):
    atk = 0.008
    rel = 0.04
    start_i = max(0, int(start_sec * sr))
    end_i = min(total_frames, int((start_sec + dur_sec + rel) * sr))
    if end_i <= start_i:
        return

    atk_n = max(1, int(atk * sr))
    note_n = max(1, int(dur_sec * sr))
    rel_n = max(1, int(rel * sr))
    amp = vel * 0.28
    dp = freq / sr
    sin = math.sin
    two_pi = 2.0 * math.pi
    p = 0.0

    for idx in range(start_i, end_i):
        k = idx - start_i
        if k < atk_n:
            env = k / atk_n
        elif k < note_n:
            env = 1.0 - 0.35 * ((k - atk_n) / max(1, note_n - atk_n))
        else:
            env = 0.65 * max(0.0, 1.0 - (k - note_n) / rel_n)

        tri = 1.0 - 4.0 * abs((p % 1.0) - 0.5)
        sig = (sin(two_pi * p) * 0.68 + tri * 0.32) * env * amp
        j = idx * 2
        buf[j] += sig
        buf[j + 1] += sig
        p += dp


def _add_pad_chord(buf, total_frames, sr, start_sec, dur_sec, midis, vel):
    if not midis:
        return
    atk = min(0.22, dur_sec * 0.25)
    rel = 0.22
    start_i = max(0, int(start_sec * sr))
    end_i = min(total_frames, int((start_sec + dur_sec + rel) * sr))
    if end_i <= start_i:
        return

    atk_n = max(1, int(atk * sr))
    note_n = max(1, int(dur_sec * sr))
    rel_n = max(1, int(rel * sr))
    voice_amp = (vel * 0.20) / max(1.0, math.sqrt(len(midis)))
    sin = math.sin
    two_pi = 2.0 * math.pi
    n_voices = len(midis)

    for v_idx, midi in enumerate(midis):
        freq = note_freq(midi)
        spread = 0.0 if n_voices == 1 else (v_idx / (n_voices - 1) - 0.5) * 0.4
        pan_l = 0.5 - spread
        pan_r = 0.5 + spread
        dp1 = freq / sr
        dp2 = (freq * 2.0) / sr
        dp3 = (freq * 1.003) / sr
        p1 = 0.0
        p2 = 0.0
        p3 = 0.0

        for idx in range(start_i, end_i):
            k = idx - start_i
            if k < atk_n:
                env = k / atk_n
            elif k < note_n:
                env = 1.0
            else:
                env = max(0.0, 1.0 - (k - note_n) / rel_n)

            wave_val = (
                sin(two_pi * p1) * 0.65
                + sin(two_pi * p2) * 0.15
                + sin(two_pi * p3) * 0.20
            )
            sig = wave_val * env * voice_amp
            j = idx * 2
            buf[j] += sig * pan_l
            buf[j + 1] += sig * pan_r
            p1 += dp1
            p2 += dp2
            p3 += dp3


def _add_drum_hit(buf, total_frames, sr, start_sec, kind, vel, lcg_seed):
    start_i = max(0, int(start_sec * sr))
    if start_i >= total_frames:
        return

    sin = math.sin
    exp = math.exp
    two_pi = 2.0 * math.pi

    if kind == "kick":
        dur_n = int(0.16 * sr)
        end_i = min(total_frames, start_i + dur_n)
        amp = vel * 0.42
        phase = 0.0
        for idx in range(start_i, end_i):
            t = (idx - start_i) / sr
            freq = 46.0 + 105.0 * exp(-t * 36.0)
            env = exp(-t * 22.0)
            sig = sin(two_pi * phase) * env * amp
            j = idx * 2
            buf[j] += sig
            buf[j + 1] += sig
            phase += freq / sr
        return

    state = (lcg_seed * 2654435761 + 1013904223) & 0xFFFFFFFF
    prev_n = 0.0

    if kind == "snare":
        dur_n = int(0.15 * sr)
        end_i = min(total_frames, start_i + dur_n)
        amp = vel * 0.26
        phase = 0.0
        dp_body = 185.0 / sr
        for idx in range(start_i, end_i):
            t = (idx - start_i) / sr
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            noise = (state / 2147483648.0) - 1.0
            hp = noise - 0.65 * prev_n
            prev_n = noise
            body = sin(two_pi * phase) * exp(-t * 34.0) * 0.45
            sig = (hp * 0.55 * exp(-t * 24.0) + body) * amp
            j = idx * 2
            buf[j] += sig
            buf[j + 1] += sig
            phase += dp_body
    else:
        dur_n = int(0.055 * sr)
        end_i = min(total_frames, start_i + dur_n)
        amp = vel * 0.18
        for idx in range(start_i, end_i):
            t = (idx - start_i) / sr
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            noise = (state / 2147483648.0) - 1.0
            hp = noise - 0.92 * prev_n
            prev_n = noise
            sig = hp * exp(-t * 68.0) * amp
            j = idx * 2
            buf[j] += sig * 0.55
            buf[j + 1] += sig * 0.45


def render(events_by_track, seconds, sample_rate=44100, bpm=None) -> array:
    """Synthesize stereo float32 samples with a 50ms linear tail-to-head loop crossfade."""
    n_frames = max(1, int(round(seconds * sample_rate)))
    fade_frames = min(max(1, int(round((CROSSFADE_MS / 1000.0) * sample_rate))), n_frames // 4)
    total_frames = n_frames + fade_frames
    work = [0.0] * (total_frames * CHANNELS)

    beat_sec = (60.0 / float(bpm)) if bpm else _infer_beat_sec(events_by_track, seconds)

    for ev in events_by_track.get("pad", ()):
        s_sec = ev.get("start_sec", ev["start_beat"] * beat_sec)
        d_sec = ev.get("dur_sec", ev["dur_beat"] * beat_sec)
        midis = ev.get("midis") or ([ev["midi"]] if "midi" in ev else [])
        _add_pad_chord(work, total_frames, sample_rate, s_sec, d_sec, midis, ev.get("velocity", 0.35))

    for ev in events_by_track.get("bass", ()):
        s_sec = ev.get("start_sec", ev["start_beat"] * beat_sec)
        d_sec = ev.get("dur_sec", ev["dur_beat"] * beat_sec)
        _add_bass_note(work, total_frames, sample_rate, s_sec, d_sec, note_freq(ev["midi"]), ev.get("velocity", 0.7))

    for ev in events_by_track.get("melody", ()):
        s_sec = ev.get("start_sec", ev["start_beat"] * beat_sec)
        d_sec = ev.get("dur_sec", ev["dur_beat"] * beat_sec)
        _add_melody_note(work, total_frames, sample_rate, s_sec, d_sec, note_freq(ev["midi"]), ev.get("velocity", 0.7))

    for drum_idx, ev in enumerate(events_by_track.get("drums", ())):
        s_sec = ev.get("start_sec", ev["start_beat"] * beat_sec)
        _add_drum_hit(
            work,
            total_frames,
            sample_rate,
            s_sec,
            ev.get("kind", "hat"),
            ev.get("velocity", 0.5),
            drum_idx + 1,
        )

    out = array("f", work[: n_frames * CHANNELS])
    tail_offset = n_frames * CHANNELS
    for k in range(fade_frames):
        alpha = k / float(fade_frames)
        inv_alpha = 1.0 - alpha
        h_idx = k * CHANNELS
        t_idx = tail_offset + h_idx
        out[h_idx] = work[h_idx] * alpha + work[t_idx] * inv_alpha
        out[h_idx + 1] = work[h_idx + 1] * alpha + work[t_idx + 1] * inv_alpha

    peak = 0.0
    for s in out:
        a = -s if s < 0.0 else s
        if a > peak:
            peak = a
    if peak > 0.95:
        gain = 0.95 / peak
        for i in range(len(out)):
            out[i] *= gain

    return out


def measure_seam(samples, sample_rate) -> dict:
    """Measure loop seam continuity.

    Definitions:
        wrap_jump: Maximum over L/R channels of |head_first - tail_last|, comparing
            sample frame 0 against sample frame N-1.
        wrap_rms: Root-mean-square sample difference between the first W stereo frames
            (0..W-1, where W = min(256, N)) and the last W stereo frames (N-W..N-1)
            wrapped across the loop boundary.
    """
    n_frames = len(samples) // CHANNELS
    if n_frames == 0:
        return {"wrap_jump": 0.0, "wrap_rms": 0.0}

    jump_l = abs(samples[0] - samples[-2])
    jump_r = abs(samples[1] - samples[-1])
    wrap_jump = max(jump_l, jump_r)

    win = min(256, n_frames)
    span = win * CHANNELS
    tail_start = len(samples) - span
    sq_sum = 0.0
    for i in range(span):
        diff = samples[i] - samples[tail_start + i]
        sq_sum += diff * diff
    wrap_rms = math.sqrt(sq_sum / span)

    return {"wrap_jump": float(wrap_jump), "wrap_rms": float(wrap_rms)}


def _write_wav(out_path, samples, sample_rate=SAMPLE_RATE):
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    pcm = array("h", (max(-32767, min(32767, int(round(s * 32767.0)))) for s in samples))
    if sys.byteorder != "little":
        pcm.byteswap()
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def generate(preset_name, seed=7, bars=None, out_path=None) -> dict:
    """Generate a procedural looping WAV for preset_name and return a metadata report."""
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown preset: {preset_name!r}")
    base_preset = PRESETS[preset_name]
    eff_bars = int(bars) if bars is not None else int(base_preset["bars"])
    if eff_bars < 1:
        raise ValueError("bars must be >= 1")

    eff_preset = dict(base_preset)
    eff_preset["bars"] = eff_bars

    rng = random.Random(int(seed) + int(eff_preset["seed_offset"]))
    chords = _build_chords(eff_preset, bars=eff_bars)
    melody = generate_melody(rng, eff_preset, chords)
    bass = generate_bass(rng, eff_preset, chords)
    pad = generate_pad(eff_preset, chords)
    drums = generate_drums(rng, eff_preset)

    seconds = eff_bars * BEATS_PER_BAR * (60.0 / eff_preset["bpm"])
    samples = render(
        {"melody": melody, "bass": bass, "pad": pad, "drums": drums},
        seconds,
        sample_rate=SAMPLE_RATE,
        bpm=eff_preset["bpm"],
    )
    seam = measure_seam(samples, SAMPLE_RATE)

    if out_path is None:
        out_path = f"{preset_name}.wav"
    _write_wav(out_path, samples, SAMPLE_RATE)

    with open(out_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    return {
        "format": "uzu-music/1",
        "preset": preset_name,
        "key": eff_preset["key"],
        "mode": eff_preset["mode"],
        "bpm": eff_preset["bpm"],
        "bars": eff_bars,
        "seconds": seconds,
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "events": {
            "melody": len(melody),
            "bass": len(bass),
            "pad": len(pad),
            "drums": len(drums),
        },
        "seam": seam,
        "sha256": sha256,
        "file": out_path,
    }


def run_cli(out_dir, argv) -> dict:
    """Parse CLI arguments, generate requested WAV(s) in out_dir, and return report."""
    preset_name = "village"
    seed = 7
    bars = None
    gen_all = False

    i = 0
    args = list(argv)
    while i < len(args):
        arg = args[i]
        if arg == "--all":
            gen_all = True
            i += 1
        elif arg == "--preset":
            if i + 1 >= len(args):
                raise ValueError("--preset requires a value")
            preset_name = args[i + 1]
            i += 2
        elif arg.startswith("--preset="):
            preset_name = arg.split("=", 1)[1]
            i += 1
        elif arg == "--seed":
            if i + 1 >= len(args):
                raise ValueError("--seed requires a value")
            seed = int(args[i + 1])
            i += 2
        elif arg.startswith("--seed="):
            seed = int(arg.split("=", 1)[1])
            i += 1
        elif arg == "--bars":
            if i + 1 >= len(args):
                raise ValueError("--bars requires a value")
            bars = int(args[i + 1])
            i += 2
        elif arg.startswith("--bars="):
            bars = int(arg.split("=", 1)[1])
            i += 1
        else:
            raise ValueError(f"Unknown argument: {arg!r}")

    os.makedirs(out_dir, exist_ok=True)
    if gen_all:
        results = []
        for name in PRESETS:
            out_path = os.path.join(out_dir, f"{name}.wav")
            results.append(generate(name, seed=seed, bars=bars, out_path=out_path))
        return {"results": results}

    out_path = os.path.join(out_dir, f"{preset_name}.wav")
    return generate(preset_name, seed=seed, bars=bars, out_path=out_path)


if __name__ == "__main__":
    report = run_cli(".", sys.argv[1:])
    print(json.dumps(report, indent=2))
