# -*- coding: utf-8 -*-
"""假的模型接口，用来在没有 key 的情况下验证 plan.py 的整条链路。

    python mock_llm.py 8901
    set TRIPBOOK_API_KEY=test
    set TRIPBOOK_BASE_URL=http://127.0.0.1:8901/v1
    python plan.py

第一轮问一句，第二轮直接吐一份最小可渲染的 JSON。
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TRIP = {
    "title": "测试三天",
    "output": "测试三天.pdf",
    "pages": [
        {"type": "cover", "place": "测试 · 自驾", "title": "测试三天",
         "sub": "甲地 到 乙地", "dates": "某个周末",
         "facts": [["同行", "两个人"]],
         "stats": [["1", "天"]], "mood": "别赶路。"},
        {"type": "day", "no": "01", "title": "Day 1", "accent": "red",
         "lead": "到了先吃饭",
         "rows": [["10:00", "出发", "一小时车程"],
                  ["12:00", "午饭", "人均三十"]],
         "badge": "步数 ≈ 2,000 · 节奏 很轻", "task": "数一数有几座桥"},
        {"type": "budget", "no": "02", "title": "预算", "accent": "grey",
         "lead": "两个人，约 ¥800",
         "items": [["油费", 200], ["住宿", 300], ["吃饭", 300]],
         "todos": {"title": "出发前", "items": ["订房"]},
         "emergencyLabel": "应急", "emergency": [["急救", "120"]]},
    ],
}

ROUNDS = {"n": 0}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.headers.get("Expect", "").lower() == "100-continue":
            self.send_response(100)
            self.end_headers()
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        ROUNDS["n"] += 1
        if ROUNDS["n"] == 1:
            content = "先问一下：从哪出发，玩几天？"
        else:
            content = "好，排好了。\n\n```json\n" + json.dumps(TRIP, ensure_ascii=False, indent=2) + "\n```"
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
    print("mock llm on 127.0.0.1:%d" % port, flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

