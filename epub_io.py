# -*- coding: utf-8 -*-
"""
EPUB 讀取與寫出：萃取 HTML 內文、套用轉換後寫回 .epub
"""

import html as _html
import re
from pathlib import Path
from typing import Callable, List, Tuple

from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup, NavigableString


def get_text_from_html(html: str) -> str:
    """從 HTML 字串萃取出純文字（保留段落結構，一個區塊一行）。"""
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text(separator="\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_by_ratio(text: str, ratios: List[float]) -> List[str]:
    """依比例把 text 切成 len(ratios) 段，最後一段取到結尾避免遺漏。"""
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
        out.append(text[start:end])
        start = end
    return out


def set_text_in_html(html: str, new_text: str) -> str:
    """
    將新文字填回 HTML：
    - 只替換「文字節點」，保留標籤與屬性（粗體、置中、圖片等）。
    - 段落數與原文對齊，避免過度換行（多出的合併、不足的用最後一段補）。
    """
    if not html or not new_text:
        return html
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not body:
        return html

    block_tags = body.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"])
    blocks_old: List[str] = []
    for tag in block_tags:
        t = tag.get_text(strip=True)
        if t:
            blocks_old.append(t)

    # 依單一換行切，再合併多餘換行成一段，使段落數與原文一致
    raw_paras = [p.strip() for p in re.split(r"\n+", new_text) if p.strip()]
    n_blocks = len(blocks_old)
    if n_blocks == 0 or not raw_paras:
        return html
    if len(raw_paras) > n_blocks:
        # 多出的段落合併到最後一段（不強制加空格，避免中英混排多空格）
        merged = raw_paras[: n_blocks - 1]
        merged.append("".join(raw_paras[n_blocks - 1 :]))
        new_paras = merged
    elif len(raw_paras) < n_blocks:
        new_paras = raw_paras + [""] * (n_blocks - len(raw_paras))
    else:
        new_paras = raw_paras

    idx = 0
    for tag in block_tags:
        t = tag.get_text(strip=True)
        if not t or idx >= len(new_paras):
            if t:
                idx += 1
            continue
        new_para = new_paras[idx]
        # 只替換文字節點，保留 <strong>/<em>/<img> 等
        text_nodes = [n for n in tag.descendants if isinstance(n, NavigableString) and str(n).strip()]
        if not text_nodes:
            idx += 1
            continue
        if len(text_nodes) == 1:
            text_nodes[0].replace_with(new_para)
        else:
            lengths = [len(str(n).strip()) for n in text_nodes]
            total_len = sum(lengths)
            if total_len > 0:
                ratios = [float(l) for l in lengths]
                segments = _split_by_ratio(new_para, ratios)
                for node, seg in zip(text_nodes, segments):
                    node.replace_with(seg)
        idx += 1
    return str(soup)


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
        new_text = text_transform(text)
        new_html = set_text_in_html(html, new_text)
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
        new_text, glossary = translate_english_to_traditional(text, glossary=glossary, engine=engine)
        new_html = set_text_in_html(html, new_text)
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
    epub.write_epub(str(output_path), book, {})
