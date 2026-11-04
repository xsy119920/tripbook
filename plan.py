#!/usr/bin/env python3
"""旅行攻略智能体：命令行对话，聊完直接出 PDF。

    export TRIPBOOK_API_KEY=sk-...
    python plan.py

可选环境变量：
    TRIPBOOK_BASE_URL   默认 https://api.deepseek.com/v1
    TRIPBOOK_MODEL      默认 deepseek-chat
    TRIPBOOK_MAX_TURNS  默认 30，聊太久会自动砍掉最早的几轮

聊天里可以随时用：
    /build   用当前数据重新出一遍 PDF
    /show    打印当前的行程 JSON
    /reset   清空对话，从头开始
    /quit    退出

模型一旦输出一个 ```json 代码块，就会当作完整行程：先校验，通过就出 PDF。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from design.validate import validate  # noqa: E402
from fetch import grab  # noqa: E402

BASE_URL = os.environ.get("TRIPBOOK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
MODEL = os.environ.get("TRIPBOOK_MODEL", "deepseek-chat")
KEY = os.environ.get("TRIPBOOK_API_KEY", "")
MAX_TURNS = int(os.environ.get("TRIPBOOK_MAX_TURNS", "30"))

PROTOCOL = """

---

## 输出协议（这一段是程序要求的，不对外解释）

