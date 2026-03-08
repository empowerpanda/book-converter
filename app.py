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
    #progress { margin-top: 1rem; font-size: 0.9rem; color: #555; }
    #progress.err { color: #991b1b; }
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
</head>
<body>
  <h1>書籍轉換工具</h1>
  <p class="sub">上傳 .epub（簡體或英文），自動轉成臺灣繁體 .epub 並可下載。</p>

  <div class="card">
    <form id="form" method="post" action="/convert" enctype="multipart/form-data">
      <label for="file">選擇 .epub 檔案</label>
      <input type="file" name="file" id="file" accept=".epub" required>
      <button type="submit" id="btn">開始轉換</button>
      <p id="progress"></p>
    </form>
    <p class="msg info" style="margin-top:1rem;">
      支援：簡體→臺灣繁體（含用語轉換）；英文→繁體中文（整書術語一致）。簡體與英文書皆會逐章轉換，大書也不受單次時間限制；<strong>整本書的語意、用詞會統一</strong>（英文：人名／術語 glossary 跨章傳遞；簡體：兩岸用語表整書統一套用）。
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
  (function() {
    var form = document.getElementById('form');
    var fileInput = document.getElementById('file');
    var btn = document.getElementById('btn');
    var progress = document.getElementById('progress');

    function setProgress(txt, isErr) {
      progress.textContent = txt;
      progress.className = isErr ? 'msg err' : '';
    }

    function stripHtml(html) {
      var div = document.createElement('div');
      div.innerHTML = html;
      return (div.textContent || div.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 15000);
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
        if (id && (mt.indexOf('html') >= 0 || /\.(x?html?)$/i.test(href))) manifest[id] = href;
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

    form.addEventListener('submit', function(e) {
      e.preventDefault();
      var file = fileInput.files[0];
      if (!file) return;
      btn.disabled = true;
      setProgress('讀取檔案並偵測語言…');

      function doClassicSubmit() {
        setProgress('');
        form.submit();
      }

      function readAsArrayBuffer(f) {
        return new Promise(function(resolve, reject) {
          var r = new FileReader();
          r.onload = function() { resolve(r.result); };
          r.onerror = reject;
          r.readAsArrayBuffer(f);
        });
      }

      readAsArrayBuffer(file).then(function(ab) {
        return window.JSZip ? Promise.resolve(window.JSZip) : Promise.reject(new Error('JSZip 未載入'));
      }).then(function(JSZip) {
        return JSZip.loadAsync(ab);
      }).then(function(zip) {
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
        var firstText = data.ordered.length ? stripHtml(data.ordered[0].content) : '';
        if (!firstText) { doClassicSubmit(); return; }
        return fetch('/api/detect-lang', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: firstText })
        }).then(function(r) { return r.json(); }).then(function(res) {
          if (res.error) throw new Error(res.error);
          var lang = res.language;
          if (lang !== 'en' && lang !== 'zh-cn' && lang !== 'zh') {
            doClassicSubmit();
            return;
          }
          var total = data.ordered.length;
          var apiUrl = (lang === 'en') ? '/api/translate-chapter' : '/api/convert-chapter-zh';
          var glossary = {};
          return data.ordered.reduce(function(p, item, i) {
            return p.then(function() {
              setProgress('轉換中：第 ' + (i + 1) + ' / ' + total + ' 章…');
              var body = JSON.stringify({ html: item.content, glossary: glossary });
              return fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body
              }).then(function(r) { return r.json(); }).then(function(apiRes) {
                if (apiRes.error) throw new Error(apiRes.error);
                item.content = (lang === 'en') ? apiRes.translated_html : apiRes.converted_html;
                if (apiRes.glossary) glossary = apiRes.glossary;
              });
            });
          }, Promise.resolve()).then(function() {
            setProgress('組裝 epub 中…');
            return data.zip.file(data.opfPath).async('string');
          }).then(function(opfStr) {
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
              body: JSON.stringify({ text: title, lang: lang })
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
              return { opfStr: newOpfStr, opfPath: data.opfPath, safeName: safeName };
            });
          }).then(function(meta) {
            var outZip = new window.JSZip();
            var pathMap = {};
            data.ordered.forEach(function(o) { pathMap[o.path] = o.content; });
            pathMap[meta.opfPath] = meta.opfStr;
            var names = Object.keys(data.zip.files);
            return Promise.all(names.map(function(path) {
              if (pathMap[path]) { outZip.file(path, pathMap[path]); return Promise.resolve(); }
              var entry = data.zip.files[path];
              return entry.async('uint8array').then(function(arr) { outZip.file(path, arr); });
            })).then(function() { return outZip.generateAsync({ type: 'blob' }); }).then(function(blob) { return { blob: blob, meta: meta }; });
          }).then(function(result) {
            var blob = result.blob;
            var meta = result.meta;
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = (meta.safeName || 'book') + '.epub';
            a.click();
            URL.revokeObjectURL(a.href);
            setProgress('下載已開始。');
            btn.disabled = false;
          });
        });
      }).catch(function(err) {
        setProgress('錯誤：' + (err.message || err), true);
        btn.disabled = false;
      });
    });
  })();
  </script>
