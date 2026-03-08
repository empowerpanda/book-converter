# -*- coding: utf-8 -*-
"""
英文 → 繁體中文翻譯：以段落為單位、術語／人名整書一致。
策略：用詞彙表（glossary）把已出現的專有名詞在原文中替換成 placeholder，翻譯後再換回目標語；
章節間傳遞並更新 glossary，確保整本書語意、用詞統一。
"""

import os
import re
import time
from typing import Dict, List

# 若無法自動偵測地區，可先設定：os.environ["translators_default_region"] = "EN" 或 "CN"
if "translators_default_region" not in os.environ:
    os.environ.setdefault("translators_default_region", "EN")

try:
    import translators as ts
except ImportError:
    ts = None

_argos_installed = False
def _argos_translate(text: str) -> str:
    """使用 Argos Translate 離線翻譯 en→zh，再轉臺灣繁體。"""
    global _argos_installed
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError:
        raise RuntimeError("請安裝 Argos：pip install argostranslate，並執行 argospm update && argospm install translate-en_zh")
    if not _argos_installed:
        argostranslate.package.update_package_index()
        pkgs = argostranslate.package.get_available_packages()
        pkg = next((p for p in pkgs if p.from_code == "en" and p.to_code == "zh"), None)
        if not pkg:
            raise RuntimeError("找不到 en→zh 語言包，請執行：argospm update && argospm install translate-en_zh")
        argostranslate.package.install_from_path(pkg.download())
        _argos_installed = True
    out = argostranslate.translate.translate(text.strip(), "en", "zh")
    if not out:
        return ""
    # Argos 多為簡體，轉臺灣繁體
    try:
        from opencc import OpenCC
        out = OpenCC("s2tw").convert(out)
    except Exception:
        pass
    return out.strip()

# 每段最長字數，避免單次請求過大
MAX_CHUNK_CHARS = 3000
# 請求間隔（秒），降低被限流風險
REQUEST_DELAY = 0.5


def _translate_with_engine(text: str, engine: str = "google") -> str:
    """呼叫翻譯引擎，目標語言為臺灣繁體。engine 可為 google/deepl/...（需 translators）或 argos（離線，需 argostranslate）。"""
    text = text.strip()
    if not text:
        return ""
    if engine == "argos":
        return _argos_translate(text)
    if not ts:
        raise RuntimeError("請安裝 translators：pip install translators")
    try:
        out = ts.translate_text(
            query_text=text,
            to_language="zh-TW",
            translator=engine,
        )
    except TypeError:
        out = ts.translate_text(text, to_language="zh-TW", translator=engine)
    return (out or "").strip()


def _extract_candidate_terms(text: str) -> List[str]:
    """
    從英文段落中擷取可能的人名／專有名詞（連續大寫開頭的詞、或已見於詞彙表的）。
    簡單規則：連續 2+ 個「大寫開頭+字母」視為候選。
    """
    # 匹配 "Word Word" 或 "Word-Word" 型
    pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+[A-Z]\.?)?)\b"
    found = re.findall(pattern, text)
    return list(dict.fromkeys(f for f in found if len(f) > 1))


def _split_into_paragraphs(text: str) -> List[str]:
    """依雙換行分段落，過長的段落再依句點切開。"""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    result: List[str] = []
    for p in paras:
        if len(p) <= MAX_CHUNK_CHARS:
            result.append(p)
            continue
        # 依句點或問號、驚嘆號切
        parts = re.split(r"(?<=[.!?])\s+", p)
        current = ""
        for part in parts:
            if len(current) + len(part) + 1 <= MAX_CHUNK_CHARS:
                current += (" " if current else "") + part
            else:
                if current:
                    result.append(current)
                current = part
        if current:
            result.append(current)
    return result


def _apply_glossary_to_source(text: str, glossary: Dict[str, str]) -> tuple[str, Dict[str, str]]:
    """
    把原文中出現在 glossary 的詞替換成 placeholder，並回傳替換對照（placeholder -> 繁中）。
    """
    placeholders: Dict[str, str] = {}
    result = text
    # 依詞長降序，先替換長詞
    for en in sorted(glossary.keys(), key=lambda x: -len(x)):
        zh = glossary[en]
        # 用不常見的 placeholder，避免與內文混淆
        key = f"__GLOSS_{len(placeholders)}__"
        placeholders[key] = zh
        result = result.replace(en, key)
    return result, placeholders


def _apply_placeholders_back(text: str, placeholders: Dict[str, str]) -> str:
    """把翻譯結果中的 placeholder 換回對應繁中。"""
    for key, zh in placeholders.items():
        text = text.replace(key, zh)
    return text


def _ensure_glossary_has_candidates(en_para: str, glossary: Dict[str, str], engine: str) -> None:
    """
    對本段中首次出現的候選專有名詞（大寫開頭連續詞）單獨翻譯並加入 glossary，
    之後整段翻譯時會用 placeholder 替換，保證整書一致。
    """
    candidates = _extract_candidate_terms(en_para)
    for term in candidates:
        if term in glossary:
            continue
        try:
            zh = _translate_with_engine(term, engine=engine)
            if zh and zh.strip():
                glossary[term] = zh.strip()
                time.sleep(REQUEST_DELAY * 0.3)
        except Exception:
            pass


def translate_english_to_traditional(
    text: str,
    glossary: Dict[str, str] | None = None,
    engine: str = "google",
) -> tuple[str, Dict[str, str]]:
    """
    將英文長文翻譯成繁體中文，並維護 glossary 使同一詞／人名整篇一致。
    回傳 (翻譯後全文, 更新後的 glossary)。
    """
    if glossary is None:
        glossary = {}
    paragraphs = _split_into_paragraphs(text)
    out_paras: List[str] = []
    for i, en in enumerate(paragraphs):
        if not en.strip():
            out_paras.append("")
            continue
        # 先為本段中「首次出現」的專有名詞單獨翻譯並加入 glossary
        _ensure_glossary_has_candidates(en, glossary, engine)
        # 套用 glossary 到原文（placeholder），再翻譯整段
        en_masked, placeholders = _apply_glossary_to_source(en, glossary)
        try:
            zh = _translate_with_engine(en_masked, engine=engine)
        except Exception as e:
            zh = f"[翻譯錯誤: {e}]"
        zh = _apply_placeholders_back(zh, placeholders)
        out_paras.append(zh)
        time.sleep(REQUEST_DELAY)
    return "\n\n".join(out_paras), glossary


def translate_paragraph(
    en_para: str,
    glossary: Dict[str, str],
    engine: str = "google",
) -> tuple[str, Dict[str, str]]:
    """
    翻譯單一段落，並更新 glossary。回傳 (繁中段落, 更新後的 glossary)。
    """
    if not en_para.strip():
        return "", glossary
    _ensure_glossary_has_candidates(en_para, glossary, engine)
    en_masked, placeholders = _apply_glossary_to_source(en_para, glossary)
    try:
        zh = _translate_with_engine(en_masked, engine=engine)
    except Exception as e:
        zh = f"[翻譯錯誤: {e}]"
    zh = _apply_placeholders_back(zh, placeholders)
    return zh, glossary
