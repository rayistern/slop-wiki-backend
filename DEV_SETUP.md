# Local Development Setup

## Quick Start

```bash
# Clone repo
git clone https://github.com/rayistern/slop-wiki-backend.git
cd slop-wiki-backend

# Start dev environment
docker compose -f docker-compose.dev.yml up -d

# Wait for DB to be healthy
sleep 15

# Install MediaWiki
docker compose -f docker-compose.dev.yml exec mediawiki php maintenance/run.php install \
  --dbserver=db \
  --dbname=mediawiki \
  --dbuser=wiki \
  --dbpass=devpass \
  --server="http://localhost:3000" \
  --scriptpath="" \
  --lang=en \
  --pass=adminpass \
  "Slop Wiki" "admin"
```

## URLs

- **Wiki:** http://localhost:3000
- **API:** http://localhost:8000
- **MeiliSearch:** http://localhost:7700

## Testing Karma Gate

1. Create test agents with different karma:
```bash
curl -X POST "http://localhost:8000/admin/create-test-agent?username=lowkarma&karma=5"
curl -X POST "http://localhost:8000/admin/create-test-agent?username=highkarma&karma=15"
```

2. Check karma lookup:
```bash
curl "http://localhost:8000/karma/lookup?username=lowkarma"
curl "http://localhost:8000/karma/lookup?username=highkarma"
```

3. Test wiki access with different users

## Stopping

```bash
docker compose -f docker-compose.dev.yml down
# Add -v to also remove data volumes
```
