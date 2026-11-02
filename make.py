#!/usr/bin/env python3
"""Render a trip JSON into an A5 print booklet (HTML -> PDF via a Chromium print).

Usage:
    python make.py trips/chaoshan.json
    python make.py trips/chaoshan.json --png      # one contact sheet of all pages
    python make.py trips/chaoshan.json --html-only

The build writes:
    out/book.html     intermediate, absolute file:// paths
    out/<output>.pdf  the booklet
    out/preview.png   only with --png
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DESIGN = ROOT / "design"
OUT = ROOT / "out"

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_browser() -> str:
    env = os.environ.get("TRIPBOOK_BROWSER")
    if env and Path(env).exists():
        return env
    for p in BROWSERS:
        if Path(p).exists():
            return p
    found = shutil.which("chrome") or shutil.which("chromium") or shutil.which("msedge")
    if found:
        return found
    sys.exit(
        "找不到 Chromium 系浏览器。装 Edge 或 Chrome，或用环境变量指定：\n"
        "  TRIPBOOK_BROWSER=/path/to/chrome python make.py trips/x.json"
    )


# ---------------------------------------------------------------- markup
def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def asset(path: str, base: Path) -> str:
    """Resolve an asset against the trip file, then the repo root.

    Returns a path relative to the repo root, so book.html stays portable.
    """
    p = Path(path)
    if not p.is_absolute():
        for root in (base, ROOT):
            cand = root / p
            if cand.exists():
                p = cand
                break
        else:
            p = ROOT / p
    p = p.resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_uri()


def head(no: str, title: str) -> str:
    return f'<div class="head"><span class="no">{esc(no)}</span><h2>{esc(title)}</h2></div>'


def rows(items) -> str:
    out = ['<ul class="rows">']
    for when, what, note in items:
        n = f"<span>{esc(note)}</span>" if note else ""
        out.append(
            f'<li><span class="when">{esc(when)}</span>'
            f'<span class="what"><b>{esc(what)}</b>{n}</span></li>'
        )
    out.append("</ul>")
    return "".join(out)


def rules(items) -> str:
    out = ['<ol class="rules">']
    for main, note in items:
        n = f"<em>{esc(note)}</em>" if note else ""
        out.append(f"<li><p>{esc(main)}{n}</p></li>")
    out.append("</ol>")
    return "".join(out)


def facts_strip(items, split=False) -> str:
    if not items:
        return ""
    cells = "".join(
        f"<div><b>{esc(big)}</b><span>{esc(small)}</span></div>" for big, small in items
    )
    cls = "facts-row split" if split else "facts-row"
    return f'<div class="{cls}">{cells}</div>'


def warn_block(box, split=False) -> str:
    if not box:
        return ""
    lines = box if isinstance(box, list) else [box]
    inner = "".join(f"<p>{esc(x)}</p>" for x in lines)
    cls = "warn split" if split else "warn"
    return f'<div class="{cls}">{inner}</div>'


def sheet(n: int, body: str) -> str:
    return f'<section class="sheet">{body}<span class="pnum">{n:02d}</span></section>'


# ---------------------------------------------------------------- page types
def page_cover(p, base, n):
    facts = "".join(
        f"<div><b>{esc(a)}</b>{esc(b)}</div>" for a, b in p.get("facts", [])
    )
    return f"""<section class="sheet cover">
  <img class="bleed" src="{asset(p['image'], base)}" alt="">
  <div class="veil"></div>
  <div class="plate">
    <p class="place">{esc(p.get('place', ''))}</p>
    <h1>{esc(p['title'])}</h1>
    <p class="sub">{esc(p.get('sub', ''))}</p>
    <div class="facts">{facts}</div>
  </div>
