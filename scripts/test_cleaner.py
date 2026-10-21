import re
import html
import unicodedata

def clean_paragraph_text(text: str) -> str:
    if not text:
        return ""

    # 1. Decode HTML entities (e.g. &amp;, &quot;, &#39;, &lt;, &gt;, &nbsp;)
    text = html.unescape(text)

    # 2. Fix explicit unicode escapes like \u003c, \u003e, \u0026 that were double-escaped as literal backslash-u
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

    # 6. Normalize mathematical monospace / bold unicode characters often used by pirate scrapers to evade filters
    text = unicodedata.normalize('NFKD', text)

    # 7. Repair corrupted UTF-8 replacement characters (U+FFFD: )
    contractions = [
        (r"\b(don)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(can)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(won)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(didn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(isn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(aren)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(wasn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(weren)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(hasn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(haven)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(hadn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(couldn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(shouldn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(wouldn)[\ufffd]+(t)\b", r"\1'\2"),
        (r"\b(i)[\ufffd]+(m)\b", r"\1'\2"),
        (r"\b(you)[\ufffd]+(re)\b", r"\1'\2"),
        (r"\b(he)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(she)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(it)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(we)[\ufffd]+(re)\b", r"\1'\2"),
        (r"\b(they)[\ufffd]+(re)\b", r"\1'\2"),
        (r"\b(i)[\ufffd]+(ve)\b", r"\1'\2"),
        (r"\b(you)[\ufffd]+(ve)\b", r"\1'\2"),
        (r"\b(we)[\ufffd]+(ve)\b", r"\1'\2"),
        (r"\b(they)[\ufffd]+(ve)\b", r"\1'\2"),
        (r"\b(i)[\ufffd]+(ll)\b", r"\1'\2"),
        (r"\b(you)[\ufffd]+(ll)\b", r"\1'\2"),
        (r"\b(he)[\ufffd]+(ll)\b", r"\1'\2"),
        (r"\b(she)[\ufffd]+(ll)\b", r"\1'\2"),
        (r"\b(it)[\ufffd]+(ll)\b", r"\1'\2"),
        (r"\b(we)[\ufffd]+(ll)\b", r"\1'\2"),
        (r"\b(they)[\ufffd]+(ll)\b", r"\1'\2"),
        (r"\b(that)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(what)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(there)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(here)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(who)[\ufffd]+(s)\b", r"\1'\2"),
        (r"\b(let)[\ufffd]+(s)\b", r"\1'\2"),
        # General possessive: word +  + s
        (r"([a-zA-Z0-9\]\)])[\ufffd]+(s)\b", r"\1'\2"),
        # Word-internal apostrophe: e.g. OHara -> O'Hara
        (r"([a-zA-Z])[\ufffd]+([a-zA-Z])", r"\1'\2"),
        # Ellipsis: 2 or more  in a row
        (r"[\ufffd]{2,}", r"..."),
    ]
    for pattern, repl in contractions:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # Corrupted dialogue quotes at start or end of text
    text = re.sub(r'^[\ufffd]+', '"', text)
    text = re.sub(r'[\ufffd]+$', '"', text)
    text = re.sub(r'[\ufffd]+\s', '" ', text)
    text = re.sub(r'\s[\ufffd]+', ' "', text)
    # Any remaining  replaced by empty string
    text = text.replace('', '').replace('\ufffd', '')

    # 8. Strip inline injected watermarks and stealth domain suffixes
    inline_watermarks = [
        r'[\'\"“‘\(]?\s*Search\s+[^\w\s]*Freewebnovel\.com[^\w\s]*\s+on\s+google\s*[\'\"”’\)]?',
        r'[\'\"“‘]?\s*Please\s+reading\s+on\s+Freewebnovel\.com\.?\s*[\'\"”’]?',
        r'[\'\"“‘]?\s*The\s+source\s+of\s+this\s+content\s+is\s+Freewebn[oᴏ]vel\.com\.?\s*[\'\"”’]?',
        r'[\'\"“‘]?\s*Source:\s*novgo\.co\s*[\'\"”’]?',
        r'[\'\"“‘]?\s*Updates\s+by\s+vipnovel\.com\s*[\'\"”’]?',
        r'Dear\s+readers!?\s*you\s+are\s+reading\s+on\s+our\s+content\s+(?:copy|stealing)\s+site\.?\s*Please\s+copy\s+and\s+search\s+this\s+link\s*[\'\"“]?\s*https?://\S+\s*[\'\"”]?\s*to\s+support\s+us',
        r'For\s+more,\s+visit:?\s*(?:AllFreeWebNovel|MtNovel|FreeWebNovel)\.com\.?',
        r'Find\s+authorized\s+novels\s+in\s+Webnovel\s*[,\.]?\s*faster\s+updates\s*[,\.]?\s*better\s+experience\s*[,\.]?\s*Please\s+click\s+(?:www\.webnovel\.com|https?://\S+)\s+for\s+visiting\.?',
        r'Please\s+bookmark\s+this\s+website\s+to\s+save\s+your\s+progress',
        r'All\s+ɴᴏᴠᴇʟ\s+full\.co\S*',
        r'You\s+can\s+read\s+the\s+story\s+for\s+free\s+at\s+LatestNovel\.Net\s+or\s+NovelGreat\.Net\.?',
        r'BoxNovel\.com',
        r'if\s+those\s+who\s+wonder\s+were\s+I\s+copy\s+this\s+I\s+give\s+you\s+the\s+link:?\s*https?://nyx-translation\.com/?',
        r'No\s+movement\.?\\n\(o\)v\.e\\l\.com',
        r'free\\NovelBin\.c\s*o\(m\)',
    ]
    for iw in inline_watermarks:
        text = re.sub(iw, '', text, flags=re.IGNORECASE)

    # Stealth domain suffix attached to sentence ends: e.g. "said.freewebnovel.com" -> "said."
    text = re.sub(r'([\.\!\?\"\'”’\)])\s*(?:https?://)?(?:www\.)?(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b[\'\"”’\.\,\)]*', r'\1', text, flags=re.I)
    text = re.sub(r'(?<=[a-zA-Z0-9])\.(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b', '.', text, flags=re.I)
    text = re.sub(r'[\s\(\[\'\"]*(?:https?://)?(?:www\.)?(?:free|allfree|mt)?webnovel\.(?:com|net|org)\b[\s\)\]\'\"\.]*', ' ', text, flags=re.I)

    # 9. Clean redundant multiple quotes like """Hello""" -> "Hello"
    text = re.sub(r'"{2,}', '"', text)
    text = re.sub(r"'{2,}", "'", text)

    # 10. Clean excessive spaces, tabs, and non-breaking whitespace
    text = re.sub(r'[\r\t\u00a0\u200b\u200e\u200f\ufeff]+', ' ', text)
    text = re.sub(r' {2,}', ' ', text)

    # 11. Replace runs of more than 5 plus signs (e.g. ++++++++++++ or ++++++%) used as status borders/dividers
    # with asterisks (*****) so TTS engines do not vocalize "plus plus plus..."
    text = re.sub(r'\+{6,}%?', '*****', text)

    return text.strip()


