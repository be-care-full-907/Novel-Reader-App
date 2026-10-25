import re
import html
import unicodedata

from novel_cleaner import clean_paragraph_text, is_ad_or_watermark_paragraph, clean_chapter_data

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
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
        '"Now you\'re at your peak state, go and finish this guy as soon as possible." Your next journey awaits at m v|l-e-NovelBin',
        'Updates by Freewebnovel. com',
        'Visit our comic site ReadReadReadFreeWebNovel.live',
        'You’re reading on ReadReadReadReadFreeWebNovel. com Thanks!',
        '[75\\95 HP]',
        'trailing backslash test\\',
        '++++++++++++++++',
        '++++++++++++',
        '++++++%',
        'Status: ++++++++++++++++ Level Up',
        'Strength +1',
        'Luck value + Divine Sin Wheel',
        'Evolution Progress: 100%',
        '+50%',
        'Class: Dust Lord [SSS+(?)]',
        '--------------------',
        '********************',
        '""',
        '"',
        'Hello，world！',
        'Soft\xadhyphen',
        'â€™Helloâ€œ'
    ]

    print("=== RUNNING NOVEL CLEANER TEST SAMPLES ===")
    for s in samples:
        cleaned = clean_paragraph_text(s)
        is_ad = is_ad_or_watermark_paragraph(cleaned)
        print(f"BEFORE: {s}")
        print(f"CLEAN : {cleaned}")
        print(f"IS_AD : {is_ad}\n")

    # Critical assertions
    assert clean_paragraph_text('++++++++++++++++') == '', "Pluses must be removed completely"
    assert clean_paragraph_text('++++++++++++') == '', "Pluses must be removed completely"
    assert clean_paragraph_text('++++++%') == '', "Pluses must be removed completely"
    assert clean_paragraph_text('Status: ++++++++++++++++ Level Up') == 'Status: Level Up', "Inline pluses removed cleanly"
    assert clean_paragraph_text('Strength +1') == 'Strength +1', "Real stat plus must be preserved"
    assert clean_paragraph_text('Evolution Progress: 100%') == 'Evolution Progress: 100%', "Stat percentage preserved"
    assert clean_paragraph_text('+50%') == '+50%', "Stat buff preserved"
    assert clean_paragraph_text('Class: Dust Lord [SSS+(?)]') == 'Class: Dust Lord [SSS+(?)]', "Class SSS+ preserved"
    assert clean_paragraph_text('--------------------') == '', "Divider line dropped"
    assert clean_paragraph_text('********************') == '', "Asterisks divider dropped"
    assert clean_paragraph_text('""') == '', "Empty quote line dropped"
    assert clean_paragraph_text('Hello，world！') == 'Hello, world!', "Fullwidth punctuation translated"
    assert clean_paragraph_text('Soft\xadhyphen') == 'Softhyphen', "Soft hyphen removed"
    assert clean_paragraph_text('â€™Helloâ€œ') == "'Hello\"", "Mojibake repaired"

    # End-to-end chapter test
    test_ch = {
        "title": "Chapter 1: The Beginning",
        "chapter_index": 1,
        "paragraphs": [
            "Chapter 1: The Beginning",
            "++++++++++++++++",
            "Status: ++++++++++++++++ Level Up",
            "Strength +1 (+50%)",
            "--------------------",
            "Search Freewebnovel.com. on google",
            "\"\""
            "This is a real paragraph of the story.",
            "Updates by Freewebnovel. com",
            "Join Discord: https://discord.gg/HQFRrS8y6Q"
        ]
    }
    cleaned_ch = clean_chapter_data(test_ch)
    assert "Chapter 1: The Beginning" not in cleaned_ch["paragraphs"], "Duplicate title in P0 dropped"
    assert "++++++++++++++++" not in cleaned_ch["paragraphs"], "Plus divider dropped"
    assert "--------------------" not in cleaned_ch["paragraphs"], "Dash divider dropped"
    assert "Updates by Freewebnovel. com" not in cleaned_ch["paragraphs"], "Watermark dropped"
    assert "Join Discord: https://discord.gg/HQFRrS8y6Q" not in cleaned_ch["paragraphs"], "Discord dropped"
    assert len(cleaned_ch["paragraphs"]) == 3, f"Expected 3 clean paragraphs, got {len(cleaned_ch['paragraphs'])}: {cleaned_ch['paragraphs']}"

    print("ALL CLEANER UNIT & INTEGRATION TESTS PASSED!")
