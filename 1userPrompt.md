ou are a senior software architect and backend engineer.

I am building a Daily Multilingual News Digest System with the following strict requirements.
You must follow these rules exactly and ask no clarifying questions unless something is technically impossible.

1. Project Goal

Build a system that automatically generates a daily multilingual news report using RSS feeds as the primary data source, then outputs:

Web version (with real tabs)

Email version (email-safe layout)

The system runs every day at 08:00 (Asia/Taipei) and emails the digest to me.

2. Output Structure (MANDATORY)
Tabs (exactly 4)

中文新聞

中文產業新聞

English News (original English)

日本語ニュース (original Japanese)

⚠️ Email version MUST NOT use real JS/CSS tabs.
Use anchor-based navigation for email compatibility.

3. Content Rules (STRICT)
For ALL languages

Each category shows exactly 5 news items

Each news item must include:

Title

Source

Publish date

Link

Summary (see language rules below)

Language-specific summary rules
中文（新聞 + 產業）

Generate a ~150 Chinese-character summary

Use DeepSeek API for summarization

Tone: neutral, professional, news-style

No opinion, no emojis, no exaggeration

English News

Output original English

Do NOT translate

If RSS provides a summary → truncate cleanly

If not → generate a ~150-word English summary

Japanese News

Output original Japanese

Do NOT translate

If RSS provides a summary → truncate cleanly

If not → generate a ~150-character Japanese summary

4. Style Requirements (VERY IMPORTANT)

All layouts must follow Financial Times–style aesthetics:

Clean, editorial layout

Serif headline feeling

Muted colors (off-white background, dark text)

Clear section dividers

No modern card UI, no excessive color

You are NOT allowed to copy FT proprietary code or fonts.
Only style inspiration, not duplication.

5. News Classification Rules (Chinese)

Chinese content must be classified into the following categories ONLY:

頭條新聞

產經

股市

全球國際新聞

社會

生活

娛樂

運動

房市

Use RSS source + keywords + rules for classification.
LLM classification is allowed only if deterministic fallback exists.

6. RSS-FIRST POLICY (CRITICAL)

RSS feeds are the primary and default source

DO NOT scrape websites

DO NOT crawl HTML

DO NOT use Firecrawl or similar unless explicitly told later

If RSS lacks content:

Use description

If still missing → fallback summary from title only

7. Approved RSS Sources (ONLY THESE)
中文（中央社 CNA）

https://feeds.feedburner.com/rsscna/politics

https://feeds.feedburner.com/rsscna/intworld

https://feeds.feedburner.com/rsscna/mainland

https://feeds.feedburner.com/rsscna/technology

https://feeds.feedburner.com/rsscna/lifehealth

https://feeds.feedburner.com/rsscna/social

https://feeds.feedburner.com/rsscna/local

https://feeds.feedburner.com/rsscna/culture

https://feeds.feedburner.com/rsscna/sport

https://feeds.feedburner.com/rsscna/stars

English RSS

Startup / Tech / News

http://news.ycombinator.com/rss

http://blog.samaltman.com/posts.atom

http://andrewchen.co/feed/

https://techcrunch.com/startups/feed/

https://techcrunch.com/feed/

http://www.fastcodesign.com/rss.xml

http://www.forbes.com/entrepreneurs/index.xml

http://feeds.slashgear.com/slashgear

http://www.theverge.com/rss/full.xml

http://feeds.bbci.co.uk/news/rss.xml

http://feeds.bbci.co.uk/news/world/rss.xml

http://feeds.bbci.co.uk/news/business/rss.xml

http://feeds.bbci.co.uk/news/technology/rss.xml

https://feedx.net/rss/ap.xml

https://feeds.nbcnews.com/nbcnews/public/news

https://abcnews.go.com/abcnews/topstories

https://www.cbsnews.com/latest/rss/main

Japanese RSS

Asahi + Yahoo Japan

https://www.asahi.com/rss/asahi/newsheadlines.rdf

https://www.asahi.com/rss/asahi/national.rdf

https://www.asahi.com/rss/asahi/politics.rdf

https://www.asahi.com/rss/asahi/business.rdf

https://www.asahi.com/rss/asahi/international.rdf

https://www.asahi.com/rss/asahi/sports.rdf

https://www.asahi.com/rss/asahi/culture.rdf

Yahoo Japan Topics:

https://news.yahoo.co.jp/rss/topics/top-picks.xml

https://news.yahoo.co.jp/rss/topics/domestic.xml

https://news.yahoo.co.jp/rss/topics/world.xml

https://news.yahoo.co.jp/rss/topics/business.xml

https://news.yahoo.co.jp/rss/topics/entertainment.xml

https://news.yahoo.co.jp/rss/topics/sports.xml

https://news.yahoo.co.jp/rss/topics/it.xml

https://news.yahoo.co.jp/rss/topics/science.xml

https://news.yahoo.co.jp/rss/topics/local.xml

8. Tech Stack Constraints

Language: Python

RSS parsing: feedparser or equivalent

Summarization API: DeepSeek

Scheduling: GitHub Actions (cron)

Email: SMTP

Web output: static HTML (can later be hosted)

9. Required Deliverables (STEP-BY-STEP)

You must produce the following in order:

Step 1 — System Architecture

High-level diagram (text)

Data flow

Failure handling

Step 2 — File / Repo Structure

Clear module boundaries

Separation of concerns

Step 3 — RSS Normalization & Dedup Logic

How duplicates are detected

How many items per feed are fetched

Step 4 — Classification Rules

Deterministic mapping rules

Fallback strategy

Step 5 — DeepSeek Prompt Design

Chinese summary prompt

English summary prompt

Japanese summary prompt

Step 6 — HTML Templates

Web version (real tabs)

Email version (anchor-based)

Step 7 — GitHub Actions Workflow

Cron at 08:00 Asia/Taipei

Environment variables

Error notification strategy

10. Hard Rules

Do NOT invent new RSS sources

Do NOT skip steps

Do NOT output partial code

Be precise, professional, production-ready

Assume this will run daily without supervision

Begin with Step 1: System Architecture.