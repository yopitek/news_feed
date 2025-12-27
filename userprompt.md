# Claude Coding Kickoff Prompt

You are a senior software engineer.

Goal:
Build a daily multilingual RSS-first news digest that runs at 08:00 Asia/Taipei, renders:
1) Web version with 4 tabs
2) Email version (anchor navigation)

Strict rules:
- Use feeds.yaml as the single source of truth for all feed URLs and categories.
- English and Japanese output must remain in original language (no translation).
- Chinese summaries must be Traditional Chinese, ~150 characters (130–170).
- Summarize ONLY selected items (top 5 per category) to control cost.
- Implement robust error handling; a single feed failure must not fail the run.
- No JS in email; prefer conservative HTML/CSS.

Deliverables:
- Python modules under src/ as suggested in repostructure.md
- Templates under templates/
- GitHub Actions workflow under .github/workflows/daily.yml

Start with:
1) feed_fetcher.py + normalizer.py
2) deduper.py
3) selection logic (top 5 per category)
Then implement summarization and rendering.
