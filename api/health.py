# -*- coding: utf-8 -*-
"""最簡健康檢查：不依賴 Flask 或 app，確認 Vercel 能執行 api 目錄內的 Python。"""
from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "api": "health"}).encode("utf-8"))

    def do_POST(self):
        self.do_GET()
