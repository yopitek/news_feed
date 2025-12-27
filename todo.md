# TODO

## Project Setup
- [ ] Create GitHub repo and commit initial docs + config
- [ ] Add secrets for SMTP and DeepSeek

## Data
- [ ] Validate all RSS URLs in feeds.yaml
- [ ] Define final category mapping for Chinese tabs
- [ ] Add per-source limits (avoid one source dominating)

## Pipeline
- [ ] Implement RSS/Atom fetch + parse with retry/timeout
- [ ] Implement normalization and deduplication
- [ ] Implement selection logic (top 5 per category)
- [ ] Implement DeepSeek summary calls (Chinese only in v1)
- [ ] Add summary cache keyed by URL hash

## Rendering
- [ ] Implement Email FT HTML rendering with anchor navigation
- [ ] Implement Web 4-tab FT rendering

## Ops
- [ ] Add GitHub Actions workflow (08:00 Asia/Taipei)
- [ ] Add structured logging + run report
- [ ] Validate email deliverability (SPF/DKIM/DMARC if custom domain)
