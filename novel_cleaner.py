"""
novel_cleaner.py
----------------
Universal Text Sanitizer & Quality Normalizer for Web Novels.
Cleans raw scraped chapters:
  1. Fixes escaped characters (e.g. \", \', \\, \u003c, \u003e, \u0026, orphan backslashes)
  2. Decodes all HTML entities (&amp;, &quot;, &#39;, &lt;, &gt;, &nbsp;, etc.)
  3. Repairs corrupted UTF-8 replacement characters (U+FFFD:  in contractions and dialogue)
  4. Removes inline injected pirate site watermarks and domain advertisements
  5. Drops standalone promo / Patreon / Discord / donation paragraphs
  6. Prunes duplicate chapter title lines in paragraph 0
  7. Cleans whitespace, zero-width characters, and repeated quotes
  8. Re-tokenizes sentences for flawless Android TTS audio synchronization
"""

import os
import re
import html
import json
import unicodedata
from typing import Dict, List, Tuple, Optional

# Regex for sentence boundary tokenization
SENTENCE_SPLIT_REGEX = re.compile(r'(?<=[.!?…])\s+(?=[A-Z0-9"“‘\[<—])')

# Common English contraction mappings for  (U+FFFD)
CONTRACTIONS = [
    (re.compile(r"\b(don)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(can)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(won)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(didn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(isn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(aren)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(wasn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(weren)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(hasn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(haven)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(hadn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(couldn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(shouldn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(wouldn)[\ufffd]+(t)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(i)[\ufffd]+(m)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(you)[\ufffd]+(re)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(he)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(she)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(it)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(we)[\ufffd]+(re)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(they)[\ufffd]+(re)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(i)[\ufffd]+(ve)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(you)[\ufffd]+(ve)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(we)[\ufffd]+(ve)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(they)[\ufffd]+(ve)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(i)[\ufffd]+(ll)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(you)[\ufffd]+(ll)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(he)[\ufffd]+(ll)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(she)[\ufffd]+(ll)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(it)[\ufffd]+(ll)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(we)[\ufffd]+(ll)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(they)[\ufffd]+(ll)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(that)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(what)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(there)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(here)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(who)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    (re.compile(r"\b(let)[\ufffd]+(s)\b", re.I), r"\1'\2"),
    # Possessives: Quinns -> Quinn's, [Last Stand]s -> [Last Stand]'s
    (re.compile(r"([a-zA-Z0-9\]\)])[\ufffd]+(s)\b"), r"\1'\2"),
    # Word-internal apostrophes: OHara -> O'Hara, rocknroll -> rock'n'roll
    (re.compile(r"([a-zA-Z])[\ufffd]+([a-zA-Z])"), r"\1'\2"),
    # Ellipsis: 2 or more 
    (re.compile(r"[\ufffd]{2,}"), r"..."),
]

# Injected inline watermark patterns
INLINE_WATERMARK_PATTERNS = [
    re.compile(r'[\'\"“‘\(]?\s*Search\s+[^\w\s]*Freewebnovel\.com[^\w\s]*\s+on\s+google\s*[\'\"”’\)]?', re.I),
    re.compile(r'[\'\"“‘]?\s*Please\s+reading\s+on\s+Freewebnovel\.com\.?\s*[\'\"”’]?', re.I),
    re.compile(r'[\'\"“‘]?\s*The\s+source\s+of\s+this\s+content\s+is\s+Freewebn[oᴏ]vel\.com\.?\s*[\'\"”’]?', re.I),
    re.compile(r'[\'\"“‘]?\s*Source:\s*novgo\.co\s*[\'\"”’]?', re.I),
    re.compile(r'[\'\"“‘]?\s*Updates\s+by\s+vipnovel\.com\s*[\'\"”’]?', re.I),
    re.compile(r'Dear\s+readers!?\s*you\s+are\s+reading\s+on\s+our\s+content\s+(?:copy|stealing)\s+site\.?\s*Please\s+copy\s+and\s+search\s+this\s+link\s*[\'\"“]?\s*https?://\S+\s*[\'\"”]?\s*to\s+support\s+us', re.I),
    re.compile(r'For\s+more,\s+visit:?\s*(?:AllFreeWebNovel|MtNovel|FreeWebNovel)\.com\.?', re.I),
    re.compile(r'Find\s+authorized\s+novels\s+in\s+Webnovel\s*[,\.]?\s*faster\s+updates\s*[,\.]?\s*better\s+experience\s*[,\.]?\s*Please\s+click\s+(?:www\.webnovel\.com|https?://\S+)\s+for\s+visiting\.?', re.I),
    re.compile(r'Please\s+bookmark\s+this\s+website\s+to\s+save\s+your\s+progress', re.I),
    re.compile(r'All\s+ɴᴏᴠᴇʟ\s+full\.co\S*', re.I),
    re.compile(r'You\s+can\s+read\s+the\s+story\s+for\s+free\s+at\s+LatestNovel\.Net\s+or\s+NovelGreat\.Net\.?', re.I),
    re.compile(r'\bBoxNovel\.com\b', re.I),
    re.compile(r'if\s+those\s+who\s+wonder\s+were\s+I\s+copy\s+this\s+I\s+give\s+you\s+the\s+link:?\s*https?://nyx-translation\.com/?', re.I),
    re.compile(r'No\s+movement\.?\\n\(o\)v\.e\\l\.com', re.I),
    re.compile(r'free\\NovelBin\.c\s*o\(m\)', re.I),
]

# Standalone ad / promo paragraph patterns
STANDALONE_AD_PATTERNS = [
    re.compile(r'^https?://(?:discord(?:\.gg|app\.com)|t\.me|twitter\.com|instagram\.com)/\S+$', re.I),
    re.compile(r'^(?:join\s+)?(?:the\s+)?discord(?:\s+server)?\s*:?\s*https?://discord', re.I),
    re.compile(r'^(?:my\s+)?p[4a]tre[0o][mn](?:\.com)?\s*(?:is)?:?\s*(?:https?://|pa[-_ ]?tre[-_ ]?[0o]?[mn]\.com)', re.I),
    re.compile(r'p[4a]t?r?[-_ ]?e?[-_ ]?[0o]?[mn]\.com/aidnovels', re.I),
    re.compile(r'^(?:remember\s+to\s+)?support\s+(?:me|the\s+author)\s+on\s+pa[-_ ]*tre[0o]n', re.I),
    re.compile(r'visit\s+my\s+pa[-_ ]*tre[0o]n:?\s*pa[-_ ]*tre[0o]n\.com/', re.I),
    re.compile(r'^(?:if\s+you\s+want\s+to\s+support\s+(?:you\s+can\s+)?on\s+my\s+)?p[\.\s_-]*a[\.\s_-]*t[\.\s_-]*r[\.\s_-]*e[\.\s_-]*o[\.\s_-]*n', re.I),
    re.compile(r'^(?:source:?\s*)?(?:freewebnovel|novelping|webnovel|novelbin|boxnovel|mtnovel|vipnovel|allfreewebnovel|latestnovel|novelgreat|novgo)\.com?$', re.I),
    re.compile(r'^visit\s+.*?\s+for\s+(?:more\s+)?(?:chapters|updates)\.?$', re.I),
    re.compile(r'^read\s+(?:more\s+)?(?:latest\s+)?chapters?\s+(?:at|on)\s+.*$', re.I),
    re.compile(r'^advertisement$', re.I),
    re.compile(r'^prev(?:ious)?\s*chapter$', re.I),
    re.compile(r'^next\s*chapter$', re.I),
    re.compile(r'^chapter\s*list$', re.I),
    re.compile(r'^options$', re.I),
]


def clean_paragraph_text(text: str) -> str:
    """
    Cleans a single paragraph string:
    - Decodes HTML entities
    - Unescapes literal backslashes (\", \', \\, \u003c, \u003e, \u0026)
    - Fixes ratio backslashes like 75\95 HP -> 75/95 HP
    - Removes orphan backslashes before characters and spaces
    - Normalizes obscure unicode characters used for filter evasion
    - Repairs corrupted UTF-8 replacement characters (U+FFFD: )
    - Strips inline injected watermarks and stealth domain suffixes
    - Cleans excessive quotes and whitespace
    """
    if not text:
        return ""

    # 1. Decode HTML entities (e.g. &amp;, &quot;, &#39;, &lt;, &gt;, &nbsp;, &hellip;)
    text = html.unescape(text)

    # 2. Fix explicit unicode escapes like \u003c, \u003e, \u0026
    def unescape_unicode_match(m):
        try:
            return chr(int(m.group(1), 16))
        except Exception:
            return m.group(0)
    text = re.sub(r'\\u([0-9a-fA-F]{4})', unescape_unicode_match, text)

    # 3. Unescape escaped double/single quotes and common escaped symbols: \", \', \$, \(, \), \-
    text = text.replace(r'\"', '"').replace(r"\'", "'")
    text = text.replace(r'\$', '$').replace(r'\(', '(').replace(r'\)', ')')
    text = text.replace(r'\-', '-')

    # 4. Handle ratio backslashes like 75\95 HP -> 75/95 HP
    text = re.sub(r'(\d+)\\(\d+)', r'\1/\2', text)

    # 5. Remove orphan backslashes before characters or spaces, and trailing backslashes
    text = re.sub(r'\\\s+', ' ', text)
    text = re.sub(r'\\([a-zA-Z0-9_\-])', r'\1', text)
    text = re.sub(r'\\+\s*$', '', text)
    text = text.replace(r'\\', '')

    # 6. Normalize mathematical monospace / bold unicode characters
    text = unicodedata.normalize('NFKD', text)

    # 7. Repair corrupted UTF-8 replacement characters (U+FFFD: )
    for reg, repl in CONTRACTIONS:
        text = reg.sub(repl, text)

    # Corrupted dialogue quotes at start or end of text
    text = re.sub(r'^[\ufffd]+', '"', text)
    text = re.sub(r'[\ufffd]+$', '"', text)
    text = re.sub(r'[\ufffd]+\s', '" ', text)
    text = re.sub(r'\s[\ufffd]+', ' "', text)
    # Any remaining  removed
    text = text.replace('', '').replace('\ufffd', '')

    # 8. Strip inline injected watermarks
    for iw in INLINE_WATERMARK_PATTERNS:
        text = iw.sub('', text)

    # Stealth domain suffixes attached to sentence ends: e.g. "said.freewebnovel.com" -> "said."
    text = re.sub(r'([\.\!\?\"\'”’\)])\s*(?:https?://)?(?:www\.)?(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b[\'\"”’\.\,\)]*', r'\1', text, flags=re.I)
    text = re.sub(r'(?<=[a-zA-Z0-9])\.(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b', '.', text, flags=re.I)
    text = re.sub(r'[\s\(\[\'\"]*(?:https?://)?(?:www\.)?(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b[\s\)\]\'\"\.]*', ' ', text, flags=re.I)

    # 9. Clean redundant multiple quotes like """Hello""" -> "Hello"
    text = re.sub(r'"{2,}', '"', text)
    text = re.sub(r"'{2,}", "'", text)

    # 10. Clean excessive spaces, tabs, and non-breaking whitespace
    text = re.sub(r'[\r\t\u00a0\u200b\u200e\u200f\ufeff]+', ' ', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def is_ad_or_watermark_paragraph(text: str) -> bool:
    """Returns True if the entire paragraph is an ad, promotional link, or scraper watermark."""
    if not text:
        return True

    clean_p = text.strip().lower()

    if len(clean_p) < 85 and re.search(r'https?://(?:www\.)?ko-fi\.com/\S+', clean_p):
        return True

    if len(clean_p) < 120 and re.search(r'https?://(?:www\.)?discord(?:\.gg|app\.com/\S+)', clean_p):
        return True

    if 'jksmangafreewebnovel.com' in clean_p:
        return True

    for pat in STANDALONE_AD_PATTERNS:
        if pat.search(clean_p):
            return True

    return False


def clean_chapter_data(chapter: dict) -> dict:
    """
    Cleans an entire chapter dictionary in-place and returns it:
    - Cleans title
    - Cleans and filters paragraphs
    - Removes duplicate title in paragraph 0
    - Re-tokenizes sentences for TTS
    - Updates word_count
    """
    raw_title = chapter.get("title", "")
    title = clean_paragraph_text(raw_title)

    raw_paragraphs = chapter.get("paragraphs", [])
    cleaned_paragraphs = []

    for p in raw_paragraphs:
        cleaned_p = clean_paragraph_text(p)
        if not cleaned_p:
            continue
        if is_ad_or_watermark_paragraph(cleaned_p):
            continue
        cleaned_paragraphs.append(cleaned_p)

    # Check for duplicate chapter title in paragraph 0
    if cleaned_paragraphs and title:
        p0_norm = re.sub(r'[^a-zA-Z0-9]', '', cleaned_paragraphs[0]).lower()
        t_norm = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
        ch_idx_str = str(chapter.get('chapter_index', ''))
        if p0_norm and (p0_norm == t_norm or p0_norm == f"chapter{ch_idx_str}"):
            cleaned_paragraphs.pop(0)

    # Fallback placeholder if chapter ended up completely empty
    if not cleaned_paragraphs:
        cleaned_paragraphs = ["Content currently being updated."]

    # Re-tokenize sentences for Android TTS & word tracking
    sentences = []
    s_idx = 0
    for p_idx, para in enumerate(cleaned_paragraphs):
        raw_s = SENTENCE_SPLIT_REGEX.split(para)
        for s in raw_s:
            s_clean = s.strip()
            if s_clean:
                sentences.append({
                    "id": s_idx,
                    "paragraph_id": p_idx,
                    "text": s_clean
                })
                s_idx += 1

    chapter["title"] = title
    chapter["paragraphs"] = cleaned_paragraphs
    chapter["sentences"] = sentences
    chapter["word_count"] = sum(len(p.split()) for p in cleaned_paragraphs)
    return chapter


def clean_novel_file(filepath: str) -> Tuple[bool, int]:
    """
    Cleans a novel JSON file on disk atomically.
    Returns (changed: bool, chapters_cleaned: int).
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return False, 0

    if not isinstance(data, dict):
        return False, 0

    key = "chapters" if "chapters" in data else ("bundled_chapters" if "bundled_chapters" in data else None)
    if not key or not isinstance(data[key], list):
        return False, 0

    orig_json = json.dumps(data, ensure_ascii=False)

    chapters = data[key]
    for ch in chapters:
        clean_chapter_data(ch)

    new_json = json.dumps(data, ensure_ascii=False, indent=2)
    if orig_json != new_json:
        tmp_file = filepath + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(new_json)
        os.replace(tmp_file, filepath)
        return True, len(chapters)

    return False, len(chapters)


if __name__ == "__main__":
    import argparse
    import glob

    parser = argparse.ArgumentParser(description="Sanitize and clean novel chapters.")
    parser.add_argument("--novel", type=str, default="all", help="Novel ID or 'all' to clean all novels")
    parser.add_argument("--file", type=str, default="", help="Specific file to clean")
    args = parser.parse_args()

    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) if os.path.dirname(__file__).endswith("scripts") else os.path.abspath(os.path.dirname(__file__))

    files_to_clean = []
    if args.file:
        files_to_clean.append(args.file)
    elif args.novel == "all":
        files_to_clean.extend(glob.glob(os.path.join(PROJECT_ROOT, "data", "**", "*.json"), recursive=True))
        files_to_clean.extend(glob.glob(os.path.join(PROJECT_ROOT, "android-app", "app", "src", "main", "assets", "*_data.json")))
        files_to_clean.extend(glob.glob(os.path.join(PROJECT_ROOT, "*_data.json")))
    else:
        target_dir = os.path.join(PROJECT_ROOT, "data", args.novel)
        if os.path.exists(target_dir):
            files_to_clean.extend(glob.glob(os.path.join(target_dir, "*.json")))
        elif args.novel == "infinite-mana-in-the-apocalypse":
            files_to_clean.extend(glob.glob(os.path.join(PROJECT_ROOT, "data", "chapters_*.json")))

    files_to_clean = [f for f in files_to_clean if os.path.basename(f) not in ["index.json", "archive_cache.json", "novels.json"]]
    print(f"Discovered {len(files_to_clean)} novel bundle files to check/clean.")

    modified_count = 0
    total_chapters_cleaned = 0

    for idx, fpath in enumerate(files_to_clean, 1):
        changed, count = clean_novel_file(fpath)
        if changed:
            modified_count += 1
            total_chapters_cleaned += count
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            print(f"[{idx}/{len(files_to_clean)}] Cleaned: {rel} ({count} chapters)")

    print(f"\nCleaning Complete! Updated {modified_count} files ({total_chapters_cleaned} chapters sanitized).")
