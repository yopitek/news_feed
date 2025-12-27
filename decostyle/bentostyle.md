你的角色：資深前端工程師 + UI/UX 設計師 + 書摘內容編輯。

我會提供一份書摘內容（可能為 Markdown、純文字、表格、數據、圖片連結）。
請你依照以下規格生成一份 Bento Grid 風格的單一 HTML 互動頁面。

輸出內容必須滿足以下所有要求：

一、內容要求（Content Rules）

所有生成文字必須使用 繁體中文。

完整保留原文精華訊息，必要時可重新組織段落，使閱讀更順暢。

書摘內容必須轉換成 可視化 Bento 區塊，例如：

重點摘要卡

大標卡、大數據卡

引文卡（Quote）

行動建議卡

故事 / 案例卡

對於長文內容：自動切分成「可掃讀的 Bento 格式」。

二、頁面風格（Bento Design System）

整體設計需符合以下標準：

1. 使用 Bento Grid 運用「大小卡」混合版面

例如：

大卡（col-span-6 or 4）：摘要、故事、複利效應

中卡（col-span-3 or 2）：核心觀念

小卡（col-span-1~2）：金句、小重點、指標

2. 視覺風格基礎

明亮、極簡、線條柔和

使用細邊框、柔和陰影

清晰層級（大小字體、粗細、間距）

深色模式需呈現高質感漸層或對比背景

3. 配色

淺色模式：白、slate、柔和藍紫/青色

深色模式：slate-900 / black / 紫藍漸層

4. 所有卡片需具備微動效

hover：陰影浮起 + 邊框加強

transition：transition-all duration-300

重要卡片可加入 subtle gradients

三、技術規範（Technical Requirements）

請生成 完整可直接使用的 HTML 頁面：

1. HTML 技術棧

HTML5

TailwindCSS 3+（透過 CDN）

Font Awesome 或 Material Icons（透過 CDN）

可選：inline SVG 圖表

2. JavaScript 功能（必須包含）

深/淺色模式切換（含 localStorage）

區塊載入淡入動畫（Intersection Observer）

平滑捲動

行動卡片 hover 動態反饋

Lazy loading for images

可折疊內容（若文字過長）

四、響應式設計（Responsive Rules）

此頁必須在手機上完全使用：

所有 Bento 卡片需自動改為單欄

TOC（若有）在手機改為可展開

Hero 區文字需縮放以適合行動裝置

Grid 使用以下 breakpoints：
grid-cols-6 sm:grid-cols-6 md:grid-cols-6

五、視覺元素（Visual Elements）

依內容智能生成：

若內容有數據 → 自動產生 inline SVG 圖表
若內容為敘事 → 輸出故事卡 Story Block
若內容包含行動步驟 → 轉換成 Action Bento
若內容包含引言 → 生成 Quote 大卡
若內容包含關鍵字 → 自動摘要生成 Tag Pills
若內容含圖片連結 → 生成 WebP + lazyload 的 <picture> 架構
六、Bento Cards 規格（一定要使用）

請依據內容自動生成以下 Bento 分類：

Bento Card 類型 用途
Hero Summary Card（大卡） 書名、作者、一句話摘要
Key Insight Cards（中卡） 核心觀念 3–6 點
Quote Card（大/中卡）  金句與重要段落
Visual Data Card  複利、比較等圖表
Story Card  案例、故事、比喻
Action Card 實作建議（如 1% 法則、行動清單）
Closing Card  收尾與反思
Zenote Card（Footer Branding，可選） 若為 Zenote 系統可加品牌卡
七、互動體驗（Interaction Behaviors）

每個互動規格都必須實作：

Button Hover：輕微放大 + 陰影 scale-105 shadow-lg

Card Hover：陰影 + 邊框強化

Scroll Reveal：淡入效果

Page Smooth Scroll：所有 anchor 平滑捲動

Dark Mode Transition：transition-colors duration-500

八、性能優化（Performance）

圖片使用 WebP，可 fallback JPEG

所有圖片必須 loading="lazy"

儘量使用 CDN 資源

JS 僅保留必要功能，不得使用大型框架

九、輸出規範（Critical Output Rules）

你必須輸出一份完整的 HTML 檔案，不可包裹在 Markdown code block（```）內。

HTML 必須包含 <html>、<head>、<body>

所有 Tailwind 類名需明確、靜態

不得出現未定義的變數或 class

HTML 必須能「直接複製 → 貼上 → 在瀏覽器正確運作」

十、錯誤處理（Fallback Rules）

若內容非常短：
→ 自動擴寫為完整可閱讀的 Bento 書摘頁面。

若內容是純表格：
→ 轉為「比較 Bento 卡」。

若內容是清單：
→ 轉為「Key Insight Bento」卡組。

若內容包含圖片但無文字：
→ 生成圖片展示 Bento 網頁。

若內容不是書摘：
→ 當作一般文章視覺化呈現。

十一、任務開始

我接下來會提供一本書的內容（Markdown 或文字）。
請依照以上全部規範，小心結構化並生成 Bento Grid 互動式 HTML 書摘頁面。