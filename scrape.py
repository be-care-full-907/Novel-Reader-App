"""
scrape.py
---------
Interactive Novel Scraper & Simultaneous Cleaner.
Designed for simple, one-command execution by the user.

Usage:
  1. Interactive Menu Mode:
     python scrape.py

  2. Command-Line Mode:
     python scrape.py --novel fourth-princes-debauchery --start 401 --end 500
     python scrape.py --novel 6-times-a-day --start 151 --end 200 --workers 4
     python scrape.py --all
"""

import os
import sys
import re
import json
import time
import random
import subprocess
import argparse
import urllib.request
import urllib.error
import math
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from novel_scraper import NovelScraper
from novel_cleaner import clean_chapter_data

# Comprehensive catalog of all 13 supported novels
NOVELS_CATALOG = {
    "fourth-princes-debauchery": {
        "id": "fourth-princes-debauchery",
        "title": "Fourth Prince's Debauchery",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "fourth-princes-debauchery"),
        "default_start": 1,
        "max_chapters": 734,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=fourth-princes-debauchery"
    },
    "infinite-mana-in-the-apocalypse": {
        "id": "infinite-mana-in-the-apocalypse",
        "title": "Infinite Mana In The Apocalypse",
        "target_dir": os.path.join(PROJECT_ROOT, "data"),
        "default_start": 1780,
        "max_chapters": 5873,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=infinite-mana-in-the-apocalypse"
    },
    "supreme-harem-god-system": {
        "id": "supreme-harem-god-system",
        "title": "Supreme Harem God System",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "supreme-harem-god-system"),
        "default_start": 1,
        "max_chapters": 2410,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=supreme-harem-god-system"
    },
    "my-vampire-system": {
        "id": "my-vampire-system",
        "title": "My Vampire System",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "my-vampire-system"),
        "default_start": 1,
        "max_chapters": 2545,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=my-vampire-system"
    },
    "alchemy-emperor-of-the-divine-dao": {
        "id": "alchemy-emperor-of-the-divine-dao",
        "title": "Alchemy Emperor of the Divine Dao",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "alchemy-emperor-of-the-divine-dao"),
        "default_start": 1,
        "max_chapters": 4932,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=alchemy-emperor-of-the-divine-dao"
    },
    "primordial-chaos-dragon-tower-harem-system": {
        "id": "primordial-chaos-dragon-tower-harem-system",
        "title": "Primordial Chaos Dragon Tower Harem System",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "primordial-chaos-dragon-tower-harem-system"),
        "default_start": 1,
        "max_chapters": 1916,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=primordial-chaos-dragon-tower-harem-system"
    },
    "my-three-wives-are-beautiful-vampires-novel": {
        "id": "my-three-wives-are-beautiful-vampires-novel",
        "title": "My Three Wives Are Beautiful Vampires",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "my-three-wives-are-beautiful-vampires-novel"),
        "default_start": 1,
        "max_chapters": 1162,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=my-three-wives-are-beautiful-vampires-novel"
    },
    "starting-with-an-sss-rank-goddess-summon": {
        "id": "starting-with-an-sss-rank-goddess-summon",
        "title": "Starting With An SSS-Rank Goddess Summon",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "starting-with-an-sss-rank-goddess-summon"),
        "default_start": 1,
        "max_chapters": 684,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=starting-with-an-sss-rank-goddess-summon"
    },
    "6-times-a-day": {
        "id": "6-times-a-day",
        "title": "6 Times a Day",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "6-times-a-day"),
        "default_start": 1,
        "max_chapters": 1364,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=6-times-a-day"
    },
    "my-taboo-harem": {
        "id": "my-taboo-harem",
        "title": "My Taboo Harem",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "my-taboo-harem"),
        "default_start": 1,
        "max_chapters": 1373,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=my-taboo-harem"
    },
    "dimensional-descent": {
        "id": "dimensional-descent",
        "title": "Dimensional Descent",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "dimensional-descent"),
        "default_start": 1,
        "max_chapters": 3294,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=dimensional-descent"
    },
    "raising-my-trash-ability-into-a-broken-sss-rank-skill": {
        "id": "raising-my-trash-ability-into-a-broken-sss-rank-skill",
        "title": "Raising My Trash Ability Into A Broken SSS-Rank Skill",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "raising-my-trash-ability-into-a-broken-sss-rank-skill"),
        "default_start": 1,
        "max_chapters": 888,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=raising-my-trash-ability-into-a-broken-sss-rank-skill"
    },
    "i-got-cheat-ability-in-a-different-world": {
        "id": "i-got-cheat-ability-in-a-different-world",
        "title": "I Got Cheat Ability In A Different World",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "i-got-cheat-ability-in-a-different-world"),
        "default_start": 1,
        "max_chapters": 107,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=i-got-cheat-ability-in-a-different-world"
    },
    "tsuki-ga-michibiku-isekai-douchuu": {
        "id": "tsuki-ga-michibiku-isekai-douchuu",
        "title": "Tsuki Ga Michibiku Isekai Douchuu",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "tsuki-ga-michibiku-isekai-douchuu"),
        "default_start": 1,
        "max_chapters": 503,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=tsuki-ga-michibiku-isekai-douchuu"
    },
    "oh-no-after-i-reincarnated-my-moms-became-son-cons": {
        "id": "oh-no-after-i-reincarnated-my-moms-became-son-cons",
        "title": "Oh No After I Reincarnated My Moms Became Son Cons",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "oh-no-after-i-reincarnated-my-moms-became-son-cons"),
        "default_start": 1,
        "max_chapters": 1127,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=oh-no-after-i-reincarnated-my-moms-became-son-cons"
    },
    "cheat-awakening": {
        "id": "cheat-awakening",
        "title": "Cheat Awakening",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "cheat-awakening"),
        "default_start": 1,
        "max_chapters": 764,
        "archive_url": "https://freewebnovel.com/novel/cheat-awakening"
    },
    "illicit-relationship": {
        "id": "illicit-relationship",
        "title": "Illicit Relationship",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "illicit-relationship"),
        "default_start": 1,
        "max_chapters": 1792,
        "archive_url": "https://freewebnovel.com/novel/illicit-relationship"
    }
}


