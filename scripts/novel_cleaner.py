"""
novel_cleaner.py
----------------
High-Performance, Multi-Stage Universal Text Sanitizer & Quality Normalizer for Web Novels.
Cleans raw scraped chapters:
  1. Fast rejection of pure divider lines (e.g. ---, ***, ===, +++, ~~~) and isolated quotes
  2. Decodes all HTML entities (&amp;, &quot;, &#39;, &lt;, &gt;, &nbsp;, etc.)
  3. Fixes escaped characters (\", \', \\, \u003c, \u003e, \u0026, orphan backslashes)
  4. Repairs UTF-8 Mojibake artifacts (â€™, â€œ, etc.) and corrupted replacement chars (U+FFFD: )
  5. Strips invisible zero-width and control characters (\ufeff, \u200b-\u200f, \xad, \x00-\x1f)
  6. Normalizes fullwidth Asian punctuation to standard ASCII with English spacing
  7. Removes runs of 6+ plus signs (++++++) and 4+ divider symbols into '' (nothing)
  8. Strips stealth injected pirate site watermarks and domain advertisements
  9. Drops standalone promo / Patreon / Discord / donation / bookmark paragraphs
  10. Normalizes excessive punctuation spam (?????, !!!!!, ,,,,,)
  11. Prunes duplicate chapter title lines in paragraph 0
  12. Re-tokenizes sentences for flawless Android TTS audio synchronization
"""

import os
import sys
import re
import html
import json
import unicodedata
from typing import Dict, List, Tuple, Optional

# Regex for sentence boundary tokenization
SENTENCE_SPLIT_REGEX = re.compile(r'(?<=[.!?…])\s+(?=[A-Z0-9"“‘\[<—])')

# Pre-compiled high-performance regexes
INVISIBLE_CHARS_REGEX = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u2028\u2029\ufeff\xad]')
UNICODE_ESCAPE_REGEX = re.compile(r'\\u([0-9a-fA-F]{4})')
RATIO_SLASH_REGEX = re.compile(r'(\d+)\\(\d+)')
ORPHAN_BACKSLASH_REGEX1 = re.compile(r'\\\s+')
ORPHAN_BACKSLASH_REGEX2 = re.compile(r'\\([a-zA-Z0-9_\-])')
ORPHAN_BACKSLASH_REGEX3 = re.compile(r'\\+\s*$')

# Fullwidth punctuation to standard ASCII (for correct TTS pausing and readability)
FULLWIDTH_TRANSLATION = str.maketrans({
    '，': ',', '。': '.', '！': '!', '？': '?',
    '：': ':', '；': ';', '（': '(', '）': ')',
    '［': '[', '］': ']', '【': '[', '】': ']',
    '《': '<', '》': '>', '—': '—', '–': '-'
})
PUNCT_SPACING_REGEX = re.compile(r'([,;:!?])(?=[a-zA-Z])')

# Punctuation spam reduction
EXCESSIVE_COMMAS = re.compile(r',{2,}')
EXCESSIVE_QUESTIONS = re.compile(r'\?{3,}')
EXCESSIVE_EXCLAMATIONS = re.compile(r'!{4,}')
EXCESSIVE_QUOTES_D = re.compile(r'"{2,}')
EXCESSIVE_QUOTES_S = re.compile(r"'{2,}")
EXCESSIVE_SPACES = re.compile(r' {2,}')

# Repeated special characters >= 3 times -> '' (blank)
# E.g. +++, ++++++%, ***, ---, ===, ~~~, ###, $$$, ///, \\\, ____, •••
# Guards standard sentence punctuation: . (preserves 1-3 dots for ellipsis), !, ?, quotes, commas
REPEATED_SPECIAL_CHARS = re.compile(r"([^\w\s.!?,\"']|_)\1{2,}%?")

# Spaced symbol divider runs: e.g. * * *, - - -, + + +, = = =
SPACED_DIVIDER_RUNS = re.compile(r'(?:\s*[-_~=*+#•]\s*){3,}')

# Excessive periods (4 or more dots) normalized to standard ellipsis ...
EXCESSIVE_PERIODS = re.compile(r'\.{4,}')

