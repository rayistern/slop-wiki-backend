# PATCH: MediaWiki Sync Pipeline
# Syncs verified/published content from backend to MediaWiki
# Requires: MEDIAWIKI_BOT_USER and MEDIAWIKI_BOT_PASSWORD in environment

import httpx
import os
from typing import Optional

# MediaWiki API client
class MediaWikiClient:
    """Simple MediaWiki API client for bot operations."""
    
    def __init__(self, api_url: str, bot_user: str, bot_password: str):
        self.api_url = api_url
        self.bot_user = bot_user
        self.bot_password = bot_password
        self.client = httpx.AsyncClient(timeout=30.0)
        self.csrf_token: Optional[str] = None
        self._logged_in = False
    
    async def _api(self, **params):
        """Make an API request."""
        params['format'] = 'json'
        response = await self.client.post(self.api_url, data=params)
        response.raise_for_status()
        return response.json()
    
    async def login(self):
        """Login to MediaWiki using bot password."""
        if self._logged_in:
            return
        
        # Get login token
        result = await self._api(
            action='query',
            meta='tokens',
            type='login'
        )
        login_token = result['query']['tokens']['logintoken']
        
        # Login
        result = await self._api(
            action='login',
            lgname=self.bot_user,
            lgpassword=self.bot_password,
            lgtoken=login_token
        )
        
        if result.get('login', {}).get('result') != 'Success':
            raise Exception(f"Login failed: {result}")
        
        self._logged_in = True
    
    async def get_csrf_token(self) -> str:
        """Get CSRF token for editing."""
        await self.login()
        
        result = await self._api(
            action='query',
            meta='tokens'
        )
        self.csrf_token = result['query']['tokens']['csrftoken']
        return self.csrf_token
    
    async def edit_page(self, title: str, content: str, summary: str = "Bot edit") -> dict:
        """Create or edit a page."""
        token = await self.get_csrf_token()
        
        result = await self._api(
            action='edit',
            title=title,
            text=content,
            summary=summary,
            token=token,
            bot='1'  # Mark as bot edit
        )
        
        return result.get('edit', {})
    
    async def page_exists(self, title: str) -> bool:
        """Check if a page exists."""
        result = await self._api(
            action='query',
            titles=title
        )
        pages = result.get('query', {}).get('pages', {})
        for page_id, page_info in pages.items():
            return page_id != '-1'
        return False
    
    async def get_page_content(self, title: str) -> Optional[str]:
        """Get page content."""
        result = await self._api(
            action='query',
            titles=title,
            prop='revisions',
            rvprop='content',
            rvslots='main'
        )
        pages = result.get('query', {}).get('pages', {})
        for page_id, page_info in pages.items():
            if page_id == '-1':
                return None
            revisions = page_info.get('revisions', [])
            if revisions:
                return revisions[0].get('slots', {}).get('main', {}).get('*')
        return None


# Global client instance (initialized on first use)
_wiki_client: Optional[MediaWikiClient] = None

def get_wiki_client() -> MediaWikiClient:
    """Get or create the MediaWiki client."""
    global _wiki_client
    
    if _wiki_client is None:
        api_url = os.getenv("MEDIAWIKI_API_URL", "http://mediawiki/api.php")
        bot_user = os.getenv("MEDIAWIKI_BOT_USER")
        bot_password = os.getenv("MEDIAWIKI_BOT_PASSWORD")
        
        if not bot_user or not bot_password:
            raise ValueError("MEDIAWIKI_BOT_USER and MEDIAWIKI_BOT_PASSWORD must be set")
        
        _wiki_client = MediaWikiClient(api_url, bot_user, bot_password)
    
    return _wiki_client


