#!/usr/bin/env python3
"""把一份行程 JSON 渲染成一册卡片式 PDF。

    python make.py trips/chaoshan.json
    python make.py trips/chaoshan.json --scale 3 --png

输出：
    out/<标题>.pdf      整册
    out/preview.png     全部页面的缩略图（--png）
    out/pages/*.png     单页（--png）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from design import tokens as T          # noqa: E402
from design.canvas import Canvas        # noqa: E402

W, H, M = 1080, 1440, 64


# ------------------------------------------------------------------ 公用
def head(c: Canvas, no: str, title: str, accent: str) -> float:
    c.rect(M, M, 108, 76, accent, r=38)
    c.text(M + 54, M + 38, no, size=34, fill="#FFFFFF", bold=True, anchor="mm")
    c.text(M + 132, M + 38, title, size=38, fill=accent, bold=True, anchor="lm")
    c.line([(M, M + 100), (W - M, M + 100)], T.LINE, 2)
    return M + 116


def stat_box(c, x, y, w, value, label, accent=T.RED, h=150):
    c.rect(x, y, w, h, T.CREAM, r=22, outline=T.LINE, lw=2)
    c.text(x + w / 2, y + h * 0.42, value, size=36, fill=accent, bold=True, anchor="mm")
    c.text(x + w / 2, y + h * 0.75, label, size=23, fill=T.MUTED, anchor="mm")


def stat_row(c, y, stats, accent=T.RED, h=104):
    bw = (W - 2 * M - (len(stats) - 1) * 16) / len(stats)
    for i, (value, label) in enumerate(stats):
        x = M + i * (bw + 16)
        c.rect(x, y, bw, h, T.CREAM, r=20, outline=T.LINE, lw=2)
        c.text(x + bw / 2, y + h * 0.40, value, size=32, fill=accent, bold=True, anchor="mm")
        c.text(x + bw / 2, y + h * 0.76, label, size=21, fill=T.MUTED, anchor="mm")


def numbered(c, x, y, n, accent):
    c.circle(x + 14, y + 16, 14, accent)
    c.text(x + 14, y + 16, str(n), size=19, fill="#FFFFFF", bold=True, anchor="mm")


def timeline(c, y, rows, accent, gap):
    for i, (when, what, note) in enumerate(rows):
        cy = y + i * gap
        if i < len(rows) - 1:
            c.line([(M + 9, cy + 42), (M + 9, cy + gap + 8)], T.LINE, 3)
        c.circle(M + 9, cy + 23, 9, accent)
        c.text(M + 44, cy - 2, when, size=28, fill=T.GOLD, bold=True)
        c.text(M + 168, cy - 4, what, size=34, bold=True)
        if note:
            c.para(M + 168, cy + 46, note, 26, W - M - (M + 168), 34, fill=T.MUTED)


def base(c: Canvas, n: int):
    """页眉右上角的页码，避开底部的整块色块。"""
    c.text(W - M, M + 38, "%02d" % n, size=22, fill=T.MUTED, anchor="rm")


# ------------------------------------------------------------------ 页面
def page_cover(c, p, n):
    c.photo(p["image"], 0, 0, W, 470, r=0)

    veil = Image.new("RGBA", (int(W * c.s), int(470 * c.s)), (0, 0, 0, 0))
    vd = ImageDraw.Draw(veil)
    for yy in range(int(470 * c.s)):
        a = int(66 + 120 * (yy / (470 * c.s)) ** 1.5)
        vd.line([(0, yy), (W * c.s, yy)], fill=(26, 11, 7, a))
    left = Image.new("L", (1, 1), 0)
    lw = Image.new("L", (int(W * c.s), 1), 0)
    ld = ImageDraw.Draw(lw)
    for xx in range(int(W * c.s)):
        ld.point((xx, 0), fill=int(135 * max(0.0, 1 - xx / (W * c.s)) ** 2))
    dark = Image.new("RGBA", veil.size, (26, 11, 7, 255))
    dark.putalpha(lw.resize(veil.size, Image.BICUBIC))
    veil = Image.alpha_composite(veil, dark)

    base_img = c.img.crop((0, 0, int(W * c.s), int(470 * c.s))).convert("RGBA")
    c.img.paste(Image.alpha_composite(base_img, veil).convert("RGB"), (0, 0))
    c.d = ImageDraw.Draw(c.img)

    c.rect(0, 470, W, 6, T.GOLD)
    c.text(M, 216, p.get("place", ""), size=28, fill="#F6DCCB", bold=True)
    c.text(M, 250, p["title"], size=94, fill="#FFFFFF", bold=True)
    c.text(M, 366, p.get("sub", ""), size=36, fill="#F7E3D8")
    c.text(M, 416, p.get("dates", ""), size=28, fill="#FFFFFF", bold=True)

    facts = p.get("facts", [])
    py = 522
    c.panel(M, py, W - 2 * M, 50 + len(facts) * 62)
    yy = py + 32
    for key, value in facts:
        c.text(M + 40, yy, key, size=28, fill=T.GOLD, bold=True)
        c.text(M + 150, yy - 4, value, size=30)
        yy += 62

    sy = py + 60 + len(facts) * 62
    stats = p.get("stats", [])
    if stats:
        bw = (W - 2 * M - (len(stats) - 1) * 18) / len(stats)
        for i, (value, label) in enumerate(stats):
            stat_box(c, M + i * (bw + 18), sy, bw, value, label, h=142)

    my = sy + 192
    c.text(M, my, p.get("moodLabel", "这趟的气质"), size=26, fill=T.GOLD, bold=True)
    c.para(M, my + 44, p.get("mood", ""), 34, W - 2 * M, 54, bold=True)

    foot = p.get("foot", "")
    if foot:
        c.rect(0, H - 132, W, 132, T.RED)
        c.text(M, H - 86, foot["left"], size=30, fill="#FFFFFF", bold=True)
        if foot.get("right"):
            c.text(W - M, H - 86, foot["right"], size=25, fill="#F2D6C6", anchor="rm")


def page_rules(c, p, n):
    accent = T.ACCENTS[p.get("accent", "red")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        y = c.para(M, y + 2, p["lead"], 38, W - 2 * M, 52, bold=True)

    items = p.get("items", [])
    yy = y + 44
    target = 1000 if p.get("stats") else 1060
    gap = int(min(150, max(96, (target - yy) / max(len(items), 1))))
    for i, (main, note) in enumerate(items, 1):
        numbered(c, M + 34, yy, i, accent)
        c.text(M + 88, yy + 2, main, size=30, bold=True)
        if note:
            c.text(M + 88, yy + 48, note, size=25, fill=T.MUTED)
        yy += gap

    foot = p.get("foot")
    if foot:
        c.para(M, yy + 24, foot, 26, W - 2 * M, 40, fill=T.MUTED)
    if p.get("stats"):
        stat_row(c, 1180, p["stats"], accent=accent)
    base(c, n)


def page_compare(c, p, n):
    accent = T.ACCENTS[p.get("accent", "red")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        y = c.para(M, y + 2, p["lead"], 38, W - 2 * M, 52, bold=True)

    left, right = p["left"], p["right"]
    pw = (W - 2 * M - 24) / 2
    ph = 132 + max(len(left["items"]), len(right["items"])) * 62
    c.panel(M, 300, pw, ph, fill=T.RED_SOFT, outline=T.LINE)
    c.panel(M + pw + 24, 300, pw, ph, fill=T.GREEN_SOFT, outline=T.LINE)
    c.text(M + 32, 326, left["title"], size=28, fill=T.RED, bold=True)
    c.text(M + pw + 56, 326, right["title"], size=28, fill=T.GREEN, bold=True)
    for i, item in enumerate(left["items"]):
        yy = 384 + i * 62
        c.rect(M + 34, yy + 12, 12, 12, T.RED)
        c.para(M + 62, yy, item, 28, pw - 90, 36)
    for i, item in enumerate(right["items"]):
        yy = 384 + i * 62
        c.rect(M + pw + 58, yy + 12, 12, 12, T.GREEN)
        c.para(M + pw + 86, yy, item, 28, pw - 90, 36)

    yy = 300 + ph + 40
    if p.get("strip"):
        c.rect(M, yy, W - 2 * M, 108, T.RED, r=22)
        c.text(M + 32, yy + 16, p["strip"]["label"], size=26, fill="#F2D6C6", bold=True)
        c.para(M + 32, yy + 54, p["strip"]["text"], 28, W - 2 * M - 64, 38, fill="#FFFFFF")
        yy += 148

    if p.get("quote"):
        qh = 130
        c.panel(M, yy, W - 2 * M, qh, fill=T.CREAM, outline=T.GOLD)
        c.text(M + 32, yy + 22, p["quote"]["label"], size=26, fill=T.GOLD, bold=True)
        c.para(M + 32, yy + 66, p["quote"]["text"], 30, W - 2 * M - 64, 48, fill=T.INK)
        yy += qh + 30

    if p.get("foot"):
        c.panel(M, yy, W - 2 * M, 150)
        c.text(M + 32, yy + 22, p["foot"]["label"], size=26, fill=T.RED, bold=True)
        c.para(M + 32, yy + 64, p["foot"]["text"], 27, W - 2 * M - 64, 44, fill=T.MUTED)
    base(c, n)


def page_route(c, p, n):
    accent = T.ACCENTS[p.get("accent", "red")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        c.text(M, y + 2, p["lead"], size=34, bold=True)

    c.panel(M, 300, W - 2 * M, 372)
    stops = p["stops"]
    xs = [M + 108 + i * 240 for i in range(len(stops))]
    ly = 300 + 186
    c.line([(xs[0], ly), (xs[-1], ly)], T.LINE, 4)
    for i, stop in enumerate(stops):
        cx = xs[i]
        colour = T.GREEN if i == len(stops) - 1 else accent
        c.circle(cx, ly, 26, colour)
        c.text(cx, ly, str(i + 1), size=26, fill="#FFFFFF", bold=True, anchor="mm")
        c.text(cx, ly + 56, stop["name"], size=36, bold=True, anchor="ma")
        c.text(cx, ly + 104, stop["note"], size=22, fill=T.MUTED, anchor="ma")
        if i < len(stops) - 1:
            c.text((xs[i] + xs[i + 1]) / 2, ly - 54, stop["leg"], size=22,
                   fill=T.GOLD, bold=True, anchor="mm")

    if p.get("stats"):
        stat_row(c, 692, p["stats"], accent=accent)

    yy = 826
    for panel in p.get("panels", []):
        c.panel(M, yy, W - 2 * M, 236)
        c.text(M + 32, yy + 24, panel["title"], size=26, fill=T.GOLD, bold=True)
        c.para(M + 32, yy + 70, panel["text"], 27, W - 2 * M - 64, 46, fill=T.MUTED)
        yy += 262
    base(c, n)


def page_spread(c, p, n):
    accent = T.ACCENTS[p.get("accent", "gold")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        c.text(M, y + 2, p["lead"], size=34, bold=True)

    c.photo(p["hero"], 70, 288, 940, 380, r=24)
    c.text(72, 684, p.get("heroCaption", ""), size=25, bold=True)
    c.photo(p["a"], 70, 748, 458, 270)
    c.photo(p["b"], 552, 748, 458, 270)
    c.text(72, 1030, p.get("aCaption", ""), size=24, fill=T.MUTED)
    c.text(554, 1030, p.get("bCaption", ""), size=24, fill=T.MUTED)

    if p.get("tip"):
        c.rect(M, 1100, W - 2 * M, 106, T.SOFT, r=20)
        c.para(M + 26, 1122, p["tip"], 25, W - 2 * M - 52, 38, fill=T.RED, bold=True)
    base(c, n)


def page_day(c, p, n):
    accent = T.ACCENTS[p.get("accent", "red")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        c.text(M, y + 2, p["lead"], size=36, bold=True)

    rows = p.get("rows", [])
    gap = min(126, int((1150 - 280) / max(len(rows), 1)))
    timeline(c, 280, rows, accent, gap)

    if p.get("badge"):
        c.panel(M, 1180, W - 2 * M, 96, fill=T.CREAM)
        c.text(M + 32, 1228, p["badge"], size=26, fill=T.MUTED, bold=True, anchor="lm")
    if p.get("task"):
        c.rect(M, 1300, W - 2 * M, 84, T.SOFT, r=20)
        c.para(M + 28, 1322, p["task"], 26, W - 2 * M - 56, 40, fill=T.RED, bold=True)
    base(c, n)


def page_photos2(c, p, n):
    accent = T.ACCENTS[p.get("accent", "gold")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        c.text(M, y + 2, p["lead"], size=36, bold=True)

    c.photo(p["a"], 70, 288, 458, 330, r=24)
    c.photo(p["b"], 552, 288, 458, 330, r=24)
    c.text(72, 634, p["aCaption"], size=25, bold=True)
    c.text(554, 634, p["bCaption"], size=25, bold=True)

    yy = 692
    if p.get("panel"):
        c.panel(M, yy, W - 2 * M, 216)
        c.text(M + 32, yy + 24, p["panel"]["title"], size=26, fill=T.GOLD, bold=True)
        c.para(M + 32, yy + 72, p["panel"]["text"], 26, W - 2 * M - 64, 44, fill=T.MUTED)
        yy += 232

    if p.get("box"):
        c.rect(M, yy + 16, W - 2 * M, 214, T.RUST, r=22)
        c.text(M + 32, yy + 38, p["box"]["label"], size=26, fill="#F0DCC0", bold=True)
        c.para(M + 32, yy + 82, p["box"]["text"], 28, W - 2 * M - 64, 46, fill="#FFFFFF",
               bold=True)
    base(c, n)


def page_traffic(c, p, n):
    accent = T.ACCENTS[p.get("accent", "gold")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        c.text(M, y + 2, p["lead"], size=36, bold=True)

    cols = p["columns"]
    cw = (W - 2 * M - 2 * 20) / 3
    colours = {"green": (T.GREEN, T.GREEN_SOFT), "gold": (T.GOLD, T.CREAM),
               "red": (T.RED, T.RED_SOFT)}
    for i, col in enumerate(cols):
        fg, bg = colours[col["colour"]]
        x = M + i * (cw + 20)
        c.panel(x, 296, cw, 450, fill=bg)
        c.text(x + 26, 320, col["title"], size=26, fill=fg, bold=True)
        for j, item in enumerate(col["items"]):
            c.para(x + 26, 380 + j * 60, item, 26, cw - 52, 34)

    if p.get("shops"):
        c.panel(M, 782, W - 2 * M, 150 + len(p["shops"]) * 58)
        c.text(M + 32, 806, p["shopsLabel"], size=26, fill=T.GOLD, bold=True)
        yy = 856
        for name, note in p["shops"]:
            c.text(M + 32, yy, name, size=27, bold=True)
            c.text(M + 316, yy + 2, note, size=23, fill=T.MUTED)
            yy += 58

    if p.get("box"):
        c.rect(M, 1166, W - 2 * M, 200, T.RUST, r=22)
        c.text(M + 32, 1188, p["box"]["label"], size=26, fill="#F0DCC0", bold=True)
        c.para(M + 32, 1232, p["box"]["text"], 28, W - 2 * M - 64, 46, fill="#FFFFFF",
               bold=True)
    base(c, n)


def page_budget(c, p, n):
    accent = T.ACCENTS[p.get("accent", "grey")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        c.text(M, y + 2, p["lead"], size=36, bold=True)

    items = p["items"]
    top = max(v for _, v in items) or 1
    c.panel(M, 290, W - 2 * M, 400)
    barx, barw = M + 300, 470
    for i, (key, value) in enumerate(items):
        yy = 326 + i * 58
        c.text(M + 40, yy, key, size=25, fill=T.MUTED, bold=True)
        c.rect(barx, yy + 6, barw, 26, T.SOFT, r=13)
        c.rect(barx, yy + 6, barw * value / top, 26, T.GOLD, r=13)
        c.text(W - M - 40, yy + 2, "¥%d" % value, size=25, bold=True, anchor="ra")

    yy = 726
    if p.get("todos"):
        c.panel(M, yy, W - 2 * M, 330)
        c.text(M + 32, yy + 24, p["todos"]["title"], size=26, fill=T.RED, bold=True)
        ty = yy + 78
        for i, item in enumerate(p["todos"]["items"], 1):
            numbered(c, M + 34, ty, i, T.RED)
            c.para(M + 78, ty + 2, item, 27, W - 2 * M - 130, 36)
            ty += 62
        yy += 352

    if p.get("emergency"):
        rows = p["emergency"]
        c.rect(M, yy, W - 2 * M, 120 + len(rows) * 44, T.RED, r=24)
        c.text(M + 36, yy + 24, p["emergencyLabel"], size=26, fill="#F2D6C6", bold=True)
        ry = yy + 72
        for key, value in rows:
            c.text(M + 36, ry, key, size=25, fill="#FFFFFF", bold=True)
            c.text(M + 330, ry + 2, value, size=23, fill="#F2D6C6")
            ry += 44
    base(c, n)


def page_candidates(c, p, n):
    """不知道去哪时的一页：两到三个目的地并排比。"""
    accent = T.ACCENTS[p.get("accent", "rust")]
    y = head(c, p["no"], p["title"], accent)
    if p.get("lead"):
        y = c.para(M, y + 2, p["lead"], 34, W - 2 * M, 48, bold=True)

    items = p["candidates"]
    count = len(items)
    gap = 20
    cw = (W - 2 * M - (count - 1) * gap) / count

    top = max(y + 24, 268)
    bottom = 1080 if p.get("strip") else 1290
    labels = [("fit", "为什么适合"), ("pace", "节奏"), ("food", "吃什么"), ("watch", "要当心")]

    for i, item in enumerate(items):
        x = M + i * (cw + gap)
        ink = T.ACCENTS[item.get("accent", "red")]
        c.rect(x, top, cw, bottom - top, T.CARD, r=24)
        c.rect(x + 24, top + 34, 44, 4, ink)
        c.text(x + 24, top + 54, item["name"], size=32, bold=True)
        c.text(x + 24, top + 98, item.get("sub", ""), size=21, fill=T.MUTED)

        yy = top + 150
        for key, label in labels:
            if not item.get(key):
                continue
            c.text(x + 24, yy, label, size=20, fill=T.GOLD, bold=True)
            yy = c.para(x + 24, yy + 28, item[key], 23, cw - 48, 32, fill=T.MUTED) + 18

        if item.get("verdict"):
            c.rect(x + 24, bottom - 84, cw - 48, 56, ink, r=28)
            c.text(x + cw / 2, bottom - 56, item["verdict"], size=24, fill="#FFFFFF",
                   bold=True, anchor="mm")

    if p.get("strip"):
        c.rect(M, 1120, W - 2 * M, 150, T.SOFT, r=20)
        c.para(M + 26, 1148, p["strip"], 24, W - 2 * M - 52, 36, fill=T.RED, bold=True)
    base(c, n)


PAGES = {
    "cover": page_cover,
    "rules": page_rules,
    "compare": page_compare,
    "candidates": page_candidates,
    "route": page_route,
    "spread": page_spread,
    "day": page_day,
    "photos2": page_photos2,
    "traffic": page_traffic,
    "budget": page_budget,
}


def render(trip: dict, base: Path, scale: int, outdir: Path) -> list[Path]:
    paths = []
    pages_dir = outdir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(trip["pages"], 1):
        fn = PAGES.get(p["type"])
        if not fn:
            sys.exit("未知页面类型：%s" % p["type"])
        c = Canvas(W, H, scale=scale)
        fn(c, p, i)
        out = pages_dir / ("%02d_%s.png" % (i, p["type"]))
        c.save(str(out))
        paths.append(out)
        print("  %02d  %s" % (i, p["type"]))
    return paths


def to_pdf(paths: list[Path], out: Path, scale: int):
    imgs = [Image.open(p).convert("RGB") for p in paths]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], resolution=150.0 * scale)
    print("pdf   %s" % out)


def contact_sheet(paths: list[Path], out: Path, cols: int = 4):
    thumbs = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        im.thumbnail((320, 427), Image.LANCZOS)
        thumbs.append(im)
    rows = (len(thumbs) + cols - 1) // cols
    gap = 10
    sheet = Image.new("RGB", (cols * (320 + gap) + gap, rows * (427 + gap) + gap), "#E7DFD0")
    for i, im in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(im, (gap + c * (320 + gap), gap + r * (427 + gap)))
    sheet.save(out, "PNG")
    print("png   %s" % out)


def asset(path: str, base: Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        for root in (base, ROOT):
            if (root / p).exists():
                return str(root / p)
        return str(ROOT / p)
    return str(p)


def main():
    ap = argparse.ArgumentParser(description="把行程 JSON 渲染成卡片式 PDF")
    ap.add_argument("trip")
    ap.add_argument("--scale", type=int, default=2, help="渲染倍数，默认 2（2160x2880）")
    ap.add_argument("--png", action="store_true", help="同时输出单页 PNG 和缩略图")
    args = ap.parse_args()

    trip_path = Path(args.trip).resolve()
    trip = json.loads(trip_path.read_text(encoding="utf-8-sig"))
    base = trip_path.parent

    for p in trip["pages"]:
        for key in ("image", "hero", "a", "b", "second"):
            if key in p and isinstance(p[key], str):
                p[key] = asset(p[key], base)

    outdir = ROOT / "out"
    outdir.mkdir(exist_ok=True)
    print("render %d pages @%dx" % (len(trip["pages"]), args.scale))
    paths = render(trip, base, args.scale, outdir)
    pdf = outdir / trip.get("output", trip["title"] + ".pdf")
    to_pdf(paths, pdf, args.scale)
    if args.png:
        contact_sheet(paths, outdir / "preview.png")
    print("done  %s" % pdf)


if __name__ == "__main__":
    main()




