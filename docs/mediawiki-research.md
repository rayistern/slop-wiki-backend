# MediaWiki Research for slop.wiki

**Date**: 2025-02-03  
**Purpose**: Evaluate MediaWiki as a replacement for Wiki.js  
**Use Case**: Bot-driven content curation wiki

---

## Executive Summary

**Recommendation: GO - Switch to MediaWiki**

MediaWiki is significantly better suited for bot-driven content curation than Wiki.js. Its mature bot ecosystem, robust API, and Wikipedia-identical appearance make it the obvious choice for slop.wiki.

---

## 1. Bot Authentication

### How Wikipedia Bots Authenticate

MediaWiki offers multiple authentication methods for bots:

#### 1.1 Bot Passwords (Recommended for Our Use Case)
- **What**: Special passwords generated per-application, separate from main account password
- **How**: User creates a "bot password" at `Special:BotPasswords` with specific permissions
- **Self-Registration**: **NO** - A user account must exist first, created by admin or via registration
- **Workflow**:
  1. Create a regular user account (can be done via API with `action=createaccount`)
  2. Log in as that user
  3. Go to `Special:BotPasswords`
  4. Create a bot password with specific grants (edit, create pages, etc.)
  5. Use format `Username@BotPasswordName` + generated password for API auth

#### 1.2 OAuth (For Third-Party Apps)
- More complex, requires extension installation (`Extension:OAuth`)
- Better for user-facing apps where users authorize access
- Overkill for our bot-driven use case

#### 1.3 Login Token Flow (Legacy)
```
POST /api.php
action=login
lgname=BotUsername
lgpassword=BotPassword
lgtoken=<obtained from action=query&meta=tokens&type=login>
```

### Bot Permissions in MediaWiki
- Granular permission system: `edit`, `createpage`, `createtalk`, `upload`, `delete`, etc.
- Can create a "bot" user group with specific rights
- Rate limits can be relaxed for bot accounts
- Bot edits can be flagged/hidden from Recent Changes

### Can Bots Self-Register?
**Not directly.** Options:
1. Admin pre-creates bot accounts manually
2. Use API `action=createaccount` (requires CAPTCHA bypass or admin action)
3. Disable CAPTCHA for account creation (not recommended for public wikis)

For slop.wiki, **pre-create a single bot account** with appropriate permissions.

---

## 2. API Capabilities

MediaWiki's API is **extremely mature** (20+ years of development). Key endpoints:

### 2.1 Reading Content
```bash
# Get page content
GET /api.php?action=query&titles=PageName&prop=revisions&rvprop=content&format=json

# Search pages
GET /api.php?action=query&list=search&srsearch=searchterm&format=json

# Get page info
GET /api.php?action=query&titles=PageName&prop=info&format=json
```

### 2.2 Creating/Editing Pages
```bash
# Edit a page (requires authentication)
POST /api.php
action=edit
title=PageName
text=Full page content in wikitext
token=<csrf token>
summary=Edit summary
bot=1  # Flag as bot edit
```

### 2.3 Other Bot-Relevant Actions
- `action=upload` - Upload files
- `action=move` - Rename pages
- `action=delete` - Delete pages (requires permission)
- `action=protect` - Protect pages
- `action=parse` - Parse wikitext to HTML
- `action=query&list=recentchanges` - Monitor changes
- `action=query&list=allpages` - List all pages

### 2.4 Python Bot Libraries

**Pywikibot** (Official, Recommended):
```python
import pywikibot
site = pywikibot.Site('en', 'slop')  # Configure in user-config.py
page = pywikibot.Page(site, 'Article Title')
page.text = "New content here"
page.save(summary="Bot edit", botflag=True)
```

**mwclient** (Simpler, Good for Custom Scripts):
```python
import mwclient
site = mwclient.Site('slop.wiki', path='/w/')
site.login('BotUser@BotPasswordName', 'BotPassword')
page = site.pages['Article Title']
page.save('New content', summary='Bot edit')
```

### 2.5 API vs Wiki.js Comparison

| Feature | MediaWiki | Wiki.js |
|---------|-----------|---------|
| API Maturity | 20+ years, battle-tested | Newer, less documented |
| Bot Libraries | Pywikibot, mwclient, many more | Custom REST calls |
| Rate Limiting | Configurable, bot-friendly | Less granular |
| Bulk Operations | Native support | Limited |
| Documentation | Extensive | Moderate |

---

## 3. Deployment (Docker)

### 3.1 Official Docker Image

MediaWiki has an **official Docker image**: `mediawiki:latest`

