#!/usr/bin/env python3
"""Builds the two JSON UI specs of the Star Horse sample (B-1329).

The farm and entries screens are derived from the B-1326 showcase specs
(ai_loop/look_samples/b1315/project/specs/racing_*.json) so the kit's
data parts (DataTable / DetailPanel / Chip) and the B-1328 width-rule
fixes carry over unchanged. Differences: the farm spec's heading becomes
the game logo, and the entries table is cut from 12 runners to the
sample's own 8 (gate order and odds live in data.gd; keep them in sync).

Usage: python3 make_specs.py   (writes specs/farm.json, specs/entries.json)
Then build the scenes:
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


def farm():
    spec = load("racing_stable.json")
    spec["scene"] = "res://screens/farm.tscn"
    title = find(spec["root"], "Title")
    title["text"] = "スターホース牧場"
    title["font_size"] = 30
    title["size"] = [430, 44]
    dump(spec, "farm.json")


def entries():
    spec = load("racing_entries.json")
    spec["scene"] = "res://screens/entries.tscn"
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
    farm()
    entries()
