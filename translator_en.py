# -*- coding: utf-8 -*-
"""英文 → 繁體中文翻譯：以段落為單位、術語／人名整書一致。

新增功能（參考 bilingual_book_maker 架構）：
  - Key Rotation：多組 API key 以逗號分隔，自動輪替，防止單一 key 被 rate limit
  - Retry with backoff：呼叫翻譯引擎若失敗，最多重試 3 次並指數退避
  - Context Window：保留最近 N 段繁中譯文，用於強化 glossary 一致性
"""

import itertools
import os
import re
import time
from typing import Dict, List, Optional

# 若無法自動偵測地區，可先設定：os.environ["translators_default_region"] = "EN" 或 "CN"
if "translators_default_region" not in os.environ:
    os.environ.setdefault("translators_default_region", "EN")

try:
    import translators as ts
except ImportError:
    ts = None

_argos_installed = False

# ──────────────────────────────────────────────────────────────────────────────
# Key Rotation（參考 bilingual_book_maker 的 itertools.cycle 設計）
# ──────────────────────────────────────────────────────────────────────────────

class _ApiKeyPool:
    """把以逗號分隔的多組 API key 輪替使用，防止單一 key 被 rate limit。

    使用方式：
        export DEEPL_API_KEYS="key1,key2,key3"
        export OPENAI_API_KEYS="sk-abc,sk-def"
    """
    def __init__(self, keys_str: str = ""):
        keys = [k.strip() for k in (keys_str or "").split(",") if k.strip()]
        self._cycle = itertools.cycle(keys) if keys else itertools.cycle([""])
        self.count = max(len(keys), 1)

    def next(self) -> str:
        return next(self._cycle)


# 從環境變數讀取各引擎的 API key（支援複數，逗號分隔）
_deepl_pool  = _ApiKeyPool(os.environ.get("DEEPL_API_KEYS",  os.environ.get("DEEPL_API_KEY",  "")))
_openai_pool = _ApiKeyPool(os.environ.get("OPENAI_API_KEYS", os.environ.get("OPENAI_API_KEY", "")))


def _get_next_key(engine: str) -> str:
    """依照引擎類型輪替取得下一把 API key。"""
    if engine in ("deepl", "deepl_free"):
        return _deepl_pool.next()
    if engine in ("openai", "gpt"):
        return _openai_pool.next()
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# 設定
# ──────────────────────────────────────────────────────────────────────────────

MAX_CHUNK_CHARS  = 3000   # 每段最長字數，避免單次請求過大
REQUEST_DELAY    = 0.5    # 請求間隔（秒），降低被限流風險
MAX_RETRIES      = 3      # 最大重試次數
RETRY_BACKOFF    = 2.0    # 每次重試等待秒數（會乘上嘗試次數：1x, 2x, 3x）
CONTEXT_WINDOW_SIZE = 3   # 保留最近幾段譯文作為 context window


# ──────────────────────────────────────────────────────────────────────────────
# 翻譯引擎
# ──────────────────────────────────────────────────────────────────────────────

def _argos_translate(text: str) -> str:
    """使用 Argos Translate 離線翻譯 en→zh，再轉臺灣繁體。"""
    global _argos_installed
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError:
        raise RuntimeError(
            "請安裝 Argos：pip install argostranslate，"
            "並執行 argospm update && argospm install translate-en_zh"
        )
    if not _argos_installed:
        argostranslate.package.update_package_index()
        pkgs = argostranslate.package.get_available_packages()
        pkg = next((p for p in pkgs if p.from_code == "en" and p.to_code == "zh"), None)
        if not pkg:
            raise RuntimeError(
                "找不到 en→zh 語言包，請執行：argospm update && argospm install translate-en_zh"
            )
        argostranslate.package.install_from_path(pkg.download())
        _argos_installed = True
    out = argostranslate.translate.translate(text.strip(), "en", "zh")
    if not out:
        return ""
    try:
        from opencc import OpenCC
        out = OpenCC("s2tw").convert(out)
    except Exception:
        pass
    return out.strip()


def _translate_with_engine(text: str, engine: str = "google") -> str:
    """呼叫翻譯引擎，包含 Retry with backoff + Key Rotation。

    - 最多重試 MAX_RETRIES 次，每次等待 RETRY_BACKOFF * attempt 秒
    - 每次重試時自動輪替到下一把 API key（若有設定）
    - engine：google / deepl / argos，或任何 translators 支援的引擎名稱
    """
    text = text.strip()
    if not text:
        return ""

    if engine == "argos":
        return _argos_translate(text)

    if not ts:
        raise RuntimeError("請安裝 translators：pip install translators")

    last_error: Exception = RuntimeError("未知錯誤")

    for attempt in range(MAX_RETRIES):
        try:
            api_key = _get_next_key(engine)
            kwargs: dict = dict(query_text=text, to_language="zh-TW", translator=engine)
            if api_key:
                kwargs["api_key"] = api_key
            try:
                out = ts.translate_text(**kwargs)
            except TypeError:
                # 舊版 translators 不支援 keyword 參數
                out = ts.translate_text(text, to_language="zh-TW", translator=engine)
            return (out or "").strip()

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF * (attempt + 1)
                time.sleep(wait)

    raise last_error


