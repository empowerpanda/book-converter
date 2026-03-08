# -*- coding: utf-8 -*-
"""
書籍轉換工具 CLI：
- 簡體書 → 臺灣繁體（字體 + 語意／用語，如 酸奶→優格）
- 英文書 → 繁體中文（段落翻譯、人名／術語整書一致）
輸出一律為 .epub。
"""

import sys
from pathlib import Path

# 依序嘗試載入依賴，方便給出明確錯誤
try:
    from langdetect import detect, LangDetectException
except ImportError:
    detect = None
    LangDetectException = Exception

from epub_io import (
    get_epub_text_sample,
    process_epub,
    process_epub_english_to_traditional,
)


def detect_language_from_text(sample: str, max_chars: int = 15000) -> str:
    """
    從一段文字偵測主要語言。回傳 'zh-cn'、'zh'、'en' 等。
    """
    sample = (sample or "")[:max_chars]
    if not sample.strip():
        return "unknown"
    if detect is None:
        # 啟發：若多為 CJK 且出現簡體特徵（如 国、说、这）則判簡體
        for c in ["国", "说", "这", "会", "过", "时", "对", "发", "们"]:
            if c in sample:
                return "zh-cn"
        return "zh"
    try:
        lang = detect(sample)
    except LangDetectException:
        lang = "unknown"
    if lang == "zh-cn":
        return "zh-cn"
    if lang == "zh-tw" or lang == "zh-hk" or lang == "zh":
        return "zh"
    if lang == "en":
        return "en"
    return lang


def detect_language_from_epub(input_path: str) -> str:
    """從 EPUB 取樣內文偵測主要語言。"""
    sample = get_epub_text_sample(input_path, max_chars=15000)
    return detect_language_from_text(sample)


def convert_simplified_epub(input_path: str, output_path: str) -> None:
    """簡體 EPUB → 臺灣繁體（字體 + 兩岸用語）。"""
    from converter_zh import convert_simplified_to_traditional

    process_epub(input_path, output_path, convert_simplified_to_traditional)


def convert_english_epub(input_path: str, output_path: str, engine: str = "google") -> None:
    """英文 EPUB → 繁體中文（段落翻譯、術語一致）。"""
    process_epub_english_to_traditional(input_path, output_path, engine=engine)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python main.py <輸入檔案.epub> [輸出檔案.epub]")
        print("  - 若省略輸出，將在輸入檔名後加 _tw.epub 作為輸出。")
        print("  - 支援：簡體中文 → 臺灣繁體（含語意轉換）；英文 → 繁體中文（整書術語一致）。")
        sys.exit(1)

    input_path = Path(sys.argv[1]).resolve()
    if not input_path.exists():
        print(f"錯誤：找不到檔案 {input_path}")
        sys.exit(2)
    if input_path.suffix.lower() != ".epub":
        print("警告：輸入副檔名不是 .epub，仍會嘗試以 EPUB 讀取。")

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2]).resolve()
    else:
        output_path = input_path.parent / f"{input_path.stem}_tw.epub"

    # 偵測語言
    print("正在偵測語言…")
    lang = detect_language_from_epub(str(input_path))
    print(f"偵測結果: {lang}")

    if lang == "zh-cn":
        print("辨識為簡體中文，進行簡體→臺灣繁體轉換（字體＋兩岸用語）。")
        convert_simplified_epub(str(input_path), str(output_path))
    elif lang == "en":
        print("辨識為英文，進行英文→繁體中文翻譯（段落順句、人名／術語一致）。")
        convert_english_epub(str(input_path), str(output_path))
    elif lang in ("zh", "zh-tw", "zh-hk"):
        print("辨識為繁體或混合中文，仍以簡體→臺灣繁體流程處理（不影響已是繁體的內容）。")
        convert_simplified_epub(str(input_path), str(output_path))
    else:
        print(f"無法辨識語言 ({lang})，預設當作簡體中文處理。")
        convert_simplified_epub(str(input_path), str(output_path))

    print(f"已輸出: {output_path}")


if __name__ == "__main__":
    main()
