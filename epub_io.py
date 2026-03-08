# -*- coding: utf-8 -*-
"""
EPUB 讀取與寫出：萃取 HTML 內文、套用轉換後寫回 .epub
"""

import html
import re
from pathlib import Path
from typing import Callable, List, Tuple

from ebooklib import epub
from bs4 import BeautifulSoup


def get_text_from_html(html: str) -> str:
    """從 HTML 字串萃取出純文字（保留段落結構）。"""
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text(separator="\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def set_text_in_html(html: str, new_text: str) -> str:
    """
    將新文字填回 HTML。策略：依序把每個「文字區塊」替換為對應的新段落。
    若段落數不一致，則整段 body 替換為單一 <p>。
    """
    if not html or not new_text:
        return html
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not body:
        return html
    # 取得所有葉節點文字區塊（依序）
    blocks_old: List[str] = []
    for tag in body.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"]):
        t = tag.get_text(strip=True)
        if t:
            blocks_old.append(t)
    new_paras = [p.strip() for p in new_text.split("\n") if p.strip()]
    if len(blocks_old) != len(new_paras):
        # 段落數不同：整段 body 用單一 div 包住新內容
        new_html = "<div>" + "".join(f"<p>{html.escape(p)}</p>" for p in new_paras) + "</div>"
        body.clear()
        body.append(BeautifulSoup(new_html, "lxml"))
        return str(soup)
    # 一一替換
    idx = 0
    for tag in body.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"]):
        t = tag.get_text(strip=True)
        if t and idx < len(new_paras):
            tag.string = new_paras[idx]
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
        if item.get_type() != epub.ITEM_DOCUMENT:
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
        if item.get_type() != epub.ITEM_DOCUMENT:
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
        if item.get_type() != epub.ITEM_DOCUMENT:
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
        if item.get_type() != epub.ITEM_DOCUMENT:
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

    epub.write_epub(str(output_path), book, {})
