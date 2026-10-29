# 个人网站项目复盘 ·「避疯港」

> 代码快照：2026-10-29。`main.py` 291 行、`content.py` 275 行、6 个模板、`static/css/style.css` 1986 行、`static/js/main.js` 115 行。
> 运行环境：`.venv` 内 Python 3.14.0 + Flask 3.1.3。
> 本文只做分析，未改动任何代码。

---

## 0. 一句话结论

这是一个**没有构建步骤的纯 SSR 单体站**：Flask 路由把 `content.py` 里的数据装配成模板变量，Jinja2 直出完整 HTML，CSS/JS 只负责视觉与少量交互。
它在"写内容不碰 HTML"这件事上做得相当干净，但**启动链路、数据真实性、品牌文案收敛、工程化配套**四处是明显短板。

---

## 一、实现逻辑与关键细节

### 1.1 数据流（按一次请求的顺序）

1. **进程启动即装配数据**：`main.py:22` `import content` → `main.py:28` 按 `date` 倒序得到 `POSTS` → `main.py:121` `ENRICHED = [enrich(post) for post in POSTS]`。
   - 派生字段全在 `enrich()` 里算：`words`/`read_minutes`/`year`/`month`/`day`/`md`/`html`（`main.py:108-118`）。
   - **正文 HTML 在导入时就一次性渲染完**（`main.py:117` 调 `render_body`），不是每次请求现算。6 篇很快，500 篇会拖慢启动。
2. **注入全局变量**：`@app.context_processor inject_globals`（`main.py:150-165`）把 `site`/`profile`/`stats`/`categories`/`all_tags`/`nav`/`today_year` 塞给所有模板。
   - 注意重复计算：`main.py:156` 调 `build_stats()`，它内部又调一次 `taxonomy()`（`main.py:137`），紧接着 `main.py:157-158` 又各调一次 `taxonomy()` —— **每个请求 3 次全量分类 + 排序**。
3. **路由分发**：
   - `/`：取 `ENRICHED[:3]`（`main.py:171`）；
   - `/blog`：读 `q`/`tag`/`category` 三个 query 参数做内存过滤（`main.py:183-200`），全文搜索是把 `body` 列表 `join` 后 `in` 判断（`main.py:199`），O(n×全文)；
   - `/blog/<slug>`：线性 `next()` 找文章（`main.py:214`），再 `order.index()` 求下标（`main.py:219`），拼出前后篇与同标签推荐（`main.py:220-227`）；
   - `/about`：纯模板（`main.py:239-241`）；404 走统一 handler（`main.py:244-246`）。
4. **模板渲染**：`base.html` 提供骨架（天空背景 15-38、header 40-75、footer 81-115、回顶按钮 117-122、脚本 124），子模板只实现 `{% block content %}` 与 `{% block title %}`（`base.html:6`）。
5. **静态资源**：全部经 `url_for('static', filename=...)` 生成（`base.html:9-10`、`base.html:124`、`index.html:39`），依赖 Flask 默认的 `static_folder="static"`。

### 1.2 页面与「组件」划分

| 层 | 文件 | 职责 |
| --- | --- | --- |
| 壳层 | `templates/base.html` | 导航、页脚、天空装饰、全局 meta |
| 页面 | `index / blog / post / about / 404` | 各自 block 内容 |
| 数据 | `content.py` | SITE / PROFILE / POSTS 三个字面量 |
| 逻辑 | `main.py` | 路由、派生字段、简易 Markdown、启动 |

没有组件系统，也没有 `{% include %}`。复用靠 **CSS class 组合**，所以「文章卡片」的 markup 在 `index.html:71-89` 与 `blog.html:46-...` 各写了一遍，`index.html:98` 与 `about.html:23` 的头像标签也重复 —— 改结构要改两处。

### 1.3 路由与「构建配置」

本项目**没有构建**：没有 webpack/vite/rollup，没有 `package.json`，没有 dist 产物。所以常见的 `@/` 路径别名、`import.meta.env`、环境变量注入、SSR/CSR 边界这些概念在这里**整体不适用**——替代它们的是：

