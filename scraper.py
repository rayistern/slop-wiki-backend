#!/usr/bin/env python3
"""
Moltbook Scraper for slop.wiki
Pulls threads from Moltbook and creates triage tasks.
"""

import os
import json
import sqlite3
import httpx
from datetime import datetime
from pathlib import Path

# Config
MOLTBOOK_API = "https://www.moltbook.com/api/v1"
SLOP_API = os.getenv("SLOP_API", "https://api.slop.wiki")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
DB_PATH = Path("slop.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_scraped_table():
    """Track which posts we've already scraped."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scraped_posts (
            moltbook_id TEXT PRIMARY KEY,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def is_already_scraped(post_id: str) -> bool:
    conn = get_db()
    result = conn.execute("SELECT 1 FROM scraped_posts WHERE moltbook_id = ?", (post_id,)).fetchone()
    conn.close()
    return result is not None

def mark_scraped(post_id: str):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO scraped_posts (moltbook_id) VALUES (?)", (post_id,))
    conn.commit()
    conn.close()

def fetch_posts(sort: str = "new", limit: int = 50, offset: int = 0) -> list:
    """Fetch posts from Moltbook."""
    url = f"{MOLTBOOK_API}/posts?sort={sort}&limit={limit}&offset={offset}"
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("posts", [])

def create_task(post: dict) -> dict:
    """Create a triage task for a post."""
    # Build verification question from post content
    has_code = "```" in post.get("content", "") or "code" in post.get("content", "").lower()
    
    task = {
        "type": "triage",
        "target_url": f"https://www.moltbook.com/m/{post['submolt']['name']}/comments/{post['id']}",
        "target_title": post.get("title", "")[:200],
        "submolt": post.get("submolt", {}).get("name", "general"),
        "verification_question": f"Does this post contain code or technical content?",
        "verification_answer": has_code,
        "submissions_needed": 5
    }
    
    resp = httpx.post(
        f"{SLOP_API}/admin/task",
        headers={"Authorization": f"Bearer {ADMIN_KEY}", "Content-Type": "application/json"},
        json=task,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()

def scrape(count: int = 50, sort: str = "new"):
    """Main scrape function."""
    init_scraped_table()
    
    print(f"Fetching {count} posts from Moltbook (sort={sort})...")
    posts = fetch_posts(sort=sort, limit=count)
    
    created = 0
    skipped = 0
    
    for post in posts:
        post_id = post.get("id")
        if not post_id:
            continue
            
        if is_already_scraped(post_id):
            skipped += 1
            continue
        
        try:
            result = create_task(post)
            mark_scraped(post_id)
            created += 1
            print(f"  ✓ Created task for: {post.get('title', '')[:50]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    print(f"\nDone. Created {created} tasks, skipped {skipped} (already scraped).")
    return {"created": created, "skipped": skipped}

if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    sort = sys.argv[2] if len(sys.argv) > 2 else "new"
    
    if not ADMIN_KEY:
        print("Set ADMIN_KEY environment variable")
        sys.exit(1)
    
    scrape(count=count, sort=sort)
