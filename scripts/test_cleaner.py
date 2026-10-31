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
    assert clean_paragraph_text('+++') == '', "Three pluses removed completely"
    assert clean_paragraph_text('***') == '', "Three asterisks removed completely"
    assert clean_paragraph_text('===') == '', "Three equals removed completely"
    assert clean_paragraph_text('~~~') == '', "Three tildes removed completely"
    assert clean_paragraph_text('###') == '', "Three hashes removed completely"
    assert clean_paragraph_text('$$$') == '', "Three dollar signs removed completely"
    assert clean_paragraph_text('///') == '', "Three slashes removed completely"
    assert clean_paragraph_text('___') == '', "Three underscores removed completely"
    assert clean_paragraph_text('Status: ++++++++++++++++ Level Up') == 'Status: Level Up', "Inline pluses removed cleanly"
    assert clean_paragraph_text('Item rating: *** (Super Rare)') == 'Item rating: (Super Rare)', "Inline asterisks removed cleanly"
    assert clean_paragraph_text('Strength +1') == 'Strength +1', "Real stat plus must be preserved"
    assert clean_paragraph_text('Language: C++') == 'Language: C++', "C++ double plus preserved"
    assert clean_paragraph_text('Evolution Progress: 100%') == 'Evolution Progress: 100%', "Stat percentage preserved"
    assert clean_paragraph_text('+50%') == '+50%', "Stat buff preserved"
    assert clean_paragraph_text('Class: Dust Lord [SSS+(?)]') == 'Class: Dust Lord [SSS+(?)]', "Class SSS+ preserved"
    assert clean_paragraph_text('"Wait..." he whispered.') == '"Wait..." he whispered.', "Standard ellipsis preserved"
    assert clean_paragraph_text('--------------------') == '', "Divider line dropped"
    assert clean_paragraph_text('********************') == '', "Asterisks divider dropped"
    assert clean_paragraph_text('""') == '', "Empty quote line dropped"
    assert clean_paragraph_text('Hello，world！') == 'Hello, world!', "Fullwidth punctuation translated"
    assert clean_paragraph_text('Soft\xadhyphen') == 'Softhyphen', "Soft hyphen removed"
    assert clean_paragraph_text('â€™Helloâ€œ') == "'Hello\"", "Mojibake repaired"

    # Author Note, Discord, Patreon, and Voting assertions
    assert is_ad_or_watermark_paragraph('<Author Note>') is True, "<Author Note> must be detected as ad/meta"
    assert is_ad_or_watermark_paragraph("<Author's Note>") is True, "<Author's Note> must be detected as ad/meta"
    assert is_ad_or_watermark_paragraph("[Author’s Note: End of Volume VIII: Into the Void Temple & Back.]") is True, "Author note detected"
    assert is_ad_or_watermark_paragraph("[A/N: Sasha is wearing the same outfit as the illustration]") is True, "A/N detected"
    assert is_ad_or_watermark_paragraph("A/N: For today’s revelation... imagine if Phei had chosen...") is True, "A/N prefix detected"
    assert is_ad_or_watermark_paragraph("Author's Note: Hello, everyone. First and foremost, I want to express my gratitude...") is True, "Author's Note prefix detected"

    assert is_ad_or_watermark_paragraph("Join our Discord Server :- https://discord/gg/pandanovel") is True, "Discord invite detected"
    assert is_ad_or_watermark_paragraph("And congrats webtoon unlocked, join the discord for more info, link in the synopsis.") is True, "Discord mention detected"
    assert is_ad_or_watermark_paragraph("He was sowing discord between you and Isabella.") is False, "Story narrative discord must NOT be dropped"

    assert is_ad_or_watermark_paragraph("Also, support me on pat-reon.com/aidnovels") is True, "Patreon link detected"
    assert is_ad_or_watermark_paragraph("Get access to the MVS webtoon on P.a.t.r.e.o.n it’s only $3 dollar a month And read My werewolf system Exclusively.") is True, "Patreon with dots detected"
    assert is_ad_or_watermark_paragraph("My P4TR30N is: pa-treon.com/aidnovels --> You can read until 20 chapters more") is True, "P4TRE0N detected"

    assert is_ad_or_watermark_paragraph("Don't forget to vote to support the book if you like it.") is True, "Vote begging detected"
    assert is_ad_or_watermark_paragraph("Keep the Magic Castles and Golden Tickets coming!") is True, "Golden tickets begging detected"
    assert is_ad_or_watermark_paragraph("4/4 Keep the Magic Castles and Golden Tickets coming! Looks like we’ll finish top 10 this month!") is True, "Magic castles begging detected"

    # End-to-end chapter test with Author Notes, Discord, Voting, and Tail Self-Promo
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
            "\"\"",
            "He knew his enemies were sowing discord among the allies.",
            "Updates by Freewebnovel. com",
            "[A/N: Remember to check my character designs!]",
            "This is a real paragraph of the story.",
            "Join Discord: https://discord.gg/HQFRrS8y6Q",
            "Don't forget to vote to support the book if you like it.",
            "--- To Be Continued ---",
            "My other novels",
            "1. Cultivator With Modern AI",
            "2. Primordial 'Dual Cultivator' Dragon With System",
            "If you guys haven't read all four, maybe you can take a peek at them."
        ]
    }
    cleaned_ch = clean_chapter_data(test_ch)
    assert "Chapter 1: The Beginning" not in cleaned_ch["paragraphs"], "Duplicate title in P0 dropped"
    assert "++++++++++++++++" not in cleaned_ch["paragraphs"], "Plus divider dropped"
    assert "--------------------" not in cleaned_ch["paragraphs"], "Dash divider dropped"
    assert "Updates by Freewebnovel. com" not in cleaned_ch["paragraphs"], "Watermark dropped"
    assert "[A/N: Remember to check my character designs!]" not in cleaned_ch["paragraphs"], "Author note dropped"
    assert "Join Discord: https://discord.gg/HQFRrS8y6Q" not in cleaned_ch["paragraphs"], "Discord dropped"
    assert "Don't forget to vote to support the book if you like it." not in cleaned_ch["paragraphs"], "Vote begging dropped"
    assert "My other novels" not in cleaned_ch["paragraphs"], "Tail self promo cut"
    assert "1. Cultivator With Modern AI" not in cleaned_ch["paragraphs"], "Tail book list cut"
    assert "--- To Be Continued ---" not in cleaned_ch["paragraphs"], "To Be Continued popped"
    assert any("sowing discord" in p for p in cleaned_ch["paragraphs"]), "Narrative discord preserved in story"
    assert any("This is a real paragraph of the story." in p for p in cleaned_ch["paragraphs"]), "Real story preserved"
    assert len(cleaned_ch["paragraphs"]) == 4, f"Expected 4 clean paragraphs, got {len(cleaned_ch['paragraphs'])}: {cleaned_ch['paragraphs']}"

    print("ALL CLEANER UNIT & INTEGRATION TESTS PASSED!")
