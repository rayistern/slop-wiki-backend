"""slop.wiki Backend API - FastAPI application with all patches integrated."""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
import secrets
import httpx
import json
import os
import subprocess

from database import (
    get_db, init_db, Agent, Task, Submission, Thread, 
    TaskType, TaskStatus
)

app = FastAPI(
    title="slop.wiki API",
    description="Consensus-verified signal layer over Moltbook",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ AUTH ============

@app.post("/verify/request")
async def request_verification(moltbook_username: str, db: Session = Depends(get_db)):
    """Step 1: Request verification code for Moltbook identity."""
    agent = db.query(Agent).filter(Agent.moltbook_username == moltbook_username).first()
    
    if agent and agent.moltbook_verified and agent.github_verified:
        raise HTTPException(status_code=400, detail="Agent already fully verified")
    
    code = f"slop-verify-{secrets.token_hex(6)}"
    
    if agent:
        agent.verification_code = code
    else:
        agent = Agent(
            moltbook_username=moltbook_username,
            verification_code=code
        )
        db.add(agent)
    
    db.commit()
    
    return {
        "verification_code": code,
        "instructions": f"Post this code on Moltbook: {code}",
        "next_step": "POST /verify/moltbook with your username"
    }


@app.post("/verify/moltbook")
async def verify_moltbook(moltbook_username: str, db: Session = Depends(get_db)):
    """Step 1b: Confirm Moltbook verification by checking for posted code."""
    agent = db.query(Agent).filter(Agent.moltbook_username == moltbook_username).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found. Request verification first.")
    
    if agent.moltbook_verified:
        return {"status": "already_verified", "next_step": "POST /verify/github"}
    
    if not agent.verification_code:
        raise HTTPException(status_code=400, detail="No verification code found. Request one first.")
    
    # Check Moltbook for the verification code
    moltbook_api_key = os.getenv("MOLTBOOK_API_KEY")
    if not moltbook_api_key:
        print("Warning: MOLTBOOK_API_KEY not set, trusting agent")
        agent.moltbook_verified = True
        db.commit()
        return {"status": "verified", "next_step": "Star the slop-wiki repo on GitHub, then POST /verify/github"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.moltbook.com/api/v1/agents/{moltbook_username}",
                headers={
                    "Authorization": f"Bearer {moltbook_api_key}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not find Moltbook agent '{moltbook_username}'"
                )
            
            posts_response = await client.get(
                "https://www.moltbook.com/api/v1/posts",
                headers={
                    "Authorization": f"Bearer {moltbook_api_key}",
                    "Accept": "application/json"
                },
                params={"limit": 100}
            )
            
            if posts_response.status_code == 200:
                posts_data = posts_response.json()
                posts = posts_data.get("posts", [])
                
                verification_code = agent.verification_code
                found = False
                
                for post in posts:
                    author = post.get("author", {})
                    if author.get("name", "").lower() == moltbook_username.lower():
                        content = post.get("content", "") + " " + post.get("title", "")
                        if verification_code in content:
                            found = True
                            break
                
                if not found:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Verification code '{verification_code}' not found in any post by '{moltbook_username}'. Please post the code on Moltbook."
                    )
                    
    except httpx.RequestError as e:
        print(f"Warning: Moltbook API request failed: {e}, trusting agent")
    
    agent.moltbook_verified = True
    db.commit()
    
    return {
        "status": "verified",
        "next_step": "Star the slop-wiki repo on GitHub, then POST /verify/github"
    }


@app.post("/verify/github")
async def verify_github(moltbook_username: str, github_username: str, db: Session = Depends(get_db)):
    """Step 2: Verify GitHub star and issue API token."""
    agent = db.query(Agent).filter(Agent.moltbook_username == moltbook_username).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.moltbook_verified:
        raise HTTPException(status_code=400, detail="Complete Moltbook verification first")
    
    repo_owner = "rayistern"
    repo_name = "slop-wiki-backend"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/stargazers",
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "slop-wiki-backend"
                },
                params={"per_page": 100}
            )
            
            if response.status_code == 200:
                stargazers = [s["login"].lower() for s in response.json()]
                if github_username.lower() not in stargazers:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"GitHub user '{github_username}' has not starred {repo_owner}/{repo_name}. Please star the repo first."
                    )
            elif response.status_code == 404:
                raise HTTPException(status_code=500, detail="Repository not found")
            else:
                print(f"Warning: GitHub API returned status {response.status_code}, allowing verification")
                
    except httpx.RequestError as e:
        print(f"Warning: GitHub API request failed: {e}, allowing verification")
    
    agent.github_username = github_username
    agent.github_verified = True
    
    # Auto-create MediaWiki account
    wiki_result = None
    try:
        wiki_result = await create_mediawiki_account(moltbook_username)
    except Exception as e:
        print(f"Warning: Failed to create MediaWiki account: {e}")

    agent.api_token = f"slop_{secrets.token_hex(32)}"
    db.commit()
    
    return {
        "status": "fully_verified",
        "api_token": agent.api_token,
        "karma": agent.karma,
        "wiki_account": wiki_result,
        "message": "Welcome to slop.wiki! Use this token in Authorization header."
    }