```yaml
# docker-compose.yml
version: '3.8'
services:
  mediawiki:
    image: mediawiki:1.43-lts
    ports:
      - "8080:80"
    volumes:
      - ./LocalSettings.php:/var/www/html/LocalSettings.php
      - ./images:/var/www/html/images
    environment:
      - MEDIAWIKI_DB_HOST=database
      - MEDIAWIKI_DB_NAME=mediawiki
      - MEDIAWIKI_DB_USER=wiki
      - MEDIAWIKI_DB_PASSWORD=secret
    depends_on:
      - database

  database:
    image: mariadb:10
    environment:
      - MYSQL_DATABASE=mediawiki
      - MYSQL_USER=wiki
      - MYSQL_PASSWORD=secret
      - MYSQL_ROOT_PASSWORD=rootsecret
    volumes:
      - db_data:/var/lib/mysql

volumes:
  db_data:
```

### 3.2 Initial Setup
1. Run `docker-compose up`
2. Visit `http://localhost:8080` to run the installer
3. Download generated `LocalSettings.php`
4. Mount it into container
5. Restart

### 3.3 Key Extensions to Install
For bot-driven wiki:
- **VisualEditor** - Better editing experience
- **Parsoid** - Required for VisualEditor
- **Echo** - Notifications
- **CategoryTree** - Better category navigation
- **Cite** - References/citations
- **CodeEditor** - If editing code/configs

### 3.4 Migration from Wiki.js

**Difficulty: MODERATE**

Wiki.js uses Markdown; MediaWiki uses Wikitext. Options:

1. **Pandoc Conversion**: Convert Markdown → Wikitext
   ```bash
   pandoc -f markdown -t mediawiki input.md -o output.wiki
   ```

2. **Bot-Assisted Migration**:
   - Export Wiki.js content via API/database
   - Convert with Pandoc
   - Import via MediaWiki API

3. **Manual Recreation**: For small wikis, might be fastest

**Data to Migrate**:
- Page content (convert format)
- Images/files (upload via API)
- User accounts (recreate manually)
- Categories (map to MediaWiki categories)

---

## 4. Look and Feel

### Does It Look Like Wikipedia?

**YES - It IS Wikipedia's software.**

MediaWiki with the default **Vector** skin is visually identical to Wikipedia:
- Same sidebar navigation
- Same search box behavior
- Same edit buttons and tabs
- Same table of contents
- Same category footer

### Customization Options
- **Skins**: Vector (default), Timeless, MonoBook, Minerva (mobile)
- **Logo**: Customizable in `LocalSettings.php`
- **CSS/JS**: Full custom styling via `MediaWiki:Common.css`
- **Extensions**: Thousands available for any feature

### Vector 2022 (Modern)
Wikipedia recently updated to Vector 2022 (enabled by default in new installs):
- Cleaner, more modern appearance
- Collapsible sidebar
- Sticky header
- Better mobile responsiveness

---

## 5. MediaWiki vs Wiki.js Comparison

| Aspect | MediaWiki | Wiki.js |
|--------|-----------|---------|
| **Bot Ecosystem** | ⭐⭐⭐⭐⭐ Mature, Pywikibot | ⭐⭐ Basic REST API |
| **API** | ⭐⭐⭐⭐⭐ Comprehensive | ⭐⭐⭐ GraphQL, adequate |
| **Docker** | ⭐⭐⭐⭐ Official image | ⭐⭐⭐⭐ Official image |
| **Wikipedia Look** | ⭐⭐⭐⭐⭐ Identical | ⭐⭐ Different entirely |
| **Learning Curve** | ⭐⭐⭐ Wikitext syntax | ⭐⭐⭐⭐ Markdown |
| **Performance** | ⭐⭐⭐ Needs caching | ⭐⭐⭐⭐ Fast out of box |
| **Extensions** | ⭐⭐⭐⭐⭐ Thousands | ⭐⭐⭐ Modules |
| **Community** | ⭐⭐⭐⭐⭐ Huge | ⭐⭐⭐ Growing |
| **Self-Hosted** | ⭐⭐⭐⭐ Well documented | ⭐⭐⭐⭐ Easy |

### For Bot-Driven Content Curation
MediaWiki wins decisively:
- Pywikibot is specifically designed for automated editing
- API is feature-complete for any bot operation
- Bot accounts have special status and rate limits
- 20 years of Wikipedia bot development best practices

---

## 6. Alternative Wiki Platforms

### 6.1 DokuWiki
- **Pros**: File-based (no database), simple, PHP
- **Cons**: No native bot API, not Wikipedia-like, limited for automation
- **Verdict**: Not suitable for bot-driven use

### 6.2 BookStack
- **Pros**: Modern UI, organized hierarchically, good API
- **Cons**: Not wiki-style (more documentation), doesn't look like Wikipedia
- **Verdict**: Good for docs, not for Wikipedia-style wiki