# Pure divider line or isolated punctuation/empty quote paragraph
PURE_DIVIDER_PARAGRAPH = re.compile(r'^(?:[-_~=*#+•\s]{2,}|["\'“”‘’`´«»│|—–\-_.\s]{1,4})$')

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

# Mojibake lookup for broken UTF-8 byte sequences
MOJIBAKE_MAP = {
    'â€™': "'", 'â€˜': "'", 'â€œ': '"', 'â€': '"',
    'â€”': '—', 'â€“': '–', 'â€¦': '…', 'Â ': ' ', 'Ã©': 'é'
}

# Injected inline watermark patterns (compiled once)
INLINE_WATERMARK_PATTERNS = [
    re.compile(r'[\'\"“‘\(]?\s*Search\s+[^\w\s]*(?:Freewebnovel|VipNovel|NovelPing|NovelBin)(?:\.com|\.live|\.org|\/c0m|\.c0m)?[^\w\s]*\s*on\s+google\s*[\'\"”’\)]?', re.I),
    re.compile(r'[\'\"“‘]?\s*(?:Please\s+)?reading\s+on\s+(?:ReadReadRead)?Freewebnovel(?:\.\s*com|\.live)?\.?\s*[\'\"”’]?', re.I),
    re.compile(r'[\'\"“‘]?\s*The\s+source\s+of\s+this\s+content\s+is\s+Freewebn[oᴏ]vel\.com\.?\s*[\'\"”’]?', re.I),
    re.compile(r'[\'\"“‘]?\s*Source:\s*novgo\.co\s*[\'\"”’]?', re.I),
    re.compile(r'[\'\"“‘]?\s*Updates\s+by\s+(?:vipnovel|freewebnovel)(?:\.\s*com)?\s*[\'\"”’]?', re.I),
    re.compile(r'read\s+(?:comics\s+on\s+our\s+ReadReadReadFreeWebNovel\.live|more\s+chapters?\s+at\s+FreeWebNovel)', re.I),
    re.compile(r'Visit\s+our\s+comic\s+site\s+ReadReadReadFreeWebNovel\.live', re.I),
    re.compile(r'You(?:’re|\'re)?\s+reading\s+on\s+ReadReadReadReadFreeWebNovel\.\s*com\s+Thanks!?', re.I),
    re.compile(r'welcome\s+to\s+NovelBin(?:\s*[\w\-,]+)*', re.I),
    re.compile(r'(?:Continue\s+your\s+saga\s+on|Your\s+next\s+journey\s+awaits\s+at)\s+(?:m[|\-v\'el\s]+)?NovelBin', re.I),
    re.compile(r'your-NovelBin-story', re.I),
    re.compile(r'NovelBin[|/][\w\-,]+(?:\s+chapter)?', re.I),
    re.compile(r'free\\?NovelBin\.c\s*o\(m\)', re.I),
    re.compile(r'No\s+movement\.?\\n\(o\)v\.e\\l\.com', re.I),
    re.compile(r'Dear\s+readers!?\s*you\s+are\s+reading\s+on\s+our\s+content\s+(?:copy|stealing)\s+site\.?\s*Please\s+copy\s+and\s+search\s+this\s+link\s*[\'\"“]?\s*https?://\S+\s*[\'\"”]?\s*to\s+support\s+us', re.I),
    re.compile(r'For\s+more,\s+visit:?\s*(?:AllFreeWebNovel|MtNovel|FreeWebNovel)\.com\.?', re.I),
    re.compile(r'Find\s+authorized\s+novels\s+in\s+Webnovel\s*[,\.]?\s*faster\s+updates\s*[,\.]?\s*better\s+experience\s*[,\.]?\s*Please\s+click\s+(?:www\.webnovel\.com|https?://\S+)\s+for\s+visiting\.?', re.I),
    re.compile(r'Please\s+bookmark\s+this\s+website\s+to\s+save\s+your\s+progress', re.I),
    re.compile(r'All\s+ɴᴏᴠᴇʟ\s+full\.co\S*', re.I),
    re.compile(r'You\s+can\s+read\s+the\s+story\s+for\s+free\s+at\s+LatestNovel\.Net\s+or\s+NovelGreat\.Net\.?', re.I),
    re.compile(r'\bBoxNovel\.com\b', re.I),
    re.compile(r'if\s+those\s+who\s+wonder\s+were\s+I\s+copy\s+this\s+I\s+give\s+you\s+the\s+link:?\s*https?://nyx-translation\.com/?', re.I),
]

