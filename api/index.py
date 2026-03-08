# -*- coding: utf-8 -*-
"""
Vercel 入口：從專案根目錄載入 Flask app，供 api 目錄內的 Serverless Function 使用。
"""
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app import app
except Exception as e:
    # 若載入失敗，回傳錯誤以便除錯（Vercel 上可見）
    _import_error = str(e)
    _import_tb = traceback.format_exc()
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/")
    @app.route("/<path:path>")
    def _fail(path=""):
        return jsonify({"error": "app import failed", "message": _import_error, "traceback": _import_tb}), 500
