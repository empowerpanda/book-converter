# -*- coding: utf-8 -*-
"""
EPUB 讀取與寫出：萃取 HTML 內文、套用轉換後寫回 .epub
"""

import html as _html
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup, NavigableString, Tag

# 視為區塊的標籤；只處理「葉子」區塊（內含不再有這些標籤），避免巢狀重複導致段落錯亂、內容消失
BLOCK_TAG_NAMES = ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"]

# 版權頁內容（轉換／翻譯書籍時插入為第一頁）
COPYRIGHT_PAGE_HTML = """<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="zh-TW" xml:lang="zh-TW">
<head><meta charset="utf-8"/><title>版權頁</title></head>
<body>
  <p>本書籍轉換工具，由「熊貓原點有限公司」維護。</p>
  <p>若有任何建議或靈感，歡迎聯繫 panda@nps.tw</p>
</body>
</html>"""


def _is_leaf_block(tag: Tag) -> bool:
    """若 tag 本身是區塊標籤，且內部沒有其他區塊標籤（即為葉子），回傳 True。"""
    if tag.name not in BLOCK_TAG_NAMES:
        return False
    for child in tag.descendants:
        if child is tag:
            continue
        if isinstance(child, Tag) and child.name in BLOCK_TAG_NAMES:
            return False
    return True


def _get_leaf_blocks_in_order(body) -> list:
    """依文件順序回傳所有「葉子區塊」標籤。"""
    all_blocks = body.find_all(BLOCK_TAG_NAMES)
    return [t for t in all_blocks if _is_leaf_block(t)]


def get_text_from_html(html: str) -> str:
    """從 HTML 萃取出純文字，一個葉子區塊一行，與 set_text_in_html 對應。"""
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    body = soup.find("body")
    if not body:
        text = soup.get_text(separator="\n")
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    leaf_blocks = _get_leaf_blocks_in_order(body)
    lines = [tag.get_text(separator=" ", strip=True) for tag in leaf_blocks]
    return "\n".join(lines)


def _split_by_ratio(text: str, ratios: List[float]) -> List[str]:
    """依比例把 text 切成 len(ratios) 段；盡量在換行處切，避免從字中間切斷。"""
    if not ratios or not text:
        return [text] if text else []
    total = sum(ratios)
    if total <= 0:
        return [text]
    out: List[str] = []
    start = 0
    for i, r in enumerate(ratios):
        if i == len(ratios) - 1:
            out.append(text[start:])
            break
        end = start + max(0, int(round(len(text) * r / total)))
        # 若有換行，盡量在換行邊界切，避免切在字中間
        if "\n" in text:
            # 優先：從 end 往後找第一個 \n，若不太遠就用它
            next_nl = text.find("\n", end)
            if 0 <= next_nl < end + 80:
                end = next_nl + 1
            else:
                # 否則從 end 往前找最後一個 \n
                prev_nl = text.rfind("\n", start, end + 1)
                if prev_nl >= start:
                    end = prev_nl + 1
        out.append(text[start:end])
        start = end
    return out


def set_text_in_html(html: str, new_text_or_paras: Union[str, List[Optional[str]]]) -> str:
    """
    將新文字填回 HTML。只處理「葉子區塊」，一區塊對應一行。
    區塊內的 <a href="...">、<img src="..."> 僅保留不更動（內部章節連結、錨點、外部連結皆保留）。
    new_text_or_paras: 若為 List[Optional[str]] 且長度等於葉子區塊數，則依序對應填回
      （None 表示不修改該區塊，保留圖片等）；若為 str 則沿用舊邏輯（空區塊會設為不修改）。
    """
    if not html:
        return html
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not body:
        return html

    leaf_blocks = _get_leaf_blocks_in_order(body)
    blocks_old: List[str] = [tag.get_text(separator=" ", strip=True) for tag in leaf_blocks]
    n_blocks = len(leaf_blocks)
    if n_blocks == 0:
        return html

    if isinstance(new_text_or_paras, list):
        new_paras = (new_text_or_paras + [None] * n_blocks)[:n_blocks]
    else:
        new_text = new_text_or_paras
        if not new_text:
            return html
        raw_paras = [p.strip() for p in re.split(r"\n+", new_text) if p.strip()]
        if not raw_paras:
            return html
        if len(raw_paras) > n_blocks:
            merged = raw_paras[: n_blocks - 1]
            merged.append("".join(raw_paras[n_blocks - 1 :]))
            new_paras = merged
        elif len(raw_paras) < n_blocks:
            combined = "\n".join(raw_paras)
            if not combined.strip():
                new_paras = raw_paras + [""] * (n_blocks - len(raw_paras))
            else:
                ratios = [float(max(1, len(b))) for b in blocks_old]
                new_paras = _split_by_ratio(combined, ratios)
        else:
            new_paras = raw_paras
        new_paras = (new_paras + [""] * n_blocks)[:n_blocks]
        for i in range(n_blocks):
            if not blocks_old[i].strip():
                new_paras[i] = None

    for tag, new_para, old_text in zip(leaf_blocks, new_paras, blocks_old):
        if new_para is None:
            continue  # 保留區塊原樣（含圖片）
        # 只替換內文，不更動 tag 的 style/class（標題置中等樣式會保留）
        if not new_para:
            tag.clear()
            continue
        if tag.find("img") is None and tag.find("a") is None:
            tag.clear()
            tag.append(NavigableString(new_para))
        else:
            # 區塊內有 img 或 a（圖片、內部章節連結、外部連結）：只替換文字節點，保留標籤與 href/src
            text_nodes = [n for n in tag.descendants if isinstance(n, NavigableString) and str(n).strip()]
            if len(text_nodes) == 1:
                text_nodes[0].replace_with(new_para)
            elif len(text_nodes) > 1:
                lengths = [len(str(n).strip()) for n in text_nodes]
                total_len = sum(lengths)
                if total_len > 0:
                    segments = _split_by_ratio(new_para, [float(l) for l in lengths])
                    for node, seg in zip(text_nodes, segments):
                        node.replace_with(seg)
            else:
                tag.clear()
                tag.append(NavigableString(new_para))
    return str(soup)