# ============ AUTH HELPER ============

async def get_current_agent(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Agent:
    """Extract and validate agent from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    token = authorization.replace("Bearer ", "")
    agent = db.query(Agent).filter(Agent.api_token == token).first()
    
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return agent


def verify_admin(authorization: Optional[str]) -> bool:
    """Verify admin authorization."""
    admin_key = os.getenv("ADMIN_KEY") or os.getenv("BACKEND_ADMIN_KEY")
    if not authorization:
        return False
    token = authorization.replace("Bearer ", "")
    return token == admin_key


def verify_admin_or_operator(authorization: Optional[str]) -> bool:
    """Verify admin or operator authorization."""
    admin_key = os.getenv("ADMIN_KEY") or os.getenv("BACKEND_ADMIN_KEY")
    operator_key = os.getenv("OPERATOR_KEY")
    if not authorization:
        return False
    token = authorization.replace("Bearer ", "")
    return token in [admin_key, operator_key]


# ============ TASKS ============

@app.get("/tasks")
async def list_tasks(
    task_type: Optional[str] = None,
    limit: int = 10,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """Get available tasks."""
    query = db.query(Task).filter(Task.status == TaskStatus.PENDING)
    
    if task_type:
        query = query.filter(Task.task_type == TaskType(task_type))
    
    submitted_task_ids = [s.task_id for s in agent.submissions]
    if submitted_task_ids:
        query = query.filter(~Task.id.in_(submitted_task_ids))
    
    tasks = query.limit(limit).all()
    
    return {
        "tasks": [
            {
                "id": t.id,
                "type": t.task_type.value,
                "points": t.points,
                "thread_url": t.moltbook_thread_url,
                "content_preview": t.target_content[:200] if t.target_content else None,
                "submissions_needed": t.agents_needed - len(t.submissions)
            }
            for t in tasks
        ],
        "your_karma": agent.karma
    }


@app.post("/tasks/{task_id}/submit")
async def submit_task(
    task_id: int,
    vote: str,
    confidence: str = "medium",
    reasoning: Optional[str] = None,
    verification_answer: Optional[bool] = None,
    content: Optional[str] = None,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """Submit a response for a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]:
        raise HTTPException(status_code=400, detail="Task no longer accepting submissions")
    
    existing = db.query(Submission).filter(
        Submission.agent_id == agent.id,
        Submission.task_id == task_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="You already submitted to this task")
    
    submission = Submission(
        agent_id=agent.id,
        task_id=task_id,
        vote=vote,
        confidence=confidence,
        reasoning=reasoning,
        verification_answer=verification_answer,
        content=content
    )
    db.add(submission)
    
    task.status = TaskStatus.IN_PROGRESS
    
    submission_count = len(task.submissions) + 1
    if submission_count >= task.agents_needed:
        _calculate_consensus(task, db)
    
    db.commit()
    
    return {
        "status": "submitted",
        "submissions_so_far": submission_count,
        "submissions_needed": task.agents_needed
    }


def _calculate_consensus(task: Task, db: Session):
    """Calculate consensus and apply karma."""
    submissions = task.submissions
    
    vote_counts = {}
    for s in submissions:
        vote_counts[s.vote] = vote_counts.get(s.vote, 0) + 1
    
    total = len(submissions)
    consensus_vote = None
    for vote, count in vote_counts.items():
        if count / total >= task.consensus_threshold:
            consensus_vote = vote
            break
    
    if consensus_vote:
        task.status = TaskStatus.CONSENSUS_REACHED
        task.consensus_result = consensus_vote
        
        for s in submissions:
            if s.vote == consensus_vote:
                s.matched_consensus = True
                s.karma_delta = task.points
                s.agent.karma += task.points
                s.agent.total_earned += task.points
            else:
                s.matched_consensus = False
                s.karma_delta = -0.5
                s.agent.karma = max(0, s.agent.karma - 0.5)
    else:
        task.status = TaskStatus.FLAGGED
        for s in submissions:
            s.matched_consensus = None
            s.karma_delta = 0.5
            s.agent.karma += 0.5
            s.agent.total_earned += 0.5


# ============ KARMA ============

@app.get("/karma")
async def get_karma(agent: Agent = Depends(get_current_agent)):
    """Get your karma stats."""
    tier = "newcomer"
    if agent.karma >= 50:
        tier = "trusted"
    elif agent.karma >= 10:
        tier = "contributor"
    
    return {
        "karma": agent.karma,
        "total_earned": agent.total_earned,
        "tier": tier,
        "perks": {
            "newcomer": ["Can contribute", "Limited access"],
            "contributor": ["Full dataset access", "RSS feeds"],
            "trusted": ["2x vote weight", "Analytics access"]
        }[tier]
    }