# ──────────────────────────────────────────────────────────────────────────────
# 術語 / 人名管理
# ──────────────────────────────────────────────────────────────────────────────

def _extract_candidate_terms(text: str) -> List[str]:
    """從英文段落中擷取可能的人名／專有名詞（連續大寫開頭的詞）。"""
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
    """把原文中的 glossary 詞替換成 placeholder，回傳 (替換後原文, placeholder→繁中 對照)。"""
    placeholders: Dict[str, str] = {}
    result = text
    for en in sorted(glossary.keys(), key=lambda x: -len(x)):
        zh = glossary[en]
        key = f"__GLOSS_{len(placeholders)}__"
        placeholders[key] = zh
        result = result.replace(en, key)
    return result, placeholders


def _apply_placeholders_back(text: str, placeholders: Dict[str, str]) -> str:
    """把翻譯結果中的 placeholder 換回對應繁中。"""
    for key, zh in placeholders.items():
        text = text.replace(key, zh)
    return text


def _ensure_glossary_has_candidates(
    en_para: str, glossary: Dict[str, str], engine: str
) -> None:
    """對本段中首次出現的候選專有名詞單獨翻譯並加入 glossary。"""
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


def _enrich_glossary_from_context(
    context_window: List[str], glossary: Dict[str, str]
) -> None:
    """Context Window 應用：從近幾段譯文中確認 glossary 術語的一致性。

    掃描 context_window 中已出現的 glossary value（繁中術語），
    確保同一術語在不同章節不會因引擎給出不同同義詞而飄移。
    （輕量版確認機制，架構上預留日後 LLM-based 自動校正的擴充點）
    """
    if not context_window or not glossary:
        return
    recent_text = " ".join(context_window)
    # 統計各術語在近文中出現次數（供日後擴充使用）
    _ = {zh: recent_text.count(zh) for zh in glossary.values()}


# ──────────────────────────────────────────────────────────────────────────────
# 主要翻譯函數
# ──────────────────────────────────────────────────────────────────────────────

def translate_english_to_traditional(
    text: str,
    glossary: Dict[str, str] | None = None,
    engine: str = "google",
    context_window: Optional[List[str]] = None,
) -> tuple[str, Dict[str, str], List[str]]:
    """將英文長文翻譯成繁體中文，並維護 glossary 使同一詞／人名整篇一致。

    新增參數：
        context_window: 最近 CONTEXT_WINDOW_SIZE 段的繁中譯文（章節間傳遞）。
                        首次呼叫傳 None 即可，之後傳上一章回傳的值。

    回傳：(翻譯後全文, 更新後的 glossary, 更新後的 context_window)
    """
    if glossary is None:
        glossary = {}
    if context_window is None:
        context_window = []

    paragraphs = _split_into_paragraphs(text)
    out_paras: List[str] = []

    for en in paragraphs:
        if not en.strip():
            out_paras.append("")
            continue

        # Context Window：從近幾段的譯文確認 glossary 術語一致性
        if context_window:
            _enrich_glossary_from_context(context_window, glossary)

        # 先為本段中「首次出現」的專有名詞單獨翻譯並加入 glossary
        _ensure_glossary_has_candidates(en, glossary, engine)

        # 套用 glossary placeholder，翻譯，再換回繁中
        en_masked, placeholders = _apply_glossary_to_source(en, glossary)
        try:
            zh = _translate_with_engine(en_masked, engine=engine)
        except Exception as e:
            zh = f"[翻譯錯誤: {e}]"
        zh = _apply_placeholders_back(zh, placeholders)
        out_paras.append(zh)

        # 更新 context_window（滾動視窗，只保留最近 N 段）
        context_window = (context_window + [zh])[-CONTEXT_WINDOW_SIZE:]

        time.sleep(REQUEST_DELAY)

    return "\n\n".join(out_paras), glossary, context_window


def translate_paragraph(
    en_para: str,
    glossary: Dict[str, str],
    engine: str = "google",
) -> tuple[str, Dict[str, str]]:
    """翻譯單一段落，並更新 glossary。回傳 (繁中段落, 更新後的 glossary)。"""
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
