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
    }
}


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


def fetch_archive_with_retry(novel_id: str, target_dir: str) -> Dict[int, Dict]:
    """Fetches chapter archive mapping."""
    cache_path = os.path.join(target_dir, "archive_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached and isinstance(cached, dict) and len(cached) > 0:
                return {int(k): v for k, v in cached.items()}
        except Exception:
            pass

    archive_url = f"https://novelping.com/ajax/chapter-archive?novelId={novel_id}"
    log(f"Fetching complete chapter archive from NovelPing: {archive_url}...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://novelping.com/book/{novel_id}"
    }

    from bs4 import BeautifulSoup
    html = ""
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(archive_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as res:
                html = res.read().decode("utf-8", errors="ignore")
            if html and len(html) > 500:
                break
        except Exception as e:
            time.sleep(attempt * 2)

    if not html:
        est = NOVELS_CATALOG[novel_id]["max_chapters"]
        log(f"Archive endpoint busy; generating index (1 to {est}) with FreeWebNovel mirrors.")
        return {
            ch: {
                "chapter_number": ch,
                "title": f"Chapter {ch}",
                "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch}"
            }
            for ch in range(1, est + 1)
        }

    soup = BeautifulSoup(html, "html.parser")
    chapter_map = {}
    for a in soup.find_all("a"):
        href = a.get("href", "")
        title_attr = a.get("title", "")
        inner_text = " ".join(a.stripped_strings) or a.get_text(strip=True)
        if not href:
            continue

        m = re.search(r'chapter[- ](\d+)', title_attr, re.I)
        display_title = title_attr
        if not m:
            m = re.search(r'chapter[- ](\d+)', inner_text, re.I)
            display_title = inner_text or display_title
        if not m:
            m = re.search(r'chapter-(\d+)', href, re.I)

        if m:
            ch_num = int(m.group(1))
            full_url = href if href.startswith("http") else f"https://novelping.com{href}"
            if ch_num not in chapter_map or title_attr:
                chapter_map[ch_num] = {
                    "chapter_number": ch_num,
                    "title": display_title or f"Chapter {ch_num}",
                    "url": full_url
                }

    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chapter_map.items()}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return chapter_map


def fetch_chapter_with_retries(scraper: NovelScraper, novel_id: str, ch_num: int, ch_meta: dict, max_retries: int = 5) -> dict:
    """Fetches and simultaneously cleans a single chapter with mirror failover."""
    candidate_urls = []
    if ch_meta and ch_meta.get("url"):
        candidate_urls.append(ch_meta["url"])
    candidate_urls.extend([
        f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}",
        f"https://freewebnovel.com/{novel_id}/chapter-{ch_num}.html",
        f"https://novelping.com/book/{novel_id}/chapter-{ch_num}"
    ])

    last_error = None
    for url in candidate_urls:
        for attempt in range(1, max_retries + 1):
            try:
                ch_data = scraper.fetch_chapter(url)
                paragraphs = ch_data.get("paragraphs", [])
                if paragraphs and len(paragraphs) > 0:
                    ch_payload = {
                        "chapter_index": ch_num,
                        "title": ch_data.get("title") or (ch_meta.get("title") if ch_meta else f"Chapter {ch_num}"),
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
    """Commits and pushes scraped bundles to GitHub with retry."""
    try:
        add_cmd = ["git", "add", "data", "novels.json"]
        subprocess.run(add_cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        commit_msg = f"Add & clean chapters {s_ch}-{e_ch} for {novel_id}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=PROJECT_ROOT, capture_output=True, text=True)

        for attempt in range(1, 4):
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_ROOT, capture_output=True, text=True)
            if push_res.returncode == 0:
                log(f"Successfully pushed to GitHub origin/main!")
                return True
            time.sleep(attempt * 2)

        log("Notice: Local bundles saved. Push can be done manually via 'git push origin main'.")
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
    chunk_size: int = 50
):
    """Scrapes, cleans, and bundles a specified range for a novel."""
    info = NOVELS_CATALOG[novel_id]
    novel_title = info["title"]
    target_dir = info["target_dir"]
    os.makedirs(target_dir, exist_ok=True)

    log(f"\n{'='*70}")
    log(f"  SCRAPING: {novel_title}")
    log(f"  Range: Chapters {start_ch} to {end_ch} | Workers: {workers}")
    log(f"  Auto-Clean: ON (zero backslashes, zero ads, TTS ready)")
    log(f"{'='*70}\n")

    chapter_map = fetch_archive_with_retry(novel_id, target_dir)

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

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_num = {}
            for ch_num in chapters_to_fetch:
                ch_meta = chapter_map.get(ch_num, {
                    "chapter_number": ch_num,
                    "title": f"Chapter {ch_num}",
                    "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}"
                })
                f = executor.submit(fetch_chapter_with_retries, scraper, novel_id, ch_num, ch_meta, 5)
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
                    rescued = fetch_chapter_with_retries(scraper, novel_id, ch_num, ch_meta, max_retries=6)
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
        print(" [ A] Scrape all novels with missing chapters")
        print(" [ Q] Quit")
        print("=" * 75)

        choice = input("\nSelect a novel number (1-13), 'A' for all, or 'Q' to quit: ").strip().lower()

        if choice in ('q', 'quit', 'exit', ''):
            print("Exiting. Happy reading!")
            break

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
                print("Invalid number. Please select between 1 and 13.")
                continue
        except ValueError:
            print("Invalid input. Please enter a number or 'Q'.")
            continue

        selected_id = novel_keys[choice_idx]
        selected_info = NOVELS_CATALOG[selected_id]
        count, min_ch, max_ch = get_local_novel_status(selected_id)
        default_start = (max_ch + 1) if max_ch > 0 else selected_info["default_start"]
        default_end = selected_info["max_chapters"]

        print(f"\nSelected: {selected_info['title']}")
        print(f"Current local chapters: {count} (Ch {min_ch} to {max_ch})")
        print(f"Online total available: ~{default_end} chapters")

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

        scrape_novel_range(selected_id, start_ch, end_ch, workers=workers, push=push)


def main():
    parser = argparse.ArgumentParser(description="Interactive & CLI Web Novel Scraper + Cleaner")
    parser.add_argument("--novel", type=str, help="Novel ID to scrape")
    parser.add_argument("--start", type=int, help="Start chapter index")
    parser.add_argument("--end", type=int, help="End chapter index")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--no-push", action="store_true", help="Do not push to GitHub")
    parser.add_argument("--all", action="store_true", help="Scrape all incomplete novels")

    args = parser.parse_args()

    if args.all:
        for nid, info in NOVELS_CATALOG.items():
            count, min_ch, max_ch = get_local_novel_status(nid)
            if count < info["max_chapters"]:
                start = max_ch + 1 if max_ch > 0 else info["default_start"]
                end = info["max_chapters"]
                scrape_novel_range(nid, start, end, workers=args.workers, push=not args.no_push)
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
        scrape_novel_range(args.novel, start, end, workers=args.workers, push=not args.no_push)
        return

    # No arguments -> Launch Interactive Menu
    interactive_menu()


if __name__ == "__main__":
    main()
