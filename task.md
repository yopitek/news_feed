# Task Breakdown

## Milestone 1 (MVP: RSS → Email)
1. Feeds config (feeds.yaml)
2. RSS fetcher + parser
3. Normalize + dedupe
4. Category bucket selection (top 5)
5. Chinese summary via DeepSeek (fallback to truncated description)
6. Email HTML render (FT-inspired)
7. SMTP send
8. GitHub Actions scheduling

## Milestone 2 (Add Web Version)
9. Web 4-tab renderer
10. Basic hosting (GitHub Pages / Vercel / simple static)

## Milestone 3 (Quality Improvements)
11. Better dedupe (fuzzy)
12. Optional LLM classification for Chinese fine-grain categories
13. Observability dashboard (optional)
