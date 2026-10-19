"""
bulk_novel_scraper.py
---------------------
High-performance, resilient bulk scraper for web novels on NovelPing.
Supports multi-novel scraping, concurrent chapter downloads, automatic
gap detection, existing bundle skipping, atomic file writes, index.json
manifest management, and automated git push with rebase retries.

Target Novels:
  1. Infinite Mana In The Apocalypse (infinite-mana-in-the-apocalypse)
  2. Supreme Harem God System (supreme-harem-god-system)
  3. My Vampire System (my-vampire-system)
  [Optional: Alchemy Emperor of the Divine Dao]

Usage Examples:
  # Bulk scrape all 3 novels and push to GitHub:
  python scripts/bulk_novel_scraper.py

  # Scrape a specific novel:
  python scripts/bulk_novel_scraper.py --novels my-vampire-system

  # Scrape without pushing to GitHub:
  python scripts/bulk_novel_scraper.py --novels supreme-harem-god-system --no-push

  # Scrape specific chapter range with 6 worker threads:
  python scripts/bulk_novel_scraper.py --novels my-vampire-system --start 51 --end 500 --workers 6
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from novel_scraper import NovelScraper
try:
    from novel_cleaner import clean_chapter_data
except ImportError:
    from scripts.novel_cleaner import clean_chapter_data

# Known novels configuration
KNOWN_NOVELS = {
    "fourth-princes-debauchery": {
        "id": "fourth-princes-debauchery",
        "title": "Fourth Prince's Debauchery",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "fourth-princes-debauchery"),
        "default_start": 351,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=fourth-princes-debauchery"
    },
    "infinite-mana-in-the-apocalypse": {
        "id": "infinite-mana-in-the-apocalypse",
        "title": "Infinite Mana In The Apocalypse",
        "target_dir": os.path.join(PROJECT_ROOT, "data"),
        "default_start": 1780,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=infinite-mana-in-the-apocalypse"
    },
    "supreme-harem-god-system": {
        "id": "supreme-harem-god-system",
        "title": "Supreme Harem God System",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "supreme-harem-god-system"),
        "default_start": 1001,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=supreme-harem-god-system"
    },
    "my-vampire-system": {
        "id": "my-vampire-system",
        "title": "My Vampire System",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "my-vampire-system"),
        "default_start": 1,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=my-vampire-system"
    },
    "alchemy-emperor-of-the-divine-dao": {
        "id": "alchemy-emperor-of-the-divine-dao",
        "title": "Alchemy Emperor of the Divine Dao",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "alchemy-emperor-of-the-divine-dao"),
        "default_start": 1,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=alchemy-emperor-of-the-divine-dao"
    },
    "starting-with-an-sss-rank-goddess-summon": {
        "id": "starting-with-an-sss-rank-goddess-summon",
        "title": "Starting With An SSS-Rank Goddess Summon",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "starting-with-an-sss-rank-goddess-summon"),
        "default_start": 638,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=starting-with-an-sss-rank-goddess-summon"
    },
    "6-times-a-day": {
        "id": "6-times-a-day",
        "title": "6 Times a Day",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "6-times-a-day"),
        "default_start": 51,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=6-times-a-day"
    },
    "my-three-wives-are-beautiful-vampires-novel": {
        "id": "my-three-wives-are-beautiful-vampires-novel",
        "title": "My Three Wives Are Beautiful Vampires",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "my-three-wives-are-beautiful-vampires-novel"),
        "default_start": 1161,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=my-three-wives-are-beautiful-vampires-novel"
    },
    "primordial-chaos-dragon-tower-harem-system": {
        "id": "primordial-chaos-dragon-tower-harem-system",
        "title": "Primordial Chaos Dragon Tower Harem System",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "primordial-chaos-dragon-tower-harem-system"),
        "default_start": 1,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=primordial-chaos-dragon-tower-harem-system"
    },
    "my-taboo-harem": {
        "id": "my-taboo-harem",
        "title": "My Taboo Harem",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "my-taboo-harem"),
        "default_start": 101,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=my-taboo-harem"
    },
    "dimensional-descent": {
        "id": "dimensional-descent",
        "title": "Dimensional Descent",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "dimensional-descent"),
        "default_start": 51,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=dimensional-descent"
    },
    "raising-my-trash-ability-into-a-broken-sss-rank-skill": {
        "id": "raising-my-trash-ability-into-a-broken-sss-rank-skill",
        "title": "Raising My Trash Ability Into A Broken SSS-Rank Skill",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "raising-my-trash-ability-into-a-broken-sss-rank-skill"),
        "default_start": 51,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=raising-my-trash-ability-into-a-broken-sss-rank-skill"
    },
    "tsuki-ga-michibiku-isekai-douchuu": {
        "id": "tsuki-ga-michibiku-isekai-douchuu",
        "title": "Tsuki Ga Michibiku Isekai Douchuu",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "tsuki-ga-michibiku-isekai-douchuu"),
        "default_start": 1,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=tsuki-ga-michibiku-isekai-douchuu"
    },
    "oh-no-after-i-reincarnated-my-moms-became-son-cons": {
        "id": "oh-no-after-i-reincarnated-my-moms-became-son-cons",
        "title": "Oh No After I Reincarnated My Moms Became Son Cons",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "oh-no-after-i-reincarnated-my-moms-became-son-cons"),
        "default_start": 1,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=oh-no-after-i-reincarnated-my-moms-became-son-cons"
    },
    "cheat-awakening": {
        "id": "cheat-awakening",
        "title": "Cheat Awakening",
        "target_dir": os.path.join(PROJECT_ROOT, "data", "cheat-awakening"),
        "default_start": 1,
        "archive_url": "https://novelping.com/ajax/chapter-archive?novelId=cheat-awakening"
    }
}

DEFAULT_THREE_NOVELS = [
    "infinite-mana-in-the-apocalypse",
    "supreme-harem-god-system",
    "my-vampire-system",
    "alchemy-emperor-of-the-divine-dao"
]


def log(msg: str):
    """Prints a timestamped log message with immediate stdout flush."""
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


def fetch_archive_with_retry(novel_id: str, target_dir: str, refresh_cache: bool = False) -> Dict[int, Dict]:
    """
    Fetches and caches the chapter archive from NovelPing.
    Returns a dictionary mapping: chapter_number -> {chapter_number, title, url}.
    """
    cache_path = os.path.join(target_dir, "archive_cache.json")
    if not refresh_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached and isinstance(cached, dict) and len(cached) > 0:
                # Sanity check: Ensure key '1' is not corrupted by a later book (e.g. Book 19/20)
                item1 = cached.get("1") or cached.get(1)
                is_corrupted = False
                if item1 and isinstance(item1, dict):
                    t1 = item1.get("title", "")
                    m_b = re.search(r'\b(?:book|volume|vol)\s*(\d+)', t1, re.I)
                    if m_b and int(m_b.group(1)) > 1:
                        is_corrupted = True

                cat_info = KNOWN_NOVELS.get(novel_id, {})
                expected_max = cat_info.get("max_chapters", 0)
                if expected_max > 100 and len(cached) < expected_max * 0.6:
                    is_corrupted = True

                if not is_corrupted:
                    chapter_map = {int(k): v for k, v in cached.items()}
                    log(f"Loaded {len(chapter_map)} chapters from local archive cache: {cache_path}")
                    return chapter_map
                else:
                    log(f"Cached archive for '{novel_id}' was corrupted or incomplete ({len(cached)} items); refreshing online archive...")
        except Exception as e:
            log(f"Warning: Failed to read archive cache ({e}), re-fetching...")

    archive_url = f"https://novelping.com/ajax/chapter-archive?novelId={novel_id}"
    log(f"Fetching complete chapter archive from NovelPing: {archive_url}...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://novelping.com/book/{novel_id}"
    }

    from bs4 import BeautifulSoup
    html = ""
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(archive_url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as res:
                html = res.read().decode("utf-8", errors="ignore")
            if html and len(html) > 500:
                log(f"Received archive response ({len(html):,} bytes) on attempt {attempt}.")
                break
        except urllib.error.HTTPError as e:
            wait_time = attempt * 3
            log(f"  [Attempt {attempt}/5] HTTP {e.code} fetching archive. Retrying in {wait_time}s...")
            time.sleep(wait_time)
        except Exception as e:
            wait_time = attempt * 3
            log(f"  [Attempt {attempt}/5] Error fetching archive: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    KNOWN_ESTIMATES = {
        "fourth-princes-debauchery": 734,
        "infinite-mana-in-the-apocalypse": 5873,
        "supreme-harem-god-system": 2410,
        "my-vampire-system": 2545,
        "alchemy-emperor-of-the-divine-dao": 4932,
        "starting-with-an-sss-rank-goddess-summon": 684,
        "6-times-a-day": 1364,
        "my-three-wives-are-beautiful-vampires-novel": 1162,
        "primordial-chaos-dragon-tower-harem-system": 1907,
        "my-taboo-harem": 1373,
        "dimensional-descent": 3294,
        "raising-my-trash-ability-into-a-broken-sss-rank-skill": 888,
        "tsuki-ga-michibiku-isekai-douchuu": 503,
        "oh-no-after-i-reincarnated-my-moms-became-son-cons": 1127
    }

    if not html:
        est = KNOWN_ESTIMATES.get(novel_id, 3000)
        log(f"Notice: NovelPing archive unavailable for '{novel_id}'. Generating synthetic chapter index (1 to {est}) using FreeWebNovel.")
        return {
            ch: {
                "chapter_number": ch,
                "title": f"Chapter {ch}",
                "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch}"
            }
            for ch in range(1, est + 1)
        }

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

    total_links = len(raw_links)
    parsed_nums = [item["parsed_num"] for item in raw_links if item["parsed_num"] is not None]
    has_duplicates = len(parsed_nums) != len(set(parsed_nums))
    has_multi_book = any(re.search(r'\b(?:book|volume|vol)\s*\d+', item["title"], re.I) for item in raw_links)
    max_parsed = max(parsed_nums) if parsed_nums else 0
    collapsed_count = max_parsed > 0 and max_parsed < total_links * 0.75

    use_sequential_toc = has_duplicates or has_multi_book or collapsed_count

    chapter_map = {}
    if use_sequential_toc:
        log(f"Multi-book/volume or duplicate chapters detected for '{novel_id}'. Using sequential Table-of-Contents indexing (1 to {total_links}).")
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

    log(f"Discovered {len(chapter_map)} unique chapters in archive for '{novel_id}'.")

    # Save to local archive cache
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chapter_map.items()}, f, indent=2, ensure_ascii=False)
        log(f"Cached archive mapping to {cache_path}.")
    except Exception as e:
        log(f"Warning: Could not save archive cache: {e}")

    return chapter_map


def is_bundle_complete(bundle_path: str, expected_count: int) -> bool:
    """Verifies that a local bundle file exists, is valid JSON, and has complete chapters."""
    if not os.path.exists(bundle_path):
        return False
    try:
        if os.path.getsize(bundle_path) < 1000:
            return False
        with open(bundle_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chapters = data.get("chapters", [])
        if len(chapters) == expected_count and all(c.get("paragraphs") and len(c["paragraphs"]) > 0 for c in chapters):
            return True
    except Exception:
        pass
    return False


def fetch_chapter_with_retries(scraper: NovelScraper, novel_id: str, ch_num: int, ch_meta: dict, max_retries: int = 5) -> dict:
    """Fetches a single chapter with retry backoff and URL fallbacks."""
    candidate_urls = []
    if ch_meta and ch_meta.get("url"):
        candidate_urls.append(ch_meta["url"])
        slug_part = ch_meta["url"].rstrip("/").split("/")[-1].rstrip(".html")
        if slug_part:
            candidate_urls.append(f"https://novelping.com/book/{novel_id}/{slug_part}")
            candidate_urls.append(f"https://freewebnovel.com/novel/{novel_id}/{slug_part}")
    candidate_urls.extend([
        f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}",
        f"https://freewebnovel.com/{novel_id}/chapter-{ch_num}.html",
        f"https://novelping.com/book/{novel_id}/chapter-{ch_num}"
    ])

    seen = set()
    unique_candidates = [u for u in candidate_urls if not (u in seen or seen.add(u))]

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
                    return clean_chapter_data(ch_payload)
                else:
                    time.sleep(1.0)
            except urllib.error.HTTPError as e:
                last_error = e
                if e.code == 429:
                    # Switch immediately to next mirror without wasting time
                    break
                elif e.code in (502, 503, 504):
                    wait_time = attempt * 1.5 + random.uniform(0.3, 0.8)
                    time.sleep(wait_time)
                else:
                    time.sleep(1.0)
            except Exception as e:
                last_error = e
                wait_time = attempt * 1.5 + random.uniform(0.3, 0.8)
                time.sleep(wait_time)

    raise RuntimeError(f"Ch. {ch_num} failed on all candidate URLs after {max_retries} attempts. Last error: {last_error}")


def update_manifest(output_dir: str, bundle_filename: str, start_ch: int, end_ch: int, count: int, novel_id: str):
    """Atomically updates target_dir/index.json with the newly created bundle."""
    manifest_path = os.path.join(output_dir, "index.json")
    manifest = {"novel_id": novel_id, "bundles": []}

    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            pass

    manifest["novel_id"] = novel_id
    manifest["bundles"] = [b for b in manifest.get("bundles", []) if b.get("bundle_file") != bundle_filename]
    manifest["bundles"].append({
        "bundle_file": bundle_filename,
        "start_chapter": start_ch,
        "end_chapter": end_ch,
        "chapter_count": count,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    })
    manifest["bundles"].sort(key=lambda b: (b.get("start_chapter", 0), b.get("end_chapter", 0)))

    tmp_path = manifest_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, manifest_path)


def git_commit_and_push(target_dir: str, commit_msg: str, max_retries: int = 5) -> bool:
    """Stages target_dir, commits, rebases with origin main, and pushes to GitHub."""
    try:
        # Check if there are changes
        subprocess.run(["git", "add", target_dir], cwd=PROJECT_ROOT, check=True)
        diff_res = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=PROJECT_ROOT)
        if diff_res.returncode == 0:
            log("No changes to commit for git push.")
            return True

        # Commit
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=PROJECT_ROOT, check=True)
        log(f"Committed: '{commit_msg}'")

        # Push with pull --rebase retry loop
        for attempt in range(1, max_retries + 1):
            log(f"Pulling with rebase and pushing to origin main (attempt {attempt}/{max_retries})...")
            # 1. Pull rebase
            pull_res = subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=PROJECT_ROOT)
            if pull_res.returncode != 0:
                subprocess.run(["git", "rebase", "--abort"], cwd=PROJECT_ROOT)
                subprocess.run(["git", "pull", "--no-edit", "origin", "main"], cwd=PROJECT_ROOT)

            # 2. Push
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_ROOT)
            if push_res.returncode == 0:
                log("Successfully pushed to GitHub main!")
                return True

            wait = attempt * 3
            log(f"Push rejected or failed. Retrying in {wait}s...")
            time.sleep(wait)

        log("Warning: Git push failed after all retries.")
        return False
    except Exception as e:
        log(f"Warning: git command error during push: {e}")
        return False


def scrape_novel_bundles(
    novel_info: dict,
    start_override: Optional[int] = None,
    end_override: Optional[int] = None,
    workers: int = 4,
    push: bool = True,
    push_frequency: str = "bundle",  # "bundle" or "novel"
    chunk_size: int = 50,
    refresh_archive: bool = False
):
    """
    Scrapes all missing bundles for a given novel and saves them cleanly.
    """
    novel_id = novel_info["id"]
    novel_title = novel_info["title"]
    target_dir = novel_info["target_dir"]
    os.makedirs(target_dir, exist_ok=True)

    log(f"\n{'='*70}")
    log(f"  STARTING BULK SCRAPER: {novel_title} ({novel_id})")
    log(f"  Target Directory: {target_dir}")
    log(f"  Concurrency: {workers} worker threads | Push to GitHub: {push}")
    log(f"{'='*70}\n")

    # 1. Fetch / Load Archive
    chapter_map = fetch_archive_with_retry(novel_id, target_dir, refresh_cache=refresh_archive)
    if not chapter_map:
        log(f"Error: No chapters discovered for '{novel_id}'. Skipping.")
        return

    archive_min = min(chapter_map.keys())
    archive_max = max(chapter_map.keys())

    start_ch = start_override if start_override is not None else novel_info.get("default_start", archive_min)
    end_ch = end_override if end_override is not None else archive_max

    log(f"Selected Chapter Range: {start_ch} to {end_ch} (out of {len(chapter_map)} archive chapters)")

    # 2. Partition into 50-chapter slices
    slices: List[Tuple[int, int]] = []
    curr = start_ch
    while curr <= end_ch:
        slice_end = min(curr + chunk_size - 1, end_ch)
        slices.append((curr, slice_end))
        curr = slice_end + 1

    log(f"Total standard {chunk_size}-chapter bundles to process: {len(slices)}")

    scraper = NovelScraper()
    newly_saved_bundles = 0

    for idx, (s_ch, e_ch) in enumerate(slices, 1):
        slice_count = e_ch - s_ch + 1
        bundle_filename = f"chapters_{s_ch}_{e_ch}.json"
        bundle_path = os.path.join(target_dir, bundle_filename)

        # Check if already complete
        if is_bundle_complete(bundle_path, slice_count):
            log(f"[{idx}/{len(slices)}] Bundle {bundle_filename} already complete on disk. Skipping.")
            # Make sure manifest records it
            update_manifest(target_dir, bundle_filename, s_ch, e_ch, slice_count, novel_id)
            continue

        log(f"\n--- [{idx}/{len(slices)}] Fetching Chapters {s_ch} to {e_ch} ({slice_count} chapters) ---")
        t_slice_start = time.time()

        bundled_chapters: List[dict] = []
        chapters_to_fetch = list(range(s_ch, e_ch + 1))

        # Concurrent fetching with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_num = {}
            for ch_num in chapters_to_fetch:
                ch_meta = chapter_map.get(ch_num, {
                    "chapter_number": ch_num,
                    "title": f"Chapter {ch_num}",
                    "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}"
                })
                # Submit worker
                f = executor.submit(fetch_chapter_with_retries, scraper, novel_id, ch_num, ch_meta, 5)
                future_to_num[f] = ch_num
                time.sleep(0.6)  # polite stagger to prevent FreeWebNovel/NovelPing rate-limits

            for future in as_completed(future_to_num):
                ch_num = future_to_num[future]
                try:
                    ch_result = future.result()
                    bundled_chapters.append(ch_result)
                    p_count = len(ch_result.get("paragraphs", []))
                    log(f"  ✓ Ch. {ch_num} ({ch_result.get('title', '')}) - {p_count} paragraphs [{len(bundled_chapters)}/{slice_count}]")
                except Exception as e:
                    log(f"  ✗ Ch. {ch_num} failed: {e}")

        # Gap verification and rescue pass
        fetched_indexes = set(c["chapter_index"] for c in bundled_chapters)
        missing = [ch for ch in range(s_ch, e_ch + 1) if ch not in fetched_indexes]

        if missing:
            log(f"\n[WARNING] Missing {len(missing)} chapters in slice {s_ch}-{e_ch}: {missing}. Running rescue pass...")
            for ch_num in list(missing):
                ch_meta = chapter_map.get(ch_num, {
                    "chapter_number": ch_num,
                    "title": f"Chapter {ch_num}",
                    "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}"
                })
                try:
                    rescued = fetch_chapter_with_retries(scraper, novel_id, ch_num, ch_meta, max_retries=6)
                    bundled_chapters.append(rescued)
                    missing.remove(ch_num)
                    log(f"  [RESCUED] Successfully retrieved Ch. {ch_num}!")
                except Exception as e:
                    log(f"  [RESCUE FAILED] Ch. {ch_num}: {e}")

        # Strict completeness check
        fetched_indexes = set(c["chapter_index"] for c in bundled_chapters)
        final_missing = [ch for ch in range(s_ch, e_ch + 1) if ch not in fetched_indexes]
        if final_missing:
            raise RuntimeError(f"Critical error: Incomplete bundle {bundle_filename}! Missing chapters: {final_missing}")

        # Sort chapters strictly by index
        bundled_chapters.sort(key=lambda c: c["chapter_index"])

        # Write atomically to file
        bundle_payload = {
            "novel_id": novel_id,
            "start_chapter": s_ch,
            "end_chapter": e_ch,
            "total_chapters": len(bundled_chapters),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "chapters": bundled_chapters
        }

        tmp_bundle_path = bundle_path + ".tmp"
        with open(tmp_bundle_path, "w", encoding="utf-8") as f:
            json.dump(bundle_payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_bundle_path, bundle_path)

        elapsed = round(time.time() - t_slice_start, 1)
        log(f"Saved {bundle_filename} ({len(bundled_chapters)} chapters) in {elapsed}s to {bundle_path}")

        # Update index.json manifest
        update_manifest(target_dir, bundle_filename, s_ch, e_ch, len(bundled_chapters), novel_id)
        newly_saved_bundles += 1

        # Git push if configured for per-bundle pushes
        if push and push_frequency == "bundle":
            commit_msg = f"Add Chapter Bundle [{novel_id}] {s_ch}-{e_ch}"
            git_commit_and_push(target_dir, commit_msg)

    # Git push if configured for per-novel pushes
    if push and push_frequency == "novel" and newly_saved_bundles > 0:
        commit_msg = f"Add {newly_saved_bundles} Chapter Bundles for [{novel_id}]"
        git_commit_and_push(target_dir, commit_msg)

    log(f"\n[COMPLETED] Novel '{novel_title}' processed. {newly_saved_bundles} new bundles saved and synced.")


def main():
    parser = argparse.ArgumentParser(description="Bulk Web Novel Scraper and GitHub Sync")
    parser.add_argument(
        "--novels",
        type=str,
        default="three",
        help="Novels to scrape: 'three' (default 3 novels), 'all', or comma-separated list of novel IDs"
    )
    parser.add_argument("--start", type=int, default=None, help="Override start chapter")
    parser.add_argument("--end", type=int, default=None, help="Override end chapter")
    parser.add_argument("--workers", type=int, default=2, help="Concurrent worker threads (default: 2)")
    parser.add_argument("--push", action="store_true", default=True, help="Push changes to GitHub (default)")
    parser.add_argument("--no-push", action="store_false", dest="push", help="Do not push changes to GitHub")
    parser.add_argument("--push-freq", type=str, choices=["bundle", "novel"], default="bundle", help="Git push frequency")
    parser.add_argument("--refresh-archive", action="store_true", help="Force refresh archive cache")
    args = parser.parse_args()

    # Determine list of novel IDs to process
    if args.novels.lower() in ("three", "default"):
        target_novel_ids = DEFAULT_THREE_NOVELS
    elif args.novels.lower() == "all":
        target_novel_ids = list(KNOWN_NOVELS.keys())
    else:
        target_novel_ids = [n.strip() for n in args.novels.split(",") if n.strip()]

    log(f"Target Novels to Scrape: {target_novel_ids}")

    for novel_id in target_novel_ids:
        if novel_id in KNOWN_NOVELS:
            novel_info = KNOWN_NOVELS[novel_id]
        else:
            # Custom novel not in predefined dictionary
            novel_info = {
                "id": novel_id,
                "title": novel_id.replace("-", " ").title(),
                "target_dir": os.path.join(PROJECT_ROOT, "data", novel_id),
                "default_start": 1,
                "archive_url": f"https://novelping.com/ajax/chapter-archive?novelId={novel_id}"
            }

        try:
            scrape_novel_bundles(
                novel_info=novel_info,
                start_override=args.start,
                end_override=args.end,
                workers=args.workers,
                push=args.push,
                push_frequency=args.push_freq,
                refresh_archive=args.refresh_archive
            )
        except Exception as e:
            log(f"Error processing novel '{novel_id}': {e}")
            import traceback
            traceback.print_exc()

    log("\nAll requested novels have completed bulk scraping processing!")


if __name__ == "__main__":
    main()
