# -*- coding: utf-8 -*-
"""
書籍轉換工具 - 網頁版：上傳 .epub → 自動轉換 → 下載。
執行: python app.py  然後在瀏覽器開啟 http://127.0.0.1:5000
"""

import os
import re
import uuid
from pathlib import Path

from flask import Flask, request, send_file, render_template_string, redirect, url_for

ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = ROOT / "upload"
OUTPUT_DIR = ROOT / "output"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB


def safe_filename(name: str) -> str:
    base = Path(name).stem
    base = re.sub(r"[^\w\s\-\.]", "", base)[:80] or "book"
    return base + ".epub"


def run_conversion(input_path: str) -> str:
    """回傳輸出檔路徑。"""
    sys_path = list(__import__("sys").path)
    if str(ROOT) not in sys_path:
        __import__("sys").path.insert(0, str(ROOT))
    from main import (
        detect_language_from_epub,
        convert_simplified_epub,
        convert_english_epub,
    )

    lang = detect_language_from_epub(input_path)
    out_path = str(Path(input_path).parent / (Path(input_path).stem + "_tw.epub"))

    if lang == "en":
        convert_english_epub(input_path, out_path)
    else:
        convert_simplified_epub(input_path, out_path)
    return out_path


HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>書籍轉換工具</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: "Segoe UI", "PingFang TC", "Microsoft JhengHei", sans-serif;
      max-width: 560px;
      margin: 2rem auto;
      padding: 0 1rem;
      color: #1a1a1a;
      background: #f8f9fa;
    }
    h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #333; }
    p.sub { color: #666; font-size: 0.95rem; margin-bottom: 1.5rem; }
    .card {
      background: #fff;
      border-radius: 12px;
      padding: 1.5rem;
      box-shadow: 0 2px 12px rgba(0,0,0,0.06);
      margin-bottom: 1rem;
    }
    label {
      display: block;
      margin-bottom: 0.5rem;
      font-weight: 500;
      color: #444;
    }
    input[type="file"] {
      width: 100%;
      padding: 0.75rem;
      border: 2px dashed #ccc;
      border-radius: 8px;
      background: #fafafa;
      cursor: pointer;
    }
    input[type="file"]:hover { border-color: #6b9eed; background: #f0f6ff; }
    button {
      width: 100%;
      margin-top: 1rem;
      padding: 0.85rem 1.2rem;
      font-size: 1rem;
      font-weight: 600;
      color: #fff;
      background: #2563eb;
      border: none;
      border-radius: 8px;
      cursor: pointer;
    }
    button:hover { background: #1d4ed8; }
    button:disabled { background: #94a3b8; cursor: not-allowed; }
    .msg {
      margin-top: 1rem;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      font-size: 0.9rem;
    }
    .msg.success { background: #dcfce7; color: #166534; }
    .msg.error { background: #fee2e2; color: #991b1b; }
    .msg.info { background: #e0f2fe; color: #075985; }
    a.dl {
      display: inline-block;
      margin-top: 0.5rem;
      padding: 0.5rem 1rem;
      background: #16a34a;
      color: #fff;
      text-decoration: none;
      border-radius: 6px;
      font-weight: 500;
    }
    a.dl:hover { background: #15803d; }
  </style>
</head>
<body>
  <h1>書籍轉換工具</h1>
  <p class="sub">上傳 .epub（簡體或英文），自動轉成臺灣繁體 .epub 並可下載。</p>

  <div class="card">
    <form method="post" action="/convert" enctype="multipart/form-data">
      <label for="file">選擇 .epub 檔案</label>
      <input type="file" name="file" id="file" accept=".epub" required>
      <button type="submit" id="btn">開始轉換</button>
    </form>
    <p class="msg info" style="margin-top:1rem;">
      支援：簡體→臺灣繁體（含用語轉換）；英文→繁體中文（整書術語一致）。轉換時間依書本長度而定，請稍候。
    </p>
  </div>

  {% if download_url %}
  <div class="card">
    <p class="msg success">轉換完成，請下載檔案。</p>
    <a class="dl" href="{{ download_url }}" download>下載 {{ download_name }}</a>
  </div>
  {% endif %}
  {% if error %}
  <div class="card">
    <p class="msg error">{{ error }}</p>
  </div>
  {% endif %}

  <script>
    document.querySelector('form').addEventListener('submit', function() {
      var btn = document.getElementById('btn');
      btn.disabled = true;
      btn.textContent = '轉換中，請稍候…';
    });
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(
        HTML,
        download_url=None,
        download_name=None,
        error=request.args.get("error"),
    )


@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return redirect(url_for("index", error="請選擇一個檔案"))
    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".epub"):
        return redirect(url_for("index", error="請上傳 .epub 檔案"))
    safe = safe_filename(f.filename)
    job_id = uuid.uuid4().hex[:8]
    input_path = UPLOAD_DIR / f"{job_id}_{safe}"
    try:
        f.save(str(input_path))
        out_path = run_conversion(str(input_path))
        out_name = Path(out_path).name
        # 把輸出移到 OUTPUT_DIR 並用 job 名供下載
        final_name = f"{job_id}_{Path(out_path).name}"
        final_path = OUTPUT_DIR / final_name
        import shutil
        shutil.move(out_path, str(final_path))
        return redirect(url_for("download", filename=final_name))
    except Exception as e:
        return redirect(url_for("index", error=f"轉換失敗：{e}"))
    finally:
        if input_path.exists():
            try:
                input_path.unlink()
            except Exception:
                pass


@app.route("/download/<filename>")
def download(filename: str):
    path = OUTPUT_DIR / filename
    if not path.is_file():
        return redirect(url_for("index", error="檔案不存在或已清除"))
    # 下載後可選擇刪除暫存（此處保留，方便重複下載）
    # 下載檔名去掉 job id 前綴，例如 a1b2c3d4_書名_tw.epub → 書名_tw.epub
    if len(filename) > 9 and filename[8:9] == "_":
        download_name = filename[9:]
    else:
        download_name = path.name
    return send_file(path, as_attachment=True, download_name=download_name)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("書籍轉換工具 - 網頁版")
    print(f"請在瀏覽器開啟: http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)