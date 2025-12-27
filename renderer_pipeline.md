# RSS → JSON → Web / Email Renderer Pipeline

## High-level Flow
RSS Feeds
  ↓
RSS Parser (feedparser)
  ↓
Normalize Articles
  ↓
Group by Language & Category
  ↓
Claude (Single Prompt)
  ↓
sample_data.json
  ↓
Web Renderer (Bento Grid HTML)
Email Renderer (FT-style HTML)

---

## Design Principles
- JSON is the Single Source of Truth.
- Claude handles summarization and structure.
- Renderers handle layout only.
- Web and Email share the same JSON.

---

## Pseudo Code

### Normalize
```python
def normalize(entry, lang):
    return {
        "title": entry.title,
        "source": entry.source,
        "published_at": entry.published,
        "content": entry.summary,
        "url": entry.link,
        "language": lang
    }
```
### Group
```python
def group(entries):
    grouped = {...}
    for e in entries:
        grouped[e["language"]][e["category"]].append(e)
    return grouped
```
### Claude Call
```python
def call_claude(data):
    prompt = load("claude_full_json_prompt.md")
    result = claude.generate(prompt, json.dumps(data))
    return json.loads(result)
```
### Render Web
```python
def render_web(data):
    html = load("web_bento_template.html")
    return apply_cards(html, data)
```
### Render Email
```python
def render_email(data):
    html = load("email_ft_template.html")
    return apply_sections(html, data)
```
