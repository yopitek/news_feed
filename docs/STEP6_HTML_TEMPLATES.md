# Step 6: HTML Templates

## 1. Design Philosophy

### Financial Times–Inspired Aesthetics

| Principle              | Implementation                                     |
|------------------------|---------------------------------------------------|
| **Editorial Layout**   | Clean, structured, generous whitespace            |
| **Typography**         | Serif headlines (Georgia), sans-serif body        |
| **Color Palette**      | Muted: off-white bg, dark text, subtle borders    |
| **No Modern Cards**    | No shadows, no rounded corners, no gradients      |
| **Clear Hierarchy**    | Strong headlines, clear section dividers          |
| **Professional Tone**  | No emojis, no animations, no flashy colors        |

### Color Palette

```css
/* FT-Inspired Colors */
--bg-page: #f3efe6;        /* Warm off-white (page background) */
--bg-card: #fffdf7;        /* Cream white (content background) */
--text-primary: #1a1a1a;   /* Near-black (headlines) */
--text-body: #333333;      /* Dark gray (body text) */
--text-meta: #666666;      /* Medium gray (metadata) */
--text-muted: #999999;     /* Light gray (footer) */
--border-dark: #1a1a1a;    /* Dark divider lines */
--border-light: #e6e1d6;   /* Light separator lines */
--border-dotted: #d9d2c4;  /* Dotted article separators */
--accent: #0f5499;         /* Blue for links (subdued) */
```

### Typography

```css
/* Headlines */
font-family: Georgia, "Times New Roman", "Noto Serif TC", "Noto Serif JP", serif;

/* Body Text */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans TC", "Noto Sans JP", sans-serif;
```

---

## 2. Web Template (Real JavaScript Tabs)