| 构建期概念 | 本项目的对应物 |
| --- | --- |
| 路径别名（`@/`） | 服务端 `url_for('post_detail', slug=...)`；资源用 `url_for('static', ...)` |
| 环境变量注入 | 运行时读 `os.environ`：`PORT`（`main.py:274`）、`FLASK_DEBUG`（`main.py:275`，**默认 "1"**）、`OPEN_BROWSER`（`main.py:280`） |
| 构建配置 | `app.config["TEMPLATES_AUTO_RELOAD"] = True`（`main.py:25`），仅此一项 |
| 依赖锁定 | `requirements.txt` 只有 `Flask>=3.0`，无 lock、无上限 |

### 1.4 状态管理

- **服务端**：无数据库、无 session。唯一「状态」是导入期快照 `POSTS`/`ENRICHED`（`main.py:28`、`121`），进程重启就回到 `content.py` 的字面量。
- **客户端**：无 store，UI 状态用 DOM class 表达：`.is-scrolled`、`.is-open`、`.is-in`，进度条写 `#readBar` 的 `style.width`（`main.js:47-62`）。整个脚本是 IIFE，无全局污染（`main.js:2-115`）。
- **视图状态**：筛选条件放在 URL query（`main.py:183-185` 读、`blog.html:26-30` 生成链接）——可分享、可后退，这个选择是对的。
- **断点**：`blog.html:21` 只在搜索表单里保留了 `category` 的 hidden input，**没保留 `tag`**，所以在「标签筛选 + 关键词搜索」组合下会丢标签条件。

### 1.5 样式方案

- 单文件、全局作用域：`style.css` 1986 行，38,120 字节（gzip 8,216）。
- Token 层在 `:root`（`style.css:6-45`）：`--sky/--ink/--accent/--mint/--butter`、圆角、三级阴影。
- 视觉手法：玻璃拟态 `.glass-card`（`style.css:195`，`backdrop-filter` 双前缀）、天蓝渐变 `.sky`（`105`）、云朵漂移动画、三处 `@keyframes`。
- 响应式：三个断点 `1080 / 860 / 640`（`style.css:1772`、`1805`、`1859`），另有 `prefers-reduced-motion` 兜底（`1972`）。
- 无预处理器、无 CSS Modules、无 utility 框架 —— 命名靠前缀，`.hero-*`、`.post-*`、`.side-*`，冲突风险主要来自未来新增模块。

### 1.6 数据来源与部署

- **数据来源**：Python 字面量。`SITE`（`content.py:20-33`）、`PROFILE`（`36-78`）、`POSTS`（`81-275`）。改内容 = 改代码 + 重启。
- **部署方式**：目前只有 Flask dev server（`main.py:291`）。没有 `wsgi.py`、没有 gunicorn/waitress、没有 Dockerfile/CI，`README.md:1-40` 给的是本地运行步骤。
- 参考站是 GitHub Pages 上的 Vue/Vite 静态站；本项目是 SSR，**不能直接丢到 GitHub Pages**，这是换平台时第一个会撞的墙（需要冻结成静态文件，或换到能跑 Python 的托管）。

### 1.7 易踩坑清单

1. **端口探测 + 浏览器开窗时序（真实事故，见下）**：`pick_port` 用 `connect_ex` 判空（`main.py:260-266`），探不出 Windows 保留端口段，只有真正 `bind` 时才抛 `OSError`；而开浏览器的定时器在 `app.run` **之前**就已启动（`main.py:283` vs `291`）。于是「5000 被占 → 换端口 → 绑定失败 → 控制台留 traceback，浏览器照样打开一个死地址」。
   > **5002 打不开的直接原因**：上一轮我留下的测试进程占着 5000 与 5057，把启动挤到 5001，再挤到 5002；5002 那次绑定失败（或被停止），而浏览器已被定时器打开，于是你看到 `ERR_CONNECTION_REFUSED`。现已清掉所有残留进程，5000–5002 均可用。