</section>"""


def page_overview(p, base, n):
    body = head(p["no"], p["title"])
    if p.get("lede"):
        body += f'<p class="lede">{esc(p["lede"])}</p>'
    body += rows(p.get("rows", []))
    if p.get("note"):
        body += f'<p class="note">{esc(p["note"])}</p>'
    body += facts_strip(p.get("facts"), split=True)
    return sheet(n, body)


def page_rules(p, base, n):
    body = head(p["no"], p["title"])
    if p.get("lede"):
        body += f'<p class="lede">{esc(p["lede"])}</p>'
    body += rules(p.get("items", []))
    if p.get("quote"):
        body += f'<blockquote class="quote">{esc(p["quote"])}</blockquote>'
    if p.get("note"):
        body += f'<p class="note">{esc(p["note"])}</p>'
    body += facts_strip(p.get("facts"), split=True)
    return sheet(n, body)


def page_route(p, base, n):
    stops = "".join(
        f"<div><b>{esc(name)}</b><span>{detail}</span></div>"
        for name, detail in p.get("stops", [])
    )
    body = head(p["no"], p["title"]) + f'<div class="route">{stops}</div>'
    body += rows(p.get("rows", []))
    body += facts_strip(p.get("facts"), split=True)
    return sheet(n, body)


def page_spread(p, base, n):
    body = head(p["no"], p["title"]) + f"""
    <figure>
      <img class="ph hero-ph" src="{asset(p['hero'], base)}" alt="">
      <figcaption>{esc(p.get('heroCaption', ''))}</figcaption>
    </figure>
    <div class="duo">
      <figure><img class="ph" src="{asset(p['a'], base)}" alt="">
        <figcaption>{esc(p.get('aCaption', ''))}</figcaption></figure>
      <figure><img class="ph" src="{asset(p['b'], base)}" alt="">
        <figcaption>{esc(p.get('bCaption', ''))}</figcaption></figure>
    </div>"""
    return sheet(n, body)


def page_day(p, base, n):
    body = head(p["no"], p["title"]) + rows(p.get("rows", []))
    if p.get("note"):
        body += f'<p class="note">{esc(p["note"])}</p>'
    body += warn_block(p.get("box"), split=True)
    return sheet(n, body)


def page_food(p, base, n):
    body = head(p["no"], p["title"]) + f"""
    <figure>
      <img class="ph" src="{asset(p['hero'], base)}" alt="" style="height:72mm">
      <figcaption>{esc(p.get('heroCaption', ''))}</figcaption>
    </figure>
    <figure style="margin-top:5mm">
      <img class="ph" src="{asset(p['second'], base)}" alt="" style="height:46mm">
      <figcaption>{esc(p.get('secondCaption', ''))}</figcaption>
    </figure>"""
    body += warn_block(p.get("box"))
    return sheet(n, body)


def page_budget(p, base, n):
    items = p.get("items", [])
    top = max((v for _, v in items), default=1)
    bars = "".join(
        f'<li><span class="k">{esc(k)}</span>'
        f'<span class="track"><span class="fill" style="width:{v / top * 100:.0f}%"></span></span>'
        f'<span class="v">¥{v:,}</span></li>'
        for k, v in items
    )
    body = head(p["no"], p["title"]) + f"""
    <ul class="bars">{bars}</ul>
    <div class="total"><span>{esc(p.get('totalNote', ''))}</span><b>{esc(p['total'])}</b></div>"""
    if p.get("note"):
        body += f'<p class="note">{esc(p["note"])}</p>'
    body += facts_strip(p.get("facts"), split=True)
    return sheet(n, body)


def page_checklist(p, base, n):
    body = head(p["no"], p["title"]) + rules(p.get("items", []))
    body += warn_block(p.get("box"), split=True)
    return sheet(n, body)


def page_back(p, base, n):
    return f"""<section class="sheet cover">
  <img class="bleed" src="{asset(p['image'], base)}" alt="">
  <div class="veil"></div>
  <div class="plate">
    <h1 style="font-size:22pt">{esc(p['title'])}</h1>
    <p class="sub">{esc(p.get('sub', ''))}</p>
    <p class="place" style="margin-top:6mm">{esc(p.get('credit', ''))}</p>
  </div>
</section>"""


PAGES = {
    "cover": page_cover,
    "overview": page_overview,
    "rules": page_rules,
    "route": page_route,
    "spread": page_spread,
    "day": page_day,
    "food": page_food,
    "budget": page_budget,
    "checklist": page_checklist,
    "back": page_back,
}


# ---------------------------------------------------------------- build
def build_html(trip: dict, base: Path, preview: bool) -> str:
    pages = []
    for i, p in enumerate(trip["pages"]):
        fn = PAGES.get(p["type"])
        if not fn:
            sys.exit(f"未知页面类型：{p['type']}")
        pages.append(fn(p, base, i + 1))

    extra = '<link rel="stylesheet" href="design/preview.css">' if preview else ""
    html_class = ' class="preview"' if preview else ""
    return f"""<!doctype html>
<html lang="zh-CN"{html_class}>
<head>
<meta charset="utf-8">
<title>{esc(trip['title'])}</title>
<meta name="description" content="{esc(trip.get('meta_description', trip['title']))}">
<link rel="stylesheet" href="design/doc.css">
{extra}
</head>
<body>
{''.join(pages)}
</body>
</html>"""


def run_browser(browser: str, args: list[str]) -> None:
    subprocess.run([browser, "--headless=new", "--disable-gpu", *args],
                   check=False, capture_output=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="把行程 JSON 渲染成 A5 PDF")
    ap.add_argument("trip", help="行程 JSON 路径")
    ap.add_argument("--png", action="store_true", help="另外输出一张全部页面的缩略图")
    ap.add_argument("--html-only", action="store_true", help="只生成 HTML，不打印 PDF")
    args = ap.parse_args()

    trip_path = Path(args.trip).resolve()
    base = trip_path.parent
    trip = json.loads(trip_path.read_text(encoding="utf-8"))

    OUT.mkdir(exist_ok=True)
    book = ROOT / "book.html"
    book.write_text(build_html(trip, base, False), encoding="utf-8")
    print(f"html   {book}")

    if args.html_only:
        return

    browser = find_browser()
    pdf = OUT / trip.get("output", f"{trip['title']}.pdf")
    if pdf.exists():
        pdf.unlink()
    run_browser(browser, ["--no-pdf-header-footer", "--virtual-time-budget=4000", f"--print-to-pdf={pdf}", book.as_uri()])

    if not pdf.exists():
        sys.exit("打印失败。确认浏览器版本支持 --print-to-pdf。")
    data = pdf.read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    box = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", data)
    print(f"pdf    {pdf}")
    print(f"pages  {pages}")
    if box:
        w, h = float(box.group(3)), float(box.group(4))
        print(f"size   {w:.0f} x {h:.0f} pt ({w / 72 * 25.4:.0f} x {h / 72 * 25.4:.0f} mm)")

    if args.png:
        png = OUT / "preview.png"
        preview = ROOT / "preview.html"
        preview.write_text(build_html(trip, base, True), encoding="utf-8")
        run_browser(browser, [
            "--hide-scrollbars", "--window-size=1000,860", "--virtual-time-budget=4000",
            f"--screenshot={png}", preview.as_uri(),
        ])
        print(f"png    {png}")


if __name__ == "__main__":
    main()



