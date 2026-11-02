# -*- coding: utf-8 -*-
"""色板与字体。改这里就能换整本的颜色，页面文件里不出现色值。"""
import os
import sys

# 纸、墨、线、四种信号色
BG = "#F6F1E7"
CARD = "#FFFFFF"
PAPER_2 = "#EFE8DA"
INK = "#241E19"
MUTED = "#6E6154"
LINE = "#E3D8C4"
SOFT = "#EFE5D3"
CREAM = "#FFF9F0"
SHADOW = "#E4D8C2"

RED = "#A33A2B"
RED_SOFT = "#F7E7E2"
GREEN = "#2E5B4A"
GREEN_SOFT = "#E7F0EA"
GOLD = "#B0801F"
RUST = "#8C5A1E"
GREY = "#5A5A5A"

ACCENTS = {
    "red": RED,
    "green": GREEN,
    "gold": GOLD,
    "rust": RUST,
    "grey": GREY,
}

FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"),
    ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
     "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
]


def font_paths():
    env = os.environ.get("TRIPBOOK_FONTS")
    if env and os.pathsep in env:
        bold, regular = env.split(os.pathsep, 1)
        if os.path.exists(bold) and os.path.exists(regular):
            return bold, regular
    for bold, regular in FONT_CANDIDATES:
        if os.path.exists(bold) and os.path.exists(regular):
            return bold, regular
    sys.exit(
        "找不到中文字体。装一个思源黑体，或用环境变量指定粗体和常规体：\n"
        "  TRIPBOOK_FONTS=/path/bold.ttc:/path/regular.ttc python make.py trips/x.json"
    )
