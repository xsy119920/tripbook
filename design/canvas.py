# -*- coding: utf-8 -*-
"""画布。所有坐标按 1080x1440 的逻辑尺寸写，渲染时整体乘以 scale。"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

from . import tokens as T

PUNCT = "，。、；：！？）》」』%"


class Canvas:
    def __init__(self, width: int, height: int, scale: int = 2, bg: str = T.BG):
        self.w = width
        self.h = height
        self.s = scale
        self.img = Image.new("RGB", (width * scale, height * scale), bg)
        self.d = ImageDraw.Draw(self.img)
        self._fonts: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}
        self._bold_path, self._regular_path = T.font_paths()

    # ------------------------------------------------------------ text
    def font(self, size: float, bold: bool = False):
        key = (int(size), bold)
        if key not in self._fonts:
            path = self._bold_path if bold else self._regular_path
            self._fonts[key] = ImageFont.truetype(path, int(size * self.s))
        return self._fonts[key]

    def tw(self, text: str, size: float, bold: bool = False) -> float:
        return self.d.textlength(text, font=self.font(size, bold)) / self.s

    def wrap(self, text: str, size: float, maxw: float, bold: bool = False) -> list[str]:
        out, cur = [], ""
        for ch in text:
            if ch == "\n":
                out.append(cur)
                cur = ""
                continue
            candidate = cur + ch
            if self.tw(candidate, size, bold) <= maxw:
                cur = candidate
            elif ch in PUNCT:
                out.append(cur + ch)
                cur = ""
            else:
                out.append(cur)
                cur = ch
        if cur:
            out.append(cur)
        return out

    def text(self, x, y, s, size=28, fill=T.INK, bold=False, anchor="la"):
        self.d.text((x * self.s, y * self.s), s, font=self.font(size, bold),
                    fill=fill, anchor=anchor)

    def para(self, x, y, s, size, maxw, lh, fill=T.INK, bold=False) -> float:
        for line in self.wrap(s, size, maxw, bold):
            self.text(x, y, line, size=size, fill=fill, bold=bold)
            y += lh
        return y

    # ------------------------------------------------------------ shapes
    def rect(self, x, y, w, h, fill, r=0, outline=None, lw=2):
        box = [x * self.s, y * self.s, (x + w) * self.s, (y + h) * self.s]
        if r:
            self.d.rounded_rectangle(box, r * self.s, fill=fill,
                                     outline=outline, width=int(lw * self.s) if outline else 0)
        else:
            self.d.rectangle(box, fill=fill, outline=outline,
                             width=int(lw * self.s) if outline else 0)

    def line(self, pts, fill, lw=2):
        self.d.line([(px * self.s, py * self.s) for px, py in pts],
                    fill=fill, width=int(lw * self.s))

    def circle(self, cx, cy, r, fill):
        self.d.ellipse([(cx - r) * self.s, (cy - r) * self.s,
                        (cx + r) * self.s, (cy + r) * self.s], fill=fill)

    def panel(self, x, y, w, h, fill=T.CARD, outline=None, r=26, shadow=True):
        if shadow:
            self.rect(x + 5, y + 8, w, h, T.SHADOW, r=r)
        self.rect(x, y, w, h, fill, r=r, outline=outline)

    # ------------------------------------------------------------ images
    def photo(self, path, x, y, w, h, r=22):
        if not path or not os.path.exists(path):
            self._placeholder(os.path.basename(str(path)), x, y, w, h, r)
            return
        im = Image.open(path).convert("RGB")
        target = (int(w * self.s), int(h * self.s))
        if im.size != target:
            im = im.resize(target, Image.LANCZOS)
        if r:
            mask = Image.new("L", target, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, target[0], target[1]], r * self.s, fill=255)
            self.img.paste(im, (int(x * self.s), int(y * self.s)), mask)
        else:
            self.img.paste(im, (int(x * self.s), int(y * self.s)))

    def _placeholder(self, name, x, y, w, h, r):
        """缺图时画一个中性色块，仓库里不带任何别人的照片。"""
        self.rect(x, y, w, h, T.PAPER_2, r=r)
        self.rect(x + 1, y + 1, w - 2, h - 2, T.PAPER_2, r=r, outline=T.LINE, lw=2)
        label = name or "photo"
        size = min(26, max(16, int(w / 18)))
        self.text(x + w / 2, y + h / 2, label, size=size, fill=T.MUTED, anchor="mm")

    def save(self, path: str):
        self.img.save(path, "PNG")

    def scaled(self) -> Image.Image:
        return self.img