1. 需要更多信息时，直接用中文提问，一次最多两个问题。
2. 当你认为信息够了，输出**一个** ```json 代码块，里面是完整的一册书。代码块之外不要写别的。
3. JSON 结构：

```json
{
  "title": "标题",
  "output": "标题.pdf",
  "pages": [ ... ]
}
```

4. pages 里每一项的 type 只能是下面十种，字段照抄结构，不要自创：

cover    {"type":"cover","title":"","sub":"","place":"","dates":"","image":"photos/x.jpg","facts":[["同行","两个人"]],"stats":[["690km","全程"]],"mood":"","foot":{"left":"","right":""}}
candidates {"type":"candidates","no":"01","title":"","lead":"","candidates":[{"name":"","sub":"","accent":"red","fit":"","pace":"","food":"","watch":"","verdict":""}],"strip":""}
compare  {"type":"compare","no":"","title":"","accent":"red","lead":"","left":{"title":"","items":[""]},"right":{"title":"","items":[""]},"strip":{"label":"","text":""},"quote":{"label":"","text":""},"foot":{"label":"","text":""}}
rules    {"type":"rules","no":"","title":"","accent":"rust","lead":"","items":[["主","注"]],"foot":"","stats":[["",""]]}
route    {"type":"route","no":"","title":"","accent":"green","lead":"","stops":[{"name":"","note":"","leg":""}],"stats":[["",""]],"panels":[{"title":"","text":""}]}
spread   {"type":"spread","no":"","title":"","accent":"gold","hero":"photos/a.jpg","heroCaption":"","a":"photos/b.jpg","aCaption":"","b":"photos/c.jpg","bCaption":"","tip":""}
day      {"type":"day","no":"","title":"","accent":"red","lead":"","rows":[["08:00","出发","小字"]],"badge":"","task":""}
photos2  {"type":"photos2","no":"","title":"","accent":"gold","lead":"","a":"","aCaption":"","b":"","bCaption":"","panel":{"title":"","text":""},"box":{"label":"","text":""}}
traffic  {"type":"traffic","no":"","title":"","accent":"gold","lead":"","columns":[{"colour":"green","title":"","items":[""]}],"shopsLabel":"","shops":[["店名","备注"]],"box":{"label":"","text":""}}
budget   {"type":"budget","no":"","title":"","accent":"grey","lead":"","items":[["油费",600]],"todos":{"title":"","items":[""]},"emergencyLabel":"应急","emergency":[["急救","120"]]}

accent 只能是 red、green、gold、rust、grey 之一。数字写数字，别加 ¥ 和逗号。
5. 图片：写 "photos/xxx.jpg" 这种路径；程序会自动去 Unsplash 找。
   同时在最外层给一个 shots 数组：按页面顺序，为每一张需要图的槽位写一句中文检索词。
   槽位顺序是：cover 一张；每个 spread 三张（hero、a、b）；每个 photos2 两张（a、b）。
   检索词写得越具体越好，比如「大理 洱海 日出」「潮州 牌坊街 夜景」，别写「风景」。
6. 不确定的事实写「出发前核对」，不要编具体时间。
"""


def system_prompt() -> str:
    spec = (ROOT / "agent" / "SYSTEM.md").read_text(encoding="utf-8")
    return spec + PROTOCOL


def chat(messages):
    url = BASE_URL + "/chat/completions"
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        "stream": False,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + KEY)
    opener = urllib.request.build_opener()
    try:
        with opener.open(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise SystemExit("模型接口返回 %s：%s" % (exc.code, detail))
    except urllib.error.URLError as exc:
        raise SystemExit("连不上 %s：%s" % (BASE_URL, exc.reason))
    return data["choices"][0]["message"]["content"]


def extract_json(text: str):
    block = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if not block:
        return None
    try:
        return json.loads(block.group(1))
    except json.JSONDecodeError:
        return None


def build(trip_path: Path) -> bool:
    proc = subprocess.run([sys.executable, str(ROOT / "make.py"), str(trip_path)],
                          cwd=str(ROOT), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out.strip())
    return proc.returncode == 0, out



SLOTS = {
    "cover": [("image", (1080, 470))],
    "spread": [("hero", (940, 380)), ("a", (458, 270)), ("b", (458, 270))],
    "photos2": [("a", (458, 330)), ("b", (458, 330))],
}


def fill_photos(trip, slug):
    """把 JSON 里指向 photos/ 但文件不存在的槽位，用 Unsplash 补上。

    查询词优先用 trip["shots"]（每张一句，按页面顺序），没有就用页面标题。
    """
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not key:
        return []

    shots = trip.get("shots") or []
    made = []
    i = 0
    for page in trip["pages"]:
        for field, size in SLOTS.get(page.get("type"), []):
            path = page.get(field)
            if not path:
                continue
            target = ROOT / path
            query = shots[i] if i < len(shots) else page.get("title", trip["title"])
            i += 1
            if target.exists():
                continue
            # 文件名沿用 JSON 里写的，保证版式不用改
            name = Path(path).stem + ".jpg"
            dest = ROOT / "photos" / name
            hit = grab(query, dest, size, key)
            if not hit:
                continue
            page[field] = "photos/" + name
            made.append((query, hit[1]["author"], hit[1]["page"]))
            print("  配图 %s ← 「%s」（%s）" % (name, query, hit[1]["author"]))
    return made


def save(trip: dict) -> Path:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", trip.get("title", "trip")).strip("-") or "trip"
    trip.setdefault("output", trip.get("title", "trip") + ".pdf")
    path = ROOT / "trips" / ("%s.json" % slug)
    path.write_text(json.dumps(trip, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    # Windows 的控制台默认是 GBK，打印「¥」这类字符会直接崩。统一按 UTF-8 输出。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if not KEY:
        sys.exit("先设一个模型 key：\n  export TRIPBOOK_API_KEY=sk-...\n"
                 "（Windows 用 set TRIPBOOK_API_KEY=sk-...）")

    print("旅行探路者。说说这次想怎么玩，或者直接说「不知道去哪」。")
    print("输入 /quit 退出。\n")

    messages = [{"role": "system", "content": system_prompt()}]
    current = None

    while True:
        try:
            user = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/quit", "/exit"):
            break
        if user == "/reset":
            messages = [{"role": "system", "content": system_prompt()}]
            current = None
            print("已清空。\n")
            continue
        if user == "/show":
            print(json.dumps(current, ensure_ascii=False, indent=2) if current else "还没有行程。")
            print()
            continue
        if user == "/build":
            if not current:
                print("还没有行程。\n")
                continue
            path = save(current)
            print("写到 %s" % path)
            build(path)
            print()
            continue

        messages.append({"role": "user", "content": user})
        if len(messages) > MAX_TURNS * 2:
            messages = [messages[0]] + messages[-MAX_TURNS:]

        reply = chat(messages)
        messages.append({"role": "assistant", "content": reply})
        print("\n它 > %s\n" % reply)

        trip = extract_json(reply)
        if not trip:
            continue

        try:
            validate(trip)
        except SystemExit as exc:
            print("（生成的 JSON 不合格，让它自己修）\n%s\n" % exc)
            messages.append({"role": "user",
                             "content": "上面那份 JSON 有问题：%s\n请重新输出一个完整的 ```json 代码块。" % exc})
            fixed = chat(messages)
            messages.append({"role": "assistant", "content": fixed})
            trip = extract_json(fixed)
            if not trip:
                continue
            try:
                validate(trip)
            except SystemExit as exc2:
                print("还是不合格：%s\n" % exc2)
                continue

        current = trip
        made = fill_photos(trip, trip.get("title", "trip"))
        path = save(trip)
        print("行程写到 %s" % path)
        ok, err = build(path)
        if ok:
            print("\n出好了。")
            print("看完想改哪页，直接说；改完再出一次。\n")
        else:
            tail = "\n".join(err.strip().splitlines()[-6:])
            print("\n出册失败，把报错交回去让它改。\n")
            messages.append({"role": "user",
                             "content": "排版时报错了，说明这份 JSON 有字段写错：\n%s\n"
                                        "请按报错改，然后重新输出完整的 ```json 代码块。" % tail})
            fixed = chat(messages)
            messages.append({"role": "assistant", "content": fixed})
            retry = extract_json(fixed)
            if retry:
                try:
                    validate(retry)
                    current = retry
                    path = save(retry)
                    ok2, _ = build(path)
                    print("\n改完重出：%s" % ("好了" if ok2 else "还是失败，看上面的报错"))
                except SystemExit as exc:
                    print("改完还是不合格：%s" % exc)
            print()


if __name__ == "__main__":
    main()