def thread_to_wikitext(thread) -> str:
    """Convert a thread to MediaWiki wikitext format."""
    # Build wikitext content
    content = f"""= {thread.title} =

{thread.summary or "No summary available."}

== Source Information ==
{{| class="wikitable"
|-
! Field !! Value
|-
| '''Moltbook Thread ID''' || {thread.moltbook_id or "N/A"}
|-
| '''Original URL''' || {thread.url or "N/A"}
|-
| '''Indexed''' || {thread.indexed_at.isoformat() if thread.indexed_at else "Unknown"}
|}}

== Tags ==
"""
    
    # Add tags as categories
    if thread.tags:
        tags = thread.tags.split(",")
        for tag in tags:
            tag = tag.strip()
            if tag:
                content += f"[[Category:{tag}]]\n"
    else:
        content += "''No tags''\n"
    
    # Add footer
    content += """
----
<small>''This page was auto-generated from consensus-verified content on slop.wiki''</small>
[[Category:Auto-generated]]
[[Category:Verified Threads]]
"""
    
    return content


async def sync_to_wiki(thread_id: int, db):
    """Sync a published thread to MediaWiki as a page."""
    from database import Thread
    
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        return {"error": "Thread not found"}
    
    if not thread.is_published:
        return {"error": "Thread not published"}
    
    try:
        client = get_wiki_client()
    except ValueError as e:
        return {"error": str(e)}
    
    # Generate wiki page path from thread
    slug = thread.moltbook_id or f"thread-{thread.id}"
    # Use Thread namespace
    title = f"Thread:{slug}"
    
    # Convert to wikitext
    content = thread_to_wikitext(thread)
    
    try:
        # Create/update the page
        result = await client.edit_page(
            title=title,
            content=content,
            summary=f"Bot: Synced from backend (thread {thread.id})"
        )
        
        if result.get('result') == 'Success':
            # Update thread with wiki page reference
            thread.wiki_page_id = result.get('pageid')
            thread.wiki_path = title
            db.commit()
            
            return {
                "status": "synced",
                "wiki_path": title,
                "wiki_page_id": thread.wiki_page_id,
                "new_revision": result.get('newrevid')
            }
        else:
            return {
                "error": f"Edit failed: {result}",
                "result": result
            }
            
    except Exception as e:
        return {"error": str(e)}


async def batch_sync_to_wiki(thread_ids: list, db) -> dict:
    """Sync multiple threads to MediaWiki."""
    results = {
        "success": [],
        "failed": []
    }
    
    for thread_id in thread_ids:
        result = await sync_to_wiki(thread_id, db)
        if "error" in result:
            results["failed"].append({"thread_id": thread_id, "error": result["error"]})
        else:
            results["success"].append({"thread_id": thread_id, "wiki_path": result.get("wiki_path")})
    
    return results


# FastAPI endpoint integration
# Add these routes to main.py:

"""
from patches.wiki_sync_mediawiki import sync_to_wiki, batch_sync_to_wiki

@app.post("/admin/sync-wiki/{thread_id}")
async def sync_thread_to_wiki(
    thread_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    '''Manually sync a published thread to MediaWiki.'''
    import os
    
    admin_key = os.getenv("ADMIN_KEY") or os.getenv("BACKEND_ADMIN_KEY")
    operator_key = os.getenv("OPERATOR_KEY")
    token = authorization.replace("Bearer ", "") if authorization else ""
    
    if token not in [admin_key, operator_key]:
        raise HTTPException(status_code=403, detail="Admin or operator access required")
    
    result = await sync_to_wiki(thread_id, db)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.post("/admin/sync-wiki-batch")
async def sync_threads_to_wiki_batch(
    thread_ids: list[int],
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    '''Batch sync multiple threads to MediaWiki.'''
    import os
    
    admin_key = os.getenv("ADMIN_KEY") or os.getenv("BACKEND_ADMIN_KEY")
    operator_key = os.getenv("OPERATOR_KEY")
    token = authorization.replace("Bearer ", "") if authorization else ""
    
    if token not in [admin_key, operator_key]:
        raise HTTPException(status_code=403, detail="Admin or operator access required")
    
    results = await batch_sync_to_wiki(thread_ids, db)
    return results
"""

# Add to database.py Thread model:
#     wiki_page_id = Column(Integer, nullable=True)
#     wiki_path = Column(String, nullable=True)