2. **debug 重载让脚本跑两遍**：`app.run(debug=True)` 会重启一次进程，`main.py:280-283` 已用 `WERKZEUG_RUN_MAIN` 规避重复开窗；但要知道 `ENRICHED`（`main.py:121`）也会被算两遍。
3. **静态资源无指纹**：`base.html:9-10`、`124` 引用的 CSS/JS 不带版本号。今天靠 Flask 默认协商缓存没出事，一旦上 CDN 或加长缓存，改样式后用户会拿旧文件。
4. **版本未锁定**：`requirements.txt` 仅 `Flask>=3.0`，实际 `3.1.3`。换机重装可能拿到 4.x，`app.run`/`send_file` 行为变化会直接炸。
5. **`main.py:5` 的文档承诺**：docstring 写死 `127.0.0.1:5000`，但端口会被 `pick_port` 改掉——承诺与实际不一致，正是这次困惑的来源之一。
6. **死代码/死资源**：`base.html:2` 的 `class="no-js"` 与 `main.js:5` 的 `remove("no-js")` 已无 CSS 规则消费（`style.css` 里搜不到 `.no-js`）；`static/avatar.svg` 在 `content.py:39` 改用 `loong.jpg` 后成为死资源。
7. **派生字段靠字符串切片**：`main.py:113-116` 用 `post["date"][5:7]`、`[8:]` 取年月日。若日期写成 `2026-10-5`（少一位补零），`day` 会取成 `"5"`、`month` 仍对但排序/显示会错位；没有格式校验。
8. **slug 无唯一性校验**：`main.py:214` 的 `next()` 与 `219` 的 `index()` 都只取第一个匹配。两篇文章写同一个 `slug`，前者正常、后者永远打不开，且不报错。

---

## 二、常见技术问题与解决方案

### 2.1 响应式适配

- **成因**：移动端视口单位、固定宽度容器、长英文/URL 不换行、`<br>` 硬断行。
- **思路**：网格用 `minmax(0, 1fr)` 允许收缩、字号用 `clamp()`、断点由内容决定而非设备、避免 `100vw`（含滚动条会溢出）。
- **本项目**：三个断点齐备（`style.css:1772/1805/1859`），网格普遍用 `minmax(0, 1fr)`，实测 390–1440 六个宽度无横向溢出；移动端菜单、单列文章卡、页脚单列都有处理。
  **遗留**：`index.html:12-13` 的 `<br>` 硬断行在 375px 下会把首行挤成两行半；`.hero-facts` 三组数字在 640 以下用 `space-between`（`style.css:1859` 起）偏拥挤。

### 2.2 SEO 与元信息

- **成因**：SPA 首屏是空 `#app`，爬虫/分享卡片拿不到内容；全站复用一条 description；缺 canonical/sitemap。
- **思路**：SSR 或预渲染；每页独立 title/description/OG；`sitemap.xml` + `robots.txt`；文章页补 JSON-LD `Article`。
- **本项目**：**SSR 是最大红利**——直出 HTML，无需 JS 即可读全文，这一点强于参考站的 SPA。
  但 `base.html:7` 的 `description` 全站同一条；**完全没有** `og:*`、`twitter:card`、`canonical`、`application/ld+json`（全仓 grep 无命中）；也没有 `robots.txt` / `sitemap.xml`（文件清单确认）。分享到微信/微博会是一条裸链接。

### 2.3 首屏性能与体积

- **成因**：阻塞渲染的 CSS/字体、未压缩图片、无缓存策略、第三方脚本。
- **思路**：关键 CSS 内联、字体子集化、图片定尺寸 + 现代格式、gzip/brotli、资源指纹。
- **本项目**：底子很轻——无第三方库、无 web font，CSS 38.1KB（gzip 8.2KB）、JS 3.6KB（gzip 1.4KB）。
  **浪费点**：`static/loong.jpg` 45KB 被渲染成 46/88/152px 三种尺寸（`blog.html` 侧栏、`index.html:98`、`about.html:23`），且 `<img>` 没有 `width`/`height`（`index.html:39`、`98`）→ 有 CLS 风险；dev server 不做 gzip。

### 2.4 样式冲突与主题切换

