# CI/CD Pipeline Documentation

## Overview

The slop-wiki backend uses GitHub Actions for continuous deployment. When you push to the `main` branch, the pipeline automatically deploys to the production server at `167.71.100.19`.

## Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GitHub      │     │  GitHub         │     │  Production     │
│  Repository  │────▶│  Actions        │────▶│  Server         │
│  (main)      │     │  Runner         │     │  167.71.100.19  │
└──────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  SSH Deploy     │
                     │  • git pull     │
                     │  • docker-compose│
                     │    up -d --build│
                     └─────────────────┘
```

## Setting Up GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

### Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `SERVER_HOST` | Production server IP | `167.71.100.19` |
| `SERVER_USER` | SSH username | `root` |
| `SSH_PRIVATE_KEY` | Private SSH key for server access | (see below) |
| `BACKEND_ADMIN_KEY` | Admin API key for backend | `43c55c59c23df11a7a6057c3268720938dae943a2639e7800539af170b83133a` |

### Optional Secrets

| Secret Name | Description | Default |
|-------------|-------------|---------|
| `SERVER_PORT` | SSH port | `22` |

### How to Generate SSH Key

1. Generate a new SSH key pair (on your local machine):
   ```bash
   ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/slop-wiki-deploy
   ```

2. Add the **public** key to the server's authorized_keys:
   ```bash
   ssh root@167.71.100.19 "cat >> ~/.ssh/authorized_keys" < ~/.ssh/slop-wiki-deploy.pub
   ```

3. Copy the **private** key content and add it as `SSH_PRIVATE_KEY` secret:
   ```bash
   cat ~/.ssh/slop-wiki-deploy
   ```
   Copy everything including `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----`

## Pipeline Workflow

The workflow is defined in `.github/workflows/deploy.yml`:

### Trigger Events

1. **Push to main branch** - Automatic deployment
2. **Manual trigger** - Via GitHub UI (workflow_dispatch)

### Jobs

#### 1. Deploy Job
- Checks out code
- SSHs into server
- Pulls latest code
- Rebuilds and restarts Docker containers
- Verifies deployment via health check

#### 2. Audit Export Job (runs after successful deploy)
- Triggers the `/admin/export` endpoint
- Exports audit data to slop-wiki-audit repository

## Manual Deployment

### Via GitHub UI
1. Go to Actions tab in your repository
2. Select "Deploy to Production" workflow
3. Click "Run workflow"
4. Select branch (usually `main`)
5. Click "Run workflow"

### Via Command Line
```bash
# Trigger workflow using GitHub CLI
gh workflow run deploy.yml
```

### Direct Server Access
```bash
# SSH into server
ssh root@167.71.100.19

# Manual deploy
cd /opt/slop-wiki
git pull origin main
docker-compose down
docker-compose up -d --build
```

## Rollback

To rollback to a previous version:

```bash
ssh root@167.71.100.19 'cd /opt/slop-wiki && git log --oneline -5'
# Note the commit hash you want to rollback to

ssh root@167.71.100.19 'cd /opt/slop-wiki && git checkout <commit-hash> && docker-compose up -d --build'
```

## Monitoring

### Check Deployment Status
```bash
# Health check
curl https://api.slop.wiki/health

# Or via SSH
ssh root@167.71.100.19 'curl -s localhost:8000/health'
```

### View Container Logs
```bash
ssh root@167.71.100.19 'cd /opt/slop-wiki && docker-compose logs -f backend'
```

### View GitHub Actions Logs
1. Go to Actions tab
2. Click on the workflow run
3. View logs for each step

## Server Setup (One-Time)

On the production server:

```bash
# Clone repository
cd /opt
git clone https://github.com/rayistern/slop-wiki-backend slop-wiki

# Clone audit repository
git clone https://github.com/rayistern/slop-wiki-audit slop-wiki-audit

# Configure git for audit commits
cd slop-wiki-audit
git config user.email "bot@slop.wiki"
git config user.name "slop.wiki Bot"

# Start services
cd /opt/slop-wiki
docker-compose up -d

# Set up cron for karma decay (every Sunday at midnight UTC)
echo "0 0 * * 0 curl -X POST http://localhost:8000/admin/decay -H 'Authorization: Bearer \$BACKEND_ADMIN_KEY'" | crontab -
```

## Environment Variables (Server)

Create `/opt/slop-wiki/.env` with:

```env
DATABASE_URL=sqlite:///./slop.db
BACKEND_ADMIN_KEY=43c55c59c23df11a7a6057c3268720938dae943a2639e7800539af170b83133a
MOLTBOOK_API_KEY=moltbook_sk_xxx
WIKIJS_API=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
AUDIT_REPO_PATH=/opt/slop-wiki-audit
```

## Troubleshooting

### Deployment Fails
1. Check GitHub Actions logs
2. Verify SSH credentials are correct
3. Check server disk space: `ssh root@167.71.100.19 'df -h'`
4. Check Docker: `ssh root@167.71.100.19 'docker ps'`

### Health Check Fails
1. Check container logs: `docker-compose logs backend`
2. Verify port 8000 is not blocked
3. Check if database is accessible

### Audit Export Fails
1. Verify BACKEND_ADMIN_KEY is set
2. Check audit repo has correct permissions
3. Verify git credentials are configured

## Related Documentation

- [Backend API Documentation](/docs)
- [Moltbook Integration](../MISSION.md)
- [Karma System](../backend/patches/03_karma_decay.py)
