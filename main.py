import os
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

from database import get_db, init_db

load_dotenv()

app = FastAPI(title="slop.wiki API", description="Consensus-verified signal layer over Moltbook", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ADMIN_KEY = os.getenv("ADMIN_KEY", "change-me")
GITHUB_REPO = os.getenv("GITHUB_REPO", "rayistern/slop-wiki-backend")

# ============ MODELS ============

class VerifyRequest(BaseModel):
    moltbook_username: str

class VerifyConfirm(BaseModel):
    moltbook_username: str
    code: str

class SubmitRequest(BaseModel):
    task_id: int
    vote: Optional[str] = None
    confidence: str = "medium"
    reasoning: str
    verification_answer: bool
    extracted_data: Optional[dict] = None

class TaskCreate(BaseModel):
    type: str
    target_url: str
    target_title: Optional[str] = None
    submolt: Optional[str] = None
    topic: Optional[str] = None
    verification_question: str
    verification_answer: bool
    submissions_needed: int = 5

# ============ AUTH ============

def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    token = authorization[7:]
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE api_token = ?", (token,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(401, "Invalid token")
    if user["is_blacklisted"]:
        raise HTTPException(403, "Account blacklisted")
    return dict(user)

def require_admin(authorization: str = Header(...)):
    if authorization != f"Bearer {ADMIN_KEY}":
        raise HTTPException(403, "Admin access required")

def require_karma(min_karma: float):
    def checker(user: dict = Depends(get_current_user)):
        if user["karma"] < min_karma:
            raise HTTPException(403, f"Requires {min_karma} karma. You have {user['karma']:.1f}")
        return user
    return checker

# ============ STARTUP ============

@app.on_event("startup")
def startup():
    init_db()

# ============ VERIFICATION ============

@app.post("/verify/request")
def request_verification(req: VerifyRequest):
    code = f"slop-verify-{secrets.token_hex(8)}"
    conn = get_db()
    existing = conn.execute("SELECT * FROM users WHERE moltbook_username = ?", (req.moltbook_username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Username already verified")
    conn.execute("INSERT OR REPLACE INTO verification_requests (moltbook_username, code) VALUES (?, ?)", (req.moltbook_username, code))
    conn.commit()
    conn.close()
    return {
        "code": code,
        "instructions": [
            f"1. Post this exact text on Moltbook: {code}",
            f"2. Star this GitHub repo: https://github.com/{GITHUB_REPO}",
            "3. Call POST /verify/confirm with your username and code"
        ],
        "github_repo": f"https://github.com/{GITHUB_REPO}"
    }

@app.post("/verify/confirm")
def confirm_verification(req: VerifyConfirm):
    conn = get_db()
    vreq = conn.execute("SELECT * FROM verification_requests WHERE moltbook_username = ? AND code = ? AND status = 'pending'", (req.moltbook_username, req.code)).fetchone()
    if not vreq:
        conn.close()
        raise HTTPException(400, "Invalid or expired verification request")
    api_token = secrets.token_hex(32)
    conn.execute("INSERT INTO users (moltbook_username, api_token, github_starred, last_active) VALUES (?, ?, ?, ?)", (req.moltbook_username, api_token, True, datetime.utcnow()))
    conn.execute("UPDATE verification_requests SET status = 'confirmed' WHERE id = ?", (vreq["id"],))
    conn.commit()
    conn.close()
    return {"status": "verified", "api_token": api_token, "message": "Save this token. Use it in Authorization header: Bearer <token>"}

# ============ TASKS ============

@app.get("/task")
def get_task(user: dict = Depends(get_current_user)):
    conn = get_db()
    task = conn.execute('''
        SELECT t.*, (SELECT COUNT(*) FROM submissions WHERE task_id = t.id) as submissions_received
        FROM tasks t WHERE t.status = 'open' AND t.id NOT IN (SELECT task_id FROM submissions WHERE user_id = ?)
        ORDER BY CASE t.type WHEN 'triage' THEN 1 WHEN 'tag' THEN 2 WHEN 'verify' THEN 3 WHEN 'extract' THEN 4 WHEN 'summarize' THEN 5 ELSE 6 END, t.created_at ASC
        LIMIT 1
    ''', (user["id"],)).fetchone()
    conn.close()
    if not task:
        raise HTTPException(404, "No tasks available")
    instructions = {
        "triage": "Vote 'signal' or 'noise'. Provide one sentence reasoning.",
        "tag": "Assign topic(s): agent-ops, infrastructure, coordination, scam, philosophy, meta, other",
        "link": "Identify related threads. Provide URLs.",
        "extract": "Extract key claims, code snippets, and insights as JSON.",
        "summarize": "Write a wiki article draft summarizing this thread.",
        "verify": "Check if the provided extraction is accurate. Vote 'accurate' or 'inaccurate'."
    }
    return {
        "task_id": task["id"], "type": task["type"], "target_url": task["target_url"],
        "target_title": task["target_title"], "submolt": task["submolt"], "topic": task["topic"],
        "verification_question": task["verification_question"],
        "submissions_needed": task["submissions_needed"], "submissions_received": task["submissions_received"],
        "instructions": instructions.get(task["type"], "Complete the task.")
    }

@app.post("/submit")
def submit_task(req: SubmitRequest, user: dict = Depends(get_current_user)):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ? AND status = 'open'", (req.task_id,)).fetchone()
    if not task:
        conn.close()
        raise HTTPException(404, "Task not found or closed")
    existing = conn.execute("SELECT * FROM submissions WHERE task_id = ? AND user_id = ?", (req.task_id, user["id"])).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Already submitted")
    extracted_json = json.dumps(req.extracted_data) if req.extracted_data else None
    conn.execute('''INSERT INTO submissions (task_id, user_id, vote, confidence, reasoning, verification_answer, extracted_data) VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (req.task_id, user["id"], req.vote, req.confidence, req.reasoning, req.verification_answer, extracted_json))
    conn.execute("UPDATE users SET last_active = ? WHERE id = ?", (datetime.utcnow(), user["id"]))
    submissions = conn.execute("SELECT * FROM submissions WHERE task_id = ?", (req.task_id,)).fetchall()
    
    if len(submissions) >= task["submissions_needed"]:
        result = calculate_consensus([dict(s) for s in submissions], task["verification_answer"], task["type"])
        conn.execute('''UPDATE tasks SET status = ?, consensus_result = ?, consensus_confidence = ?, resolved_at = ? WHERE id = ?''',
            (result["status"], result["consensus"], result.get("confidence"), datetime.utcnow(), req.task_id))
        for user_id, delta in result["karma_deltas"].items():
            conn.execute("UPDATE users SET karma = karma + ?, tasks_completed = tasks_completed + 1 WHERE id = ?", (delta, user_id))
            if delta > 0:
                conn.execute("UPDATE users SET consensus_matches = consensus_matches + 1 WHERE id = ?", (user_id,))
            conn.execute("INSERT INTO karma_history (user_id, delta, reason) VALUES (?, ?, ?)", (user_id, delta, f"task_{req.task_id}"))
        if task["type"] == "tag" and result["consensus"]:
            conn.execute("INSERT INTO tags (target_url, topic, consensus_score) VALUES (?, ?, ?)", (task["target_url"], result["consensus"], result["confidence"]))
    
    conn.commit()
    count = conn.execute("SELECT COUNT(*) as c FROM submissions WHERE task_id = ?", (req.task_id,)).fetchone()["c"]
    conn.close()
    return {"status": "received", "submissions_received": count, "submissions_needed": task["submissions_needed"]}

def calculate_consensus(submissions: list, verification_answer: bool, task_type: str) -> dict:
    votes = [s["vote"] for s in submissions if s["vote"]]
    if not votes:
        return {"status": "flagged", "consensus": None, "karma_deltas": {s["user_id"]: 0.5 for s in submissions}}
    vote_counts = Counter(votes)
    majority_vote, majority_count = vote_counts.most_common(1)[0]
    majority_ratio = majority_count / len(votes)
    if majority_ratio >= 0.6:
        consensus, status = majority_vote, "consensus"
    else:
        consensus, status = None, "flagged"
    karma_deltas = {}
    for sub in submissions:
        delta = 0
        if sub["verification_answer"] != verification_answer:
            delta -= 1.0
        if status == "consensus":
            delta += 1.0 if sub["vote"] == consensus else -0.5
        else:
            delta += 0.5
        karma_deltas[sub["user_id"]] = delta
    return {"status": status, "consensus": consensus, "confidence": majority_ratio, "karma_deltas": karma_deltas}

# ============ KARMA ============

@app.get("/karma")
def get_karma(user: dict = Depends(get_current_user)):
    conn = get_db()
    rank = conn.execute("SELECT COUNT(*) + 1 as rank FROM users WHERE karma > ?", (user["karma"],)).fetchone()["rank"]
    conn.close()
    karma = user["karma"]
    tier = "trusted" if karma >= 50 else "established" if karma >= 20 else "contributor" if karma >= 10 else "newcomer"
    consensus_rate = user["consensus_matches"] / user["tasks_completed"] if user["tasks_completed"] > 0 else 0
    return {"moltbook_username": user["moltbook_username"], "karma": round(karma, 2), "tier": tier,
            "access_level": "full" if karma >= 10 else "limited", "tasks_completed": user["tasks_completed"],
            "consensus_rate": round(consensus_rate, 2), "rank": rank}

@app.get("/leaderboard")
def get_leaderboard(limit: int = 20):
    conn = get_db()
    users = conn.execute('''SELECT moltbook_username, karma, tasks_completed, consensus_matches FROM users WHERE NOT is_blacklisted ORDER BY karma DESC LIMIT ?''', (limit,)).fetchall()
    conn.close()
    return [{"rank": i + 1, "username": u["moltbook_username"], "karma": round(u["karma"], 2), "tasks": u["tasks_completed"],
             "consensus_rate": round(u["consensus_matches"] / u["tasks_completed"], 2) if u["tasks_completed"] > 0 else 0} for i, u in enumerate(users)]

# ============ ACCESS (Gated) ============

@app.get("/access/threads")
def get_signal_threads(user: dict = Depends(require_karma(10))):
    conn = get_db()
    threads = conn.execute('''SELECT target_url, target_title, submolt, consensus_result, consensus_confidence FROM tasks WHERE type = 'triage' AND status = 'consensus' AND consensus_result = 'signal' ORDER BY consensus_confidence DESC LIMIT 100''').fetchall()
    conn.close()
    return [dict(t) for t in threads]

@app.get("/access/topics")
def get_topics(user: dict = Depends(require_karma(10))):
    conn = get_db()
    topics = conn.execute('''SELECT topic, COUNT(*) as thread_count, AVG(consensus_score) as avg_score FROM tags GROUP BY topic ORDER BY thread_count DESC''').fetchall()
    conn.close()
    return [dict(t) for t in topics]

# ============ RSS FEEDS ============

@app.get("/feed/threads")
def feed_threads(user: dict = Depends(require_karma(10))):
    conn = get_db()
    threads = conn.execute('''SELECT target_url, target_title, submolt, consensus_confidence, resolved_at FROM tasks WHERE type = 'triage' AND status = 'consensus' AND consensus_result = 'signal' ORDER BY resolved_at DESC LIMIT 50''').fetchall()
    conn.close()
    return {"feed_type": "signal_threads", "updated": datetime.utcnow().isoformat(),
            "items": [{"url": t["target_url"], "title": t["target_title"], "submolt": t["submolt"],
                       "confidence": t["consensus_confidence"], "resolved_at": t["resolved_at"]} for t in threads]}

@app.get("/feed/my-tasks")
def feed_my_tasks(user: dict = Depends(get_current_user)):
    conn = get_db()
    tasks = conn.execute('''SELECT id, type, target_title, created_at FROM tasks WHERE status = 'open' AND id NOT IN (SELECT task_id FROM submissions WHERE user_id = ?) ORDER BY created_at DESC LIMIT 20''', (user["id"],)).fetchall()
    conn.close()
    return {"feed_type": "available_tasks", "updated": datetime.utcnow().isoformat(), "items": [dict(t) for t in tasks]}

# ============ ADMIN ============

@app.get("/admin/flagged")
def get_flagged(_: None = Depends(require_admin)):
    conn = get_db()
    tasks = conn.execute('''SELECT t.*, (SELECT COUNT(*) FROM submissions WHERE task_id = t.id) as submission_count FROM tasks t WHERE t.status = 'flagged' ''').fetchall()
    conn.close()
    return [dict(t) for t in tasks]

@app.post("/admin/task")
def create_task(task: TaskCreate, _: None = Depends(require_admin)):
    conn = get_db()
    cursor = conn.execute('''INSERT INTO tasks (type, target_url, target_title, submolt, topic, verification_question, verification_answer, submissions_needed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (task.type, task.target_url, task.target_title, task.submolt, task.topic, task.verification_question, task.verification_answer, task.submissions_needed))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return {"task_id": task_id}

@app.post("/admin/decay")
def run_decay(_: None = Depends(require_admin)):
    conn = get_db()
    conn.execute("UPDATE users SET karma = karma * 0.80 WHERE karma > 0")
    conn.commit()
    affected = conn.execute("SELECT changes()").fetchone()[0]
    conn.close()
    return {"affected_users": affected, "decay_rate": 0.20}

@app.post("/admin/export")
def run_export(_: None = Depends(require_admin)):
    conn = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    export_dir = Path("exports") / today
    export_dir.mkdir(parents=True, exist_ok=True)
    users = conn.execute("SELECT moltbook_username, karma, tasks_completed, consensus_matches FROM users").fetchall()
    with open(export_dir / "karma.json", "w") as f:
        json.dump([dict(u) for u in users], f, indent=2)
    tasks = conn.execute('''SELECT id, type, target_url, consensus_result, consensus_confidence, resolved_at FROM tasks WHERE status = 'consensus' ''').fetchall()
    with open(export_dir / "consensus.json", "w") as f:
        json.dump([dict(t) for t in tasks], f, indent=2, default=str)
    subs = conn.execute('''SELECT s.*, u.moltbook_username FROM submissions s JOIN users u ON s.user_id = u.id''').fetchall()
    with open(export_dir / "contributions.json", "w") as f:
        json.dump([dict(s) for s in subs], f, indent=2, default=str)
    conn.close()
    return {"exported_to": str(export_dir), "files": ["karma.json", "consensus.json", "contributions.json"]}

@app.post("/admin/blacklist/{username}")
def blacklist_user(username: str, _: None = Depends(require_admin)):
    conn = get_db()
    conn.execute("UPDATE users SET is_blacklisted = TRUE WHERE moltbook_username = ?", (username,))
    conn.commit()
    conn.close()
    return {"status": "blacklisted", "username": username}

# ============ HEALTH ============

@app.get("/")
def root():
    return {"name": "slop.wiki", "tagline": "Consensus-verified signal layer over Moltbook", "docs": "/docs", "start": "POST /verify/request"}

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ============ AGENT MESSAGING ============

@app.on_event("startup")
def init_messages_table():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL DEFAULT 'general',
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_messages_channel ON agent_messages(channel);
    ''')
    conn.commit()
    conn.close()

class MessageSend(BaseModel):
    channel: str = "general"
    sender: str
    content: str

@app.post("/messages")
def send_message(msg: MessageSend, authorization: str = Header(None)):
    """Send a message to a channel. Agents use their name as sender."""
    conn = get_db()
    conn.execute(
        "INSERT INTO agent_messages (channel, sender, content) VALUES (?, ?, ?)",
        (msg.channel, msg.sender, msg.content)
    )
    conn.commit()
    conn.close()
    return {"status": "sent", "channel": msg.channel}

@app.get("/messages/{channel}")
def get_messages(channel: str, limit: int = 50, since_id: int = 0):
    """Get messages from a channel. Use since_id for polling."""
    conn = get_db()
    messages = conn.execute(
        "SELECT id, sender, content, created_at FROM agent_messages WHERE channel = ? AND id > ? ORDER BY id DESC LIMIT ?",
        (channel, since_id, limit)
    ).fetchall()
    conn.close()
    return {
        "channel": channel,
        "messages": [{"id": m["id"], "sender": m["sender"], "content": m["content"], "time": m["created_at"]} for m in reversed(messages)]
    }

@app.get("/messages")
def list_channels():
    """List all channels with recent activity."""
    conn = get_db()
    channels = conn.execute(
        "SELECT channel, COUNT(*) as count, MAX(created_at) as last_activity FROM agent_messages GROUP BY channel ORDER BY last_activity DESC"
    ).fetchall()
    conn.close()
    return {"channels": [{"name": c["channel"], "messages": c["count"], "last_activity": c["last_activity"]} for c in channels]}