- **成因**：全局 CSS 无作用域、颜色散落、缺少 dark mode 设计。
- **思路**：颜色/间距全部 token 化、`color-scheme`、`prefers-color-scheme`、禁止裸 hex。
- **本项目**：token 层做得不错（`style.css:6-45`），但 `:root` 之外仍有 **35 处硬编码 hex**，且集中在最显眼的地方：
  - `.btn-primary`（`style.css:273-274`）、`.chip.is-on`（`351-352`）、`.filter-row .chip.is-on`（`998-999`）都写死 `#35b0cf → #1c7f9e`；
  - `.brand-mark`（`401-408`）写死 `#52c3de`；
  - `.read-progress span`（`1214-1218`）、`.skill-bar span`（`1533-1537`）写死渐变；
  - `.prose pre`（`1353-1357`）写死 `#143d4b` 深底。
  结果：改 `--accent` 只能换掉一半主题，按钮/进度条/品牌图标不变。另外**没有深色模式**，`theme-color` 固定为 `#7ecdf0`（`content.py:26`）。

### 2.5 交互无障碍（a11y）

- **成因**：只按视觉稿实现，忽略键盘焦点、对比度、语义。
- **思路**：`:focus-visible` 统一焦点环、对比度 ≥ 4.5:1、`aria-controls`/`aria-expanded`、标题层级、动效尊重 `prefers-reduced-motion`。
- **本项目**：已有 `alt`、`aria-hidden`、`aria-expanded`（`base.html:43/70/117`），动效降级也写了（`style.css:1972`）。
  **问题**：`style.css:969` 给搜索框 `outline: none` 却没有补 `:focus-visible` → 键盘用户看不到焦点；`--muted: #7d98a2`（`style.css:11`）在白色玻璃卡上对比度约 3:1，被用在 11.5px 的 `.post-meta`、`.footer-bottom` 上，不达 WCAG AA；`#navToggle` 缺 `aria-controls="navLinks"`（`base.html:70`）；`post.html:7-83` 用外层 `<article>` 包住了上下篇与「相关推荐」，语义上应让这些兄弟区块独立。

### 2.6 浏览器兼容与降级

- **成因**：`backdrop-filter`、`IntersectionObserver`、`clamp()`、`-webkit-line-clamp` 的差异。
- **思路**：`@supports` 兜底；JS 特性检测；关键内容不依赖 JS。
- **本项目**：`backdrop-filter` 写了 `-webkit-` 前缀（`style.css:201-202`）；文本截断带 `-webkit-line-clamp`；`main.js:79-80` 只有在支持 `IntersectionObserver` 时才加 `.js-reveal`，不支持则内容直接可见——**降级路径是对的**。缺 `@supports` 兜底，老浏览器上玻璃卡会退化成不透明白卡（可接受）。

### 2.7 数据统计与埋点

- **成因**：静态数据不会自增，但页面又显示「N 次阅读」。
- **思路**：服务端自增 + 持久化（SQLite/JSON 原子写）+ 去重（session 或 IP+UA 哈希）+ 爬虫过滤；或接 Umami/Plausible。
- **本项目**：`views` 在 6 篇文章里全部写死 `0`（`content.py:87/118/145/176/216/253`），`main.py:143` 只是 `sum()`。所以首页「浏览」统计恒为 0（`index.html:112`），卡片与详情页的「0 次阅读」是装饰（`index.html:86`、`blog.html:54`、`post.html:24`）。**这是当前最“假”的一处展示。**

### 2.8 部署与 CI/CD

- **成因**：dev server ≠ 生产；无构建产物时容易低估「怎么上线」的复杂度。
- **思路**：WSGI（gunicorn/waitress）+ 反代、或改造成静态导出上 CDN；Git + CI + 冒烟测试；健康检查与日志。
- **本项目**：`main.py:291` 直接 `app.run(debug=True)`，`FLASK_DEBUG` 默认 `1`（`main.py:275`）→ 一旦对外就是 Werkzeug 调试器暴露；无 `wsgi.py`/`Dockerfile`/`Procfile`；`requirements.txt` 只有 Flask；**没有 git 仓库、没有 .gitignore**（`.venv/`、`__pycache__/`、`.idea/workspace.xml` 全在工作区里）；无任何测试。

---

## 三、优劣评价

### 优点

