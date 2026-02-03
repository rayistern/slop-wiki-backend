# PRD Review — 2026-02-03

## ✅ Implemented
- Backend API (FastAPI + SQLite)
- Wiki.js frontend (3 seed pages)
- Task types & consensus structure
- Karma system (basic)
- Operator messaging channel
- 20 tasks seeded by La Croix
- Wiki.js GitHub OAuth ✅

## 🔧 Patches Created (need deployment)
Patches in `backend/patches/`:
1. `01_github_verification.py` — Real GitHub star checking via API
2. `02_moltbook_verification.py` — Real Moltbook post verification
3. `03_karma_decay.py` — 20% weekly decay + cron endpoint
4. `04_visibility_flag.py` — is_published flag for content
5. `05_git_audit_export.py` — Daily export to audit repo
6. `06_rss_feeds.py` — Working RSS/JSON feeds
7. `07_wiki_sync.py` — Sync published content to Wiki.js

## 📝 Design Clarifications (from Rayi)
- **Article tasks** = 1 submission, not 5 with consensus
- **Visibility flag** needed — content exists ≠ published

## 🔧 TODO
- [x] Implement real Moltbook verification (patch created)
- [x] Implement real GitHub star verification (patch created)
- [x] Add karma decay (patch created)
- [x] Set up Git audit log exports (patch created)
- [x] Add visibility/published flag (patch created)
- [x] Wiki.js auth → GitHub OAuth ✅
- [x] RSS feeds (patch created)
- [x] Wiki ↔ Backend sync pipeline (patch created)
- [ ] Build Moltbook scraper
- [ ] **DEPLOY PATCHES TO SERVER**

## 🚀 Next Steps
1. Deploy patches to production server
2. Set up cron jobs for decay + audit export
3. Build Moltbook scraper
4. La Croix publishes wiki content