# Standalone ad / promo paragraph patterns
STANDALONE_AD_PATTERNS = [
    re.compile(r'^(?:https?://(?:discord(?:\.gg|app\.com)|t\.me|twitter\.com|instagram\.com)/\S+|discord\s*:\s*\S+)$', re.I),
    re.compile(r'^(?:join\s+)?(?:the\s+)?discord(?:\s+server)?\s*:?\s*https?://discord', re.I),
    re.compile(r'^(?:my\s+)?p[4a]tre[0o][mn](?:\.com)?\s*(?:is)?:?\s*(?:https?://|pa[-_ ]?tre[-_ ]?[0o]?[mn]\.com)', re.I),
    re.compile(r'p[4a]t?r?[-_ ]?e?[-_ ]?[0o]?[mn]\.com/aidnovels', re.I),
    re.compile(r'^(?:remember\s+to\s+)?support\s+(?:me|the\s+author)\s+on\s+pa[-_ ]*tre[0o]n', re.I),
    re.compile(r'visit\s+my\s+pa[-_ ]*tre[0o]n:?\s*pa[-_ ]*tre[0o]n\.com/', re.I),
    re.compile(r'^(?:if\s+you\s+want\s+to\s+support\s+(?:you\s+can\s+)?on\s+my\s+)?p[\.\s_-]*a[\.\s_-]*t[\.\s_-]*r[\.\s_-]*e[\.\s_-]*o[\.\s_-]*n', re.I),
    re.compile(r'^(?:source:?\s*)?(?:freewebnovel|novelping|webnovel|novelbin|boxnovel|mtnovel|vipnovel|allfreewebnovel|latestnovel|novelgreat|novgo)\.com?$', re.I),
    re.compile(r'^(?:freewebnovel|novelping|novelbin|vipnovel)$', re.I),
    re.compile(r'^visit\s+.*?\s+for\s+(?:more\s+)?(?:chapters|updates)\.?$', re.I),
    re.compile(r'^read\s+(?:more\s+)?(?:latest\s+)?chapters?\s+(?:at|on)\s+.*$', re.I),
    re.compile(r'^(?:my\s+werewolf\s+system\s+(?:has\s+finally\s+arrived|is\s+now\s+out)\s+on\s+(?:the\s+)?freewebnovel.*)$', re.I),
    re.compile(r'^advertisement$', re.I),
    re.compile(r'^prev(?:ious)?\s*chapter$', re.I),
    re.compile(r'^next\s*chapter$', re.I),
    re.compile(r'^chapter\s*list$', re.I),
    re.compile(r'^options$', re.I),
]

# Discord Links & Invites
DISCORD_URL_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:discord\.(?:gg|com/invite)/[a-zA-Z0-9_\-]+|discord\s*/\s*gg\s*/[a-zA-Z0-9_\-]+)',
    re.I
)
DISCORD_INVITE_PARAGRAPH = re.compile(
    r'(?i)^(?:.*?\b(?:join|invite\s+link\s+to|link\s+to|check\s+(?:out\s+)?(?:the\s+)?pictures?\s+on)\s+(?:our|the|my)?\s*discord\b.*|.*?\bdiscord\s+(?:server|link|invite|channel)\b.*)$'
)
# Protect regular English usage of the word "discord" (e.g. "sow discord", "civil discord")
DISCORD_STORY_CONTEXT = re.compile(
    r'(?i)\b(?:sow(?:ing|s|ed)?|cause(?:d|s)?|bring|brought|unneeded|family|civil|internal|marital|disrupts?|creates?)\s+discord\b|\bdiscord\s+(?:between|among|disrupts)\b'
)

