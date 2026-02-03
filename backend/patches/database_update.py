"""
Database model update for wiki_username field.

Add this to database.py in the Agent class:

    wiki_username = Column(String, nullable=True)

Then run the migration or recreate the database.
"""

# To apply migration manually:
# sqlite3 slop.db < database_migration.sql

# Or use SQLAlchemy to add column:
from sqlalchemy import text

def migrate_add_wiki_username(engine):
    """Add wiki_username column if it doesn't exist."""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(agents)"))
        columns = [row[1] for row in result]
        
        if 'wiki_username' not in columns:
            conn.execute(text("ALTER TABLE agents ADD COLUMN wiki_username VARCHAR"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agents_wiki_username ON agents (wiki_username)"))
            conn.commit()
            print("Migration complete: added wiki_username column")
        else:
            print("Column wiki_username already exists")

if __name__ == "__main__":
    from database import engine
    migrate_add_wiki_username(engine)
