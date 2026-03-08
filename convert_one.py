# -*- coding: utf-8 -*-
"""
單檔轉換：讀取 input/ 裡的一個 .epub，轉換後寫入 output/。
供「丟檔給 AI」或指令列一鍵轉換使用。
用法:
  python convert_one.py                    # 轉換 input/ 中第一個 .epub
  python convert_one.py /path/to/book.epub # 指定輸入，輸出到 output/
"""

import sys
from pathlib import Path

# 專案根目錄
ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"


def main() -> None:
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1]).resolve()
    else:
        epubs = list(INPUT_DIR.glob("*.epub"))
        if not epubs:
            print("請把要轉換的 .epub 放到 input/ 資料夾，或執行: python convert_one.py <檔案.epub>")
            sys.exit(1)
        input_path = epubs[0]

    if not input_path.exists():
        print(f"錯誤：找不到檔案 {input_path}")
        sys.exit(2)

    out_name = f"{input_path.stem}_tw.epub"
    output_path = OUTPUT_DIR / out_name

    sys.path.insert(0, str(ROOT))
    from main import (
        detect_language_from_epub,
        convert_simplified_epub,
        convert_english_epub,
    )

    print("正在偵測語言…")
    lang = detect_language_from_epub(str(input_path))
    print(f"偵測結果: {lang}")

    if lang == "zh-cn":
        print("辨識為簡體中文，進行簡體→臺灣繁體轉換。")
        convert_simplified_epub(str(input_path), str(output_path))
    elif lang == "en":
        print("辨識為英文，進行英文→繁體中文翻譯。")
        convert_english_epub(str(input_path), str(output_path))
    else:
        print("以簡體→臺灣繁體流程處理。")
        convert_simplified_epub(str(input_path), str(output_path))

    print(f"已輸出: {output_path}")
    return output_path


if __name__ == "__main__":
    main()