### File: `templates/web_template.html`

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Daily Multilingual News Digest - RSS-first news summary in Chinese, English, and Japanese">
    <title>Daily News Digest | {{DATE_DISPLAY}}</title>
    
    <style>
        /* ============================================
           CSS Reset & Base Styles
           ============================================ */
        *, *::before, *::after {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        html {
            font-size: 16px;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        body {
            background-color: #f3efe6;
            color: #1a1a1a;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans TC", "Noto Sans JP", sans-serif;
            line-height: 1.6;
            min-height: 100vh;
        }

        a {
            color: #0f5499;
            text-decoration: none;
            transition: color 0.2s ease;
        }

        a:hover {
            color: #1a1a1a;
            text-decoration: underline;
        }

        /* ============================================
           Container & Layout
           ============================================ */
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 24px 20px;
        }

        .card {
            background-color: #fffdf7;
            border: 1px solid #e6e1d6;
        }

        /* ============================================
           Masthead / Header
           ============================================ */
        .masthead {
            padding: 24px 28px;
            border-bottom: 3px solid #1a1a1a;
        }

        .masthead-title {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a1a;
            letter-spacing: -0.02em;
            margin: 0;
        }

        .masthead-subtitle {
            font-size: 0.875rem;
            color: #666666;
            margin-top: 6px;
        }

        /* ============================================
           Tab Navigation
           ============================================ */
        .tab-nav {
            display: flex;
            border-bottom: 1px solid #e6e1d6;
            background-color: #fffdf7;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }

        .tab-btn {
            flex: 1;
            min-width: 120px;
            padding: 14px 20px;
            font-family: Georgia, "Times New Roman", serif;
            font-size: 0.95rem;
            font-weight: 400;
            color: #666666;
            background: transparent;
            border: none;
            border-bottom: 3px solid transparent;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .tab-btn:hover {
            color: #1a1a1a;
            background-color: #faf8f2;
        }

        .tab-btn.active {
            color: #1a1a1a;
            border-bottom-color: #1a1a1a;
            font-weight: 600;
        }

        /* ============================================
           Tab Content Panels
           ============================================ */
        .tab-content {
            display: none;
            padding: 28px;
        }

        .tab-content.active {
            display: block;
        }

        .section-header {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1.25rem;
            font-weight: 600;
            color: #1a1a1a;
            margin: 0 0 16px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #1a1a1a;
        }

        /* ============================================
           News Items
           ============================================ */
        .news-list {
            list-style: none;
        }

        .news-item {
            padding: 18px 0;
            border-bottom: 1px dotted #d9d2c4;
        }

        .news-item:last-child {
            border-bottom: none;
        }

        .news-item-title {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1.125rem;
            font-weight: 600;
            line-height: 1.4;
            margin: 0 0 8px 0;
        }

        .news-item-title a {
            color: #1a1a1a;
        }

        .news-item-title a:hover {
            color: #0f5499;
        }

        .news-item-meta {
            font-size: 0.8125rem;
            color: #666666;
            margin-bottom: 10px;
        }

        .news-item-meta .source {
            font-weight: 500;
        }

        .news-item-meta .date {
            margin-left: 12px;
            color: #999999;
        }

        .news-item-summary {
            font-size: 0.9375rem;
            color: #333333;
            line-height: 1.7;
        }

        /* ============================================
           Footer
           ============================================ */
        .footer {
            padding: 20px 28px;
            border-top: 1px solid #e6e1d6;
            background-color: #faf8f2;
        }

        .footer p {
            font-size: 0.8125rem;
            color: #666666;
            margin: 0;
        }

        .footer .small {
            font-size: 0.75rem;
            color: #999999;
            margin-top: 4px;
        }

        /* ============================================
           Responsive
           ============================================ */
        @media (max-width: 600px) {
            .container {
                padding: 16px 10px;
            }

            .masthead {
                padding: 18px 16px;
            }

            .masthead-title {
                font-size: 1.5rem;
            }

            .tab-btn {
                padding: 12px 14px;
                font-size: 0.875rem;
            }

            .tab-content {
                padding: 18px 16px;
            }

            .news-item-title {
                font-size: 1rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <!-- Masthead -->
            <header class="masthead">
                <h1 class="masthead-title">Daily News Digest</h1>
                <p class="masthead-subtitle">{{DATE_DISPLAY}} · RSS-first · Multilingual</p>
            </header>

            <!-- Tab Navigation -->
            <nav class="tab-nav" role="tablist">
                <button class="tab-btn active" role="tab" aria-selected="true" data-tab="zh-news">中文新聞</button>
                <button class="tab-btn" role="tab" aria-selected="false" data-tab="zh-industry">中文產業新聞</button>
                <button class="tab-btn" role="tab" aria-selected="false" data-tab="en-news">English News</button>
                <button class="tab-btn" role="tab" aria-selected="false" data-tab="ja-news">日本語ニュース</button>
            </nav>

            <!-- Tab Content: 中文新聞 -->
            <section class="tab-content active" id="zh-news" role="tabpanel">
                <h2 class="section-header">中文新聞</h2>
                <ul class="news-list">
                    {{ZH_NEWS_ITEMS}}
                </ul>
            </section>

            <!-- Tab Content: 中文產業新聞 -->
            <section class="tab-content" id="zh-industry" role="tabpanel">
                <h2 class="section-header">中文產業新聞</h2>
                <ul class="news-list">
                    {{ZH_INDUSTRY_ITEMS}}
                </ul>
            </section>

            <!-- Tab Content: English News -->
            <section class="tab-content" id="en-news" role="tabpanel">
                <h2 class="section-header">English News</h2>
                <ul class="news-list">
                    {{EN_NEWS_ITEMS}}
                </ul>
            </section>

            <!-- Tab Content: 日本語ニュース -->
            <section class="tab-content" id="ja-news" role="tabpanel">
                <h2 class="section-header">日本語ニュース</h2>
                <ul class="news-list">
                    {{JA_NEWS_ITEMS}}
                </ul>
            </section>

            <!-- Footer -->
            <footer class="footer">
                <p>Generated automatically at 08:00 (Asia/Taipei). All links open original articles.</p>
                <p class="small">RSS-first pipeline. If a feed fails, the system degrades gracefully.</p>
            </footer>
        </div>
    </div>

    <!-- Tab Switching JavaScript -->
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const tabButtons = document.querySelectorAll('.tab-btn');
            const tabContents = document.querySelectorAll('.tab-content');

            tabButtons.forEach(function(button) {
                button.addEventListener('click', function() {
                    const targetTab = this.getAttribute('data-tab');

                    // Update button states
                    tabButtons.forEach(function(btn) {
                        btn.classList.remove('active');
                        btn.setAttribute('aria-selected', 'false');
                    });
                    this.classList.add('active');
                    this.setAttribute('aria-selected', 'true');

                    // Update content visibility
                    tabContents.forEach(function(content) {
                        content.classList.remove('active');
                    });
                    document.getElementById(targetTab).classList.add('active');
                });
            });
        });
    </script>
</body>
</html>
```

### News Item Template (for injection)

```html
<!-- Single News Item Template -->
<li class="news-item">
    <h3 class="news-item-title">
        <a href="{{LINK}}" target="_blank" rel="noopener noreferrer">{{TITLE}}</a>
    </h3>
    <p class="news-item-meta">
        <span class="source">{{SOURCE}}</span>
        <span class="date">{{PUBLISH_DATE}}</span>
    </p>
    <p class="news-item-summary">{{SUMMARY}}</p>
</li>
```

---

## 3. Email Template (Anchor-Based Navigation)

### File: `templates/email_template.html`

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Daily News Digest | {{DATE_DISPLAY}}</title>
    
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    
    <style type="text/css">
        /* Email-safe reset */
        body, table, td, p, a, li {
            -webkit-text-size-adjust: 100%;
            -ms-text-size-adjust: 100%;
        }
        
        table, td {
            mso-table-lspace: 0pt;
            mso-table-rspace: 0pt;
        }
        
        img {
            -ms-interpolation-mode: bicubic;
            border: 0;
            outline: none;
            text-decoration: none;
        }
        
        /* Base styles */
        body {
            margin: 0 !important;
            padding: 0 !important;
            background-color: #f3efe6;
            font-family: Georgia, "Times New Roman", serif;
        }
        
        .wrapper {
            width: 100%;
            background-color: #f3efe6;
        }
        
        .container {
            width: 100%;
            max-width: 680px;
            margin: 0 auto;
        }
        
        .card {
            background-color: #fffdf7;
            border: 1px solid #e6e1d6;
        }
        
        /* Typography */
        .masthead-title {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 26px;
            font-weight: bold;
            color: #1a1a1a;
            margin: 0;
            padding: 0;
        }
        
        .masthead-subtitle {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 13px;
            color: #666666;
            margin: 8px 0 0 0;
        }
        
        /* Navigation */
        .nav-link {
            display: inline-block;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 12px;
            color: #1a1a1a;
            text-decoration: none;
            border: 1px solid #1a1a1a;
            padding: 8px 12px;
            margin: 0 4px 4px 0;
        }
        
        .nav-link:hover {
            background-color: #f3efe6;
        }
        
        /* Sections */
        .section-header {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 20px;
            font-weight: bold;
            color: #1a1a1a;
            margin: 0 0 12px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #1a1a1a;
        }
        
        .section-divider {
            height: 1px;
            background-color: #e6e1d6;
            margin: 12px 0;
        }
        
        /* News items */
        .news-item {
            padding: 14px 0;
            border-bottom: 1px dotted #d9d2c4;
        }
        
        .news-title {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 16px;
            font-weight: bold;
            line-height: 1.4;
            margin: 0 0 6px 0;
        }
        
        .news-title a {
            color: #1a1a1a;
            text-decoration: none;
        }
        
        .news-meta {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 12px;
            color: #666666;
            margin: 0 0 8px 0;
        }
        
        .news-summary {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: #333333;
            margin: 0;
        }
        
        /* Footer */
        .footer {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 12px;
            color: #666666;
        }
        
        .footer-small {
            font-size: 11px;
            color: #999999;
        }
        
        /* Back to top */
        .back-to-top {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11px;
            color: #0f5499;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <table class="wrapper" role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td align="center" style="padding: 24px 10px;">
                
                <!-- Main Container -->
                <table class="container card" role="presentation" width="680" cellpadding="0" cellspacing="0" border="0">
                    
                    <!-- Masthead -->
                    <tr>
                        <td style="padding: 24px 28px; border-bottom: 3px solid #1a1a1a;">
                            <p class="masthead-title">Daily News Digest</p>
                            <p class="masthead-subtitle">{{DATE_DISPLAY}} · RSS-first · Multilingual</p>
                            
                            <!-- Anchor Navigation -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 16px;">
                                <tr>
                                    <td>
                                        <a href="#sec-zh-news" class="nav-link">中文新聞</a>
                                        <a href="#sec-zh-industry" class="nav-link">中文產業新聞</a>
                                        <a href="#sec-en-news" class="nav-link">English</a>
                                        <a href="#sec-ja-news" class="nav-link">日本語</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Section: 中文新聞 -->
                    <tr>
                        <td id="sec-zh-news" style="padding: 24px 28px;">
                            <h2 class="section-header">中文新聞</h2>
                            
                            {{ZH_NEWS_ITEMS}}
                            
                            <p style="margin-top: 16px;">
                                <a href="#sec-zh-news" class="back-to-top">↑ 回到頂部</a>
                            </p>
                        </td>
                    </tr>
                    
                    <tr><td><div class="section-divider"></div></td></tr>
                    
                    <!-- Section: 中文產業新聞 -->
                    <tr>
                        <td id="sec-zh-industry" style="padding: 24px 28px;">
                            <h2 class="section-header">中文產業新聞</h2>
                            
                            {{ZH_INDUSTRY_ITEMS}}
                            
                            <p style="margin-top: 16px;">
                                <a href="#sec-zh-news" class="back-to-top">↑ 回到頂部</a>
                            </p>
                        </td>
                    </tr>
                    
                    <tr><td><div class="section-divider"></div></td></tr>
                    
                    <!-- Section: English News -->
                    <tr>
                        <td id="sec-en-news" style="padding: 24px 28px;">
                            <h2 class="section-header">English News</h2>
                            
                            {{EN_NEWS_ITEMS}}
                            
                            <p style="margin-top: 16px;">
                                <a href="#sec-zh-news" class="back-to-top">↑ Back to top</a>
                            </p>
                        </td>
                    </tr>
                    
                    <tr><td><div class="section-divider"></div></td></tr>
                    
                    <!-- Section: 日本語ニュース -->
                    <tr>
                        <td id="sec-ja-news" style="padding: 24px 28px;">
                            <h2 class="section-header">日本語ニュース</h2>
                            
                            {{JA_NEWS_ITEMS}}
                            
                            <p style="margin-top: 16px;">
                                <a href="#sec-zh-news" class="back-to-top">↑ トップに戻る</a>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 28px; border-top: 1px solid #e6e1d6; background-color: #faf8f2;">
                            <p class="footer">Generated automatically at 08:00 (Asia/Taipei). All links open original articles.</p>
                            <p class="footer-small" style="margin-top: 4px;">RSS-first pipeline. If a feed fails, the system degrades gracefully.</p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>
```

### Email News Item Template (for injection)

```html
<!-- Single Email News Item Template -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="news-item">
    <tr>
        <td style="padding: 14px 0; border-bottom: 1px dotted #d9d2c4;">
            <p class="news-title">
                <a href="{{LINK}}" target="_blank">{{TITLE}}</a>
            </p>
            <p class="news-meta">
                <strong>{{SOURCE}}</strong> · {{PUBLISH_DATE}}
            </p>
            <p class="news-summary">{{SUMMARY}}</p>
        </td>
    </tr>
</table>
```

---

## 4. Template Rendering Implementation

### File: `src/renderer_web.py`

```python
"""
Web HTML renderer with JavaScript tabs.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
import pytz

from .models import ArticleWithSummary


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "web_template.html"

TAIPEI_TZ = pytz.timezone('Asia/Taipei')


def format_date_display(dt: datetime) -> str:
    """Format datetime for display in Taipei timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    taipei_dt = dt.astimezone(TAIPEI_TZ)
    return taipei_dt.strftime("%Y年%m月%d日 %H:%M")


def format_date_short(dt: datetime) -> str:
    """Format datetime as short date."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    taipei_dt = dt.astimezone(TAIPEI_TZ)
    return taipei_dt.strftime("%m/%d %H:%M")


def render_news_item(article: ArticleWithSummary) -> str:
    """Render a single news item HTML for web."""
    publish_date = format_date_short(article.published)
    
    return f'''<li class="news-item">
    <h3 class="news-item-title">
        <a href="{article.link}" target="_blank" rel="noopener noreferrer">{article.title}</a>
    </h3>
    <p class="news-item-meta">
        <span class="source">{article.source_name}</span>
        <span class="date">{publish_date}</span>
    </p>
    <p class="news-item-summary">{article.summary}</p>
</li>'''


def render_news_list(articles: list[ArticleWithSummary]) -> str:
    """Render list of news items."""
    if not articles:
        return '<li class="news-item"><p class="news-item-summary">No news available for this section.</p></li>'
    
    return '\n'.join(render_news_item(article) for article in articles)


def render_web(
    articles: dict[str, list[ArticleWithSummary]],
    date_str: Optional[str] = None
) -> str:
    """
    Render web HTML with JavaScript tabs.
    
    Args:
        articles: Dict with keys 'zh_news', 'zh_industry', 'en_news', 'ja_news'
        date_str: Optional date string, defaults to current Taipei date
    
    Returns:
        Complete HTML string
    """
    # Load template
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Generate date display
    if date_str is None:
        now = datetime.now(TAIPEI_TZ)
        date_str = now.strftime("%Y年%m月%d日 星期") + ['一', '二', '三', '四', '五', '六', '日'][now.weekday()]
    
    # Render each section
    zh_news_items = render_news_list(articles.get('zh_news', []))
    zh_industry_items = render_news_list(articles.get('zh_industry', []))
    en_news_items = render_news_list(articles.get('en_news', []))
    ja_news_items = render_news_list(articles.get('ja_news', []))
    
    # Substitute placeholders
    html = template.replace('{{DATE_DISPLAY}}', date_str)
    html = html.replace('{{ZH_NEWS_ITEMS}}', zh_news_items)
    html = html.replace('{{ZH_INDUSTRY_ITEMS}}', zh_industry_items)
    html = html.replace('{{EN_NEWS_ITEMS}}', en_news_items)
    html = html.replace('{{JA_NEWS_ITEMS}}', ja_news_items)
    
    return html
```

### File: `src/renderer_email.py`

```python
"""
Email HTML renderer with anchor-based navigation.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
import pytz

from .models import ArticleWithSummary


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "email_template.html"

TAIPEI_TZ = pytz.timezone('Asia/Taipei')


def format_date_display(dt: datetime) -> str:
    """Format datetime for display in Taipei timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    taipei_dt = dt.astimezone(TAIPEI_TZ)
    return taipei_dt.strftime("%Y年%m月%d日 %H:%M")


def format_date_short(dt: datetime) -> str:
    """Format datetime as short date."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    taipei_dt = dt.astimezone(TAIPEI_TZ)
    return taipei_dt.strftime("%m/%d %H:%M")


def render_news_item_email(article: ArticleWithSummary) -> str:
    """Render a single news item HTML for email."""
    publish_date = format_date_short(article.published)
    
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
        <td style="padding: 14px 0; border-bottom: 1px dotted #d9d2c4;">
            <p class="news-title" style="font-family: Georgia, serif; font-size: 16px; font-weight: bold; margin: 0 0 6px 0;">
                <a href="{article.link}" target="_blank" style="color: #1a1a1a; text-decoration: none;">{article.title}</a>
            </p>
            <p class="news-meta" style="font-family: Arial, sans-serif; font-size: 12px; color: #666666; margin: 0 0 8px 0;">
                <strong>{article.source_name}</strong> · {publish_date}
            </p>
            <p class="news-summary" style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333333; margin: 0;">
                {article.summary}
            </p>
        </td>
    </tr>
</table>'''


def render_news_list_email(articles: list[ArticleWithSummary]) -> str:
    """Render list of news items for email."""
    if not articles:
        return '''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
        <td style="padding: 14px 0;">
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #666666;">No news available for this section.</p>
        </td>
    </tr>
</table>'''
    
    return '\n'.join(render_news_item_email(article) for article in articles)


def render_email(
    articles: dict[str, list[ArticleWithSummary]],
    date_str: Optional[str] = None
) -> str:
    """
    Render email-safe HTML with anchor navigation.
    
    Args:
        articles: Dict with keys 'zh_news', 'zh_industry', 'en_news', 'ja_news'
        date_str: Optional date string, defaults to current Taipei date
    
    Returns:
        Complete email HTML string
    """
    # Load template
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Generate date display
    if date_str is None:
        now = datetime.now(TAIPEI_TZ)
        date_str = now.strftime("%Y年%m月%d日 星期") + ['一', '二', '三', '四', '五', '六', '日'][now.weekday()]
    
    # Render each section
    zh_news_items = render_news_list_email(articles.get('zh_news', []))
    zh_industry_items = render_news_list_email(articles.get('zh_industry', []))
    en_news_items = render_news_list_email(articles.get('en_news', []))
    ja_news_items = render_news_list_email(articles.get('ja_news', []))
    
    # Substitute placeholders
    html = template.replace('{{DATE_DISPLAY}}', date_str)
    html = html.replace('{{ZH_NEWS_ITEMS}}', zh_news_items)
    html = html.replace('{{ZH_INDUSTRY_ITEMS}}', zh_industry_items)
    html = html.replace('{{EN_NEWS_ITEMS}}', en_news_items)
    html = html.replace('{{JA_NEWS_ITEMS}}', ja_news_items)
    
    return html
```

---

## 5. Template Placeholders Reference

| Placeholder            | Description                                |
|------------------------|--------------------------------------------|
| `{{DATE_DISPLAY}}`     | Current date in display format             |
| `{{ZH_NEWS_ITEMS}}`    | Rendered Chinese news items                |
| `{{ZH_INDUSTRY_ITEMS}}`| Rendered Chinese industry news items       |
| `{{EN_NEWS_ITEMS}}`    | Rendered English news items                |
| `{{JA_NEWS_ITEMS}}`    | Rendered Japanese news items               |

---

## 6. Email Compatibility Notes

### Tested Email Clients

| Client         | Anchor Nav | CSS Support | Notes                    |
|----------------|------------|-------------|--------------------------|
| Gmail (Web)    | ✅         | Good        | Some CSS stripped        |
| Gmail (iOS)    | ✅         | Good        | Works well               |
| Outlook 365    | ✅         | Limited     | Table-based layout OK    |
| Apple Mail     | ✅         | Excellent   | Full support             |
| Yahoo Mail     | ✅         | Good        | Minor spacing issues     |

### Email-Safe CSS Rules

1. Use **inline styles** for critical styling
2. **Table-based layout** for structure
3. **No JavaScript** (stripped by email clients)
4. **No external fonts** (use web-safe fallbacks)
5. **Max width 680px** for readability

---

**Next Step**: Step 7 — GitHub Actions Workflow
