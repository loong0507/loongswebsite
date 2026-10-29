# 避疯港

一个用 **Python + Flask** 写的个人网站：天蓝色天空背景、会飘的云、玻璃质感的卡片，
包含首页、文章列表、文章详情、关于我这几个页面。

全部内容集中在一个文件里，改文案不用碰 HTML。

---

## 一、怎么跑起来（PyCharm）

**方式 A：直接运行（推荐）**

1. 用 PyCharm 打开这个文件夹（如果已经打开，直接看第 2 步）
2. 在左侧项目树里右键 `main.py` → **Run 'main'**
3. 控制台会打印地址，浏览器一般会自动打开：<http://127.0.0.1:5000>

**方式 B：终端运行**

```bash
# Windows（PyCharm 底部的 Terminal 就是这种）
.venv\Scripts\python main.py
```

第一次运行如果提示找不到 `flask`，先装依赖：

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

停止服务：在控制台按 `Ctrl + C`。

> **看控制台里的「请访问」那一行**为准。5000 被占用时会自动顺延到 5001、5002……，
> 并且会告诉你换到了哪个端口；浏览器是等端口真正就绪之后才打开的，不会出现「拒绝连接」的空白页。

### 三个可选的环境变量

| 变量 | 作用 | 默认 |
| --- | --- | --- |
| `PORT` | 指定端口，不再自动顺延 | 自动找 5000 起的空闲端口 |
| `FLASK_DEBUG` | `1` 开热重载（改代码自动重启），`0` 关 | `1` |
| `OPEN_BROWSER` | `0` 表示不自动打开浏览器 | `1` |

在 PyCharm 里设：**Run → Edit Configurations → Environment variables**，例如 `OPEN_BROWSER=0`。

---

## 二、项目结构

```
WebStudy/
├── main.py                 # 入口：路由 + 启动（PyCharm 里运行这个）
├── content.py              # 所有内容：个人信息、文章、技能、时间线
├── requirements.txt
├── data/
│   └── views.json          # 阅读数（第一次有人打开文章时自动生成）
├── templates/              # 页面模板（Jinja2）
│   ├── base.html           # 公共骨架：导航、页脚、天空背景
│   ├── index.html          # 首页
│   ├── blog.html           # 文章列表（带搜索、分类、标签筛选）
│   ├── post.html           # 文章详情
│   ├── about.html          # 关于我
│   └── 404.html
└── static/
    ├── css/style.css       # 全部样式
    ├── js/main.js          # 滚动动画、移动端菜单、阅读进度条
    ├── loong.jpg           # 头像
    ├── avatar.svg          # 早期头像，现在没用了（可删）
    └── favicon.svg         # 浏览器标签页小图标
```

---

## 三、改成自己的

### 1. 基本信息

打开 `content.py`，改 `SITE` 和 `PROFILE` 两段：

| 字段 | 作用 |
| --- | --- |
| `SITE["name"]` | 站点名，显示在导航栏和浏览器标题 |
| `SITE["subtitle"]` | 副标题（导航栏名字下面那行小字） |
| `SITE["since"]` | 建站日期，用来算「避疯港建了多少天」 |
| `SITE["location"]` | 所在地，显示在首屏窗口左下角 |
| `SITE["socials"]` | 页脚的社交链接 |
| `PROFILE["name"] / ["nickname"]` | 真名 / 网名 |
| `PROFILE["bio"]` | 一句话介绍 |
| `PROFILE["quote"]` | 首屏那张小卡片里的句子 |
| `PROFILE["now"]` | 正在做 / 最近在读 / 今年想看 |
| `PROFILE["skills"]` | 技能条（`level` 是 0–100 的数字） |
| `PROFILE["timeline"]` | 关于页的时间线 |
| `PROFILE["contacts"]` | 联系方式 |

### 2. 换头像

把自己的图片放到 `static/` 下（比如 `static/me.jpg`），
然后把 `PROFILE["avatar"]` 改成 `"me.jpg"`。

### 3. 加一篇文章

在 `content.py` 的 `POSTS` 列表末尾追加一个字典：

```python
{
    "slug": "my-new-post",              # 网址里用的英文短名，不能重复
    "title": "文章标题",
    "category": "技术手记",              # 分类，随便起，会自动统计
    "date": "2026-11-01",
    "views": 0,
    "tags": ["Python", "笔记"],
    "excerpt": "列表页会显示这段摘要。",
    "body": [
        "直接写就是普通段落。",
        "## 这是一个二级标题",
        "- 这是列表项",
        "> 这是引用",
    ],
}
```

保存后刷新页面就有了 —— 首页「最近在写」、文章列表、标签、分类、总字数都会自动更新。

正文支持一点点 Markdown：`## 标题`、`- 列表`、`> 引用`、` ``` ` 代码块、
行内 `**加粗**` 和 `` `行内代码` ``。

### 4. 换配色

打开 `static/css/style.css`，最上面的 `:root` 里改颜色变量（`--accent`、`--sky`、`--mint` 等）。
注意：**`:root` 只覆盖了一部分**，按钮/标签的渐变仍是写死的 hex，要一起换得改这些位置：
`.btn-primary`（`style.css:274`）、`.chip.is-on`（`352`）、`.filter-row .chip.is-on`（`999`）、
`.brand-mark`（`408`）、`.read-progress span`（`1218`）、`.skill-bar span`（`1537`）。

---

## 四、常见问题

**Q：浏览器没有自动打开？**
手动访问控制台打印的地址即可（默认 <http://127.0.0.1:5000>）。

**Q：端口被占用？**
不用管，程序会自动挑一个空闲端口，并在控制台提示「（5000 被占用了，所以换到了 xxxx）」；
想固定端口就设环境变量 `PORT=8000`，端口不合用时程序会直接告诉你，而不是抛一堆 traceback。

**Q：浏览器打开了一个端口，但页面打不开？**
先看控制台「请访问」那一行是不是同一个端口。如果对不上，说明你之前 Run 过多个实例（端口会依次 +1），
旧的那个已经停了——先按控制台里的红色停止按钮，再重新 Run 一次即可。

**Q：改代码后页面没变？**
Flask 默认开了调试模式（`debug=True`），保存文件会自动重启。
如果是改模板没生效，按一下 `Ctrl + F5` 强制刷新。

**Q：阅读数存在哪儿？能清零吗？**
存在 `data/views.json`（第一次有人打开文章时自动生成）。同一个浏览器对同一篇只算一次，刷新不会加。
清零就停掉服务、删掉这个文件再启动。

**Q：想放到网上让别人看？**
这是 Flask 站点，需要一台能跑 Python 的服务器（或云主机）。
纯展示的话也可以把页面导出成静态 HTML 再放到 GitHub Pages / EdgeOne Pages，
不过那属于另外一件事了。
