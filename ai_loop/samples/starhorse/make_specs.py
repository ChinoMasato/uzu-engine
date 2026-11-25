#!/usr/bin/env python3
"""Builds the JSON UI specs of the Star Horse sample (B-1329/B-1330).

The farm and entries screens are derived from the B-1326 showcase specs
(ai_loop/look_samples/b1315/project/specs/racing_*.json) so the kit's
data parts (DataTable / DetailPanel / Chip) and the B-1328 width-rule
fixes carry over unchanged. Since B-1330 the screens are art-led (the
B-1324/1325 pattern): the flat world panel and the cropped pano strip
are replaced by the full backdrop art (BgArt, oversized for the
parallax drift) plus a soft shade, and the kit panels sit in the art
like the reference's stable screen -- the data geometry itself only
moves, it does not change. The title screen is authored here directly.

Usage: python3 make_specs.py   (writes specs/title.json, specs/farm.json,
specs/entries.json)
Then build the scenes:
  python3 ../../uzu.py ui <project> --spec res://specs/title.json
  python3 ../../uzu.py ui <project> --spec res://specs/farm.json
  python3 ../../uzu.py ui <project> --spec res://specs/entries.json
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "look_samples", "b1315", "project", "specs")

# Gate draw of the sample race (中山11R 春風ステークス, 8 runners).
# name, sex/age, jockey, weight kg, odds, popularity -- mirrors data.gd.
FRAME_COLORS = ["#f5f5f5", "#26221f", "#e60012", "#0055c4",
                "#f7d117", "#009944", "#f08300", "#ee86a8"]
ENTRIES = [
    ("サンライズエース", "牡3", "佐々木蓮", 56, "8.4", 4),
    ("レッドヴァルキリー", "牝3", "山田悠真", 54, "9.7", 5),
    ("ホワイトオーシャン", "牡5", "小林直樹", 57, "3.1", 1),
    ("ブルームスター", "牝2", "鈴木健吾", 54, "26.4", 8),
    ("キングスパーク", "牡6", "中村恵太", 58, "18.9", 7),
    ("ミライノカゼ", "牝4", "高橋宗一郎", 55, "6.2", 3),
    ("ハヤテノツバサ", "牡3", "井上翔太", 56, "12.6", 6),
    ("シルバーグローリー", "牡4", "田村亮太", 57, "4.8", 2),
]


def find(node, name):
    if node.get("name") == name:
        return node
    for child in node.get("children", []):
        hit = find(child, name)
        if hit is not None:
            return hit
    return None


def load(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return json.load(f)


def dump(spec, name):
    out = os.path.join(HERE, "specs", name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print("wrote", out)


def art_layers(texture):
    """The art-led stage: full backdrop (oversized, so main.gd's drift
    never shows an edge) + the soft shade that grounds the panels."""
    return [
        {"type": "Image", "name": "BgArt", "texture": texture,
         "offset": [-46, -26], "size": [1244, 700], "stretch": "cover"},
        {"type": "Image", "name": "Shade", "texture": "res://art/shade.png",
         "offset": [0, 0], "size": [1152, 648], "stretch": "scale"},
    ]


def make_art_led(spec, texture, drop_names):
    children = spec["root"]["children"]
    spec["root"]["children"] = art_layers(texture) + [
        c for c in children if c.get("name") not in drop_names]
    return spec


def move(spec, name, offset=None, size=None, **extra):
    node = find(spec["root"], name)
    assert node is not None, name
    if offset is not None:
        node["offset"] = offset
    if size is not None:
        node["size"] = size
    node.update(extra)
    return node


def title():
    spec = {
        "scene": "res://screens/title.tscn",
        "theme": {"world": "racing", "font": "res://art/game_font_jp.ttf"},
        "root": {"type": "Screen", "children": art_layers(
            "res://art/title_art.jpg") + [
            {"type": "Label", "name": "Logo", "text": "スターホース牧場",
             "font_size": 92, "font_color": "#ffffff",
             "outline_color": "#201405", "outline_size": 16,
             "shadow_color": "#d9a441", "shadow_offset": [7, 7],
             "motion": "appear", "offset": [52, 48], "size": [940, 138]},
            {"type": "Label", "name": "Tagline",
             "text": "夕日の牧場で、夢を駆けろ。",
             "font_size": 25, "font_color": "#ffe9b0",
             "outline_color": "#201405", "outline_size": 6,
             "offset": [66, 200], "size": [640, 40]},
            {"type": "Button", "name": "StartBtn", "text": "ゲームスタート",
             "font_size": 28, "motion": "appear",
             "offset": [692, 380], "size": [404, 64]},
            {"type": "Button", "name": "RaceBtn", "text": "レースをみる",
             "font_size": 28, "motion": "appear",
             "offset": [692, 460], "size": [404, 64]},
            {"type": "Label", "name": "Credit", "text": "U.ZU Engine sample",
             "text_style": "caption", "align": "right",
             "anchor": "bottom_right", "offset": [28, 20],
             "size": [300, 24]},
        ]},
    }
    dump(spec, "title.json")


def farm():
    spec = load("racing_stable.json")
    spec["scene"] = "res://screens/farm.tscn"
    make_art_led(spec, "res://art/farm_art.jpg",
                 {"RacingStable", "Pano", "PanoShade"})
    move(spec, "Title", offset=[24, 16], size=[560, 58], font_size=42,
         font_color="#ffffff", outline_color="#14260f", outline_size=11,
         shadow_color="#d9a441", shadow_offset=[4, 4])
    find(spec["root"], "Title")["text"] = "スターホース牧場"
    move(spec, "MoneyChip", offset=[704, 22])
    move(spec, "DateChip", offset=[928, 22])
    move(spec, "Tabs", offset=[17, 84])
    move(spec, "TablePanel", offset=[12, 124], size=[755, 462])
    move(spec, "Table", offset=[17, 130], size=[743, 450])
    move(spec, "Detail", offset=[778, 130], size=[357, 450])
    move(spec, "Commands", offset=[17, 594], size=[1117, 50])
    dump(spec, "farm.json")


def entries():
    spec = load("racing_entries.json")
    spec["scene"] = "res://screens/entries.tscn"
    make_art_led(spec, "res://art/racecourse_art.jpg",
                 {"RacingEntries", "Pano", "PanoShade"})
    move(spec, "RaceHead", offset=[17, 30])
    move(spec, "RaceNo", offset=[32, 32])
    move(spec, "RaceName", offset=[147, 36])
    move(spec, "RaceClass", offset=[147, 72])
    move(spec, "RaceCourse", offset=[504, 50])
    move(spec, "RaceDist", offset=[662, 49])
    move(spec, "RaceWeather", offset=[821, 49])
    move(spec, "RaceGoing", offset=[929, 49])
    move(spec, "TablePanel", offset=[12, 108], size=[755, 452])
    move(spec, "Table", offset=[17, 114], size=[743, 440])
    move(spec, "Detail", offset=[778, 114], size=[357, 440])
    table = find(spec["root"], "Table")
    rows = []
    for i, (name, sexage, jockey, weight, odds, pop) in enumerate(ENTRIES):
        gate = i + 1
        rows.append([
            {"chip": FRAME_COLORS[i], "text": str(gate)},
            {"align": "center", "text": str(gate)},
            name,
            {"align": "center", "text": sexage},
            jockey,
            {"align": "center", "text": str(weight)},
            {"align": "right", "text": odds},
            {"align": "center", "text": str(pop)},
        ])
    table["rows"] = rows
    dump(spec, "entries.json")


if __name__ == "__main__":
    title()
    farm()
    entries()
