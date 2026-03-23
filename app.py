# -*- coding: utf-8 -*-
"""
書籍轉換工具 - 網頁版：上傳 .epub → 自動轉換 → 下載。
執行: python app.py  然後在瀏覽器開啟 http://127.0.0.1:5000
"""

import os
import re
import sys
import traceback
import uuid
from pathlib import Path

from flask import Flask, request, send_file, render_template_string, redirect, url_for, jsonify

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Vercel 僅能寫入 /tmp；若本機 mkdir 失敗也 fallback 到 /tmp
if os.environ.get("VERCEL"):
    _base = Path("/tmp/book_converter")
    UPLOAD_DIR = _base / "upload"
    OUTPUT_DIR = _base / "output"
else:
    UPLOAD_DIR = ROOT / "upload"
    OUTPUT_DIR = ROOT / "output"
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    _base = Path("/tmp/book_converter")
    UPLOAD_DIR = _base / "upload"
    OUTPUT_DIR = _base / "output"
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB


@app.errorhandler(Exception)
def handle_error(e):
    """回傳錯誤訊息與 traceback，方便在 Vercel 除錯。"""
    tb = traceback.format_exc()
    if os.environ.get("VERCEL"):
        return jsonify({"error": str(e), "traceback": tb}), 500
    raise e


@app.route("/api/health")
def api_health():
    """健康檢查：不載入轉換相關模組，用於確認 Vercel 是否正常啟動。"""
    return jsonify({"ok": True, "vercel": bool(os.environ.get("VERCEL"))})


def safe_filename(name: str) -> str:
    base = Path(name).stem
    base = re.sub(r"[^\w\s\-\.]", "", base)[:80] or "book"
    return base + ".epub"


