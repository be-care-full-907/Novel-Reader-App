"""
github_chapter_fetcher.py
-------------------------
Automated chapter batch fetcher for GitHub Actions and local execution.
Fetches ANY arbitrary chapter range (e.g. 1906-1908, 1850-1865, or 50+ chapters)
from NovelPing with zero missing chapters guarantee, retry resilience, slug typo
auto-correction, and gap validation.
"""

import os
import re
import json
import time
import argparse
import urllib.request
from bs4 import BeautifulSoup
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from novel_scraper import NovelScraper
try:
    from novel_cleaner import clean_chapter_data
except ImportError:
    from scripts.novel_cleaner import clean_chapter_data

NOVEL_ID = "infinite-mana-in-the-apocalypse"
ARCHIVE_AJAX_URL = f"https://novelping.com/ajax/chapter-archive?novelId={NOVEL_ID}"

def fetch_all_chapter_links(novel_id: str = "infinite-mana-in-the-apocalypse", target_dir: str = ""):
    """Fetches and maps the complete archive of chapters from NovelPing with cache support."""
    # 1. Check local archive cache first
    candidate_cache_paths = []
    if target_dir:
        candidate_cache_paths.append(os.path.join(target_dir, "archive_cache.json"))
    candidate_cache_paths.append(os.path.join("data", novel_id, "archive_cache.json"))
    if novel_id == "infinite-mana-in-the-apocalypse":
        candidate_cache_paths.append(os.path.join("data", "archive_cache.json"))

    for cpath in candidate_cache_paths:
        if os.path.exists(cpath):
            try:
                with open(cpath, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached and isinstance(cached, dict) and len(cached) > 0:
                    chapter_map = {int(k): v for k, v in cached.items()}
                    print(f"Loaded {len(chapter_map)} chapters from local archive cache: {cpath}")
                    return chapter_map
            except Exception as e:
                print(f"Warning: Could not read archive cache at {cpath}: {e}")

    archive_url = f"https://novelping.com/ajax/chapter-archive?novelId={novel_id}"
    print(f"Fetching complete chapter archive for novel '{novel_id}' from {archive_url}...")
    req = urllib.request.Request(
        archive_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://novelping.com/book/{novel_id}"
        }
    )

    html = ""
    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                html = res.read().decode("utf-8", errors="ignore")
            if html and len(html) > 500:
                print(f"Received archive response ({len(html):,} bytes) on attempt {attempt}.")
                break
        except Exception as e:
            wait_time = attempt * 2
            print(f"  [Attempt {attempt}/2] Error fetching archive: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    if not html:
        print(f"Warning: Failed to fetch archive for '{novel_id}'. Proceeding with direct FreeWebNovel URLs.")
        return {}

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a")
    
    chapter_map = {}
    for a in links:
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

    print(f"Discovered {len(chapter_map)} unique chapters in archive.")

    # Save to archive_cache.json if target_dir provided
    save_dir = target_dir or (os.path.join("data", novel_id) if novel_id != "infinite-mana-in-the-apocalypse" else "data")
    try:
        os.makedirs(save_dir, exist_ok=True)
        cache_file = os.path.join(save_dir, "archive_cache.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chapter_map.items()}, f, indent=2, ensure_ascii=False)
        print(f"Saved archive cache to {cache_file}.")
    except Exception as e:
        print(f"Warning: Could not save archive cache: {e}")

    return chapter_map

def fetch_single_chapter_with_retry(scraper, novel_id: str, ch_num: int, ch_meta: dict, max_retries: int = 4):
    """Fetches a single chapter with retries and fallback URLs."""
    urls_to_try = [
        f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}",
        f"https://freewebnovel.com/{novel_id}/chapter-{ch_num}.html",
    ]
    if ch_meta and ch_meta.get('url') and ch_meta['url'] not in urls_to_try:
        urls_to_try.append(ch_meta['url'])
        
    direct_fallback = f"https://novelping.com/book/{novel_id}/chapter-{ch_num}"
    if direct_fallback not in urls_to_try:
        urls_to_try.append(direct_fallback)
        
    last_err = None
    for url in urls_to_try:
        for attempt in range(max_retries):
            try:
                ch_data = scraper.fetch_chapter(url)
                paragraphs = ch_data.get('paragraphs', [])
                if paragraphs and len(paragraphs) > 0:
                    ch_payload = {
                        "chapter_index": ch_num,
                        "title": ch_data.get('title') or ch_meta.get('title') or f"Chapter {ch_num}",
                        "url": url,
                        "paragraphs": paragraphs,
                        "sentences": ch_data.get('sentences', []),
                        "word_count": ch_data.get('word_count', 0)
                    }
                    return clean_chapter_data(ch_payload)
                else:
                    print(f"  [Attempt {attempt+1}] Empty paragraphs for Ch. {ch_num} at {url}. Retrying...")
                    time.sleep(1.5)
            except Exception as e:
                last_err = e
                wait_time = (attempt + 1) * 2
                print(f"  [Attempt {attempt+1}] Error fetching Ch. {ch_num} ({url}): {e}. Waiting {wait_time}s...")
                time.sleep(wait_time)
                
    raise RuntimeError(f"Failed to fetch Chapter {ch_num} after trying all candidate URLs. Last error: {last_err}")

def download_bundle(start_ch: int, end_ch: int, output_dir: str = "data", novel_id: str = "infinite-mana-in-the-apocalypse", chunk_size: int = 50):
    """Downloads chapters from start_ch to end_ch for the given novel, automatically chunking into 50-chapter bundles."""
    if start_ch > end_ch:
        start_ch, end_ch = end_ch, start_ch

    # If output_dir is "data" and novel is not infinite-mana, organize into subfolder
    if output_dir == "data" and novel_id != "infinite-mana-in-the-apocalypse":
        target_dir = os.path.join(output_dir, novel_id)
    else:
        target_dir = output_dir

    os.makedirs(target_dir, exist_ok=True)
    chapter_map = fetch_all_chapter_links(novel_id, target_dir)
    scraper = NovelScraper()

    total_expected = end_ch - start_ch + 1
    print(f"\n=======================================================")
    print(f"  Novel: {novel_id}")
    print(f"  Downloading Chapter Range: {start_ch} to {end_ch} ({total_expected} Chapters)")
    print(f"  Partitioning into standard bundles of up to {chunk_size} chapters")
    print(f"  Target Directory: {target_dir}")
    print(f"=======================================================\n")
    
    # Calculate slices
    slices = []
    curr = start_ch
    while curr <= end_ch:
        slice_end = min(curr + chunk_size - 1, end_ch)
        slices.append((curr, slice_end))
        curr = slice_end + 1

    saved_bundle_paths = []
    
    for slice_idx, (s_ch, e_ch) in enumerate(slices, 1):
        slice_count = e_ch - s_ch + 1
        bundle_filename = f"chapters_{s_ch}_{e_ch}.json"
        bundle_path = os.path.join(target_dir, bundle_filename)

        # Check if bundle already exists and is complete
        if os.path.exists(bundle_path):
            try:
                with open(bundle_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                existing_chapters = existing_data.get("chapters", [])
                if len(existing_chapters) == slice_count and all(c.get("paragraphs") for c in existing_chapters):
                    print(f"\n--- [Bundle {slice_idx}/{len(slices)}] Chapters {s_ch} to {e_ch} already present on disk ({slice_count} chapters). Skipping. ---")
                    update_manifest(target_dir, bundle_filename, s_ch, e_ch, len(existing_chapters), novel_id)
                    saved_bundle_paths.append(bundle_path)
                    continue
            except Exception:
                pass

        print(f"\n--- [Bundle {slice_idx}/{len(slices)}] Processing Chapters {s_ch} to {e_ch} ({slice_count} chapters) ---")
        
        bundled_chapters = []
        for ch_num in range(s_ch, e_ch + 1):
            if ch_num in chapter_map:
                ch_meta = chapter_map[ch_num]
            else:
                print(f"Notice: Chapter {ch_num} not in archive index. Using direct fallback URL...")
                ch_meta = {
                    "chapter_number": ch_num,
                    "title": f"Chapter {ch_num}",
                    "url": f"https://freewebnovel.com/novel/{novel_id}/chapter-{ch_num}"
                }
                
            print(f"Fetching Chapter {ch_num} ({ch_num - s_ch + 1}/{slice_count}): {ch_meta['title']}...")
            
            try:
                chapter_obj = fetch_single_chapter_with_retry(scraper, novel_id, ch_num, ch_meta)
                bundled_chapters.append(chapter_obj)
                time.sleep(0.2)  # Polite pacing
            except Exception as e:
                print(f"  [ERROR] Failed to fetch Chapter {ch_num}: {e}")

        # Zero Missing Chapters Verification & Rescue Pass for this slice
        fetched_indexes = set(c['chapter_index'] for c in bundled_chapters)
        missing = [ch for ch in range(s_ch, e_ch + 1) if ch not in fetched_indexes]
        
        if missing:
            print(f"\n[WARNING] Missing {len(missing)} chapters in slice {s_ch}-{e_ch}: {missing}. Initiating Rescue Pass...")
            for ch_num in list(missing):
                ch_meta = chapter_map.get(ch_num, {
                    "chapter_number": ch_num,
                    "title": f"Chapter {ch_num}",
                    "url": f"https://novelping.com/book/{novel_id}/chapter-{ch_num}"
                })
                try:
                    rescued_obj = fetch_single_chapter_with_retry(scraper, novel_id, ch_num, ch_meta, max_retries=5)
                    bundled_chapters.append(rescued_obj)
                    missing.remove(ch_num)
                    print(f"  [RESCUED] Successfully recovered Chapter {ch_num}!")
                except Exception as e:
                    print(f"  [FAILED] Rescue failed for Chapter {ch_num}: {e}")
                    
        # Final strict verification for this slice
        fetched_indexes = set(c['chapter_index'] for c in bundled_chapters)
        final_missing = [ch for ch in range(s_ch, e_ch + 1) if ch not in fetched_indexes]
        
        if final_missing:
            error_msg = f"CRITICAL: Slice {s_ch}-{e_ch} incomplete! Missing chapters: {final_missing}. Aborting save."
            print(f"\n[ERROR] {error_msg}\n")
            raise RuntimeError(error_msg)

        # Strictly sort chapters by chapter_index
        bundled_chapters.sort(key=lambda c: c['chapter_index'])

        bundle_filename = f"chapters_{s_ch}_{e_ch}.json"
        bundle_path = os.path.join(target_dir, bundle_filename)
        
        bundle_payload = {
            "novel_id": novel_id,
            "start_chapter": s_ch,
            "end_chapter": e_ch,
            "total_chapters": len(bundled_chapters),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "chapters": bundled_chapters
        }

        with open(bundle_path, "w", encoding="utf-8") as f:
            json.dump(bundle_payload, f, indent=2, ensure_ascii=False)

        print(f"\n[SUCCESS] Saved slice bundle ({len(bundled_chapters)}/{slice_count} chapters) to {bundle_path}!")

        # Update index.json manifest immediately
        update_manifest(target_dir, bundle_filename, s_ch, e_ch, len(bundled_chapters), novel_id)
        saved_bundle_paths.append(bundle_path)

    return saved_bundle_paths

def update_manifest(output_dir: str, bundle_filename: str, start_ch: int, end_ch: int, count: int, novel_id: str):
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

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Updated manifest at {manifest_path}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch arbitrary chapter bundles for Novel Reader")
    parser.add_argument("--start", type=int, required=True, help="Start chapter number (e.g. 1906)")
    parser.add_argument("--end", type=int, required=True, help="End chapter number (e.g. 1908)")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory for JSON bundles")
    parser.add_argument("--novel-id", type=str, default="infinite-mana-in-the-apocalypse", help="Novel ID / Slug")
    args = parser.parse_args()

    download_bundle(args.start, args.end, args.output_dir, novel_id=args.novel_id)
