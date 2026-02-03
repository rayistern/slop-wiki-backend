#!/usr/bin/env python3
"""
slop.wiki MeiliSearch Indexing Script

Fetches all pages from MediaWiki and indexes them into MeiliSearch.
Can be run manually or scheduled via cron.

Usage:
    python scripts/index_wiki.py
    
Environment variables:
    MEDIAWIKI_API_URL - MediaWiki API endpoint (default: http://mediawiki/api.php)
    MEILI_URL - MeiliSearch URL (default: http://meilisearch:7700)
    MEILI_MASTER_KEY - MeiliSearch master key (default: masterkey)
"""

import asyncio
import httpx
import os
import sys
from datetime import datetime

# Configuration
MEDIAWIKI_URL = os.getenv("MEDIAWIKI_API_URL", "http://mediawiki/api.php")
MEILI_URL = os.getenv("MEILI_URL", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterkey")
MEILI_INDEX = "wiki"


async def fetch_all_pages(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all page titles from MediaWiki."""
    all_pages = []
    apcontinue = None
    
    print(f"[{datetime.now().isoformat()}] Fetching page list from MediaWiki...")
    
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": "500",
            "format": "json"
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        
        resp = await client.get(MEDIAWIKI_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        pages = data.get("query", {}).get("allpages", [])
        all_pages.extend(pages)
        print(f"  Fetched {len(all_pages)} pages so far...")
        
        if "continue" in data:
            apcontinue = data["continue"].get("apcontinue")
        else:
            break
    
    print(f"[{datetime.now().isoformat()}] Found {len(all_pages)} total pages")
    return all_pages


async def fetch_page_content(client: httpx.AsyncClient, titles: list[str]) -> list[dict]:
    """Fetch content and categories for a batch of pages."""
    documents = []
    batch_size = 50
    
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i+batch_size]
        titles_str = "|".join(batch)
        
        params = {
            "action": "query",
            "titles": titles_str,
            "prop": "revisions|categories",
            "rvprop": "content",
            "rvslots": "main",
            "cllimit": "max",
            "format": "json"
        }
        
        try:
            resp = await client.get(MEDIAWIKI_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Warning: Failed to fetch batch starting at {i}: {e}")
            continue
        
        pages_data = data.get("query", {}).get("pages", {})
        
        for page_id, page_info in pages_data.items():
            if int(page_id) < 0:  # Missing page
                continue
            
            title = page_info.get("title", "")
            
            # Extract content
            content = ""
            revisions = page_info.get("revisions", [])
            if revisions:
                slots = revisions[0].get("slots", {})
                main_slot = slots.get("main", {})
                content = main_slot.get("*", "")
            
            # Extract categories
            categories = []
            for cat in page_info.get("categories", []):
                cat_title = cat.get("title", "")
                if cat_title.startswith("Category:"):
                    categories.append(cat_title[9:])
            
            documents.append({
                "id": page_id,
                "title": title,
                "content": content,
                "categories": categories,
                "url": f"/wiki/{title.replace(' ', '_')}",
                "indexed_at": datetime.utcnow().isoformat()
            })
        
        if (i + batch_size) % 200 == 0:
            print(f"  Processed {min(i + batch_size, len(titles))}/{len(titles)} pages...")
    
    return documents


async def setup_meilisearch_index(client: httpx.AsyncClient):
    """Create and configure the MeiliSearch index."""
    headers = {
        "Authorization": f"Bearer {MEILI_MASTER_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"[{datetime.now().isoformat()}] Setting up MeiliSearch index...")
    
    # Create index
    try:
        await client.post(
            f"{MEILI_URL}/indexes",
            headers=headers,
            json={"uid": MEILI_INDEX, "primaryKey": "id"}
        )
        print("  Created new index")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            print("  Index already exists")
        else:
            raise
    
    # Configure settings
    settings = {
        "searchableAttributes": ["title", "content", "categories"],
        "displayedAttributes": ["id", "title", "content", "categories", "url", "indexed_at"],
        "filterableAttributes": ["categories"],
        "sortableAttributes": ["title", "indexed_at"],
        "rankingRules": [
            "words",
            "typo",
            "proximity",
            "attribute",
            "sort",
            "exactness"
        ],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {
                "oneTypo": 4,
                "twoTypos": 8
            }
        }
    }
    
    resp = await client.patch(
        f"{MEILI_URL}/indexes/{MEILI_INDEX}/settings",
        headers=headers,
        json=settings
    )
    resp.raise_for_status()
    print("  Configured index settings")


async def index_documents(client: httpx.AsyncClient, documents: list[dict]):
    """Index documents into MeiliSearch."""
    headers = {
        "Authorization": f"Bearer {MEILI_MASTER_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"[{datetime.now().isoformat()}] Indexing {len(documents)} documents...")
    
    # Index in batches of 1000
    batch_size = 1000
    tasks = []
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        resp = await client.post(
            f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",
            headers=headers,
            json=batch
        )
        resp.raise_for_status()
        task_info = resp.json()
        tasks.append(task_info.get("taskUid"))
        print(f"  Submitted batch {i//batch_size + 1} (task {task_info.get('taskUid')})")
    
    # Wait for tasks to complete
    print("  Waiting for indexing to complete...")
    for task_uid in tasks:
        while True:
            resp = await client.get(f"{MEILI_URL}/tasks/{task_uid}", headers=headers)
            task_status = resp.json()
            status = task_status.get("status")
            
            if status == "succeeded":
                break
            elif status == "failed":
                print(f"  Warning: Task {task_uid} failed: {task_status.get('error')}")
                break
            
            await asyncio.sleep(0.5)
    
    print(f"[{datetime.now().isoformat()}] Indexing complete!")


async def main():
    """Main indexing workflow."""
    print("=" * 60)
    print("slop.wiki MeiliSearch Indexing")
    print("=" * 60)
    print(f"MediaWiki: {MEDIAWIKI_URL}")
    print(f"MeiliSearch: {MEILI_URL}")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Check MeiliSearch connectivity
        try:
            resp = await client.get(f"{MEILI_URL}/health")
            if resp.json().get("status") != "available":
                print("Error: MeiliSearch not available")
                sys.exit(1)
        except Exception as e:
            print(f"Error: Cannot connect to MeiliSearch: {e}")
            sys.exit(1)
        
        # Check MediaWiki connectivity
        try:
            resp = await client.get(MEDIAWIKI_URL, params={"action": "query", "meta": "siteinfo", "format": "json"})
            resp.raise_for_status()
        except Exception as e:
            print(f"Error: Cannot connect to MediaWiki: {e}")
            sys.exit(1)
        
        # Fetch pages
        pages = await fetch_all_pages(client)
        if not pages:
            print("No pages found in MediaWiki")
            sys.exit(0)
        
        # Fetch content
        titles = [p["title"] for p in pages]
        documents = await fetch_page_content(client, titles)
        
        if not documents:
            print("No documents to index")
            sys.exit(0)
        
        # Setup and index
        await setup_meilisearch_index(client)
        await index_documents(client, documents)
        
        # Print stats
        resp = await client.get(
            f"{MEILI_URL}/indexes/{MEILI_INDEX}/stats",
            headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
        )
        stats = resp.json()
        print("\n" + "=" * 60)
        print("Index Statistics:")
        print(f"  Total documents: {stats.get('numberOfDocuments', 'N/A')}")
        print(f"  Is indexing: {stats.get('isIndexing', 'N/A')}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