def run_conversion(input_path: str, output_path: str | None = None) -> str:
    """回傳輸出檔路徑。若給 output_path 則直接寫入該路徑（避免檔名過長觸發 Errno 36）。"""
    sys_path = list(__import__("sys").path)
    if str(ROOT) not in sys_path:
        __import__("sys").path.insert(0, str(ROOT))
    from main import (
        detect_language_from_epub,
        convert_simplified_epub,
        convert_english_epub,
    )

    lang = detect_language_from_epub(input_path)
    if output_path:
        out_path = output_path
    else:
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
  <title>BookFlow 閱讀轉換器</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Nunito:wght@600;700&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Noto Sans TC", "Nunito", "PingFang TC", sans-serif;
      min-height: 100vh;
      background: linear-gradient(135deg, #fef3c7 0%, #e0e7ff 25%, #d1fae5 50%, #fce7f3 75%, #cffafe 100%);
      background-attachment: fixed;
      color: #374151;
      padding: 2.5rem 1rem 4rem;
    }
    .wrap { max-width: 520px; margin: 0 auto; }
    .hero {
      text-align: center;
      margin-bottom: 2rem;
    }
    .hero h1 {
      font-family: "Nunito", "Noto Sans TC", sans-serif;
      font-size: 1.85rem;
      font-weight: 700;
      color: #374151;
    }
    .hero .sub {
      margin-top: 0.5rem;
      font-size: 0.95rem;
      color: #6b7280;
      font-weight: 500;
    }
    .card {
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(0, 0, 0, 0.06);
      border-radius: 20px;
      padding: 1.75rem;
      margin-bottom: 1.25rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    }
    .card label {
      display: block;
      margin-bottom: 0.5rem;
      font-weight: 600;
      color: #374151;
      font-size: 0.95rem;
    }
    input[type="file"] {
      width: 100%;
      padding: 1rem;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      background: #f9fafb;
      color: #4b5563;
      cursor: pointer;
      font-weight: 500;
    }
    input[type="file"]:hover {
      background: #f3f4f6;
      border-color: #d1d5db;
    }
    button {
      width: 100%;
      margin-top: 1.25rem;
      padding: 1rem 1.5rem;
      font-size: 1rem;
      font-weight: 600;
      font-family: "Noto Sans TC", "Nunito", sans-serif;
      color: #fff;
      background: #4b5563;
      border: none;
      border-radius: 12px;
      cursor: pointer;
      transition: background 0.2s;
    }
    button:hover { background: #374151; }
    button:disabled {
      background: #9ca3af;
      cursor: not-allowed;
    }
    .msg {
      margin-top: 1rem;
      padding: 0.9rem 1.1rem;
      border-radius: 12px;
      font-size: 0.9rem;
      font-weight: 500;
    }
    .msg.success {
      background: #ecfdf5;
      color: #065f46;
    }
    .msg.error {
      background: #fef2f2;
      color: #991b1b;
    }
    .msg code { font-size: 0.9em; background: rgba(0,0,0,0.06); padding: 0.15em 0.4em; border-radius: 4px; }
    .msg.info {
      background: #f3f4f6;
      color: #4b5563;
    }
    a.dl {
      display: inline-block;
      margin-top: 0.75rem;
      padding: 0.65rem 1.25rem;
      background: #4b5563;
      color: #fff;
      text-decoration: none;
      border-radius: 10px;
      font-weight: 600;
      transition: background 0.2s;
    }
    a.dl:hover { background: #374151; }
    /* ── 視覺進度條 ── */
    .progress-wrap { margin-top: 1rem; display: none; }
    .progress-bar-bg { background: #e5e7eb; border-radius: 99px; overflow: hidden; height: 7px; }
    .progress-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #4b5563, #6b7280);
      border-radius: 99px;
      transition: width 0.35s ease;
      width: 0%;
    }
    #progressText { margin-top: 0.5rem; font-size: 0.875rem; font-weight: 500; color: #4b5563; }
    #progressText.err { color: #991b1b; }
    /* ── 雙語模式開關 ── */
    .bilingual-toggle {
      display: flex;
      align-items: center;
      gap: 0.55rem;
      margin-top: 1rem;
      cursor: pointer;
    }
    .bilingual-toggle input { width: 1rem; height: 1rem; cursor: pointer; accent-color: #4b5563; }
    .bilingual-toggle span { font-size: 0.9rem; font-weight: 500; color: #374151; }
    .cancel-btn {
      margin-top: 1rem;
      width: 100%;
      padding: 0.6rem 1rem;
      font-size: 0.9rem;
      font-weight: 600;
      color: #6b7280;
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      cursor: pointer;
    }
    .cancel-btn:hover { background: #e5e7eb; color: #374151; }
    .card.download,
    .card.error {
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(0, 0, 0, 0.06);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    }
    .footer {
      margin-top: 3rem;
      padding: 1.75rem 1.5rem;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.85);
      text-align: center;
      font-size: 0.8rem;
      color: #6b7280;
      line-height: 1.95;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    }
    .footer a { color: #4b5563; font-weight: 600; text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>BookFlow 閱讀轉換器</h1>
      <p class="sub">上傳 .epub（簡體或英文），自動轉成臺灣繁體 .epub 並可下載</p>
    </header>

    <div class="card">
      <form id="form" method="post" action="/convert" enctype="multipart/form-data">
        <label for="file">選擇 .epub 檔案</label>
        <input type="file" name="file" id="file" accept=".epub" required>
        <!-- 雙語模式開關 -->
        <label class="bilingual-toggle">
          <input type="checkbox" id="bilingualMode">
          <span>雙語模式（保留原文，每段下方顯示繁中譯文）</span>
        </label>
        <button type="submit" id="btn">開始轉換</button>
        <!-- 視覺進度條 -->
        <div class="progress-wrap" id="progressWrap">
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="progressFill"></div>
          </div>
          <p id="progressText"></p>
        </div>
        <button type="button" id="cancelBtn" class="cancel-btn" style="display:none;">取消並重新進行</button>
    </form>
      <p class="msg info" style="margin-top:1rem;">
        支援：<br>
        簡體→臺灣繁體（含用語轉換）<br>
        英文→繁體中文（包含檢視術語一致）<br>
        <br>
        本翻譯皆設定整本書的語意、用詞（尤其人名）會進行統一
      </p>
    </div>

    {% if download_url %}
    <div class="card download">
      <p class="msg success">轉換完成，請下載檔案。</p>
      <a class="dl" href="{{ download_url }}" download>下載 {{ download_name }}</a>
    </div>
    {% endif %}
    {% if error %}
    <div class="card error">
      <p class="msg error">{{ error }}</p>
    </div>
    {% endif %}

    <footer class="footer">
      <p>本工具僅限非商業使用，同時請自行留意版權相關法規。</p>
      <p>本專案由熊貓原點有限公司維護</p>
      <p>若有任何本工具之建議，歡迎來信：<a href="mailto:panda@nps.tw">panda@nps.tw</a></p>
      <p>本司代理各領域軟體、硬體採購，詳情請洽詢：<a href="https://nps.tw" target="_blank" rel="noopener">nps.tw</a></p>
    </footer>
  </div>

  <script>
  (function() {
    var form         = document.getElementById('form');
    var fileInput    = document.getElementById('file');
    var btn          = document.getElementById('btn');
    var cancelBtn    = document.getElementById('cancelBtn');
    var progressWrap = document.getElementById('progressWrap');
    var progressFill = document.getElementById('progressFill');
    var progressText = document.getElementById('progressText');
    var bilingualMode = document.getElementById('bilingualMode');

    /**
     * 更新進度條與文字。
     * pct: 0-100（可選），若省略則進度條維持現狀。
     * isErr: true 時文字顯示為紅色。
     */
    function setProgress(txt, isErr, pct) {
      if (txt) {
        progressWrap.style.display = 'block';
      } else {
        progressWrap.style.display = 'none';
        progressFill.style.width = '0%';
      }
      progressText.textContent = txt || '';
      progressText.className = isErr ? 'err' : '';
      if (typeof pct === 'number') {
        progressFill.style.width = Math.min(100, Math.max(0, pct)) + '%';
      }
    }

    function resetForm() {
      fileInput.value = '';
      btn.disabled = false;
      cancelBtn.style.display = 'none';
      setProgress('');
    }

    function stripHtml(html) {
      var div = document.createElement('div');
      div.innerHTML = html;
      return (div.textContent || div.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 15000);
    }
    function splitHtmlChunks(html, maxBytes) {
      if (!html || new Blob([html]).size <= maxBytes) return [html];
      var chunks = [];
      var pos = 0;
      var len = html.length;
      var maxChars = Math.floor(maxBytes / 2);
      while (pos < len) {
        var end = Math.min(pos + maxChars, len);
        var slice = html.slice(pos, end);
        if (end >= len) {
          chunks.push(slice);
          break;
        }
        var search = slice;
        var lastP = search.lastIndexOf('</p>');
        var lastDiv = search.lastIndexOf('</div>');
        var lastSec = search.lastIndexOf('</section>');
        var lastN = search.lastIndexOf('\\n');
        var cut = Math.max(
          lastP >= 0 ? lastP + 4 : -1,
          lastDiv >= 0 ? lastDiv + 6 : -1,
          lastSec >= 0 ? lastSec + 10 : -1,
          lastN >= 0 ? lastN + 1 : -1
        );
        if (cut < 0) cut = slice.length;
        chunks.push(html.slice(pos, pos + cut));
        pos += cut;
      }
      return chunks;
    }

    function parseOpf(xmlStr) {
      var parser = new DOMParser();
      var doc = parser.parseFromString(xmlStr, 'text/xml');
      var manifest = {};
      var items = doc.getElementsByTagName ? doc.getElementsByTagName('item') : doc.querySelectorAll('item');
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var id = item.getAttribute('id');
        var href = item.getAttribute('href') || '';
        var mt = (item.getAttribute('media-type') || '').toLowerCase();
        if (id && (mt.indexOf('html') >= 0 || /\\.(x?html?)$/i.test(href))) manifest[id] = href;
      }
      var spine = [];
      var refs = doc.getElementsByTagName ? doc.getElementsByTagName('itemref') : doc.querySelectorAll('itemref');
      for (var j = 0; j < refs.length; j++) {
        var id = refs[j].getAttribute('idref');
        if (id && manifest[id]) spine.push({ id: id, href: manifest[id] });
      }
      return { spine: spine, manifest: manifest };
    }

    function getBasePath(opfPath) {
      var i = opfPath.lastIndexOf('/');
      return i >= 0 ? opfPath.slice(0, i + 1) : '';
    }

    var COPYRIGHT_PAGE_HTML = "<?xml version='1.0' encoding='utf-8'?>\\n<!DOCTYPE html>\\n<html xmlns=\\"http://www.w3.org/1999/xhtml\\" lang=\\"zh-TW\\" xml:lang=\\"zh-TW\\">\\n<head><meta charset=\\"utf-8\\"/><title>版權頁</title></head>\\n<body>\\n  <p>本書籍轉換工具，由「熊貓原點有限公司」維護。</p>\\n  <p>若有任何建議或靈感，歡迎聯繫 panda@nps.tw</p>\\n  <p>本司代理各領域軟體、硬體採購，詳情請洽詢：<a href=\\"https://www.nps.tw\\">nps.tw</a></p>\\n</body>\\n</html>";

    form.addEventListener('submit', function(e) {
      e.preventDefault();
      var file = fileInput.files[0];
      if (!file) return;
      var controller = new AbortController();
      var signal = controller.signal;
      btn.disabled = true;
      cancelBtn.style.display = 'block';
      setProgress('讀取檔案並偵測語言…', false, 2);

      cancelBtn.onclick = function() {
        controller.abort();
        resetForm();
      };

      function readAsArrayBuffer(f) {
        return new Promise(function(resolve, reject) {
          var r = new FileReader();
          r.onload = function() { resolve(r.result); };
          r.onerror = reject;
          r.readAsArrayBuffer(f);
        });
      }

      readAsArrayBuffer(file).then(function(ab) {
        if (!window.JSZip) return Promise.reject(new Error('JSZip 未載入'));
        return window.JSZip.loadAsync(ab);
      }).then(function(zip) {
          setProgress('解析 epub 結構與目錄…');
        var containerEntry = zip.file('META-INF/container.xml') || zip.file('container.xml');
        if (!containerEntry) throw new Error('找不到 container.xml');
        return containerEntry.async('string').then(function(str) {
          var parser = new DOMParser();
          var doc = parser.parseFromString(str, 'text/xml');
          var rootfile = doc.querySelector('rootfile');
          var opfPath = rootfile ? rootfile.getAttribute('full-path') : '';
          if (!opfPath) throw new Error('找不到 content.opf 路徑');
          var base = getBasePath(opfPath);
          return zip.file(opfPath).async('string').then(function(opfStr) {
            var opf = parseOpf(opfStr);
            var ordered = [];
            return Promise.all(opf.spine.map(function(item) {
              var fullPath = base + item.href.replace(/^[^/]*\\.\\.\\//, '');
              var f = zip.file(fullPath) || zip.file(item.href) || zip.file(base + item.href);
              if (!f) return Promise.resolve(null);
              return f.async('string').then(function(html) {
                ordered.push({ path: f.name, href: item.href, content: html });
              });
            })).then(function() {
              return { zip: zip, ordered: ordered.filter(Boolean), base: base, opfPath: opfPath };
            });
          });
        });
      }).then(function(data) {
        setProgress('解析完成，偵測語言…');
        var firstText = data.ordered.length ? stripHtml(data.ordered[0].content) : '';
        // 若抓不到可用文字，改用預設簡體流程（避免整本上傳觸發 4MB 限制），直接走逐章轉換。
        if (!firstText) {
          var lang = 'zh-cn';
          var total = data.ordered.length;
          // 為避免 Vercel 4.5MB payload 限制，單段控制在約 256KB 以內
          var maxChunkBytes = 256 * 1024;
          var apiUrl = '/api/convert-chapter-zh';
          var glossary = {};
          var bilingual = bilingualMode ? bilingualMode.checked : false;
          return data.ordered.reduce(function(p, item, i) {
            return p.then(function() {
              var chunks = splitHtmlChunks(item.content, maxChunkBytes);
              return chunks.reduce(function(prev, chunkHtml, j) {
                return prev.then(function() {
                  var partLabel = chunks.length > 1 ? ' 第 ' + (j + 1) + '/' + chunks.length + ' 段' : '';
                  var pct = Math.round(((i + (j / Math.max(chunks.length, 1))) / total) * 88) + 5;
                  setProgress('轉換中：第 ' + (i + 1) + ' / ' + total + ' 章' + partLabel + '…', false, pct);
                  var body = JSON.stringify({ html: chunkHtml, glossary: glossary, bilingual: bilingual });
                  return fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: body,
                    signal: signal
                  }).then(function(r) { return r.json(); }).then(function(apiRes) {
                    if (apiRes.error) throw new Error(apiRes.error);
                    if (!item.parts) item.parts = [];
                    item.parts.push(apiRes.converted_html);
                    if (apiRes.glossary) glossary = apiRes.glossary;
                  });
                });
              }, Promise.resolve()).then(function() {
                if (item.parts) {
                  item.content = item.parts.join('');
                  delete item.parts;
                }
              });
            });
          }, Promise.resolve()).then(function() {
            setProgress('組裝 epub 中…', false, 93);
            return data.zip.file(data.opfPath).async('string');
          }).then(function(opfStr) {
            setProgress('更新書名與目錄…', false, 96);
            var title = '';
            try {
              var opfDoc = new DOMParser().parseFromString(opfStr, 'text/xml');
              var t = opfDoc.getElementsByTagName('title')[0] || opfDoc.querySelector('*[local-name()="title"]');
              if (t) title = (t.textContent || '').trim();
            } catch(e) {}
            if (!title) title = file.name.replace(/\.epub$/i, '');
            return fetch('/api/convert-text', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ text: title, lang: lang }),
              signal: signal
            }).then(function(r) { return r.json(); }).then(function(res) {
              var convertedTitle = (res.converted && res.converted.trim()) ? res.converted.trim() : title;
              function safe(s) { return (s || '').replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, ' ').trim().slice(0, 80); }
              var safeName = (safe(convertedTitle) || 'book') + '（' + (safe(title) || '') + '）';
              var newOpfStr = opfStr;
              if (convertedTitle) {
                var esc = convertedTitle.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                newOpfStr = opfStr.replace(/(<dc:title[^>]*>)([^<]*)(<\/dc:title>)/gi, '$1' + esc + '$3');
                if (newOpfStr === opfStr) newOpfStr = opfStr.replace(/(<title[^>]*>)([^<]*)(<\/title>)/gi, '$1' + esc + '$3');
              }
              var opfBase = data.opfPath.indexOf('/') >= 0 ? data.opfPath.slice(0, data.opfPath.lastIndexOf('/') + 1) : '';
              var copyrightPath = null;
              var opfWithCopyright = newOpfStr;
              if (newOpfStr.indexOf('nps_copyright') === -1) {
                copyrightPath = opfBase + 'copyright.xhtml';
                opfWithCopyright = newOpfStr
                  .replace(/<\/manifest>/, '  <item id="nps_copyright" href="copyright.xhtml" media-type="application/xhtml+xml"/>\n</manifest>')
                  .replace(/(<spine[^>]*>)(\s*)/, '$1$2  <itemref idref="nps_copyright"/>$2');
              }
              return { opfStr: opfWithCopyright, opfPath: data.opfPath, safeName: safeName, copyrightPath: copyrightPath };
            });
          }).then(function(meta) {
            setProgress('打包 epub 檔案…', false, 98);
            var outZip = new window.JSZip();
            var pathMap = {};
            data.ordered.forEach(function(o) { pathMap[o.path] = o.content; });
            pathMap[meta.opfPath] = meta.opfStr;
            if (meta.copyrightPath) {
              pathMap[meta.copyrightPath] = COPYRIGHT_PAGE_HTML;
            }
            var names = Object.keys(data.zip.files);
            return Promise.all(names.map(function(path) {
              if (pathMap[path]) { outZip.file(path, pathMap[path]); return Promise.resolve(); }
              var entry = data.zip.files[path];
              return entry.async('uint8array').then(function(arr) { outZip.file(path, arr); });
            })).then(function() {
              if (meta.copyrightPath) outZip.file(meta.copyrightPath, COPYRIGHT_PAGE_HTML);
              return outZip.generateAsync({ type: 'blob' });
            }).then(function(blob) { return { blob: blob, meta: meta }; });
          });
        }
        return fetch('/api/detect-lang', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: firstText }),
          signal: signal
        }).then(function(r) { return r.json(); }).then(function(res) {
          if (res.error) throw new Error(res.error);
          var lang = res.language;
          if (lang !== 'en' && lang !== 'zh-cn' && lang !== 'zh') {
            lang = 'zh-cn';
          }
          var total = data.ordered.length;
          // 為避免 Vercel 4.5MB payload 限制，單段控制在約 256KB 以內
          var maxChunkBytes = 256 * 1024;
          var apiUrl = (lang === 'en') ? '/api/translate-chapter' : '/api/convert-chapter-zh';
          var glossary = {};
          var context = [];  // Context Window：章節間傳遞，保持上下文連貫
          var bilingual = bilingualMode ? bilingualMode.checked : false;
          return data.ordered.reduce(function(p, item, i) {
            return p.then(function() {
              var chunks = splitHtmlChunks(item.content, maxChunkBytes);
              return chunks.reduce(function(prev, chunkHtml, j) {
                return prev.then(function() {
                  var partLabel = chunks.length > 1 ? ' 第 ' + (j + 1) + '/' + chunks.length + ' 段' : '';
                  var pct = Math.round(((i + (j / Math.max(chunks.length, 1))) / total) * 88) + 5;
                  setProgress('轉換中：第 ' + (i + 1) + ' / ' + total + ' 章' + partLabel + '…', false, pct);
                  var body = JSON.stringify({ html: chunkHtml, glossary: glossary, context: context, bilingual: bilingual });
                  return fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: body,
                    signal: signal
                  }).then(function(r) { return r.json(); }).then(function(apiRes) {
                    if (apiRes.error) throw new Error(apiRes.error);
                    if (!item.parts) item.parts = [];
                    item.parts.push((lang === 'en') ? apiRes.translated_html : apiRes.converted_html);
                    if (apiRes.glossary) glossary = apiRes.glossary;
                    if (apiRes.context) context = apiRes.context;  // 更新 Context Window
                  });
                });
              }, Promise.resolve()).then(function() {
                if (item.parts) {
                  item.content = item.parts.join('');
                  delete item.parts;
                }
              });
            });
          }, Promise.resolve()).then(function() {
            setProgress('組裝 epub 中…', false, 93);
            return data.zip.file(data.opfPath).async('string');
          }).then(function(opfStr) {
            setProgress('更新書名與目錄…', false, 96);
            var title = '';
            try {
              var opfDoc = new DOMParser().parseFromString(opfStr, 'text/xml');
              var t = opfDoc.getElementsByTagName('title')[0] || opfDoc.querySelector('*[local-name()="title"]');
              if (t) title = (t.textContent || '').trim();
            } catch(e) {}
            if (!title) title = file.name.replace(/\\.epub$/i, '');
            return fetch('/api/convert-text', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ text: title, lang: lang }),
              signal: signal
            }).then(function(r) { return r.json(); }).then(function(res) {
              var convertedTitle = (res.converted && res.converted.trim()) ? res.converted.trim() : title;
              function safe(s) { return (s || '').replace(/[<>:"/\\\\|?*]/g, '').replace(/\\s+/g, ' ').trim().slice(0, 80); }
              var safeName = (safe(convertedTitle) || 'book') + '（' + (safe(title) || '') + '）';
              var newOpfStr = opfStr;
              if (convertedTitle) {
                var esc = convertedTitle.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                newOpfStr = opfStr.replace(/(<dc:title[^>]*>)([^<]*)(<\\/dc:title>)/gi, '$1' + esc + '$3');
                if (newOpfStr === opfStr) newOpfStr = opfStr.replace(/(<title[^>]*>)([^<]*)(<\\/title>)/gi, '$1' + esc + '$3');
              }
              var opfBase = data.opfPath.indexOf('/') >= 0 ? data.opfPath.slice(0, data.opfPath.lastIndexOf('/') + 1) : '';
              var copyrightPath = null;
              var opfWithCopyright = newOpfStr;
              if (newOpfStr.indexOf('nps_copyright') === -1) {
                copyrightPath = opfBase + 'copyright.xhtml';
                opfWithCopyright = newOpfStr
                  .replace(/<\\/manifest>/, '  <item id="nps_copyright" href="copyright.xhtml" media-type="application/xhtml+xml"\\/>\\n</manifest>')
                  .replace(/(<spine[^>]*>)(\\s*)/, '$1$2  <itemref idref="nps_copyright"\\/>$2');
              }
              return { opfStr: opfWithCopyright, opfPath: data.opfPath, safeName: safeName, copyrightPath: copyrightPath };
            });
          }).then(function(meta) {
            setProgress('打包 epub 檔案…', false, 98);
            var outZip = new window.JSZip();
            var pathMap = {};
            data.ordered.forEach(function(o) { pathMap[o.path] = o.content; });
            pathMap[meta.opfPath] = meta.opfStr;
            if (meta.copyrightPath) {
              pathMap[meta.copyrightPath] = COPYRIGHT_PAGE_HTML;
            }
            var names = Object.keys(data.zip.files);
            return Promise.all(names.map(function(path) {
              if (pathMap[path]) { outZip.file(path, pathMap[path]); return Promise.resolve(); }
              var entry = data.zip.files[path];
              return entry.async('uint8array').then(function(arr) { outZip.file(path, arr); });
            })).then(function() {
              if (meta.copyrightPath) outZip.file(meta.copyrightPath, COPYRIGHT_PAGE_HTML);
              return outZip.generateAsync({ type: 'blob' });
            }).then(function(blob) { return { blob: blob, meta: meta }; });
          }).then(function(result) {
            var blob = result.blob;
            var meta = result.meta;
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = (meta.safeName || 'book') + '.epub';
            a.click();
            URL.revokeObjectURL(a.href);
            setProgress('✓ 書籍轉換完成，已開始下載！', false, 100);
            cancelBtn.style.display = 'none';
            btn.disabled = false;
          });
        });
      }).catch(function(err) {
        if (err.name === 'AbortError') {
          resetForm();
          return;
        }
        setProgress('錯誤：' + (err.message || err), true);
        cancelBtn.style.display = 'none';
        btn.disabled = false;
      });
    });
  })();
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    try:
        return render_template_string(
            HTML,
            download_url=None,
            download_name=None,
            error=request.args.get("error"),
        )
    except Exception as e:
        app.logger.exception("index failed")
        return jsonify({"error": str(e)}), 500


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
        # 使用短檔名避免檔案系統檔名過長（例如 255 bytes）導致 Errno 36
        final_name = f"{job_id}_tw.epub"
        final_path = OUTPUT_DIR / final_name
        run_conversion(str(input_path), str(final_path))
        original_stem = Path(f.filename).stem
        try:
            import ebooklib
            from ebooklib import epub as epub_lib
            book = epub_lib.read_epub(str(final_path))
            tl = book.get_metadata("DC", "title")
            converted_title = (tl[0][0] if tl and tl[0] else "") or original_stem
        except Exception:
            converted_title = original_stem
        from urllib.parse import urlencode
        q = urlencode({"original": original_stem, "converted": converted_title})
        return redirect(url_for("download", filename=final_name) + "?" + q)
    except Exception as e:
        return redirect(url_for("index", error=f"轉換失敗：{e}"))
    finally:
        if input_path.exists():
            try:
                input_path.unlink()
            except Exception:
                pass