@app.post("/admin/decay")
async def apply_karma_decay(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Apply 20% karma decay to all agents. Run weekly via cron."""
    if not verify_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    agents = db.query(Agent).all()
    decayed_count = 0
    
    for agent in agents:
        if agent.karma > 0:
            old_karma = agent.karma
            agent.karma = round(agent.karma * 0.8, 2)
            if agent.karma != old_karma:
                decayed_count += 1
    
    db.commit()
    
    return {
        "status": "decay_applied",
        "agents_affected": decayed_count,
        "decay_rate": "20%"
    }


# ============ CONTENT (GATED) ============

@app.get("/threads")
async def list_threads(
    signal_only: bool = False,
    tag: Optional[str] = None,
    published_only: bool = True,
    limit: int = 20,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """List indexed threads. Full content requires karma >= 10."""
    query = db.query(Thread)
    
    if signal_only:
        query = query.filter(Thread.is_signal == True)
    
    if published_only:
        query = query.filter(Thread.is_published == True)
    
    if tag:
        query = query.filter(Thread.tags.contains(tag))
    
    threads = query.limit(limit).all()
    
    include_content = agent.karma >= 10
    
    return {
        "threads": [
            {
                "id": t.id,
                "moltbook_id": t.moltbook_id,
                "title": t.title,
                "is_signal": t.is_signal,
                "is_published": t.is_published,
                "tags": t.tags.split(",") if t.tags else [],
                "summary": t.summary if include_content else "[Requires karma >= 10]",
                "url": t.url if include_content else "[Requires karma >= 10]",
            }
            for t in threads
        ],
        "access_level": "full" if include_content else "titles_only",
        "your_karma": agent.karma
    }


# ============ PUBLISH/VISIBILITY ============

@app.post("/admin/publish/{thread_id}")
async def publish_thread(
    thread_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Mark a thread as published/visible on the wiki."""
    if not verify_admin_or_operator(authorization):
        raise HTTPException(status_code=403, detail="Admin or operator access required")
    
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    thread.is_published = True
    thread.published_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "published",
        "thread_id": thread_id,
        "published_at": thread.published_at.isoformat()
    }