# Patreon, Ko-Fi, PayPal, and Donation Promos
DONATION_URL_REGEX = re.compile(
    r'(?i)(?:https?://)?(?:www\.)?(?:patreon\.com/[a-zA-Z0-9_\-]+|ko-fi(?:\.com)?/[a-zA-Z0-9_\-]+|paypal\.me/[a-zA-Z0-9_\-]+|p[\s.\-_*]*[a4][\s.\-_*]*t[\s.\-_*]*r[\s.\-_*]*[e3][\s.\-_*]*[o0][\s.\-_*]*n(?:\.com)?/[a-zA-Z0-9_\-]+)'
)
DONATION_PROMO_PARAGRAPH = re.compile(
    r'(?i)^(?:.*?\b(?:support\s+(?:me|the\s+author)|read\s+ahead\s+on|access\s+to\s+the\s+.*?\s+on)\s+(?:my\s+)?p[\s.\-_*]*[a4][\s.\-_*]*t[\s.\-_*]*r[\s.\-_*]*[e3][\s.\-_*]*[o0][\s.\-_*]*n\b.*|.*?\bp[\s.\-_*]*[a4][\s.\-_*]*t[\s.\-_*]*r[\s.\-_*]*[e3][\s.\-_*]*[o0][\s.\-_*]*n\s*(?:is)?\s*:.*)$'
)

# Author's Notes / Translator's Notes / Editor's Notes (A/N, T/N, E/N)
AUTHOR_NOTE_PREFIX = re.compile(
    r'(?i)^[<\[(]?\s*(?:author[\'’s\s]*notes?|a/?n|translator[\'’s\s]*notes?|t/?n|tl[\'’s\s]*notes?|editor[\'’s\s]*notes?|e/?n)\s*[:\-=–—>\]\)]\s*(.*)',
    re.DOTALL
)
AUTHOR_NOTE_HEADER = re.compile(
    r'(?i)^[<\[(]?\s*(?:author[\'’s\s]*notes?|a/?n|translator[\'’s\s]*notes?|t/?n|tl[\'’s\s]*notes?|editor[\'’s\s]*notes?|e/?n)\s*[>\])]?\s*$'
)

# Voting, Power Stones, Golden Tickets, Review Requests
VOTE_PROMO_PARAGRAPH = re.compile(
    r'(?i)^(?:.*?\b(?:power\s*stones?|golden\s*tickets?|magic\s*castles?)\b.*|.*?\b(?:vote\s+for\s+(?:this|the|my)\s+(?:book|story|novel)|rate\s+(?:and|&)\s*review|write\s+a\s+review)\b.*|don[\'’]?t\s+forget\s+to\s+vote.*|rank\s*\d+\s*=.*chapter\s+mass\s+release.*)$'
)

# Tail cleanup: Self-promotions ("My other novels", book lists) and author note headers at chapter end
TAIL_CUT_TRIGGER_REGEX = re.compile(
    r'(?i)^[-—~=*#\s]*(?:my\s+other\s+novels?|check\s+(?:out\s+)?my\s+other\s+novels?|other\s+works?|author[\'’s\s]*other\s+(?:novels?|books?)|<author[\'’s\s]*notes?>|\[author[\'’s\s]*notes?\]).*$'
)

# Trailing filler paragraphs dropped from chapter ends
TAIL_TRAILING_POP_REGEX = re.compile(
    r'(?i)^[-—~=*#\s]*(?:to\s+be\s+continued|tbc|end\s+of\s+chapter\s*\d*|thanks?\s+for\s+reading.*|adios|happy\s+new\s+month.*|new\s+chapter\s+is\s+coming\s+soon|come\s+back\s+and\s+continue\s+reading\s+tomorrow.*|chapter\s+price\s*:\s*\d+\s*coins?|unlock\s+the\s+complete\s+chapter.*|if\s+you\s+guys\s+haven[\'’]?t\s+read\s+all\s+four.*)[-—~=*#\s]*$'
)