def add_copyright_page(book) -> None:
    """在書籍最前面加入版權頁（spine 第一項），開啟時為第一頁。"""
    copyright_item = epub.EpubHtml(
        title="版權頁",
        file_name="copyright.xhtml",
        lang="zh-TW",
    )
    copyright_item.id = "nps_copyright"
    copyright_item.set_content(COPYRIGHT_PAGE_HTML.encode("utf-8"))
    book.add_item(copyright_item)
    book.spine.insert(0, (copyright_item.id, "yes"))


def process_epub(
    input_path: str,
    output_path: str,
    text_transform: Callable[[str], str],
) -> None:
    """
    讀取 EPUB，對每個 text/html 項目套用 text_transform，寫出到 output_path。
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    book = epub.read_epub(str(input_path))

    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        try:
            html = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            try:
                html = item.get_content().decode("latin-1", errors="replace")
            except Exception:
                continue
        text = get_text_from_html(html)
        if not text.strip():
            continue
        lines = text.split("\n")
        text_to_convert = "\n".join(ln for ln in lines if ln.strip())
        if not text_to_convert.strip():
            continue
        new_text = text_transform(text_to_convert)
        raw_paras = [p.strip() for p in re.split(r"\n+", new_text) if p.strip()]
        new_paras: List[Optional[str]] = [None] * len(lines)
        j = 0
        last_assigned_idx: Optional[int] = None
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
        item.set_content(new_html.encode("utf-8"))

    # 書名 metadata 一併轉換
    try:
        title_list = book.get_metadata("DC", "title")
        if title_list and title_list[0]:
            old_title = title_list[0][0]
            if isinstance(old_title, str) and old_title.strip():
                book.set_metadata("DC", "title", text_transform(old_title))
    except Exception:
        pass
    add_copyright_page(book)
    epub.write_epub(str(output_path), book, {})


def get_epub_text_sample(input_path: str, max_chars: int = 50000) -> str:
    """
    從 EPUB 萃取出前 max_chars 字，供語言偵測或翻譯前分析用。
    """
    input_path = Path(input_path).resolve()
    book = epub.read_epub(str(input_path))
    chunks: List[str] = []
    total = 0
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        try:
            html = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            continue
        text = get_text_from_html(html)
        if text:
            chunks.append(text)
            total += len(text)
            if total >= max_chars:
                break
    return "\n\n".join(chunks)[:max_chars]


def get_epub_chapters(input_path: str) -> List[Tuple[str, str]]:
    """
    回傳 [(chapter_id, html_content), ...]，用於逐章翻譯並寫回。
    """
    input_path = Path(input_path).resolve()
    book = epub.read_epub(str(input_path))
    out: List[Tuple[str, str]] = []
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        try:
            html = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            try:
                html = item.get_content().decode("latin-1", errors="replace")
            except Exception:
                continue
        out.append((item.get_name(), html))
    return out


def process_epub_english_to_traditional(
    input_path: str,
    output_path: str,
    engine: str = "google",
) -> None:
    """
    讀取英文 EPUB，逐段翻譯成繁體中文，整書共用詞彙表以保持人名／術語一致，寫出 .epub。
    """
    from translator_en import translate_english_to_traditional

    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    book = epub.read_epub(str(input_path))
    glossary: dict = {}

    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        try:
            html = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            try:
                html = item.get_content().decode("latin-1", errors="replace")
            except Exception:
                continue
        text = get_text_from_html(html)
        if not text.strip():
            continue
        lines = text.split("\n")
        text_to_convert = "\n".join(ln for ln in lines if ln.strip())
        if not text_to_convert.strip():
            continue
        new_text, glossary = translate_english_to_traditional(text_to_convert, glossary=glossary, engine=engine)
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
        item.set_content(new_html.encode("utf-8"))

    # 書名 metadata 一併翻譯
    try:
        title_list = book.get_metadata("DC", "title")
        if title_list and title_list[0]:
            old_title = title_list[0][0]
            if isinstance(old_title, str) and old_title.strip():
                new_title, _ = translate_english_to_traditional(old_title, glossary=glossary, engine=engine)
                book.set_metadata("DC", "title", new_title)
    except Exception:
        pass
    add_copyright_page(book)
    epub.write_epub(str(output_path), book, {})