1. **内容与表现分离得彻底**：全站文案集中在一个文件，加文章只动 `content.py:81-275` 的数据，派生统计（篇数/字数/标签/分类）自动重算（`main.py:99-147`）。对长期写作的个人站，这是最关键的属性。
2. **渲染策略选对了**：SSR 直出（`main.py:169-241`），没有 JS 也能读全文；对比参考站的 `<div id="app">` 空壳（Vue SPA），在首屏、SEO、分享预览上都占优。
3. **安全基础动作到位**：正文先 `escape` 再套标签（`main.py:32-37`、`58`、`93`），模板默认自动转义（`blog.html:36` 回显关键词也安全），404 走统一页（`main.py:244-246`），`host="127.0.0.1"`（`main.py:291`）不对外暴露。
4. **细节完成度超出同类作业**：颜色/圆角/阴影 token 化（`style.css:6-45`），三断点 + `prefers-reduced-motion`（`1972`），滚动用 rAF 节流（`main.js:64-72`），Esc 关闭菜单、`aria-expanded` 同步（`main.js:15-42`），入场动画还留了 JS 失效兜底（`main.js:99-106`）。

### 不足（含改进方向与优先级）

| # | 不足 | 可落地改进 | 优先级 |
| --- | --- | --- | --- |
| 1 | **启动链路不可靠**：端口探测用 `connect_ex`（`main.py:260-266`）、定时器先于绑定（`283` vs `291`）、绑定失败不留可读提示 | ①`pick_port` 改成真实 `bind` 探测（顺带排掉 Windows 保留端口）；②选中端口写回 `os.environ["PORT"]`，让 debug 子进程复用，避免父子端口不一致；③把「开浏览器」改成轮询端口就绪后再开（替换固定 1.2s）；④`app.run` 包 `try/except OSError`，打印「端口 x 被占用，已改用 y」而不是裸 traceback | **P0** |
| 2 | **视图数造假且无持久化**：`views` 全为 0（`content.py:87` 等），页面却展示「N 次阅读」（`post.html:24`、`index.html:112`） | 先删掉 `index.html:112` 的「浏览」避免误导；再做 `/blog/<slug>` 内自增 + `data/views.json`（或 SQLite）原子写，排除 HEAD、按 session 去重；不想维护就接 Umami，统计放页脚 | **P0**（先止损）/ P1（再做真埋点） |
| 3 | **品牌文案没收敛**：已改名「避疯港/loong」，但 `index.html:102`、`about.html:9` 仍硬编码「在云端，记录人间的烟火。」，`index.html:10/12-13` 写死「我的小窝」与自我介绍，`README.md:1` 还是「云端の小窝」 | 把 `slogan`、`hero_title`、`hero_lead` 提进 `PROFILE`，模板只引用；同步 README 标题与结构说明。验收：全仓 grep「云端」= 0（文章正文里的引用除外） | **P1** |
| 4 | **分享与 SEO 元信息缺失**：`base.html:7` 全站一条 description；无 `og:*`/`canonical`/JSON-LD/`robots.txt`/`sitemap.xml` | `base.html` 加 `{% block meta %}`，文章页输出 `og:title/og:description/og:type=article` + `canonical`（`url_for(..., _external=True)`）；加 `/sitemap.xml`、`/robots.txt` 两个路由由 `ENRICHED` 生成；`og:image` 另存一张 1200×630 | **P1** |
| 5 | **工程化配套为零**：无 git、无 `.gitignore`、依赖无锁（`requirements.txt` 仅 `Flask>=3.0`）、无测试；`FLASK_DEBUG` 默认开着 | `git init` + 忽略 `.venv/ __pycache__/ .idea/ *.pyc`；`pip freeze > requirements.lock`（或改 `pyproject.toml` + 固定 `Flask==3.1.3`）；补 3 个冒烟测试（首页 200、未知 slug 404、`?tag=` 过滤结果数）；`FLASK_DEBUG` 默认改 `0`，本地要热重载再显式开 | **P1** |
| 6 | **数据层有可预见的性能与结构问题**（当前 6 篇无感，量上来会痛）：每请求 3 次 `taxonomy`（`main.py:150-158`）、导入期全量渲染正文（`117`）、搜索串全文扫描（`199`）、`/blog` 无分页（`181-209`） | `taxonomy`/`build_stats` 用 `lru_cache`（键取 `len(ENRICHED)`）；搜索先用 title/excerpt 粗筛再扫正文；`/blog` 加 `?page=` 与 `per_page`；文章多了再考虑 SQLite | **P2** |