def load_catalog_from_file():
    """Loads all novels from novels.json and updates NOVELS_CATALOG dynamically."""
    novels_json_path = os.path.join(PROJECT_ROOT, "novels.json")
    if not os.path.exists(novels_json_path):
        return
    try:
        with open(novels_json_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        if isinstance(catalog, list):
            for entry in catalog:
                nid = entry.get("id")
                if not nid:
                    continue
                rel_path = entry.get("data_path", f"data/{nid}/").strip("/\\")
                target_dir = os.path.join(PROJECT_ROOT, rel_path) if rel_path else os.path.join(PROJECT_ROOT, "data", nid)
                NOVELS_CATALOG[nid] = {
                    "id": nid,
                    "title": entry.get("title", nid.replace("-", " ").title()),
                    "target_dir": target_dir,
                    "default_start": entry.get("start_bundle_chapter", 1),
                    "max_chapters": entry.get("total_chapters", 2000),
                    "archive_url": f"https://novelping.com/ajax/chapter-archive?novelId={nid}"
                }
    except Exception as e:
        print(f"Warning: Failed to load novels.json: {e}")


def parse_novel_input(raw_input: str) -> Optional[dict]:
    """Parses a FreeWebNovel URL, NovelPing URL, or novel slug into a catalog entry."""
    val = raw_input.strip()
    if not val:
        return None

    slug = ""
    source_url = val

    # 1. FreeWebNovel formats
    m = re.search(r'freewebnovel\.com/novel/([^/?#]+)', val, re.I)
    if m:
        slug = m.group(1).rstrip(".html")
    if not slug:
        m = re.search(r'freewebnovel\.com/([^/?#]+)(?:/chapter|\.html)?', val, re.I)
        if m and m.group(1).lower() not in ('sort', 'genre', 'search', 'latest-novel'):
            slug = m.group(1).rstrip(".html")

    # 2. NovelPing formats
    if not slug:
        m = re.search(r'novelping\.com/book/([^/?#]+)', val, re.I)
        if m:
            slug = m.group(1).rstrip(".html")

    # 3. Plain URL or slug fallback
    if not slug:
        if val.startswith("http://") or val.startswith("https://"):
            parts = [p.rstrip(".html") for p in val.split('/') if p]
            if parts:
                slug = parts[-1]
        else:
            slug = val
            source_url = f"https://freewebnovel.com/novel/{slug}"

    slug = re.sub(r'[^a-z0-9_-]', '-', slug.lower()).strip('-')
    if not slug:
        return None

    title = slug.replace('-', ' ').title()

    # Query archive to get true online chapter count (FreeWebNovel first, then NovelPing)
    est_chapters = 2000
    try:
        fwn_url = f"https://freewebnovel.com/novel/{slug}"
        req = urllib.request.Request(fwn_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            fwn_html = r.read().decode('utf-8', errors='ignore')
        fwn_soup = BeautifulSoup(fwn_html, "html.parser")
        root = fwn_soup.find(id="indexListPage")
        if root and int(root.get("data-total-chapters") or 0) > 0:
            est_chapters = int(root["data-total-chapters"])
    except Exception:
        pass

    if est_chapters == 2000:
        try:
            archive_url = f"https://novelping.com/ajax/chapter-archive?novelId={slug}"
            req = urllib.request.Request(archive_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest"
            })
            with urllib.request.urlopen(req, timeout=12) as r:
                html = r.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(html, "html.parser")
                valid_links = [a for a in soup.find_all("a") if a.get("href") and not a.get("href").startswith("#") and not a.get("href").startswith("javascript:")]
                if valid_links:
                    est_chapters = len(valid_links)
                else:
                    chs = re.findall(r'chapter[- ](\d+)', html, re.I)
                    if chs:
                        nums = [int(x) for x in chs]
                        est_chapters = max(nums)
        except Exception:
            pass

    return {
        "id": slug,
        "title": title,
        "author": "Web Novel",
        "cover_url": f"https://images.novelping.com/novel/{slug}.jpg",
        "source_url": source_url or f"https://freewebnovel.com/novel/{slug}",
        "data_path": f"data/{slug}/",
        "bundled_file": "chapters_1_50.json",
        "start_bundle_chapter": 1,
        "total_chapters": est_chapters,
        "description": f"Imported novel: {title}."
    }


def register_new_novel(novel_entry: dict):
    """Registers a new novel entry into novels.json and syncs to Android assets."""
    novels_json_path = os.path.join(PROJECT_ROOT, "novels.json")
    catalog = []
    if os.path.exists(novels_json_path):
        try:
            with open(novels_json_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except Exception:
            catalog = []

    # Check if already in catalog
    for n in catalog:
        if n.get("id") == novel_entry["id"]:
            log(f"Novel '{novel_entry['title']}' is already in catalog!")
            return

    catalog.append(novel_entry)

    # Write to root novels.json
    with open(novels_json_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    # Sync to android assets
    asset_catalog_path = os.path.join(PROJECT_ROOT, "android-app", "app", "src", "main", "assets", "novels.json")
    if os.path.exists(os.path.dirname(asset_catalog_path)):
        with open(asset_catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

    # Update in-memory catalog
    nid = novel_entry["id"]
    NOVELS_CATALOG[nid] = {
        "id": nid,
        "title": novel_entry["title"],
        "target_dir": os.path.join(PROJECT_ROOT, "data", nid),
        "default_start": novel_entry.get("start_bundle_chapter", 1),
        "max_chapters": novel_entry.get("total_chapters", 2000),
        "archive_url": f"https://novelping.com/ajax/chapter-archive?novelId={nid}"
    }
    log(f"✓ Registered '{novel_entry['title']}' in library catalog ({novel_entry['total_chapters']} chapters online)!")


def log(msg: str):
    """Prints timestamped message and flushes."""
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


def get_local_novel_status(novel_id: str) -> Tuple[int, int, int]:
    """Returns (count, min_ch, max_ch) for chapters existing on disk."""
    info = NOVELS_CATALOG[novel_id]
    target_dir = info["target_dir"]
    if not os.path.exists(target_dir):
        return (0, 0, 0)

    import glob
    if novel_id == "infinite-mana-in-the-apocalypse":
        bundle_files = glob.glob(os.path.join(target_dir, "chapters_*.json"))
    else:
        bundle_files = glob.glob(os.path.join(target_dir, "chapters_*.json"))

    ch_indices = set()
    for bf in bundle_files:
        try:
            with open(bf, "r", encoding="utf-8") as f:
                d = json.load(f)
                for ch in d.get("chapters", []):
                    ch_indices.add(ch.get("chapter_index"))
        except Exception:
            pass

    if not ch_indices:
        return (0, 0, 0)
    return (len(ch_indices), min(ch_indices), max(ch_indices))


def fetch_freewebnovel_archive(novel_id: str) -> Dict[int, Dict]:
    """
    Fetches complete chapter archive mapping directly from FreeWebNovel via its official AJAX endpoint.
    Returns: Dict[int, Dict] mapping chapter_number -> {chapter_number, title, url}.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    main_url = f"https://freewebnovel.com/novel/{novel_id}"
    log(f"Querying FreeWebNovel index for '{novel_id}': {main_url}...")

    html = ""
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(main_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as res:
                html = res.read().decode("utf-8", errors="ignore")
            if html:
                break
        except Exception:
            if attempt < 3:
                time.sleep(attempt * 2)

    if not html:
        log(f"FreeWebNovel index unavailable for '{novel_id}'.")
        return {}

    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(id="indexListPage")
    if not root:
        log(f"No '#indexListPage' found on FreeWebNovel for '{novel_id}'.")
        return {}

    total_chapters = int(root.get("data-total-chapters") or 0)
    if total_chapters <= 0:
        log(f"FreeWebNovel reported 0 chapters for '{novel_id}'.")
        return {}

    page_size = 200
    total_pages = math.ceil(total_chapters / page_size)
    log(f"FreeWebNovel reports {total_chapters} chapters across {total_pages} pages (pageSize={page_size}). Fetching archive...")

    page_headers = headers.copy()
    page_headers["X-Requested-With"] = "XMLHttpRequest"

    def fetch_page(p: int) -> Tuple[int, List[Tuple[str, str]]]:
        p_url = f"https://freewebnovel.com/novel/{novel_id}?ajax=chapters&page={p}&pageSize={page_size}"
        for attempt in range(1, 4):
            try:
                p_req = urllib.request.Request(p_url, headers=page_headers)
                with urllib.request.urlopen(p_req, timeout=20) as r:
                    data = json.loads(r.read().decode("utf-8"))
                s = BeautifulSoup(data.get("html", ""), "html.parser")
                links = []
                for a in s.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href or href.startswith("#") or href.startswith("javascript:"):
                        continue
                    full_url = href if href.startswith("http") else f"https://freewebnovel.com{href}"
                    title = (a.get("title") or a.get_text(strip=True)).strip()
                    links.append((title, full_url))
                return p, links
            except Exception:
                if attempt < 3:
                    time.sleep(attempt)
        return p, []

    results = {}
    with ThreadPoolExecutor(max_workers=min(6, total_pages)) as executor:
        futures = [executor.submit(fetch_page, p) for p in range(1, total_pages + 1)]
        for fut in as_completed(futures):
            p, links = fut.result()
            results[p] = links

    raw_links = []
    for p in range(1, total_pages + 1):
        raw_links.extend(results.get(p, []))

    if not raw_links:
        return {}

    parsed_nums = []
    for idx, (title, full_url) in enumerate(raw_links):
        m = re.search(r'chapter[- ](\d+)', title, re.I)
        if not m:
            m = re.search(r'chapter[- ](\d+)', full_url, re.I)
        parsed_nums.append(int(m.group(1)) if m else None)

    valid_nums = [n for n in parsed_nums if n is not None]
    has_duplicates = len(valid_nums) != len(set(valid_nums))
    has_multi_book = any(re.search(r'\b(?:book|volume|vol)\s*\d+', title, re.I) for title, _ in raw_links)
    max_parsed = max(valid_nums) if valid_nums else 0
    collapsed_count = max_parsed > 0 and max_parsed < len(raw_links) * 0.75

    use_sequential_toc = has_duplicates or has_multi_book or collapsed_count

    chapter_map = {}
    for idx, (title, full_url) in enumerate(raw_links):
        seq_idx = idx + 1
        ch_num = seq_idx if use_sequential_toc else (parsed_nums[idx] if parsed_nums[idx] is not None else seq_idx)
        chapter_map[ch_num] = {
            "chapter_number": ch_num,
            "title": title or f"Chapter {ch_num}",
            "url": full_url
        }

    log(f"Successfully discovered {len(chapter_map)} chapters from FreeWebNovel for '{novel_id}'.")
    return chapter_map


def fetch_novelping_archive(novel_id: str) -> Dict[int, Dict]:
    """
    Fetches chapter archive mapping from NovelPing fallback.
    Returns: Dict[int, Dict] mapping chapter_number -> {chapter_number, title, url}.
    """
    archive_url = f"https://novelping.com/ajax/chapter-archive?novelId={novel_id}"
    log(f"Falling back to NovelPing archive: {archive_url}...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://novelping.com/book/{novel_id}"
    }

    html = ""
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(archive_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as res:
                html = res.read().decode("utf-8", errors="ignore")
            if html and len(html) > 500:
                break
        except Exception:
            time.sleep(attempt * 2)

    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    raw_links = []
    for a in soup.find_all("a"):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        title_attr = (a.get("title") or "").strip()
        inner_text = " ".join(a.stripped_strings) or a.get_text(strip=True)
        display_title = title_attr or inner_text
        full_url = href if href.startswith("http") else f"https://novelping.com{href}"

        m = re.search(r'chapter[- ](\d+)', display_title, re.I)
        if not m:
            m = re.search(r'chapter[- ](\d+)', href, re.I)
        parsed_num = int(m.group(1)) if m else None

        raw_links.append({
            "url": full_url,
            "title": display_title,
            "parsed_num": parsed_num
        })

    if not raw_links:
        log(f"NovelPing returned 0 chapter links for '{novel_id}'.")
        return {}

    total_links = len(raw_links)
    parsed_nums = [item["parsed_num"] for item in raw_links if item["parsed_num"] is not None]
    has_duplicates = len(parsed_nums) != len(set(parsed_nums))
    has_multi_book = any(re.search(r'\b(?:book|volume|vol)\s*\d+', item["title"], re.I) for item in raw_links)
    max_parsed = max(parsed_nums) if parsed_nums else 0
    collapsed_count = max_parsed > 0 and max_parsed < total_links * 0.75

    use_sequential_toc = has_duplicates or has_multi_book or collapsed_count

    chapter_map = {}
    if use_sequential_toc:
        log(f"Multi-book/volume or duplicate chapters detected on NovelPing for '{novel_id}'. Using sequential Table-of-Contents indexing (1 to {total_links}).")
        for idx, item in enumerate(raw_links):
            seq_idx = idx + 1
            chapter_map[seq_idx] = {
                "chapter_number": seq_idx,
                "title": item["title"] or f"Chapter {seq_idx}",
                "url": item["url"]
            }
    else:
        for idx, item in enumerate(raw_links):
            ch_num = item["parsed_num"] if item["parsed_num"] is not None else (idx + 1)
            chapter_map[ch_num] = {
                "chapter_number": ch_num,
                "title": item["title"] or f"Chapter {ch_num}",
                "url": item["url"]
            }

    log(f"Discovered {len(chapter_map)} unique chapters on NovelPing for '{novel_id}'.")
    return chapter_map


def fetch_archive_with_retry(novel_id: str, target_dir: str, force_refresh: bool = False, source_site: str = "auto") -> Dict[int, Dict]:
    """
    Fetches chapter archive mapping based on selected source_site:
      - 'freewebnovel' (or 'freenovel'): FreeWebNovel only
      - 'novelping': NovelPing only
      - 'auto': FreeWebNovel first, fallback to NovelPing
    Results are cached in target_dir/archive_cache.json only when non-empty and uncorrupted.
    """
    site_key = source_site.lower()
    if site_key in ("freewebnovel", "freenovel"):
        cache_filename = "archive_cache_freewebnovel.json"
    elif site_key == "novelping":
        cache_filename = "archive_cache_novelping.json"
    else:
        cache_filename = "archive_cache.json"

    cache_path = os.path.join(target_dir, cache_filename)
    if not force_refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached and isinstance(cached, dict) and len(cached) > 0:
                item1 = cached.get("1") or cached.get(1)
                is_corrupted = False
                if item1 and isinstance(item1, dict):
                    t1 = item1.get("title", "")
                    m_b = re.search(r'\b(?:book|volume|vol)\s*(\d+)', t1, re.I)
                    if m_b and int(m_b.group(1)) > 1:
                        is_corrupted = True

                cat_info = NOVELS_CATALOG.get(novel_id, {})
                expected_max = cat_info.get("max_chapters", 0)
                if expected_max > 100 and len(cached) < expected_max * 0.6:
                    is_corrupted = True

                if not is_corrupted:
                    log(f"Loaded {len(cached)} chapters from local archive cache ({cache_filename})")
                    return {int(k): v for k, v in cached.items()}
                else:
                    log(f"Cached archive for '{novel_id}' was corrupted or incomplete ({len(cached)} items vs expected ~{expected_max}); refreshing online archive...")
        except Exception:
            pass

    chapter_map = {}
    if site_key in ("freewebnovel", "freenovel"):
        log(f"Querying archive exclusively from FreeWebNovel for '{novel_id}'...")
        chapter_map = fetch_freewebnovel_archive(novel_id)
        if not chapter_map:
            cat_info = NOVELS_CATALOG.get(novel_id, {})
            est = cat_info.get("max_chapters", 2000)
            log(f"Warning: FreeWebNovel archive unavailable for '{novel_id}'. Generating synthetic FreeWebNovel index (1 to {est}).")
            chapter_map = {
                ch: {
                    "chapter_number": ch,
                    "title": f"Chapter {ch}",
                    "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch}"
                }
                for ch in range(1, est + 1)
            }
    elif site_key == "novelping":
        log(f"Querying archive exclusively from NovelPing for '{novel_id}'...")
        chapter_map = fetch_novelping_archive(novel_id)
        if not chapter_map:
            cat_info = NOVELS_CATALOG.get(novel_id, {})
            est = cat_info.get("max_chapters", 2000)
            log(f"Warning: NovelPing archive unavailable for '{novel_id}'. Generating synthetic NovelPing index (1 to {est}).")
            chapter_map = {
                ch: {
                    "chapter_number": ch,
                    "title": f"Chapter {ch}",
                    "url": f"https://novelping.com/book/{novel_id}/chapter-{ch}"
                }
                for ch in range(1, est + 1)
            }
    else: # auto
        # 1. Try FreeWebNovel FIRST
        chapter_map = fetch_freewebnovel_archive(novel_id)

        # 2. If FreeWebNovel failed or returned 0 chapters, fallback to NovelPing
        if not chapter_map:
            chapter_map = fetch_novelping_archive(novel_id)

        # 3. If both failed, generate synthetic index using FreeWebNovel direct URLs
        if not chapter_map:
            cat_info = NOVELS_CATALOG.get(novel_id, {})
            est = cat_info.get("max_chapters", 2000)
            log(f"Warning: Neither FreeWebNovel nor NovelPing archive available for '{novel_id}'. Generating synthetic chapter index (1 to {est}) with FreeWebNovel URLs.")
            chapter_map = {
                ch: {
                    "chapter_number": ch,
                    "title": f"Chapter {ch}",
                    "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch}"
                }
                for ch in range(1, est + 1)
            }

    # 4. Save to local archive cache ONLY if valid and non-empty
    if chapter_map:
        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in chapter_map.items()}, f, indent=2, ensure_ascii=False)
            log(f"Cached {len(chapter_map)} chapters to {cache_path}.")
        except Exception as e:
            log(f"Warning: Could not save archive cache: {e}")

    return chapter_map


def fetch_chapter_with_retries(scraper: NovelScraper, novel_id: str, ch_num: int, ch_meta: dict, max_retries: int = 5, source_site: str = "auto") -> dict:
    """Fetches and simultaneously cleans a single chapter with mirror failover based on source_site."""
    site_key = source_site.lower()
    candidate_urls = []
    if ch_meta and ch_meta.get("url"):
        candidate_urls.append(ch_meta["url"])
        slug_part = ch_meta["url"].rstrip("/").split("/")[-1].rstrip(".html")
        if slug_part:
            if site_key in ("freewebnovel", "freenovel"):
                candidate_urls.append(f"https://freewebnovel.com/novel/{novel_id}/{slug_part}")
            elif site_key == "novelping":
                candidate_urls.append(f"https://novelping.com/book/{novel_id}/{slug_part}")
            else:
                candidate_urls.append(f"https://freewebnovel.com/novel/{novel_id}/{slug_part}")
                candidate_urls.append(f"https://novelping.com/book/{novel_id}/{slug_part}")

    if site_key in ("freewebnovel", "freenovel"):
        candidate_urls.extend([
            f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}",
            f"https://freewebnovel.com/{novel_id}/chapter-{ch_num}.html"
        ])
    elif site_key == "novelping":
        candidate_urls.extend([
            f"https://novelping.com/book/{novel_id}/chapter-{ch_num}",
            f"https://novelping.com/book/{novel_id}/chapter-{ch_num}.html"
        ])
    else: # auto
        candidate_urls.extend([
            f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}",
            f"https://freewebnovel.com/{novel_id}/chapter-{ch_num}.html",
            f"https://novelping.com/book/{novel_id}/chapter-{ch_num}"
        ])

    seen = set()
    unique_candidates = [u for u in candidate_urls if not (u in seen or seen.add(u))]
    if site_key in ("freewebnovel", "freenovel"):
        unique_candidates = [u for u in unique_candidates if "freewebnovel.com" in u]
    elif site_key == "novelping":
        unique_candidates = [u for u in unique_candidates if "novelping.com" in u]

    last_error = None
    for url in unique_candidates:
        for attempt in range(1, max_retries + 1):
            try:
                ch_data = scraper.fetch_chapter(url)
                paragraphs = ch_data.get("paragraphs", [])
                if paragraphs and len(paragraphs) > 0:
                    meta_title = ch_meta.get("title") if ch_meta else ""
                    page_title = ch_data.get("title") or ""
                    # Preserve book/volume titles from TOC
                    if meta_title and re.search(r'\b(?:book|volume|vol)\s*\d+', meta_title, re.I):
                        final_title = meta_title
                    else:
                        final_title = page_title or meta_title or f"Chapter {ch_num}"

                    ch_payload = {
                        "chapter_index": ch_num,
                        "title": final_title,
                        "url": url,
                        "paragraphs": paragraphs,
                        "sentences": ch_data.get("sentences", []),
                        "word_count": ch_data.get("word_count", 0)
                    }
                    # Simultaneous cleaning
                    return clean_chapter_data(ch_payload)
                else:
                    time.sleep(0.8)
            except urllib.error.HTTPError as e:
                last_error = e
                if e.code == 429:
                    # Switch immediately to next mirror
                    break
                elif e.code in (502, 503, 504):
                    time.sleep(attempt * 1.5 + random.uniform(0.3, 0.8))
                else:
                    time.sleep(1.0)
            except Exception as e:
                last_error = e
                time.sleep(attempt * 1.2)

    raise RuntimeError(f"Ch. {ch_num} failed across all candidate mirrors. Last error: {last_error}")


def is_bundle_complete(bundle_path: str, expected_count: int) -> bool:
    """Checks if bundle file is valid and complete on disk."""
    if not os.path.exists(bundle_path) or os.path.getsize(bundle_path) < 1000:
        return False
    try:
        with open(bundle_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chs = data.get("chapters", [])
        return len(chs) == expected_count and all(len(c.get("paragraphs", [])) > 0 for c in chs)
    except Exception:
        return False


def update_manifest(output_dir: str, bundle_filename: str, start_ch: int, end_ch: int, count: int, novel_id: str):
    """Updates index.json manifest atomically."""
    manifest_path = os.path.join(output_dir, "index.json")
    manifest = {"novel_id": novel_id, "bundles": []}

    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {"novel_id": novel_id, "bundles": []}

    bundles = manifest.get("bundles", [])
    bundles = [b for b in bundles if b.get("bundle_file") != bundle_filename]
    bundles.append({
        "bundle_file": bundle_filename,
        "start_chapter": start_ch,
        "end_chapter": end_ch,
        "chapter_count": count,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    })
    bundles.sort(key=lambda b: b["start_chapter"])
    manifest["bundles"] = bundles

    tmp_path = manifest_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, manifest_path)


def git_commit_and_push(novel_id: str, bundle_file: str, s_ch: int, e_ch: int) -> bool:
    """Commits and pushes scraped bundles to GitHub with retry and conflict protection."""
    try:
        # 1. Clean up any lingering merge/rebase conflict states
        merge_head = os.path.join(PROJECT_ROOT, ".git", "MERGE_HEAD")
        rebase_apply = os.path.join(PROJECT_ROOT, ".git", "rebase-apply")
        rebase_merge = os.path.join(PROJECT_ROOT, ".git", "rebase-merge")
        if os.path.exists(merge_head):
            subprocess.run(["git", "merge", "--abort"], cwd=PROJECT_ROOT, capture_output=True)
        if os.path.exists(rebase_apply) or os.path.exists(rebase_merge):
            subprocess.run(["git", "rebase", "--abort"], cwd=PROJECT_ROOT, capture_output=True)

        # 2. Stage specific novel data and catalog manifests
        target_dir = os.path.join("data", novel_id)
        add_files = [target_dir, "novels.json"]
        asset_novels = os.path.join("android-app", "app", "src", "main", "assets", "novels.json")
        if os.path.exists(os.path.join(PROJECT_ROOT, asset_novels)):
            add_files.append(asset_novels)

        subprocess.run(["git", "add"] + add_files, cwd=PROJECT_ROOT, capture_output=True, text=True)

        # 3. Check if there are staged changes to commit
        diff_res = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=PROJECT_ROOT)
        if diff_res.returncode == 0:
            log("No changes to commit for git push.")
            return True

        commit_msg = f"Add & clean chapters {s_ch}-{e_ch} for {novel_id}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=PROJECT_ROOT, capture_output=True, text=True)

        # 4. Push with pull --rebase fallback (never interactive merge)
        for attempt in range(1, 4):
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_ROOT, capture_output=True, text=True)
            if push_res.returncode == 0:
                log("Successfully pushed to GitHub origin/main!")
                return True

            log(f"Push attempt {attempt} failed, pulling remote changes with rebase...")
            pull_res = subprocess.run(["git", "pull", "--rebase", "--autostash", "-X", "ours", "origin", "main"], cwd=PROJECT_ROOT, capture_output=True, text=True)
            if pull_res.returncode != 0:
                # Always abort rebase so the working tree is NEVER left in a conflicted state
                subprocess.run(["git", "rebase", "--abort"], cwd=PROJECT_ROOT, capture_output=True)
                log("Notice: Remote rebase conflict avoided. Clean local data preserved.")
                break

            time.sleep(attempt * 2)

        log("Notice: Local bundles saved cleanly. Push can be done manually via 'git push origin main'.")
        return False
    except Exception as e:
        log(f"Git push notice: {e}")
        return False


def scrape_novel_range(
    novel_id: str,
    start_ch: int,
    end_ch: int,
    workers: int = 4,
    push: bool = True,
    chunk_size: int = 50,
    source_site: str = "auto"
):
    """Scrapes, cleans, and bundles a specified range for a novel."""
    info = NOVELS_CATALOG[novel_id]
    novel_title = info["title"]
    target_dir = info["target_dir"]
    os.makedirs(target_dir, exist_ok=True)

    log(f"\n{'='*70}")
    log(f"  SCRAPING: {novel_title}")
    log(f"  Range: Chapters {start_ch} to {end_ch} | Workers: {workers}")
    log(f"  Source Site: {source_site.upper()}")
    log(f"  Auto-Clean: ON (zero backslashes, zero ads, TTS ready)")
    log(f"{'='*70}\n")

    chapter_map = fetch_archive_with_retry(novel_id, target_dir, source_site=source_site)

    slices: List[Tuple[int, int]] = []
    curr = start_ch
    while curr <= end_ch:
        slice_end = min(curr + chunk_size - 1, end_ch)
        slices.append((curr, slice_end))
        curr = slice_end + 1

    scraper = NovelScraper()

    for idx, (s_ch, e_ch) in enumerate(slices, 1):
        slice_count = e_ch - s_ch + 1
        bundle_filename = f"chapters_{s_ch}_{e_ch}.json"
        bundle_path = os.path.join(target_dir, bundle_filename)

        if is_bundle_complete(bundle_path, slice_count):
            log(f"[{idx}/{len(slices)}] Bundle {bundle_filename} is already complete on disk. Skipping.")
            update_manifest(target_dir, bundle_filename, s_ch, e_ch, slice_count, novel_id)
            continue

        log(f"\n--- [{idx}/{len(slices)}] Fetching Chapters {s_ch} to {e_ch} ({slice_count} chapters) ---")
        t_start = time.time()
        bundled_chapters = []
        chapters_to_fetch = list(range(s_ch, e_ch + 1))

        default_url_prefix = "https://novelping.com/book" if source_site.lower() == "novelping" else "https://freewebnovel.com/novel"
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_num = {}
            for ch_num in chapters_to_fetch:
                ch_meta = chapter_map.get(ch_num, {
                    "chapter_number": ch_num,
                    "title": f"Chapter {ch_num}",
                    "url": f"{default_url_prefix}/{novel_id}/chapter-{ch_num}"
                })
                f = executor.submit(fetch_chapter_with_retries, scraper, novel_id, ch_num, ch_meta, 5, source_site)
                future_to_num[f] = ch_num
                time.sleep(0.5)

            for future in as_completed(future_to_num):
                ch_num = future_to_num[future]
                try:
                    res = future.result()
                    bundled_chapters.append(res)
                    p_count = len(res.get("paragraphs", []))
                    log(f"  ✓ Ch. {ch_num} ({res.get('title','')}) - {p_count} paras [{len(bundled_chapters)}/{slice_count}]")
                except Exception as e:
                    log(f"  ✗ Ch. {ch_num} failed: {e}")

        # Gap verification and rescue
        fetched_indexes = set(c["chapter_index"] for c in bundled_chapters)
        missing = [ch for ch in range(s_ch, e_ch + 1) if ch not in fetched_indexes]

        if missing:
            log(f"[Rescue Pass] Fetching {len(missing)} missed chapters: {missing}...")
            for ch_num in list(missing):
                ch_meta = chapter_map.get(ch_num)
                try:
                    rescued = fetch_chapter_with_retries(scraper, novel_id, ch_num, ch_meta, max_retries=6, source_site=source_site)
                    bundled_chapters.append(rescued)
                    missing.remove(ch_num)
                    log(f"  ✓ Rescued Ch. {ch_num}!")
                except Exception as e:
                    log(f"  ✗ Rescue failed for Ch. {ch_num}: {e}")

        fetched_indexes = set(c["chapter_index"] for c in bundled_chapters)
        final_missing = [ch for ch in range(s_ch, e_ch + 1) if ch not in fetched_indexes]
        if final_missing:
            log(f"Warning: Incomplete bundle {bundle_filename}! Missing: {final_missing}")

        bundled_chapters.sort(key=lambda c: c["chapter_index"])

        bundle_payload = {
            "novel_id": novel_id,
            "start_chapter": s_ch,
            "end_chapter": e_ch,
            "total_chapters": len(bundled_chapters),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "chapters": bundled_chapters
        }

        tmp_path = bundle_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(bundle_payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, bundle_path)

        update_manifest(target_dir, bundle_filename, s_ch, e_ch, len(bundled_chapters), novel_id)
        elapsed = round(time.time() - t_start, 1)
        log(f"Saved & Cleaned: {bundle_filename} ({len(bundled_chapters)} chs) in {elapsed}s")

        if push:
            git_commit_and_push(novel_id, bundle_filename, s_ch, e_ch)

    log(f"\n[DONE] Finished processing '{novel_title}'!\n")


def interactive_menu():
    """Renders interactive menu for the user."""
    while True:
        print("\n" + "="*75)
        print("                 📚 NOVEL SCRAPER & SIMULTANEOUS CLEANER")
        print("="*75)

        novel_keys = list(NOVELS_CATALOG.keys())
        for idx, nid in enumerate(novel_keys, 1):
            info = NOVELS_CATALOG[nid]
            count, min_ch, max_ch = get_local_novel_status(nid)
            online_max = info["max_chapters"]

            if count >= online_max:
                status_str = f"Ch {min_ch}-{max_ch} ({count}/{online_max}) [COMPLETE ✓]"
            elif count > 0:
                status_str = f"Ch {min_ch}-{max_ch} ({count}/{online_max}) [Missing Ch {max_ch+1}-{online_max}]"
            else:
                status_str = f"Not downloaded yet (Online: {online_max} chapters)"

            print(f" [{idx:2d}] {info['title'][:44]:<44} | {status_str}")

        print("-" * 75)
        print(" [ +] Add a NEW novel (Paste FreeWebNovel or NovelPing URL)")
        print(" [ A] Scrape all novels with missing chapters")
        print(" [ Q] Quit")
        print("=" * 75)

        choice = input(f"\nSelect a novel number (1-{len(novel_keys)}), '+' to add novel, or 'Q' to quit: ").strip().lower()

        if choice in ('q', 'quit', 'exit', ''):
            print("Exiting. Happy reading!")
            break

        if choice == '+':
            url_in = input("\nEnter FreeWebNovel URL, NovelPing URL, or novel slug: ").strip()
            entry = parse_novel_input(url_in)
            if not entry:
                print("Invalid URL or novel slug format.")
                continue
            register_new_novel(entry)
            scrape_now = input(f"Scrape Chapters 1-50 for '{entry['title']}' now? (y/n) [default y]: ").strip().lower()
            if scrape_now != 'n':
                scrape_novel_range(entry["id"], 1, min(50, entry["max_chapters"]), workers=4, push=True)
            continue

        if choice == 'a':
            confirm = input("Scrape missing chapters for ALL novels? (y/n): ").strip().lower()
            if confirm == 'y':
                for nid in novel_keys:
                    info = NOVELS_CATALOG[nid]
                    count, min_ch, max_ch = get_local_novel_status(nid)
                    if count < info["max_chapters"]:
                        start = max_ch + 1 if max_ch > 0 else info["default_start"]
                        end = info["max_chapters"]
                        scrape_novel_range(nid, start, end, workers=4, push=True)
            continue

        try:
            choice_idx = int(choice) - 1
            if not (0 <= choice_idx < len(novel_keys)):
                print(f"Invalid number. Please select between 1 and {len(novel_keys)}.")
                continue
        except ValueError:
            print("Invalid input. Please enter a number, '+', or 'Q'.")
            continue

        selected_id = novel_keys[choice_idx]
        selected_info = NOVELS_CATALOG[selected_id]
        count, min_ch, max_ch = get_local_novel_status(selected_id)
        default_start = (max_ch + 1) if max_ch > 0 else selected_info["default_start"]
        default_end = selected_info["max_chapters"]

        print(f"\nSelected: {selected_info['title']}")
        print(f"Current local chapters: {count} (Ch {min_ch} to {max_ch})")
        print(f"Online total available: ~{default_end} chapters")

        # Prompt source site
        print("\nChoose Download Source:")
        print(" [1] FreeWebNovel (Recommended)")
        print(" [2] NovelPing")
        print(" [3] Auto (FreeWebNovel with NovelPing fallback)")
        site_in = input("Select source site [default 1]: ").strip().lower()
        if site_in in ('2', 'novelping', 'ping'):
            source_site = 'novelping'
        elif site_in in ('3', 'auto'):
            source_site = 'auto'
        else:
            source_site = 'freewebnovel'

        # Prompt start
        s_input = input(f"Start Chapter [default {default_start}]: ").strip()
        start_ch = int(s_input) if s_input else default_start

        # Prompt end
        suggested_end = min(start_ch + 49, default_end)
        e_input = input(f"End Chapter [default {suggested_end}, Max {default_end}]: ").strip()
        end_ch = int(e_input) if e_input else suggested_end

        # Prompt workers
        w_input = input("Concurrency Worker Threads (2-5) [default 4]: ").strip()
        workers = int(w_input) if w_input else 4

        # Prompt push
        p_input = input("Commit and push to GitHub origin/main when done? (y/n) [default y]: ").strip().lower()
        push = False if p_input == 'n' else True

        scrape_novel_range(selected_id, start_ch, end_ch, workers=workers, push=push, source_site=source_site)


def main():
    load_catalog_from_file()

    parser = argparse.ArgumentParser(description="Interactive & CLI Web Novel Scraper + Cleaner")
    parser.add_argument("--novel", type=str, help="Novel ID to scrape")
    parser.add_argument("--start", type=int, help="Start chapter index")
    parser.add_argument("--end", type=int, help="End chapter index")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--site", "--source", choices=["auto", "freewebnovel", "freenovel", "novelping"], default="auto", help="Source website to download from (default: auto)")
    parser.add_argument("--no-push", action="store_true", help="Do not push to GitHub")
    parser.add_argument("--all", action="store_true", help="Scrape all incomplete novels")
    parser.add_argument("--add-novel", type=str, help="Add a new novel by URL or slug (e.g. https://freewebnovel.com/novel/shadow-slave)")

    args = parser.parse_args()

    if args.add_novel:
        entry = parse_novel_input(args.add_novel)
        if not entry:
            print(f"Error: Could not parse novel from '{args.add_novel}'")
            return
        register_new_novel(entry)
        if not args.no_push:
            git_commit_and_push(entry["id"], "novels.json", 0, 0)
        start = args.start if args.start is not None else 1
        end = args.end if args.end is not None else min(50, entry["max_chapters"])
        scrape_novel_range(entry["id"], start, end, workers=args.workers, push=not args.no_push, source_site=args.site)
        return

    if args.all:
        for nid, info in NOVELS_CATALOG.items():
            count, min_ch, max_ch = get_local_novel_status(nid)
            if count < info["max_chapters"]:
                start = max_ch + 1 if max_ch > 0 else info["default_start"]
                end = info["max_chapters"]
                scrape_novel_range(nid, start, end, workers=args.workers, push=not args.no_push, source_site=args.site)
        return

    if args.novel:
        if args.novel not in NOVELS_CATALOG:
            print(f"Error: Unknown novel '{args.novel}'. Available novels:")
            for k in NOVELS_CATALOG:
                print(f"  - {k}")
            return
        info = NOVELS_CATALOG[args.novel]
        count, min_ch, max_ch = get_local_novel_status(args.novel)
        start = args.start if args.start is not None else ((max_ch + 1) if max_ch > 0 else info["default_start"])
        end = args.end if args.end is not None else info["max_chapters"]
        scrape_novel_range(args.novel, start, end, workers=args.workers, push=not args.no_push, source_site=args.site)
        return

    # No arguments -> Launch Interactive Menu
    interactive_menu()


if __name__ == "__main__":
    main()