# ---------- 分章轉換 API（給英文書在 Vercel 60s 限制下用）----------

@app.route("/api/convert-text", methods=["POST"])
def api_convert_text():
    """POST JSON: text, lang (zh or en). Returns converted title/short text for filename or metadata."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        text = (data.get("text") or "").strip()[:500]
        lang = (data.get("lang") or "zh").strip().lower()
        if not text:
            return jsonify({"converted": ""})
        sys.path.insert(0, str(ROOT))
        if lang == "en":
            from translator_en import translate_english_to_traditional
            engine = os.environ.get("BOOK_TRANSLATION_ENGINE", "google")
            out, _ = translate_english_to_traditional(text, glossary={}, engine=engine)
        else:
            from converter_zh import convert_simplified_to_traditional
            out = convert_simplified_to_traditional(text)
        return jsonify({"converted": (out or "").strip()})
    except Exception as e:
        return jsonify({"error": str(e), "converted": ""}), 500


@app.route("/api/detect-lang", methods=["POST"])
def api_detect_lang():
    """POST JSON: text. Returns language: en, zh-cn, or zh."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        text = (data.get("text") or "").strip()[:20000]
        if not text:
            return jsonify({"error": "missing text"}), 400
        sys.path.insert(0, str(ROOT))
        from main import detect_language_from_text
        lang = detect_language_from_text(text)
        return jsonify({"language": lang})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/translate-chapter", methods=["POST"])