---

## 四、结论

这套代码的**结构判断是对的**（数据/视图/样式三层清楚、SSR 适合个人博客、没有为了「现代」引入构建链）。
真正要修的不是架构，而是四处小事：**启动要可靠**（P0）、**展示的数字要真**（P0）、**文案要有单一来源**（P1）、**上线要有版本控制与锁**（P1）。
把这四件做完，它就从「能跑的练习项目」变成「可以放心写三年的个人站」。

---

## 五、更新记录

### 2026-10-29 · 已完成 P0-1（启动链路）

改动只落在 `main.py:261-353` 与 `README.md`：

| 改动 | 位置 |
| --- | --- |
| `pick_port`（connect 探测）→ `can_bind` + `find_free_port`（真实 bind 探测，顺带避开 Windows 保留端口段） | `main.py:262-284` |
| 选中端口写回 `os.environ["PORT"]`，debug 子进程复用同一端口，不再二次挑选 | `main.py:326` |
| 新增 `wait_until_listening` + `open_browser_when_ready`：端口就绪后才开浏览器 | `main.py:287-306` |
| 显式 `PORT` 被占用 → 一行可读提示后退出；reloader 子进程跳过预检（父进程此时仍占着端口） | `main.py:313-318` |
| `app.run` 的 `OSError` 兜底，不再抛裸 traceback | `main.py:348-353` |
| 横幅只在服务进程打印一次 + `flush=True`（修掉 PyCharm 控制台块缓冲看不到地址） | `main.py:335-346` |

验证：5000 空闲时启动并返回 200；5000 被占时顺延 5001 且提示「（5000 被占用了，所以换到了 5001）」；显式 `PORT=5000` 冲突时退出码 1 + 可读提示；`/`、`/blog`、`/blog/<slug>`、`/about`、404、静态资源 6 条回归全通过；测试后 5000/5001 均已释放，无残留进程。

剩余未做：P0-2（浏览数）、P1 三条（文案收敛、SEO 元信息、工程化配套）。

### 2026-10-29 · 已完成 P0-2（阅读数），P1 按用户要求还原

#### 保留：P0-2 阅读数改成真的

| 改动 | 位置 |
| --- | --- |
| `data/views.json` 持久化，临时文件 + `os.replace` 原子写，读坏/缺失都退化成空 | `main.py` 的「阅读数持久化」段 |
| 进文章页自增；session 记 `seen_posts` 去重，爬虫 / `prefetch` 不计数 | `post_detail` 开头 6 行 |
| `before_request` 把「基线 + 累计」合回 `ENRICHED`，模板里的 `post.views` 始终是真值 | `_sync_views` |

实测：同一 session 连刷 3 次 → `{"story": 1}`；换新 session 再刷 → 2。首页「浏览」等于各篇之和。

#### 保留：两处数据容错（修的是 content.py 里已有的问题，不属于新功能）

- 日期 `2026-7-29` 没补零 → `date[5:7]` 会取成 `7-`、排序插到 10 月前面；`normalize_date()` 统一补成 `2026-07-29`。
- `excerpt` 被写成 tuple（多行字符串少写连接符）→ 页面直接显示 `('a', 'b')`；`as_text()` 在入口抹平，title/category/tags/body 一并兼容。

#### 已还原（用户要求只做阅读数）

P1-1 文案收敛（`slogan`/`hero_*`/`email` 字段）、P1-2 SEO（canonical/OG/JSON-LD/sitemap/robots）、
P1-3 工程化（`.gitignore`、锁版本、`tests/`、`wsgi.py`、git 仓库）全部撤回，
模板恢复成硬编码文案，`requirements.txt` 回到 `Flask>=3.0`。

> 因此第二节 2.2（SEO 元信息缺失）、第三节「文案没收敛」「工程化配套为零」三条仍然成立，属于未处理项。
