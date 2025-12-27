# Repository Structure (Suggested)

daily-multilang-news-digest/
├── feeds.yaml
├── PRD.md
├── system_architecture.md
├── deepseek_prompts.md
├── src/
│   ├── run_pipeline.py
│   ├── config.py
│   ├── feed_fetcher.py
│   ├── normalizer.py
│   ├── deduper.py
│   ├── classifier.py
│   ├── summarizer_deepseek.py
│   ├── renderer_email.py
│   ├── renderer_web.py
│   └── mailer_smtp.py
├── templates/
│   ├── email_ft.html
│   └── web_ft.html
├── .github/
│   └── workflows/
│       └── daily.yml
└── README.md
