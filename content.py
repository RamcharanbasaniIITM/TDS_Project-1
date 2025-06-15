import os
import json
import re
from datetime import datetime
from urllib.parse import urljoin
from markdownify import markdownify as md
from playwright.sync_api import sync_playwright

BASE_URL = "https://tds.s-anand.net/#/2025-01/"
BASE_ORIGIN = "https://tds.s-anand.net"
OUTPUT_DIR = "markdown_files"
METADATA_FILE = "metadata.json"

visited = set()
metadata = []

def sanitize_filename(title):
    # Remove illegal filename characters and replace spaces with underscores
    return re.sub(r'[\/*?:"<>|]', "_", title).strip().replace(" ", "_")

def extract_all_internal_links(page):
    links = page.eval_on_selector_all("a[href]", "els => els.map(el => el.href)")
    # Keep only links that belong to base origin and contain '/#/' (Docsify hash routes)
    return list(set(
        link for link in links
        if BASE_ORIGIN in link and '/#/' in link
    ))

def wait_for_article_and_get_html(page):
    page.wait_for_selector("article.markdown-section#main", timeout=10000)
    return page.inner_html("article.markdown-section#main")

def crawl_page(page, url):
    if url in visited:
        return
    visited.add(url)

    print(f"📄 Visiting: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded")
        # Small delay to allow content to render
        page.wait_for_timeout(1000)
        html = wait_for_article_and_get_html(page)
    except Exception as e:
        print(f"❌ Error loading page: {url} - {e}")
        return

    # Extract title for filename and metadata
    title = page.title().split(" - ")[0].strip() or f"page_{len(visited)}"
    filename = sanitize_filename(title)
    filepath = os.path.join(OUTPUT_DIR, f"{filename}.md")

    # Convert HTML content to markdown
    markdown = md(html)

    # Write markdown file with YAML front matter metadata
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"title: \"{title}\"\n")
        f.write(f"original_url: \"{url}\"\n")
        f.write(f"downloaded_at: \"{datetime.now().isoformat()}\"\n")
        f.write("---\n\n")
        f.write(markdown)

    metadata.append({
        "title": title,
        "filename": f"{filename}.md",
        "original_url": url,
        "downloaded_at": datetime.now().isoformat()
    })

    # Recursively crawl all internal links found on this page
    links = extract_all_internal_links(page)
    for link in links:
        if link not in visited:
            crawl_page(page, link)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global visited, metadata

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        crawl_page(page, BASE_URL)

        # Save metadata JSON
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"✅ Completed. {len(metadata)} pages saved.")
        browser.close()

if __name__ == "__main__":
    main()
