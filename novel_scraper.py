"""
novel_scraper.py
----------------
Production-ready Web Novel Scraper & Text Normalizer
Target: NovelPing and similar web novel platforms.
Tested on: https://novelping.com/book/infinite-mana-in-the-apocalypse
"""

import re
import json
import time
import urllib.request
from typing import Dict, List, Optional
from bs4 import BeautifulSoup, Tag

class NovelScraper:
    def __init__(self, base_url: str = "https://novelping.com"):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        # Common advertising and boilerplate watermark patterns in web novels
        self.ad_patterns = [
            re.compile(r"visit.*novelping.*for.*updates", re.IGNORECASE),
            re.compile(r"read.*at.*novelping", re.IGNORECASE),
            re.compile(r"if you find any errors.*let us know", re.IGNORECASE),
            re.compile(r"patreon\.com\/.*", re.IGNORECASE),
            re.compile(r"support the author on", re.IGNORECASE),
            re.compile(r"chapter.*translated by", re.IGNORECASE),
            re.compile(r"^\s*advertisement\s*$", re.IGNORECASE),
        ]

    def _fetch_html(self, url: str, max_retries: int = 4) -> str:
        """Fetch raw HTML with retry backoff and error handling."""
        import urllib.error
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=45) as response:
                    return response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_time = (attempt + 1) * 3
                    print(f"  [Rate Limit 429] Waiting {wait_time}s before retry ({attempt+1}/{max_retries}) for {url}...")
                    time.sleep(wait_time)
                elif attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"  [HTTP {e.code}] Retrying in {wait_time}s ({attempt+1}/{max_retries}) for {url}...")
                    time.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"  [Network Error: {e}] Retrying in {wait_time}s ({attempt+1}/{max_retries}) for {url}...")
                    time.sleep(wait_time)
                else:
                    raise
        raise RuntimeError(f"Failed to fetch HTML from {url} after {max_retries} attempts.")

    def extract_novel_metadata(self, book_url: str) -> Dict:
        """
        Extracts novel title, author, description, tags, and initial chapter list.
        """
        html = self._fetch_html(book_url)
        soup = BeautifulSoup(html, "html.parser")

        # 1. Title
        title_el = soup.select_one("h1, h3.title, .book-info h3")
        title = title_el.get_text(strip=True) if title_el else "Unknown Title"

        # 2. Description / Synopsis
        desc_el = soup.select_one(".desc-text, #tab-description, .summary")
        description = desc_el.get_text("\n\n", strip=True) if desc_el else ""

        # 3. Metadata (Author, Genres, Status, Cover)
        cover_el = soup.select_one(".book img, .book-info img, img.cover")
        cover_url = cover_el.get("src") if cover_el else None

        author = "Unknown"
        genres = []
        status = "Unknown"

        for li in soup.select("li"):
            text = li.get_text(" ", strip=True)
            if "Author:" in text:
                a_tag = li.find("a")
                author = a_tag.get_text(strip=True) if a_tag else text.replace("Author:", "").strip()
            elif "Genre:" in text:
                genre_links = li.find_all("a")
                if genre_links:
                    genres = [g.get_text(strip=True) for g in genre_links]
                else:
                    genres = [g.strip() for g in text.replace("Genre:", "").split(",") if g.strip()]
            elif "Status:" in text:
                status = text.replace("Status:", "").strip()

        # 4. Extract Chapter Links from #tab-chapters or page templates
        chapters = []
        tab_chapters = soup.select_one("#tab-chapters")
        if tab_chapters:
            # Look for explicit anchor tags
            chapter_links = tab_chapters.select("a[href*='/chapter-']")
            # Deduplicate preserving order
            seen_urls = set()
            for a in chapter_links:
                href = a.get("href")
                if href and href not in seen_urls:
                    seen_urls.add(href)
                    ch_title = a.get("title") or a.get_text(strip=True)
                    chapters.append({
                        "chapter_index": len(chapters) + 1,
                        "title": ch_title or f"Chapter {len(chapters) + 1}",
                        "url": href if href.startswith("http") else f"{self.base_url}{href}"
                    })

        return {
            "title": title,
            "author": author,
            "status": status,
            "genres": genres,
            "cover_url": cover_url,
            "description": description,
            "source_url": book_url,
            "total_chapters_detected": len(chapters),
            "chapters": chapters
        }

    def clean_chapter_content(self, raw_html: str) -> Dict:
        """
        Cleans chapter content:
        - Strips script, style, ads, and navigation buttons.
        - De-duplicates watermarks.
        - Tokenizes into paragraphs and TTS-friendly sentences.
        """
        soup = BeautifulSoup(raw_html, "html.parser")

        # Extract title (avoid selecting 'Novel info' sidebar heading)
        title_el = soup.select_one(".chr-title, .chr-text, .chapter-title, h1.chapter-title, h3.title")
        if not title_el:
            # Fallback to general headings if not 'Novel info'
            for h in soup.select("h1, h2, h3"):
                txt = h.get_text(strip=True)
                if txt.lower() not in ["novel info", "book info", "description", "options"]:
                    title_el = h
                    break
        chapter_title = title_el.get_text(strip=True) if title_el else ""

        # Content container
        content_container = soup.select_one("#chr-content, .chapter-content, .reading-content, #chapter-content, .chapter-inner, .entry-content")
        if not content_container:
            return {"title": chapter_title, "paragraphs": [], "sentences": []}

        # Remove irrelevant elements
        for unwanted in content_container.select("script, style, iframe, .ads, .ad, .cha-words, a.btn, noscript"):
            unwanted.decompose()

        cleaned_paragraphs: List[str] = []
        p_elements = content_container.find_all(["p", "div"])

        # Fallback if text isn't in paragraphs
        if not p_elements:
            lines = content_container.get_text("\n").splitlines()
        else:
            lines = [p.get_text(strip=True) for p in p_elements]

        for text in lines:
            text = text.strip()
            if not text:
                continue

            # Strip watermarks and ad patterns
            if any(pat.search(text) for pat in self.ad_patterns):
                continue

            # Skip short duplicate headers or next/prev chapter text
            lower_text = text.lower()
            if lower_text in ["prev chapter", "next chapter", "chapter list", "options"]:
                continue

            cleaned_paragraphs.append(text)

        # Tokenize paragraphs into sentences for TTS synchronization
        sentences: List[Dict] = []
        sentence_idx = 0
        # Regex splits by sentence boundaries (.!?) followed by space/quote/bracket
        sentence_splitter = re.compile(r'(?<=[.!?…])\s+(?=[A-Z0-9"“\[])')

        for p_idx, para in enumerate(cleaned_paragraphs):
            raw_sentences = sentence_splitter.split(para)
            for s in raw_sentences:
                s_clean = s.strip()
                if s_clean:
                    sentences.append({
                        "id": sentence_idx,
                        "paragraph_id": p_idx,
                        "text": s_clean
                    })
                    sentence_idx += 1

        return {
            "title": chapter_title,
            "paragraphs": cleaned_paragraphs,
            "sentences": sentences,
            "word_count": sum(len(p.split()) for p in cleaned_paragraphs)
        }

    def fetch_chapter(self, chapter_url: str) -> Dict:
        """Downloads and processes a single chapter."""
        html = self._fetch_html(chapter_url)
        return self.clean_chapter_content(html)