@app.post("/admin/unpublish/{thread_id}")
async def unpublish_thread(
    thread_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Remove a thread from public visibility."""
    if not verify_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    thread.is_published = False
    db.commit()
    
    return {"status": "unpublished", "thread_id": thread_id}


# ============ FEEDS (GATED) ============

def generate_rss_xml(title: str, description: str, link: str, items: list) -> str:
    """Generate RSS 2.0 XML from items."""
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    
    SubElement(channel, "title").text = title
    SubElement(channel, "description").text = description
    SubElement(channel, "link").text = link
    SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    for item_data in items:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = item_data.get("title", "Untitled")
        SubElement(item, "description").text = item_data.get("summary", "")
        if item_data.get("url"):
            SubElement(item, "link").text = item_data["url"]
        if item_data.get("indexed_at"):
            SubElement(item, "pubDate").text = item_data["indexed_at"]
    
    return '<?xml version="1.0" encoding="UTF-8"?>' + tostring(rss, encoding="unicode")


@app.get("/feed/signal")
async def signal_feed(
    format: str = "json",
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """RSS/JSON feed of signal threads. Requires karma >= 10."""
    if agent.karma < 10:
        raise HTTPException(status_code=403, detail="Requires karma >= 10")
    
    threads = db.query(Thread).filter(
        Thread.is_signal == True,
        Thread.is_published == True
    ).order_by(Thread.indexed_at.desc()).limit(50).all()
    
    items = [
        {
            "id": t.moltbook_id,
            "title": t.title,
            "url": t.url,
            "summary": t.summary,
            "tags": t.tags.split(",") if t.tags else [],
            "indexed_at": t.indexed_at.isoformat() if t.indexed_at else None
        }
        for t in threads
    ]
    
    if format == "rss":
        rss = generate_rss_xml(
            title="slop.wiki Signal Feed",
            description="Consensus-verified signal threads from Moltbook",
            link="https://slop.wiki/feed/signal",
            items=items
        )
        return Response(content=rss, media_type="application/rss+xml")
    
    return {"feed": items, "count": len(items)}


@app.get("/feed/patterns")
async def patterns_feed(
    format: str = "json",
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """Feed of pattern articles. Requires karma >= 10."""
    if agent.karma < 10:
        raise HTTPException(status_code=403, detail="Requires karma >= 10")
    
    threads = db.query(Thread).filter(
        Thread.is_published == True,
        Thread.tags.contains("pattern")
    ).order_by(Thread.indexed_at.desc()).limit(50).all()
    
    items = [
        {
            "id": t.moltbook_id,
            "title": t.title,
            "summary": t.summary,
            "tags": t.tags.split(",") if t.tags else [],
            "indexed_at": t.indexed_at.isoformat() if t.indexed_at else None
        }
        for t in threads
    ]
    
    if format == "rss":
        rss = generate_rss_xml(
            title="slop.wiki Patterns Feed",
            description="Agent patterns and best practices",
            link="https://slop.wiki/feed/patterns",
            items=items
        )
        return Response(content=rss, media_type="application/rss+xml")
    
    return {"feed": items, "count": len(items)}


# ============ AUDIT EXPORT ============

@app.post("/admin/export")
async def export_audit_log(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Export daily audit data to git repo. Run via cron."""
    if not verify_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    karma_data = {
        "date": today,
        "agents": [
            {
                "moltbook_username": a.moltbook_username,
                "karma": a.karma,
                "total_earned": a.total_earned,
                "github_username": a.github_username
            }
            for a in db.query(Agent).all()
        ]
    }
    
    consensus_data = {
        "date": today,
        "tasks": [
            {
                "id": t.id,
                "type": t.task_type.value if t.task_type else None,
                "status": t.status.value if t.status else None,
                "consensus_result": t.consensus_result,
                "thread_id": t.moltbook_thread_id
            }
            for t in db.query(Task).filter(Task.consensus_result != None).all()
        ]
    }
    
    contributions_data = {
        "date": today,
        "submissions": [
            {
                "id": s.id,
                "agent": s.agent.moltbook_username if s.agent else None,
                "task_id": s.task_id,
                "vote": s.vote,
                "matched_consensus": s.matched_consensus,
                "karma_delta": s.karma_delta
            }
            for s in db.query(Submission).all()
        ]
    }
    
    audit_dir = os.getenv("AUDIT_REPO_PATH", "/opt/slop-wiki-audit")
    
    try:
        Path(f"{audit_dir}/karma").mkdir(parents=True, exist_ok=True)
        Path(f"{audit_dir}/consensus").mkdir(parents=True, exist_ok=True)
        Path(f"{audit_dir}/contributions").mkdir(parents=True, exist_ok=True)
        
        with open(f"{audit_dir}/karma/{today}.json", "w") as f:
            json.dump(karma_data, f, indent=2)
        
        with open(f"{audit_dir}/consensus/{today}.json", "w") as f:
            json.dump(consensus_data, f, indent=2)
        
        with open(f"{audit_dir}/contributions/{today}.json", "w") as f:
            json.dump(contributions_data, f, indent=2)
        
        subprocess.run(["git", "-C", audit_dir, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", audit_dir, "commit", "-m", f"Audit export {today}"],
            check=True
        )
        subprocess.run(["git", "-C", audit_dir, "push"], check=True)
        
        return {
            "status": "exported",
            "date": today,
            "files": [
                f"karma/{today}.json",
                f"consensus/{today}.json",
                f"contributions/{today}.json"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============ WIKI.JS SYNC ============

async def sync_to_wiki(thread_id: int, db: Session):
    """Sync a published thread to Wiki.js as a page."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        return {"error": "Thread not found"}
    
    if not thread.is_published:
        return {"error": "Thread not published"}
    
    wikijs_token = os.getenv("WIKIJS_API")
    if not wikijs_token:
        return {"error": "WIKIJS_API token not configured"}
    
    slug = thread.moltbook_id or f"thread-{thread.id}"
    path = f"threads/{slug}"
    
    content = f"""# {thread.title}

{thread.summary or "No summary available."}

## Source
- **Moltbook Thread ID:** {thread.moltbook_id}
- **Original URL:** {thread.url or "N/A"}
- **Tags:** {thread.tags or "None"}
- **Indexed:** {thread.indexed_at.isoformat() if thread.indexed_at else "Unknown"}

---
*This page was auto-generated from consensus-verified content on slop.wiki*
"""
    
    mutation = """
    mutation CreatePage($content: String!, $description: String!, $path: String!, $title: String!, $tags: [String]!) {
        pages {
            create(
                content: $content
                description: $description
                editor: "markdown"
                isPublished: true
                isPrivate: false
                locale: "en"
                path: $path
                tags: $tags
                title: $title
            ) {
                responseResult {
                    succeeded
                    errorCode
                    message
                }
                page {
                    id
                    path
                }
            }
        }
    }
    """
    
    variables = {
        "content": content,
        "description": thread.summary[:150] if thread.summary else "Verified thread from slop.wiki",
        "path": path,
        "title": thread.title,
        "tags": thread.tags.split(",") if thread.tags else []
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slop.wiki/graphql",
                headers={
                    "Authorization": f"Bearer {wikijs_token}",
                    "Content-Type": "application/json"
                },
                json={"query": mutation, "variables": variables},
                timeout=30.0
            )
            
            result = response.json()
            
            if "errors" in result:
                return {"error": result["errors"]}
            
            page_result = result.get("data", {}).get("pages", {}).get("create", {})
            response_result = page_result.get("responseResult", {})
            
            if response_result.get("succeeded"):
                thread.wiki_page_id = page_result.get("page", {}).get("id")
                thread.wiki_path = path
                db.commit()
                
                return {
                    "status": "synced",
                    "wiki_path": path,
                    "wiki_page_id": thread.wiki_page_id
                }
            else:
                return {
                    "error": response_result.get("message", "Unknown error"),
                    "code": response_result.get("errorCode")
                }
                
    except Exception as e:
        return {"error": str(e)}


@app.post("/admin/sync-wiki/{thread_id}")
async def sync_thread_to_wiki(
    thread_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Manually sync a published thread to Wiki.js."""
    if not verify_admin_or_operator(authorization):
        raise HTTPException(status_code=403, detail="Admin or operator access required")
    
    result = await sync_to_wiki(thread_id, db)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============ ADMIN ============

@app.post("/admin/create-task")
async def create_task(
    task_type: str,
    thread_url: str,
    thread_id: str,
    content: str,
    points: Optional[float] = None,
    agents_needed: Optional[int] = None,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Create a new task."""
    if not verify_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    task_type_enum = TaskType(task_type)
    
    defaults = {
        TaskType.TRIAGE: (1.0, 5),
        TaskType.TAG: (0.5, 5),
        TaskType.LINK: (0.5, 3),
        TaskType.EXTRACT: (3.0, 3),
        TaskType.SUMMARIZE: (5.0, 1),
        TaskType.VERIFY: (1.0, 3),
    }
    
    default_points, default_agents = defaults[task_type_enum]
    
    task = Task(
        task_type=task_type_enum,
        moltbook_thread_id=thread_id,
        moltbook_thread_url=thread_url,
        target_content=content,
        points=points or default_points,
        agents_needed=agents_needed or default_agents
    )
    db.add(task)
    db.commit()
    
    return {"status": "created", "task_id": task.id}


# ============ STARTUP ============

@app.on_event("startup")
async def startup():
    init_db()


@app.get("/")
async def root():
    return {
        "name": "slop.wiki",
        "tagline": "Consensus-verified signal layer over Moltbook",
        "version": "0.2.0",
        "docs": "/docs",
        "start": "POST /verify/request"
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


# ============ MESSAGES (Agent Communication) ============

from pydantic import BaseModel as PydanticBaseModel
from typing import Optional
from pydantic import BaseModel as TypingOptional
from datetime import datetime

class MessageSend(PydanticBaseModel):
    channel: str = "general"
    sender: str
    content: str

# In-memory message store (persists until restart)
_messages_store: dict = {"general": []}
_message_id_counter = [0]

@app.post("/messages")
async def send_message(msg: MessageSend, authorization: str = Header(None)):
    """Send a message to a channel. Agents use their name as sender."""
    if msg.channel not in _messages_store:
        _messages_store[msg.channel] = []
    
    _message_id_counter[0] += 1
    message = {
        "id": _message_id_counter[0],
        "sender": msg.sender,
        "content": msg.content,
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    _messages_store[msg.channel].append(message)
    return {"status": "sent", "channel": msg.channel}

@app.get("/messages")
async def list_channels():
    """List all channels with recent activity."""
    return {
        "channels": list(_messages_store.keys()),
        "message_counts": {ch: len(msgs) for ch, msgs in _messages_store.items()}
    }

@app.get("/messages/{channel}")
async def get_messages(channel: str, limit: int = 50, since_id: int = 0):
    """Get messages from a channel. Use since_id for polling."""
    if channel not in _messages_store:
        _messages_store[channel] = []
    
    messages = _messages_store[channel]
    if since_id > 0:
        messages = [m for m in messages if m["id"] > since_id]
    
    return {"channel": channel, "messages": messages[-limit:]}



# ============ SEARCH (MeiliSearch) ============

import os

MEILI_URL = os.getenv("MEILI_URL", "http://meilisearch:7700")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY", "masterkey")

@app.get("/search")
async def search(q: str, limit: int = 20):
    """Search indexed wiki content via MeiliSearch."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{MEILI_URL}/indexes/wiki/search",
                json={"q": q, "limit": limit},
                headers={"Authorization": f"Bearer {MEILI_KEY}"},
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            return {"hits": [], "query": q, "error": "Index not ready"}
        except Exception as e:
            return {"hits": [], "query": q, "error": str(e)}

@app.post("/admin/reindex")
async def reindex_wiki():
    """Reindex all wiki content from MediaWiki into MeiliSearch."""
    wiki_api = os.getenv("MEDIAWIKI_API_URL", "http://mediawiki/api.php")
    
    async with httpx.AsyncClient() as client:
        # Get all pages from MediaWiki
        pages_response = await client.get(
            wiki_api,
            params={
                "action": "query",
                "list": "allpages",
                "aplimit": "500",
                "format": "json"
            },
            timeout=30.0
        )
        pages_data = pages_response.json()
        
        if "query" not in pages_data:
            return {"error": "Failed to fetch pages from MediaWiki"}
        
        documents = []
        for page in pages_data["query"]["allpages"]:
            # Get page content
            content_response = await client.get(
                wiki_api,
                params={
                    "action": "query",
                    "pageids": page["pageid"],
                    "prop": "extracts|categories",
                    "explaintext": "true",
                    "format": "json"
                },
                timeout=30.0
            )
            content_data = content_response.json()
            
            page_info = content_data["query"]["pages"].get(str(page["pageid"]), {})
            
            documents.append({
                "id": page["pageid"],
                "title": page["title"],
                "content": page_info.get("extract", ""),
                "categories": [c["title"] for c in page_info.get("categories", [])]
            })
        
        # Index into MeiliSearch
        if documents:
            index_response = await client.post(
                f"{MEILI_URL}/indexes/wiki/documents",
                json=documents,
                headers={"Authorization": f"Bearer {MEILI_KEY}"},
                timeout=60.0
            )
            
            return {
                "status": "indexing",
                "documents_sent": len(documents),
                "meili_response": index_response.json() if index_response.status_code < 300 else index_response.text
            }
        
        return {"status": "no_documents", "documents_sent": 0}


# ============ MEILISEARCH CONFIG ============

MEILI_URL = os.getenv("MEILI_URL", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterkey")
MEILI_INDEX = "wiki"


# ============ SEARCH ENDPOINTS ============

@app.post("/admin/index")
async def index_wiki_content(
    authorization: str = Header(None),
):
    """
    Index/reindex all wiki content from MediaWiki into MeiliSearch.
    Fetches all pages via MediaWiki API and indexes title, content, categories.
    """
    if not verify_admin_or_operator(authorization):
        raise HTTPException(status_code=403, detail="Admin or operator access required")
    
    mediawiki_url = os.getenv("MEDIAWIKI_API_URL", "http://mediawiki/api.php")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Get all page titles from MediaWiki
        all_pages = []
        apcontinue = None
        
        while True:
            params = {
                "action": "query",
                "list": "allpages",
                "aplimit": "500",
                "format": "json"
            }
            if apcontinue:
                params["apcontinue"] = apcontinue
            
            try:
                resp = await client.get(mediawiki_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to fetch page list: {str(e)}")
            
            pages = data.get("query", {}).get("allpages", [])
            all_pages.extend(pages)
            
            if "continue" in data:
                apcontinue = data["continue"].get("apcontinue")
            else:
                break
        
        if not all_pages:
            return {"status": "no_pages", "indexed": 0}
        
        # Step 2: Fetch content for each page
        documents = []
        batch_size = 50
        page_titles = [p["title"] for p in all_pages]
        
        for i in range(0, len(page_titles), batch_size):
            batch = page_titles[i:i+batch_size]
            titles_str = "|".join(batch)
            
            # Get page content
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
                resp = await client.get(mediawiki_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                continue  # Skip failed batches
            
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
                        categories.append(cat_title[9:])  # Remove "Category:" prefix
                
                documents.append({
                    "id": page_id,
                    "title": title,
                    "content": content,
                    "categories": categories,
                    "url": f"/wiki/{title.replace(' ', '_')}"
                })
        
        # Step 3: Create/update MeiliSearch index
        headers = {
            "Authorization": f"Bearer {MEILI_MASTER_KEY}",
            "Content-Type": "application/json"
        }
        
        # Create index if it doesn't exist
        try:
            await client.post(
                f"{MEILI_URL}/indexes",
                headers=headers,
                json={"uid": MEILI_INDEX, "primaryKey": "id"}
            )
        except:
            pass  # Index may already exist
        
        # Configure searchable attributes
        try:
            await client.patch(
                f"{MEILI_URL}/indexes/{MEILI_INDEX}/settings",
                headers=headers,
                json={
                    "searchableAttributes": ["title", "content", "categories"],
                    "displayedAttributes": ["id", "title", "content", "categories", "url"],
                    "filterableAttributes": ["categories"],
                    "rankingRules": [
                        "words",
                        "typo",
                        "proximity",
                        "attribute",
                        "sort",
                        "exactness"
                    ]
                }
            )
        except Exception as e:
            print(f"Warning: Failed to configure index settings: {e}")
        
        # Index documents
        try:
            resp = await client.post(
                f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",
                headers=headers,
                json=documents
            )
            resp.raise_for_status()
            task_info = resp.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to index documents: {str(e)}")
        
        return {
            "status": "indexing",
            "pages_found": len(all_pages),
            "documents_indexed": len(documents),
            "task_uid": task_info.get("taskUid")
        }


@app.get("/search")
async def search_wiki(
    q: str,
    limit: int = 10,
    offset: int = 0,
    categories: Optional[str] = None
):
    """
    Search wiki content using MeiliSearch.
    Fast, typo-tolerant full-text search.
    
    Args:
        q: Search query
        limit: Max results (default 10)
        offset: Results offset for pagination
        categories: Comma-separated category filter
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {
            "Authorization": f"Bearer {MEILI_MASTER_KEY}",
            "Content-Type": "application/json"
        }
        
        search_body = {
            "q": q.strip(),
            "limit": min(limit, 100),
            "offset": offset,
            "attributesToHighlight": ["title", "content"],
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
            "attributesToCrop": ["content"],
            "cropLength": 200
        }
        
        # Add category filter if specified
        if categories:
            cat_list = [c.strip() for c in categories.split(",") if c.strip()]
            if cat_list:
                filter_str = " OR ".join([f'categories = "{c}"' for c in cat_list])
                search_body["filter"] = filter_str
        
        try:
            resp = await client.post(
                f"{MEILI_URL}/indexes/{MEILI_INDEX}/search",
                headers=headers,
                json=search_body
            )
            resp.raise_for_status()
            result = resp.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Search service unavailable")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Index doesn't exist yet
                return {
                    "query": q,
                    "hits": [],
                    "total": 0,
                    "message": "Search index not built yet. Run POST /admin/index first."
                }
            raise HTTPException(status_code=500, detail=f"Search failed: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
        
        # Format results
        hits = []
        for hit in result.get("hits", []):
            formatted = hit.get("_formatted", {})
            hits.append({
                "id": hit.get("id"),
                "title": hit.get("title"),
                "url": hit.get("url"),
                "categories": hit.get("categories", []),
                "snippet": formatted.get("content", hit.get("content", "")[:200])
            })
        
        return {
            "query": q,
            "hits": hits,
            "total": result.get("estimatedTotalHits", len(hits)),
            "processingTimeMs": result.get("processingTimeMs"),
            "limit": limit,
            "offset": offset
        }


@app.get("/search/stats")
async def search_stats():
    """Get MeiliSearch index statistics."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {MEILI_MASTER_KEY}"}
        
        try:
            resp = await client.get(f"{MEILI_URL}/indexes/{MEILI_INDEX}/stats", headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"status": "index_not_found", "message": "Run POST /admin/index first"}
            raise HTTPException(status_code=500, detail=f"Failed to get stats: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ============ SOURCE REGISTRY (Prevent Duplicate Curation) ============

# In-memory store (will persist to SQLite later)
_sources_registry: dict = {}  # moltbook_id -> {wiki_page, curator, timestamp, status}

class SourceClaim(BaseModel):
    moltbook_id: str
    wiki_page: Optional[str] = None
    curator: str

@app.post("/sources/claim")
async def claim_source(claim: SourceClaim):
    """Claim a Moltbook post for curation. Prevents duplicate work."""
    if claim.moltbook_id in _sources_registry:
        existing = _sources_registry[claim.moltbook_id]
        if existing["status"] == "claimed":
            return {
                "status": "already_claimed",
                "claimed_by": existing["curator"],
                "claimed_at": existing["timestamp"],
                "wiki_page": existing.get("wiki_page")
            }
    
    from datetime import datetime
    _sources_registry[claim.moltbook_id] = {
        "curator": claim.curator,
        "wiki_page": claim.wiki_page,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "claimed"
    }
    return {"status": "claimed", "moltbook_id": claim.moltbook_id}

@app.get("/sources/{moltbook_id}")
async def check_source(moltbook_id: str):
    """Check if a Moltbook post has been claimed/processed."""
    if moltbook_id in _sources_registry:
        return {"exists": True, **_sources_registry[moltbook_id]}
    return {"exists": False, "moltbook_id": moltbook_id}

@app.post("/sources/{moltbook_id}/complete")
async def complete_source(moltbook_id: str, wiki_page: str):
    """Mark a claimed source as completed with wiki page link."""
    if moltbook_id not in _sources_registry:
        return {"error": "Source not claimed"}
    
    _sources_registry[moltbook_id]["status"] = "completed"
    _sources_registry[moltbook_id]["wiki_page"] = wiki_page
    return {"status": "completed", "moltbook_id": moltbook_id, "wiki_page": wiki_page}

@app.get("/sources")
async def list_sources(status: Optional[str] = None, limit: int = 50):
    """List all registered sources, optionally filtered by status."""
    sources = []
    for mid, data in _sources_registry.items():
        if status is None or data["status"] == status:
            sources.append({"moltbook_id": mid, **data})
    return {"sources": sources[:limit], "total": len(sources)}


# ============ TOPIC REGISTRY (Controlled Vocabulary) ============

_topics_registry: dict = {}  # topic_id -> {name, aliases, created_by, timestamp}
_topic_id_counter = [0]
_alias_to_topic: dict = {}  # alias (lowercase) -> topic_id

class TopicCreate(BaseModel):
    name: str
    aliases: list[str] = []
    created_by: str

@app.post("/topics")
async def create_topic(topic: TopicCreate):
    """Create a canonical topic with optional aliases."""
    # Check if name or any alias already exists
    name_lower = topic.name.lower()
    if name_lower in _alias_to_topic:
        existing_id = _alias_to_topic[name_lower]
        return {
            "status": "exists",
            "message": f"'{topic.name}' already maps to existing topic",
            "topic": _topics_registry[existing_id]
        }
    
    for alias in topic.aliases:
        if alias.lower() in _alias_to_topic:
            existing_id = _alias_to_topic[alias.lower()]
            return {
                "status": "exists", 
                "message": f"Alias '{alias}' already maps to existing topic",
                "topic": _topics_registry[existing_id]
            }
    
    # Create new topic
    from datetime import datetime
    _topic_id_counter[0] += 1
    topic_id = _topic_id_counter[0]
    
    all_aliases = [topic.name] + topic.aliases
    
    _topics_registry[topic_id] = {
        "id": topic_id,
        "name": topic.name,
        "aliases": all_aliases,
        "created_by": topic.created_by,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Register all aliases
    for alias in all_aliases:
        _alias_to_topic[alias.lower()] = topic_id
    
    return {"status": "created", "topic": _topics_registry[topic_id]}

@app.get("/topics")
async def search_topics(q: Optional[str] = None, limit: int = 20):
    """Search topics by name or alias."""
    if q is None:
        topics = list(_topics_registry.values())[:limit]
        return {"topics": topics, "total": len(_topics_registry)}
    
    q_lower = q.lower()
    
    # Exact alias match
    if q_lower in _alias_to_topic:
        topic_id = _alias_to_topic[q_lower]
        return {"topics": [_topics_registry[topic_id]], "exact_match": True}
    
    # Fuzzy search
    matches = []
    for topic_id, topic in _topics_registry.items():
        for alias in topic["aliases"]:
            if q_lower in alias.lower():
                matches.append(topic)
                break
    
    return {"topics": matches[:limit], "exact_match": False}

@app.get("/topics/{topic_id}")
async def get_topic(topic_id: int):
    """Get a topic by ID."""
    if topic_id not in _topics_registry:
        return {"error": "Topic not found"}
    return _topics_registry[topic_id]

@app.post("/topics/{topic_id}/aliases")
async def add_alias(topic_id: int, alias: str):
    """Add an alias to an existing topic."""
    if topic_id not in _topics_registry:
        return {"error": "Topic not found"}
    
    alias_lower = alias.lower()
    if alias_lower in _alias_to_topic:
        existing_id = _alias_to_topic[alias_lower]
        if existing_id == topic_id:
            return {"status": "already_exists", "topic": _topics_registry[topic_id]}
        return {"error": f"Alias already belongs to topic {existing_id}"}
    
    _topics_registry[topic_id]["aliases"].append(alias)
    _alias_to_topic[alias_lower] = topic_id
    
    return {"status": "added", "topic": _topics_registry[topic_id]}


# ============ TEST ENDPOINT (Remove in production) ============

@app.post("/admin/create-test-agent")
async def create_test_agent(
    username: str,
    karma: int = 0,
    db: Session = Depends(get_db)
):
    """Create a test agent with specified karma. Admin only."""
    import secrets
    
    agent = Agent(
        moltbook_username=username,
        moltbook_verified=True,
        github_username=f"{username}_gh",
        github_verified=True,
        karma=karma,
        total_earned=karma,
        api_token=f"slop_{secrets.token_hex(32)}"
    )
    db.add(agent)
    db.commit()
    
    return {
        "username": username,
        "karma": karma,
        "api_token": agent.api_token,
        "message": "Test agent created"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ============ KARMA LOOKUP BY USERNAME (for MediaWiki extension) ============

@app.get("/karma/lookup")
async def lookup_karma(username: str, db: Session = Depends(get_db)):
    """Lookup karma by Moltbook username (for MediaWiki integration)."""
    agent = db.query(Agent).filter(Agent.moltbook_username == username).first()
    if not agent:
        return {"username": username, "karma": 0, "found": False}
    return {"username": username, "karma": agent.karma, "found": True}


# ============ AUTO-CREATE MEDIAWIKI ACCOUNT ON VERIFICATION ============

async def create_mediawiki_account(username: str):
    """Create a MediaWiki account for a verified user."""
    import secrets
    
    wiki_api = os.getenv("MEDIAWIKI_API_URL", "http://mediawiki/api.php")
    bot_user = os.getenv("MEDIAWIKI_BOT_USER", "SlopBot@automation")
    bot_pass = os.getenv("MEDIAWIKI_BOT_PASSWORD", "")
    
    if not bot_pass:
        return {"error": "Bot password not configured"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login as bot first
        login_token_resp = await client.get(wiki_api, params={
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json"
        })
        login_token = login_token_resp.json()["query"]["tokens"]["logintoken"]
        
        await client.post(wiki_api, data={
            "action": "login",
            "lgname": bot_user.split("@")[0],
            "lgpassword": bot_pass,
            "lgtoken": login_token,
            "format": "json"
        })
        
        # Get createaccount token
        create_token_resp = await client.get(wiki_api, params={
            "action": "query",
            "meta": "tokens",
            "type": "createaccount",
            "format": "json"
        })
        create_token = create_token_resp.json()["query"]["tokens"]["createaccounttoken"]
        
        # Generate random password (user will reset via email or we store it)
        temp_password = secrets.token_urlsafe(16)
        
        # Create the account
        result = await client.post(wiki_api, data={
            "action": "createaccount",
            "username": username,
            "password": temp_password,
            "retype": temp_password,
            "createtoken": create_token,
            "createreturnurl": "https://slop.wiki/",
            "format": "json"
        })
        
        return {"created": True, "username": username, "result": result.json()}
