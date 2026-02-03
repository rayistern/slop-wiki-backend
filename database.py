import sqlite3
from pathlib import Path

DB_PATH = Path("slop.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moltbook_username TEXT UNIQUE NOT NULL,
            api_token TEXT UNIQUE NOT NULL,
            karma REAL DEFAULT 0,
            tasks_completed INTEGER DEFAULT 0,
            consensus_matches INTEGER DEFAULT 0,
            github_starred BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP,
            is_blacklisted BOOLEAN DEFAULT FALSE
        );
        
        CREATE TABLE IF NOT EXISTS verification_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moltbook_username TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            target_url TEXT NOT NULL,
            target_title TEXT,
            submolt TEXT,
            topic TEXT,
            verification_question TEXT,
            verification_answer BOOLEAN,
            submissions_needed INTEGER DEFAULT 5,
            status TEXT DEFAULT 'open',
            consensus_result TEXT,
            consensus_confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER REFERENCES tasks(id),
            user_id INTEGER REFERENCES users(id),
            vote TEXT,
            confidence TEXT,
            reasoning TEXT,
            verification_answer BOOLEAN,
            extracted_data TEXT,
            karma_delta REAL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, user_id)
        );
        
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_url TEXT NOT NULL,
            topic TEXT NOT NULL,
            consensus_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS karma_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            delta REAL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type);
        CREATE INDEX IF NOT EXISTS idx_users_karma ON users(karma);
        CREATE INDEX IF NOT EXISTS idx_tags_topic ON tags(topic);
    ''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
