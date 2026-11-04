# -*- coding: utf-8 -*-
"""在渲染之前检查 JSON，把错误说成人话。

渲染器一遇到缺字段就是 KeyError，报错里看不到是哪一页。这里先过一遍，
把页码、页型、缺的字段一次说清楚。
"""
from __future__ import annotations

REQUIRED = {
    "cover": ["title"],
    "candidates": ["title", "candidates"],
    "compare": ["no", "title", "left", "right"],
    "rules": ["no", "title", "items"],
    "route": ["no", "title", "stops"],
    "spread": ["no", "title", "hero", "a", "b"],
    "day": ["no", "title", "rows"],
    "photos2": ["no", "title", "a", "b"],
    "traffic": ["no", "title", "columns", "shopsLabel", "shops"],
    "budget": ["no", "title", "items"],
}

ACCENTS = {"red", "green", "gold", "rust", "grey"}


def validate(trip: dict) -> None:
    problems = []

    if not isinstance(trip, dict):
        raise SystemExit("JSON 的最外层应该是一个对象，也就是用 { } 包起来。")

    if not trip.get("title"):
        problems.append("最外层缺 title，也就是这份册子叫什么。")

    pages = trip.get("pages")
    if not isinstance(pages, list) or not pages:
        raise SystemExit("缺 pages，或者 pages 是空的。一册书至少要有封面。")

    for i, page in enumerate(pages, 1):
        kind = page.get("type")
        if kind not in REQUIRED:
            problems.append(
                "第 %d 页：type 是 %r，不认识。可用的有：%s"
                % (i, kind, "、".join(sorted(REQUIRED)))
            )
            continue
        for field in REQUIRED[kind]:
            value = page.get(field)
            if value is None or value == "" or value == []:
                problems.append("第 %d 页（%s）缺 %s" % (i, kind, field))
        accent = page.get("accent")
        if accent and accent not in ACCENTS:
            problems.append(
                "第 %d 页（%s）的 accent 是 %r，只能是 %s"
                % (i, kind, accent, "、".join(sorted(ACCENTS)))
            )
        if kind == "day" and "rows" in page:
            for j, row in enumerate(page["rows"], 1):
                if not isinstance(row, list) or len(row) != 3:
                    problems.append(
                        "第 %d 页第 %d 条时间：应该是 [时间, 标题, 小字] 三项" % (i, j)
                    )

    if problems:
        raise SystemExit("这份 JSON 有 %d 处要改：\n  - %s" % (len(problems), "\n  - ".join(problems)))
