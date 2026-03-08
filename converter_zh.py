# -*- coding: utf-8 -*-
"""
簡體中文 → 臺灣繁體中文轉換（字體 + 語意／用語）
"""

from opencc import OpenCC
from terminology_zh import apply_terminology


# 簡體 → 臺灣繁體（字型與部分詞彙）
_cc = OpenCC("s2tw")


def convert_simplified_to_traditional(text: str) -> str:
    """
    將簡體中文轉為臺灣繁體：
    1. OpenCC s2tw 字體轉換
    2. 兩岸用語對照（如 酸奶→優格、鼠標→滑鼠）
    """
    if not text or not text.strip():
        return text
    traditional = _cc.convert(text)
    return apply_terminology(traditional)
