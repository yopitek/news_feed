flowchart TD

%% ─────────── TRIGGER ───────────
A[GitHub Actions<br/>每日 08:00 排程] --> B[啟動 pipeline<br/>main.py]

%% ─────────── FETCH RSS ───────────
B --> C[RSS Fetcher<br/>feedparser (Python)]
C --> C1[讀取 RSS / Atom / Feedburner]
C --> C2[解析 title / link / summary / published_at]
C --> D[統一成 JSON 結構]

%% ─────────── OPTIONAL LLM SUMMARY ───────────
D --> E{是否啟用摘要?}

E -->|否| F[直接使用原始摘要]
E -->|是| G[Summarizer<br/>DeepSeek / Claude]
G --> G1[依規則生成繁中摘要<br/>100–150字、不可亂寫]
G --> H[回傳整理後 JSON]

%% ─────────── MERGE + RENDER ───────────
F --> I[合併新聞項目]
H --> I

I --> J[產生 Email HTML<br/>Jinja2 Template]
J --> K[寫入檔案<br/>output/email_preview.html]

%% ─────────── SEND EMAIL ───────────
K --> L[SMTP 寄送 Email]
L --> M[完成每日電子報]