</body>
</html>


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
        out_path = run_conversion(str(input_path))
        out_name = Path(out_path).name
        final_name = f"{job_id}_{Path(out_path).name}"
        final_path = OUTPUT_DIR / final_name
        import shutil
        shutil.move(out_path, str(final_path))
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
    """POST JSON { \"text\": \"...\", \"lang\": \"zh\" | \"en\" }，回傳轉換／翻譯後的書名或短句（用於檔名、章節名、metadata）。"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        text = (data.get("text") or "").strip()[:500]
        lang = (data.get("lang") or "zh").strip().lower()
        if not text:
            return jsonify({"converted": ""})
        sys.path.insert(0, str(ROOT))
        if lang == "en":
            from translator_en import translate_english_to_traditional
            out, _ = translate_english_to_traditional(text, glossary={}, engine="google")
        else:
            from converter_zh import convert_simplified_to_traditional
            out = convert_simplified_to_traditional(text)
        return jsonify({"converted": (out or "").strip()})
    except Exception as e:
        return jsonify({"error": str(e), "converted": ""}), 500


@app.route("/api/detect-lang", methods=["POST"])
def api_detect_lang():
    """POST JSON { \"text\": \"...\" }，回傳 { \"language\": \"en\" | \"zh-cn\" | \"zh\" }。"""
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
    """POST JSON { \"html\": \"...\", \"glossary\": {} }。英文→繁中，整書人名／術語一致由 glossary 在章節間傳遞並更新後回傳。"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        html = data.get("html") or ""
        glossary = data.get("glossary") or {}
        if not isinstance(glossary, dict):
            glossary = {}
        if not html.strip():
            return jsonify({"translated_html": html, "glossary": glossary})

        sys.path.insert(0, str(ROOT))
        from epub_io import get_text_from_html, set_text_in_html
        from translator_en import translate_english_to_traditional

        text = get_text_from_html(html)
        if not text.strip():
            return jsonify({"translated_html": html, "glossary": glossary})
        lines = text.split("\n")
        text_to_convert = "\n".join(ln for ln in lines if ln.strip())
        if not text_to_convert.strip():
            return jsonify({"translated_html": html, "glossary": glossary})
        new_text, glossary = translate_english_to_traditional(text_to_convert, glossary=glossary, engine="google")
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
        new_html = set_text_in_html(html, new_paras)
        return jsonify({"translated_html": new_html, "glossary": glossary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/convert-chapter-zh", methods=["POST"])
def api_convert_chapter_zh():
    """POST JSON { \"html\": \"...\", \"glossary\": {} }。簡體→臺灣繁體＋兩岸用語；glossary 為整書統一用詞（簡→繁）可選覆寫，會原樣回傳供下一章使用。"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        html = data.get("html") or ""
        glossary = data.get("glossary") or {}
        if not isinstance(glossary, dict):
            glossary = {}
        if not html.strip():
            return jsonify({"converted_html": html, "glossary": glossary})

        sys.path.insert(0, str(ROOT))
        from epub_io import get_text_from_html, set_text_in_html
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