if __name__ == "__main__":
    scraper = NovelScraper()
    novel_url = "https://novelping.com/book/infinite-mana-in-the-apocalypse"
    
    print("1. Scraping Novel Metadata...")
    metadata = scraper.extract_novel_metadata(novel_url)
    print(f"Title: {metadata['title']}")
    print(f"Author: {metadata['author']}")
    print(f"Genres: {', '.join(metadata['genres'])}")
    print(f"Chapters found on page: {metadata['total_chapters_detected']}")

    if metadata["chapters"]:
        first_chap_url = metadata["chapters"][0]["url"]
        print(f"\n2. Scraping First Chapter: {first_chap_url} ...")
        chapter_data = scraper.fetch_chapter(first_chap_url)
        print(f"Cleaned Paragraphs: {len(chapter_data['paragraphs'])}")
        print(f"Tokenized Sentences for TTS: {len(chapter_data['sentences'])}")
        print(f"Estimated Word Count: {chapter_data['word_count']}")
        print(f"Sample Sentence 0: {chapter_data['sentences'][0]['text']}")
        print(f"Sample Sentence 1: {chapter_data['sentences'][1]['text']}")
        
        # Save sample output for frontend reader
        sample_payload = {
            "novel": {
                "title": metadata["title"],
                "author": metadata["author"],
                "cover_url": metadata["cover_url"],
                "description": metadata["description"]
            },
            "current_chapter": {
                "chapter_index": 1,
                "title": metadata["chapters"][0]["title"],
                "paragraphs": chapter_data["paragraphs"],
                "sentences": chapter_data["sentences"]
            },
            "chapters_nav": metadata["chapters"][:10]
        }
        with open("sample_chapter.json", "w", encoding="utf-8") as f:
            json.dump(sample_payload, f, indent=2, ensure_ascii=False)
        print("\nSaved 'sample_chapter.json' successfully for frontend consumption.")
