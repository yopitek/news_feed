# Agent Roles (for Claude)

## 1) Config & Feeds Agent
- Maintain feeds.yaml
- Validate RSS/Atom links
- Define category mapping rules

## 2) Ingestion Agent
- Implement fetching/parsing with robust retries/timeouts
- Normalize all feed entries into a common schema

## 3) Quality Agent
- Deduplicate entries
- Apply sanity checks (missing title/link, invalid dates)

## 4) Summarization Agent
- Call DeepSeek for Chinese summaries (~150 chars)
- Enforce strict output format
- Implement caching and fallbacks

## 5) Rendering Agent
- Render Email HTML using templates/email_ft.html
- Render Web HTML (tabs) using templates/web_ft.html

## 6) Delivery Agent
- SMTP integration
- GitHub Actions schedule + secrets handling
- Error handling and reporting
