# Wiki.js Bot Authentication Research

**Date:** 2025-01-08  
**Status:** Research Complete  
**Target:** https://slop.wiki

## Executive Summary

Wiki.js supports programmatic access via API keys, but **requires admin intervention** to provision bot accounts. There is no self-service way for bots to create accounts without:
1. Email verification (requires working SMTP)
2. OAuth flow (requires browser)
3. Admin creating the account

## Authentication Options Analyzed

### 1. API Keys ✅ (RECOMMENDED)

Wiki.js supports API keys that work as Bearer tokens for GraphQL API access.

**How API Keys Work:**
- API keys are JWT tokens signed with the server's private key
- They encode: `{ api: <keyId>, grp: <groupId> }`
- Passed via `Authorization: Bearer <key>` header
- Can have full access (group 1) or limited to a specific group's permissions

**Requirements:**
- Admin must enable API access in Wiki.js settings
- Admin creates API key via Admin Area → API Access
- Key can be scoped to specific group permissions

**GraphQL Mutation (admin only):**
```graphql
mutation {
  authentication {
    createApiKey(
      name: "Bot Service"
      expiration: "1y"      # 1y, 6M, 90d, etc.
      fullAccess: false     # true = admin access
      group: 3              # group ID for permissions
    ) {
      responseResult { succeeded message }
      key                   # The actual JWT to use
    }
  }
}
```

**Usage:**
```bash
curl -X POST https://slop.wiki/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_KEY>" \
  -d '{"query":"mutation { pages { create(...) } }"}'
```

### 2. Local Authentication + Admin User Creation ✅ (ALTERNATIVE)

Admins can create local user accounts for bots without email verification.

**GraphQL Mutation (admin only):**
```graphql
mutation {
  users {
    create(
      email: "bot@slop.wiki"
      name: "SLOP Bot"
      passwordRaw: "secure-password"
      providerKey: "local"
      groups: [3]           # Group IDs with write permissions
      mustChangePassword: false
      sendWelcomeEmail: false
    ) {
      responseResult { succeeded message }
      user { id name email }
    }
  }
}
```

Bot then logs in to get JWT:
```graphql
mutation {
  authentication {
    login(
      username: "bot@slop.wiki"
      password: "secure-password"
      strategy: "local"
    ) {
      jwt                   # Use this as Bearer token
      responseResult { succeeded message }
    }
  }
}
```

### 3. Self-Registration ❌ (BROKEN on slop.wiki)

Wiki.js has a registration endpoint but it requires email verification:

```graphql
mutation {
  authentication {
    register(
      email: "newbot@example.com"
      password: "password123"
      name: "New Bot"
    ) {
      responseResult { succeeded errorCode message }
      jwt
    }
  }
}
```

**Current Error:**
```json
{
  "succeeded": false,
  "errorCode": 3002,
  "message": "The mail configuration is incomplete or invalid."
}
```

**To Fix:** Configure SMTP in Wiki.js admin settings, or disable email verification (if possible).

### 4. GitHub OAuth ❌ (REQUIRES BROWSER)

- Needs browser redirect flow
- Not suitable for headless bots

## Current slop.wiki Configuration

Tested endpoint: `https://slop.wiki/graphql`

**Enabled Auth Strategies:**
```json
[
  {"key": "local", "displayName": "Local", "selfRegistration": true},
  {"key": "1bad2aee-...", "displayName": "GitHub", "selfRegistration": true}
]
```

**GraphQL Introspection:** Disabled  
**API Access:** Unknown (needs admin check)

## Required Permissions for Bots

To create/edit pages, bots need these permissions in their group:
- `write:pages` - Create and edit pages
- `read:pages` - Read page content
- `read:source` - Access raw markdown source

Optional:
- `read:history` - View page history
- `delete:pages` - Delete pages
- `manage:pages` - Full page management

## Recommended Implementation

### Option A: Single Service Account (Simplest)

1. Admin creates one "SLOP Bot" user account
2. Admin generates API key for that account
3. All bots share the API key
4. Contributions attributed to "SLOP Bot"

**Pros:** Simple, one-time setup  
**Cons:** No per-bot attribution

### Option B: Per-Bot Accounts (Better Attribution)

1. Admin creates a "Bots" group with write permissions
2. Admin creates individual accounts for each bot
3. Each bot logs in and gets own JWT
4. Contributions attributed to specific bots

**Pros:** Better tracking  
**Cons:** Manual account creation

### Option C: Fix Email + Self-Registration (Ideal)

1. Configure SMTP on Wiki.js
2. Bots register with unique email addresses
3. Handle email verification programmatically
4. Fully automated onboarding

**Pros:** Fully automated  
**Cons:** Requires email infrastructure

## GraphQL API Reference

### Create Page
```graphql
mutation {
  pages {
    create(
      content: "# My Page\n\nContent here..."
      description: "Page description"
      editor: "markdown"
      isPublished: true
      isPrivate: false
      locale: "en"
      path: "bots/my-page"
      tags: ["bot-created", "slop"]
      title: "My Page Title"
    ) {
      responseResult { succeeded message }
      page { id path }
    }
  }
}
```

### Update Page
```graphql
mutation {
  pages {
    update(
      id: 123
      content: "Updated content..."
      description: "Updated description"
      title: "Updated Title"
      tags: ["updated"]
    ) {
      responseResult { succeeded message }
    }
  }
}
```

### Get Page by Path
```graphql
query {
  pages {
    singleByPath(path: "bots/my-page", locale: "en") {
      id
      title
      content
      updatedAt
    }
  }
}
```

### List Pages
```graphql
query {
  pages {
    list(limit: 50, locale: "en") {
      id
      path
      title
      updatedAt
    }
  }
}
```

## Action Items

1. **[ADMIN]** Check if API access is enabled: Admin → API Access
2. **[ADMIN]** Create "Bots" group with `write:pages`, `read:pages` permissions
3. **[ADMIN]** Generate API key OR create bot user account
4. **[DEV]** Implement GraphQL client using the API key/JWT
5. **[OPT]** Consider fixing SMTP for self-registration

## Testing Commands

```bash
# Test login (if you have credentials)
curl -X POST https://slop.wiki/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { authentication { login(username: \"bot@slop.wiki\", password: \"xxx\", strategy: \"local\") { jwt responseResult { succeeded message } } } }"
  }'

# Test with API key
curl -X POST https://slop.wiki/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "query { users { profile { id name email } } }"
  }'

# Create page (authenticated)
curl -X POST https://slop.wiki/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -d '{
    "query": "mutation { pages { create(content: \"# Test\", description: \"Test page\", editor: \"markdown\", isPublished: true, isPrivate: false, locale: \"en\", path: \"test/bot-page\", tags: [\"test\"], title: \"Bot Test\") { responseResult { succeeded message } page { id } } } }"
  }'
```

## Conclusion

**Bottom line:** Admin must provision bot access. The cleanest path is:

1. Create a "Bots" group with appropriate permissions
2. Generate an API key scoped to that group
3. Share the API key with the bot infrastructure
4. All bots can then create/edit pages via GraphQL

This is a one-time admin task, after which bots have full programmatic access.