### 6.3 XWiki
- **Pros**: Java-based, powerful, extensible, good API
- **Cons**: Heavy, Java ecosystem, complex, not Wikipedia-like
- **Verdict**: Overkill, doesn't match use case

### 6.4 TiddlyWiki
- **Pros**: Single HTML file, unique approach
- **Cons**: Not server-based, no multi-user, no bot support
- **Verdict**: Not suitable

### 6.5 Outline
- **Pros**: Modern, real-time collaboration, beautiful
- **Cons**: Not public wiki, team-focused, no Wikipedia look
- **Verdict**: Different use case entirely

### Conclusion on Alternatives
**None match MediaWiki** for:
- Wikipedia appearance
- Bot ecosystem
- API maturity
- Community/extensions

---

## 7. Implementation Plan

If proceeding with MediaWiki:

### Phase 1: Setup (1 day)
1. Deploy MediaWiki via Docker
2. Configure `LocalSettings.php`
3. Install essential extensions
4. Create bot account with bot password

### Phase 2: Bot Development (2-3 days)
1. Set up Pywikibot or mwclient
2. Test CRUD operations
3. Implement content curation logic
4. Set up scheduled runs

### Phase 3: Migration (1-2 days)
1. Export Wiki.js content
2. Convert Markdown → Wikitext
3. Import via bot
4. Verify and fix formatting

### Phase 4: Launch
1. Update DNS
2. Redirect old URLs if needed
3. Monitor and iterate

---

## 8. Potential Concerns

### 8.1 Wikitext vs Markdown
- Wikitext has a learning curve
- Can enable VisualEditor for WYSIWYG editing
- Bots generate wikitext, so humans don't need to write it

### 8.2 Resource Usage
- MediaWiki is heavier than Wiki.js
- Needs PHP, database, possibly caching (Memcached/Redis)
- Docker image ~500MB vs Wiki.js ~200MB

### 8.3 Maintenance
- Regular MediaWiki updates (quarterly security patches)
- Database maintenance (optimize tables periodically)
- More complex than Wiki.js

---

## 9. Decision Matrix

| Requirement | Weight | MediaWiki | Wiki.js |
|-------------|--------|-----------|---------|
| Bot automation | 30% | 10 | 5 |
| Wikipedia look | 25% | 10 | 2 |
| API capabilities | 20% | 10 | 7 |
| Docker deployment | 10% | 8 | 9 |
| Ease of use | 10% | 6 | 8 |
| Performance | 5% | 7 | 8 |
| **WEIGHTED TOTAL** | | **9.05** | **5.15** |

---

## 10. Final Recommendation

### **GO: Switch to MediaWiki**

**Reasons**:
1. **Bot ecosystem is unmatched** - Pywikibot alone is worth the switch
2. **Looks exactly like Wikipedia** - This is the stated goal
3. **API is mature and comprehensive** - 20+ years of development
4. **Docker deployment is straightforward** - Official image available
5. **Huge community** - Any problem has been solved before

**Caveats**:
- Slight learning curve for wikitext (mitigated by bot-generated content)
- Heavier resource usage (acceptable for the benefits)
- Migration effort required (one-time cost)

The bot-driven content curation use case is **exactly what MediaWiki was built for**. Wikipedia's bot ecosystem processes millions of automated edits daily. There's no reason to fight Wiki.js's limitations when MediaWiki does this natively.

---

## Appendix A: Quick Start Commands

```bash
# Pull and run MediaWiki
docker run -d --name mediawiki \
  -p 8080:80 \
  -v mediawiki_data:/var/www/html/images \
  mediawiki:1.43

# Test API is working
curl "http://localhost:8080/api.php?action=query&meta=siteinfo&format=json"

# Install Pywikibot
pip install pywikibot

# Simple bot test with mwclient
pip install mwclient
python -c "
import mwclient
site = mwclient.Site('localhost:8080', path='/w/', scheme='http')
print(list(site.allpages(limit=5)))
"
```

## Appendix B: Useful Resources

- [MediaWiki API Documentation](https://www.mediawiki.org/wiki/API:Main_page)
- [Bot Passwords](https://www.mediawiki.org/wiki/Manual:Bot_passwords)
- [Pywikibot Documentation](https://www.mediawiki.org/wiki/Manual:Pywikibot)
- [MediaWiki Docker Hub](https://hub.docker.com/_/mediawiki)
- [Extension Directory](https://www.mediawiki.org/wiki/Special:ExtensionDistributor)
- [Wikitext Syntax](https://www.mediawiki.org/wiki/Help:Formatting)