def clean_paragraph_text(text: str) -> str:
    """
    Cleans a single paragraph string with high efficiency:
    - Fast rejection of pure divider lines or empty quote lines
    - Decodes HTML entities
    - Unescapes literal backslashes (\", \', \\, \u003c, \u003e, \u0026)
    - Fixes ratio backslashes like 75\95 HP -> 75/95 HP
    - Removes orphan backslashes before characters and spaces
    - Translates fullwidth Asian punctuation to ASCII
    - Strips invisible control characters & soft hyphens
    - Normalizes obscure unicode characters used for filter evasion
    - Repairs UTF-8 replacement characters (U+FFFD: )
    - Strips inline injected watermarks and stealth domain suffixes
    - Replaces runs of 6+ plus signs (++++) and 4+ divider symbols with '' (nothing)
    - Cleans excessive quotes, punctuation spam, and whitespace
    """
    if not text:
        return ""

    # Fast rejection of pure divider lines or isolated quotes
    if PURE_DIVIDER_PARAGRAPH.match(text.strip()):
        return ""

    # 1. Decode HTML entities (e.g. &amp;, &quot;, &#39;, &lt;, &gt;, &nbsp;, &hellip;)
    if '&' in text:
        text = html.unescape(text)

    # 2. Fix explicit unicode escapes like \u003c, \u003e, \u0026
    if '\\u' in text:
        text = UNICODE_ESCAPE_REGEX.sub(lambda m: chr(int(m.group(1), 16)), text)

    # 3. Mojibake repair (e.g. â€™, â€œ)
    if 'â' in text or 'Ã' in text:
        for k, v in MOJIBAKE_MAP.items():
            text = text.replace(k, v)

    # 4. Unescape escaped double/single quotes and common escaped symbols: \", \', \$, \(, \), \-
    if '\\' in text:
        text = text.replace(r'\"', '"').replace(r"\'", "'")
        text = text.replace(r'\$', '$').replace(r'\(', '(').replace(r'\)', ')')
        text = text.replace(r'\-', '-')
        text = RATIO_SLASH_REGEX.sub(r'\1/\2', text)
        text = ORPHAN_BACKSLASH_REGEX1.sub(' ', text)
        text = ORPHAN_BACKSLASH_REGEX2.sub(r'\1', text)
        text = ORPHAN_BACKSLASH_REGEX3.sub('', text)
        text = text.replace(r'\\', '')

    # 5. Fullwidth Asian punctuation to standard ASCII (ensures natural TTS pauses)
    text = text.translate(FULLWIDTH_TRANSLATION)
    text = PUNCT_SPACING_REGEX.sub(r'\1 ', text)

    # 6. Invisible / control characters & soft hyphens
    text = INVISIBLE_CHARS_REGEX.sub('', text)

    # 7. Normalize mathematical monospace / bold unicode characters
    text = unicodedata.normalize('NFKD', text)

    # 8. Repair corrupted UTF-8 replacement characters (U+FFFD: ) - guarded for speed
    if '\ufffd' in text:
        for reg, repl in CONTRACTIONS:
            text = reg.sub(repl, text)
        text = re.sub(r'^[\ufffd]+', '"', text)
        text = re.sub(r'[\ufffd]+$', '"', text)
        text = re.sub(r'[\ufffd]+\s', '" ', text)
        text = re.sub(r'\s[\ufffd]+', ' "', text)
        text = text.replace('\ufffd', '')

    # 9. Strip inline injected watermarks, discord links, and donation URLs
    for iw in INLINE_WATERMARK_PATTERNS:
        text = iw.sub('', text)
    if 'discord' in text.lower():
        text = DISCORD_URL_REGEX.sub('', text)
    if any(k in text.lower() for k in ['patreon', 'ko-fi', 'paypal', 'p4tre0n', 'p.a.t.r.e.o.n', 'pat-reon', 'pa-treon']):
        text = DONATION_URL_REGEX.sub('', text)

    # Stealth domain suffixes attached to sentence ends: e.g. "said.freewebnovel.com" -> "said."
    text = re.sub(r'([\.\!\?\"\'”’\)])\s*(?:https?://)?(?:www\.)?(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b[\'\"”’\.\,\)]*', r'\1', text, flags=re.I)
    text = re.sub(r'(?<=[a-zA-Z0-9])\.(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b', '.', text, flags=re.I)
    text = re.sub(r'[\s\(\[\'\"]*(?:https?://)?(?:www\.)?(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b[\s\)\]\'\"\.]*', ' ', text, flags=re.I)

    # 10. Replace any special character repeated 3 or more times (e.g. +++, ++++++%, ***, ---, ===, ~~~, ###, $$$, ///, ___) with '' (blank)
    text = REPEATED_SPECIAL_CHARS.sub('', text)
    text = SPACED_DIVIDER_RUNS.sub(' ', text)
    text = EXCESSIVE_PERIODS.sub('...', text)

    # 12. Punctuation spam cleanup
    text = EXCESSIVE_COMMAS.sub(',', text)
    text = EXCESSIVE_QUESTIONS.sub('???', text)
    text = EXCESSIVE_EXCLAMATIONS.sub('!!!', text)
    text = EXCESSIVE_QUOTES_D.sub('"', text)
    text = EXCESSIVE_QUOTES_S.sub("'", text)

    # 13. Clean whitespace
    text = text.replace('\r', ' ').replace('\t', ' ')
    text = EXCESSIVE_SPACES.sub(' ', text)

    res = text.strip()
    # If after removing pluses/dividers it became empty or pure divider/quote
    if PURE_DIVIDER_PARAGRAPH.match(res):
        return ""
    return res


