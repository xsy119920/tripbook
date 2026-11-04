#!/usr/bin/env python3
"""按关键词找一张图，裁成版式要的尺寸，存进 photos/。

    set PEXELS_API_KEY=...
    python fetch.py "大理 洱海" --out dali-erhai1 --size 940x380

    set UNSPLASH_ACCESS_KEY=...
    python fetch.py "大理 洱海" --out dali-erhai1 --size 940x380 --provider unsplash

不给 --out 就存成 photos/<关键词>.jpg。
默认 provider 是 pexels，可用 --provider unsplash 切。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent
PHOTOS = ROOT / "photos"
CREDITS = PHOTOS / "CREDITS.txt"


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def get(url, headers=None, timeout=40):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)   # 不带 UA 会被 Cloudflare 拦成 403
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def search_pexels(query, count, key, orientation="landscape"):
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
        "query": query, "per_page": count, "orientation": orientation,
    })
    raw = get(url, {"Authorization": key})
    data = json.loads(raw)
    return [{
        "url": p["src"]["large2x"],
        "author": p["photographer"],
        "page": p["url"],
        "provider": "Pexels",
    } for p in data.get("photos", [])]


def search_unsplash(query, count, key, orientation="landscape"):
    url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode({
        "query": query, "per_page": count, "orientation": orientation,
    })
    raw = get(url, {"Authorization": "Client-ID " + key})
    data = json.loads(raw)
    return [{
        "url": r["urls"]["regular"],
        "author": r["user"]["name"],
        "page": r["links"]["html"],
        "provider": "Unsplash",
    } for r in data.get("results", [])]


def crop_to(im, tw, th, top=0.38):
    target = tw / th
    w, h = im.size
    if w / h > target:
        nw = int(h * target)
        left = (w - nw) // 2
        im = im.crop((left, 0, left + nw, h))
    else:
        nh = int(w / target)
        y = int((h - nh) * top)
        im = im.crop((0, y, w, y + nh))
    return im.resize((tw, th), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description="找一个配图")
    ap.add_argument("query")
    ap.add_argument("--out", default=None, help="文件名，不带扩展名")
    ap.add_argument("--size", default="940x380", help="宽x高，默认 940x380")
    ap.add_argument("--provider", choices=["pexels", "unsplash"], default="pexels")
    ap.add_argument("--count", type=int, default=5, help="拿几张里挑第一张能下的")
    ap.add_argument("--list", action="store_true", help="只列出候选，不下载")
    args = ap.parse_args()

    key = os.environ.get("PEXELS_API_KEY" if args.provider == "pexels" else "UNSPLASH_ACCESS_KEY", "")
    if not key:
        env = "PEXELS_API_KEY" if args.provider == "pexels" else "UNSPLASH_ACCESS_KEY"
        sys.exit("先设环境变量 %s，去 %s 免费申请一个。" % (
            env, "https://www.pexels.com/api/" if args.provider == "pexels" else "https://unsplash.com/developers"))

    try:
        hits = (search_pexels if args.provider == "pexels" else search_unsplash)(
            args.query, args.count, key)
    except urllib.error.HTTPError as exc:
        sys.exit("%s 返回 %s：%s" % (args.provider, exc.code, exc.read().decode("utf-8", "ignore")[:200]))
    except urllib.error.URLError as exc:
        sys.exit("连不上 %s：%s" % (args.provider, exc.reason))

    if not hits:
        sys.exit("没找到，换个关键词试试。")

    if args.list:
        for i, h in enumerate(hits, 1):
            print("%d. %s  %s  %s" % (i, h["author"], h["provider"], h["page"]))
        return

    tw, th = (int(x) for x in re.split(r"[xX×]", args.size))
    PHOTOS.mkdir(exist_ok=True)
    name = args.out or re.sub(r"[^\w\u4e00-\u9fff]+", "-", args.query).strip("-")
    dest = PHOTOS / (name if name.endswith(".jpg") else name + ".jpg")

    for hit in hits:
        try:
            data = get(hit["url"], timeout=60)
            tmp = PHOTOS / ("_tmp_" + dest.name)
            tmp.write_bytes(data)
            im = Image.open(tmp).convert("RGB")
            if im.width < 800:
                tmp.unlink(missing_ok=True)
                continue
            im = crop_to(im, tw, th)
            im = ImageEnhance.Color(im).enhance(1.14)
            im = ImageEnhance.Contrast(im).enhance(1.05)
            im.save(dest, quality=92, optimize=True)
            tmp.unlink(missing_ok=True)
        except Exception as exc:
            print("跳过一张：%s" % exc)
            continue

        with open(CREDITS, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\t%s\n" % (dest.name, hit["provider"], hit["author"], hit["page"]))
        print("存好了 %s（%s，%s）" % (dest, hit["provider"], hit["author"]))
        print("出处记在 %s" % CREDITS)
        return

    sys.exit("候选都下载失败了，换关键词或者稍后再试。")


if __name__ == "__main__":
    main()
