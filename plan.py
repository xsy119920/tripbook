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

4. pages 里每一项的 type 只能是：cover、candidates、compare、rules、route、spread、day、photos2、traffic、budget。字段要求见 README 的表格。
5. 图片：写 "photos/xxx.jpg" 这种路径；没有图就别写 image/hero/a/b 字段，程序会画占位块。
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
    return proc.returncode == 0


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
        path = save(trip)
        print("行程写到 %s" % path)
        ok = build(path)
        print("\n出好了。" if ok else "\n出册失败，看上面的报错。")
        print("看完想改哪页，直接说；改完再出一次。\n")


if __name__ == "__main__":
    main()