def api_translate_chapter():
    """POST JSON: html, glossary, context(list), bilingual(bool). EN to ZH-TW."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        html = data.get("html") or ""
        glossary = data.get("glossary") or {}
        context = data.get("context") or []   # Context Window（章節間傳遞）
        bilingual = bool(data.get("bilingual", False))
        if not isinstance(glossary, dict):
            glossary = {}
        if not isinstance(context, list):
            context = []
        if not html.strip():
            return jsonify({"translated_html": html, "glossary": glossary, "context": context})

        sys.path.insert(0, str(ROOT))
        from epub_io import get_text_from_html, set_text_in_html, set_bilingual_html
        from translator_en import translate_english_to_traditional

        text = get_text_from_html(html)
        if not text.strip():
            return jsonify({"translated_html": html, "glossary": glossary, "context": context})
        lines = text.split("\n")
        text_to_convert = "\n".join(ln for ln in lines if ln.strip())
        if not text_to_convert.strip():
            return jsonify({"translated_html": html, "glossary": glossary, "context": context})
        engine = os.environ.get("BOOK_TRANSLATION_ENGINE", "google")
        # 3-tuple 回傳，接收更新後的 context_window
        new_text, glossary, context = translate_english_to_traditional(
            text_to_convert, glossary=glossary, engine=engine, context_window=context
        )
        raw_paras = [p.strip() for p in re.split(r"\n+", new_text) if p.strip()]
        new_paras = [None] * len(lines)
        j = 0
        last_assigned_idx = None
        for i in range(len(lines)):
            if lines[i].strip():
                if j < len(raw_paras):
                    new_paras[i] = raw_paras[j]
                    j += 1
                    last_assigned_idx = i
        if j < len(raw_paras) and last_assigned_idx is not None:
            tail = "\n".join(raw_paras[j:])
            new_paras[last_assigned_idx] = (new_paras[last_assigned_idx] or "") + ("\n" + tail if tail else "")
        if bilingual:
            new_html = set_bilingual_html(html, new_paras)
        else:
            new_html = set_text_in_html(html, new_paras)
        return jsonify({"translated_html": new_html, "glossary": glossary, "context": context})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/convert-chapter-zh", methods=["POST"])
def api_convert_chapter_zh():
    """POST JSON: html, glossary, bilingual(bool). Simplified to TW traditional."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        html = data.get("html") or ""
        glossary = data.get("glossary") or {}
        bilingual = bool(data.get("bilingual", False))
        if not isinstance(glossary, dict):
            glossary = {}
        if not html.strip():
            return jsonify({"converted_html": html, "glossary": glossary})

        sys.path.insert(0, str(ROOT))
        from epub_io import get_text_from_html, set_text_in_html, set_bilingual_html
        from converter_zh import convert_simplified_to_traditional

        text = get_text_from_html(html)
        if not text.strip():
            return jsonify({"converted_html": html, "glossary": glossary})
        lines = text.split("\n")
        text_to_convert = "\n".join(ln for ln in lines if ln.strip())
        if not text_to_convert.strip():
            return jsonify({"converted_html": html, "glossary": glossary})
        new_text = convert_simplified_to_traditional(text_to_convert)
        for k in sorted(glossary.keys(), key=lambda x: -len(x)):
            new_text = new_text.replace(k, glossary[k])
        raw_paras = [p.strip() for p in re.split(r"\n+", new_text) if p.strip()]
        new_paras = [None] * len(lines)
        j = 0
        last_assigned_idx = None
        for i in range(len(lines)):
            if lines[i].strip():
                if j < len(raw_paras):
                    new_paras[i] = raw_paras[j]
                    j += 1
                    last_assigned_idx = i
        if j < len(raw_paras) and last_assigned_idx is not None:
            tail = "\n".join(raw_paras[j:])
            new_paras[last_assigned_idx] = (new_paras[last_assigned_idx] or "") + ("\n" + tail if tail else "")
        if bilingual:
            new_html = set_bilingual_html(html, new_paras)
        else:
            new_html = set_text_in_html(html, new_paras)
        return jsonify({"converted_html": new_html, "glossary": glossary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download(filename: str):
    path = OUTPUT_DIR / filename
    if not path.is_file():
        return redirect(url_for("index", error="檔案不存在或已清除"))
    # 檔名格式：翻譯名稱（原文名稱）.epub
    converted = (request.args.get("converted") or "").strip()
    original = (request.args.get("original") or "").strip()
    if converted or original:
        def safe(s):
            return (s or "").replace("\\", "").replace("/", "").replace(":", "").replace("*", "").replace("?", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "").strip()[:80]
        download_name = (safe(converted) or "book") + "（" + (safe(original) or "") + "）.epub"
    else:
        download_name = path.name
        if len(filename) > 9 and filename[8:9] == "_":
            download_name = filename[9:]
    return send_file(path, as_attachment=True, download_name=download_name)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("書籍轉換工具 - 網頁版")
    print(f"請在瀏覽器開啟: http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)