def is_ad_or_watermark_paragraph(text: str) -> bool:
    """Returns True if the entire paragraph is an ad, promotional link, or scraper watermark."""
    if not text:
        return True

    clean_p = text.strip().lower()

    # Standalone Discord / Social / Patreon links
    if re.fullmatch(r'https?://(?:discord(?:\.gg|app\.com)|t\.me|twitter\.com|instagram\.com)/\S+', clean_p):
        return True

    if re.search(r'^(?:join\s+)?(?:the\s+)?discord(?:\s+server)?\s*:?\s*https?://discord', clean_p):
        return True

    if len(clean_p) < 120 and re.search(r'https?://(?:www\.)?discord(?:\.gg|app\.com/\S+)', clean_p):
        return True

    # Standalone Patreon / Donation lines
    if re.search(r'^(?:my\s+)?p[4a]tre[0o][mn](?:\.com)?\s*(?:is)?:?\s*(?:https?://|pa[-_ ]?tre[-_ ]?[0o]?[mn]\.com)', clean_p):
        return True
    if re.search(r'p[4a]t?r?[-_ ]?e?[-_ ]?[0o]?[mn]\.com/aidnovels', clean_p):
        return True
    if re.search(r'https?://(?:www\.)?ko-fi\.com/\S+', clean_p) and len(clean_p) < 80:
        return True
    if re.search(r'^(?:remember\s+to\s+)?support\s+(?:me|the\s+author)\s+on\s+pa[-_ ]*tre[0o]n', clean_p):
        return True
    if re.search(r'visit\s+my\s+pa[-_ ]*tre[0o]n:?\s*pa[-_ ]*tre[0o]n\.com/', clean_p):
        return True
    if re.search(r'^(?:if\s+you\s+want\s+to\s+support\s+(?:you\s+can\s+)?on\s+my\s+)?p[\.\s_-]*a[\.\s_-]*t[\.\s_-]*r[\.\s_-]*e[\.\s_-]*o[\.\s_-]*n', clean_p):
        return True
    if 'jksmangafreewebnovel.com' in clean_p:
        return True

    # Standalone website watermarks
    standalone_sites = [
        r'^(?:source:?\s*)?(?:freewebnovel|novelping|webnovel|novelbin|boxnovel|mtnovel|vipnovel|allfreewebnovel|latestnovel|novelgreat|novgo)\.com?$',
        r'^visit\s+.*?\s+for\s+(?:more\s+)?(?:chapters|updates)\.?$',
        r'^read\s+(?:more\s+)?(?:latest\s+)?chapters?\s+(?:at|on)\s+.*$',
        r'^advertisement$',
        r'^prev(?:ious)?\s*chapter$',
        r'^next\s*chapter$',
        r'^chapter\s*list$'
    ]
    for sp in standalone_sites:
        if re.search(sp, clean_p):
            return True

    return False


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    samples = [
        r'\"Christine!\" Alan jumped on the stage and ran towards Christine, but Evelyn had moved before him.',
        '\"Don\ufffdt worry, I protected her mana circuits from harm. But even I can\ufffdt eliminate [Last Stand]\ufffds side-effects completely.\"',
        r'\"\"\"\"\"OOOOOOOOOOHHHHHHHHHHHHHH!!!\"\"\"\"\"',
        r'\u003cCongratulations you have been granted the Vampire System\u003e',
        '“Come, let Big Sister hug you.” Bewitching Maiden Rou stretched out her hand.Search Freewebnovel.com. on google',
        'They didn’t hide their tracks. In any case, it would have been extremely difficult to hide. “Search (Freewebnovel.com() on google” This was because they needed to use numerous Transfer Formations',
        r'When it came to the \Sacred Land, the change of day',
        r'what did I do to get this lucky?\ Kent said to himself',
        r'https://discord.gg/4FETZAf',
        r'P4TRE0N: patre-om.com/aidnovels',
        r'BoxNovel.com',
        r'if those who wonder were I copy this I give you the link:https://nyx-translation.com/',
        r'patre-on.com/aidnovels',
        r'Join Discord: https://discord.gg/HQFRrS8y6Q',
        r'If you want to support you can on my P.A.T.R.E.O.N: jksmangafreewebnovel.com',
        '“It looks like I won’t be able to leave any time soon. Help me tell my friends that they can leave first and not worry about me,” Ling Han said.freewebnovel.com',
        '"... To open the door, two hearts must be connected." Lena read the line on the door. "What does it mean?" She tilted her head.freewebnovel.com',
        '[75\\95 HP]',
        'trailing backslash test\\',
        '++++++++++++++++',
        '++++++++++++',
        '++++++%',
        'Strength +1',
        'Luck value + Divine Sin Wheel',
        'Evolution Progress: 100%',
        '+50%'
    ]

    for s in samples:
        cleaned = clean_paragraph_text(s)
        is_ad = is_ad_or_watermark_paragraph(cleaned)
        print(f"BEFORE: {s}")
        print(f"CLEAN : {cleaned}")
        print(f"IS_AD : {is_ad}\n")