def is_ad_or_watermark_paragraph(text: str) -> bool:
    """Returns True if the entire paragraph is an ad, promotional link, author note, or scraper watermark."""
    if not text:
        return True

    clean_p = text.strip()
    clean_p_lower = clean_p.lower()

    # Fast Author Note checks
    if AUTHOR_NOTE_HEADER.match(clean_p) or AUTHOR_NOTE_PREFIX.match(clean_p):
        return True

    # Discord link / invite check (guarding legitimate narrative uses of 'discord')
    if ('discord' in clean_p_lower or 'disc.gg' in clean_p_lower) and not DISCORD_STORY_CONTEXT.search(clean_p):
        if DISCORD_URL_REGEX.search(clean_p) or DISCORD_INVITE_PARAGRAPH.match(clean_p):
            return True

    # Patreon / Ko-Fi / PayPal / donation check
    if any(k in clean_p_lower for k in ['patreon', 'ko-fi', 'paypal', 'p4tre0n', 'p.a.t.r.e.o.n', 'pat-reon', 'pa-treon']):
        if DONATION_URL_REGEX.search(clean_p) or DONATION_PROMO_PARAGRAPH.match(clean_p):
            return True

    # Voting / Power Stones / Golden Tickets begging
    if len(clean_p) < 300 and VOTE_PROMO_PARAGRAPH.match(clean_p):
        return True

    # General short link checks
    if len(clean_p_lower) < 160 and re.search(r'https?:\s*//(?:www\.)?ko-fi\.com/\S+|ko-fi\.com/\S+', clean_p_lower):
        return True

    if 'jksmangafreewebnovel.com' in clean_p_lower:
        return True

    for pat in STANDALONE_AD_PATTERNS:
        if pat.search(clean_p_lower):
            return True

    return False


def clean_chapter_data(chapter: dict) -> dict:
    """
    Cleans an entire chapter dictionary in-place and returns it:
    - Cleans title
    - Cleans and filters paragraphs
    - Trims tail promo lists and author note blocks
    - Pops trailing filler phrases ("To Be Continued", "Thanks for reading", etc.)
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

    # 1. Tail cut: strip self-promo lists (e.g. "My other novels", book lists)
    # or author note headers found within the last 12 paragraphs of the chapter
    tail_window = min(12, len(cleaned_paragraphs))
    start_tail_idx = len(cleaned_paragraphs) - tail_window
    for i in range(len(cleaned_paragraphs) - 1, start_tail_idx - 1, -1):
        p_strip = cleaned_paragraphs[i].strip()
        if TAIL_CUT_TRIGGER_REGEX.match(p_strip):
            cleaned_paragraphs = cleaned_paragraphs[:i]
            break

    # 2. Pop trailing filler items (e.g. "To Be Continued", "New chapter coming soon", "Thanks for reading...", coins/unlock)
    while cleaned_paragraphs and TAIL_TRAILING_POP_REGEX.match(cleaned_paragraphs[-1].strip()):
        cleaned_paragraphs.pop()

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

    new_json = json.dumps(data, ensure_ascii=False)
    if orig_json != new_json:
        formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        tmp_file = filepath + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(formatted_json)
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
