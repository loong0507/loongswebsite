# -*- coding: utf-8 -*-
"""避疯港 —— 一个用 Flask 写的个人网站。

在 PyCharm 里直接右键运行这个文件（Run 'main'），浏览器会自动打开。
默认地址是 http://127.0.0.1:5000；如果 5000 被占用，会顺延到 5001、5002……
实际地址以控制台打印的「请访问」那一行为准。

想改内容？不用碰这里的代码，去 content.py 里改文章和资料就行。
"""

from __future__ import annotations

import json
import os
import re
import secrets
import socket
import threading
import time
import webbrowser
from datetime import date, datetime
from pathlib import Path

from flask import Flask, abort, render_template, request, session
from markupsafe import Markup, escape

import content

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# session 用来给阅读数去重（同一浏览器对同一篇只算一次）。
# 没配 SECRET_KEY 时随机生成：重启后旧 cookie 失效，最多多算一次，不影响使用。
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VIEWS_FILE = DATA_DIR / "views.json"

def normalize_date(raw: str) -> str:
    """把 2026-7-29 这种没补零的日期补成 2026-07-29。

    排序和模板都依赖固定的 YYYY-MM-DD（`date[5:7]` 取月份），
    在这里统一一次，content.py 里怎么写都不会把页面写乱。
    """
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return str(raw).strip()


# 预先把文章按时间倒序排好，全站共用
POSTS = sorted(content.POSTS, key=lambda item: normalize_date(item["date"]), reverse=True)


# ============================================================ 文本处理
def _inline(text: str) -> str:
    """处理行内的 **加粗** 和 `行内代码`（先转义，避免 HTML 注入）。"""
    safe = str(escape(text))
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)
    return safe


def render_body(body: list[str]) -> Markup:
    """把 content.py 里那种简易 Markdown 列表渲染成 HTML。"""
    out: list[str] = []
    list_open = False
    in_code = False
    code_lines: list[str] = []

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            out.append("</ul>")
            list_open = False

    for raw in [as_text(line) for line in body]:
        line = raw.rstrip()

        if line.startswith("```"):
            if in_code:
                out.append("<pre><code>" + str(escape("\n".join(code_lines))) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                close_list()
                in_code = True
            continue

        if in_code:
            code_lines.append(raw)
            continue

        if not line.strip():
            close_list()
            continue

        if line.startswith("### "):
            close_list()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("- "):
            if not list_open:
                out.append("<ul>")
                list_open = True
            out.append(f"<li>{_inline(line[2:])}</li>")
        elif line.startswith("> "):
            close_list()
            out.append(f"<blockquote><p>{_inline(line[2:])}</p></blockquote>")
        else:
            close_list()
            out.append(f"<p>{_inline(line)}</p>")

    if in_code:  # 代码块忘了收尾也不至于把内容吞掉
        out.append("<pre><code>" + str(escape("\n".join(code_lines))) + "</code></pre>")
    close_list()
    return Markup("".join(out))


# ============================================================ 统计与派生数据
def as_text(value) -> str:
    """容错：content.py 里把多行文字写成 ('a', 'b') 时，也能拼成一段正常的字符串。

    手写数据文件很容易多打一个逗号，那样 excerpt 就变成 tuple，
    直接渲染会在页面上出现 ('…', '…') 这种东西，所以在入口统一抹平。
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "".join(as_text(item) for item in value)
    return "" if value is None else str(value)


def word_count(post: dict) -> int:
    """粗略字数：中文字符按字算，差不多够用。"""
    return sum(len(as_text(line)) for line in post["body"])


def read_minutes(post: dict) -> int:
    return max(1, round(word_count(post) / 400))


def enrich(post: dict) -> dict:
    """给文章补上几个模板要用的字段，避免模板里塞逻辑。"""
    data = dict(post)
    data["date"] = normalize_date(post["date"])
    data["title"] = as_text(post["title"]).strip()
    data["category"] = as_text(post["category"]).strip()
    data["excerpt"] = as_text(post["excerpt"]).strip()
    data["tags"] = [as_text(tag).strip() for tag in post.get("tags", [])]
    data["words"] = word_count(post)
    data["read_minutes"] = read_minutes(post)
    data["year"] = data["date"][:4]
    data["md"] = data["date"][5:7] + "/" + data["date"][8:]
    data["day"] = data["date"][8:]
    data["month"] = data["date"][5:7]
    data["html"] = render_body(post["body"])
    # 搜索用的纯文本，避免每次请求都重新拼
    data["plain"] = "".join(as_text(line) for line in post["body"]).lower()
    # content.py 里的 views 是「基线」，真实阅读数 = 基线 + data/views.json 里累计的
    data["views_base"] = int(post.get("views", 0))
    return data


ENRICHED = [enrich(post) for post in POSTS]


# ------------------------------------------------------------ 阅读数持久化
_views_lock = threading.Lock()


def load_view_counts() -> dict[str, int]:
    """读 data/views.json；文件不存在或写坏了都当成空的，不影响站点启动。"""
    try:
        raw = json.loads(VIEWS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    counts: dict[str, int] = {}
    for key, value in raw.items():
        try:
            counts[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return counts


def save_view_counts(counts: dict[str, int]) -> None:
    """先写临时文件再 os.replace：写一半断电也不会把原文件写坏。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = VIEWS_FILE.with_name(VIEWS_FILE.name + ".tmp")
    tmp.write_text(json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, VIEWS_FILE)


VIEW_COUNTS = load_view_counts()

# 这些 UA 明显不是人，别把阅读数刷上去
_BOT_UA = re.compile(r"bot|spider|crawl|slurp|curl|wget|python-requests|headless|monitor", re.I)


def should_count_view() -> bool:
    if request.method != "GET":
        return False
    if request.headers.get("Purpose") == "prefetch":
        return False
    if request.headers.get("Sec-Purpose", "").startswith("prefetch"):
        return False
    ua = request.headers.get("User-Agent", "")
    return bool(ua) and not _BOT_UA.search(ua)


def add_view(slug: str) -> None:
    with _views_lock:
        counts = load_view_counts()  # 每次重读，避免多进程时内存里的数字落后
        counts[slug] = counts.get(slug, 0) + 1
        try:
            save_view_counts(counts)
        except OSError:
            return  # 磁盘写不了（只读环境）就只在内存里加，不报错
        VIEW_COUNTS[slug] = counts[slug]


def refresh_view_counts() -> None:
    """把累计阅读数合回 ENRICHED，模板里的 post.views 就永远是真实值。"""
    for item in ENRICHED:
        item["views"] = item["views_base"] + VIEW_COUNTS.get(item["slug"], 0)


@app.before_request
def _sync_views() -> None:
    refresh_view_counts()


def taxonomy(posts: list[dict]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """返回（分类, 数量）和（标签, 数量），按数量倒序。"""
    categories: dict[str, int] = {}
    tags: dict[str, int] = {}
    for post in posts:
        categories[post["category"]] = categories.get(post["category"], 0) + 1
        for tag in post["tags"]:
            tags[tag] = tags.get(tag, 0) + 1
    sort_key = lambda pair: (-pair[1], pair[0])  # noqa: E731
    return sorted(categories.items(), key=sort_key), sorted(tags.items(), key=sort_key)


def build_stats() -> dict:
    categories, tags = taxonomy(ENRICHED)
    since = datetime.strptime(content.SITE["since"], "%Y-%m-%d").date()
    return {
        "posts": len(ENRICHED),
        "tags": len(tags),
        "categories": len(categories),
        "views": sum(post["views"] for post in ENRICHED),
        "words": sum(post["words"] for post in ENRICHED),
        "days": (date.today() - since).days,
        "since": since.strftime("%Y-%m-%d"),
    }


@app.context_processor
def inject_globals() -> dict:
    """所有模板都能直接用这些变量。"""
    return {
        "site": content.SITE,
        "profile": content.PROFILE,
        "stats": build_stats(),
        "categories": taxonomy(ENRICHED)[0],
        "all_tags": taxonomy(ENRICHED)[1],
        "nav": [
            {"label": "首页", "endpoint": "index", "key": "home"},
            {"label": "文章", "endpoint": "blog", "key": "blog"},
            {"label": "关于", "endpoint": "about", "key": "about"},
        ],
        "today_year": date.today().year,
    }


# ============================================================ 路由
@app.route("/")
def index():
    recent = ENRICHED[:3]
    return render_template(
        "index.html",
        active="home",
        hero=recent[0] if recent else None,
        recent=recent,
        all_posts=ENRICHED,
    )


@app.route("/blog")
def blog():
    keyword = (request.args.get("q") or "").strip()
    tag = (request.args.get("tag") or "").strip()
    category = (request.args.get("category") or "").strip()

    result = ENRICHED
    if category:
        result = [post for post in result if post["category"] == category]
    if tag:
        result = [post for post in result if tag in post["tags"]]
    if keyword:
        lowered = keyword.lower()
        result = [
            post
            for post in result
            if lowered in post["title"].lower()
            or lowered in post["excerpt"].lower()
            or lowered in post["plain"]
        ]

    return render_template(
        "blog.html",
        active="blog",
        posts=result,
        keyword=keyword,
        current_tag=tag,
        current_category=category,
    )


@app.route("/blog/<slug>")
def post_detail(slug: str):
    current = next((post for post in ENRICHED if post["slug"] == slug), None)
    if current is None:
        abort(404)

    # 同一个浏览器对同一篇只算一次；爬虫和浏览器预取都不算
    seen = session.get("seen_posts", [])
    if slug not in seen and should_count_view():
        add_view(slug)
        session["seen_posts"] = (seen + [slug])[-40:]
    refresh_view_counts()

    order = [post["slug"] for post in ENRICHED]
    idx = order.index(slug)
    newer = ENRICHED[idx - 1] if idx > 0 else None
    older = ENRICHED[idx + 1] if idx + 1 < len(ENRICHED) else None

    related = [
        post
        for post in ENRICHED
        if post["slug"] != slug and set(post["tags"]) & set(current["tags"])
    ][:3]

    return render_template(
        "post.html",
        active="blog",
        post=current,
        newer=newer,
        older=older,
        related=related,
    )


@app.route("/about")
def about():
    return render_template("about.html", active="about")


@app.errorhandler(404)
def page_not_found(_error):
    return render_template("404.html", active=""), 404


# 模板里用的小工具
@app.template_filter("date_cn")
def date_cn(value: str) -> str:
    """2026-10-26 -> 2026 年 10 月 26 日"""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y 年 %m 月 %d 日").replace(" 0", " ")
    except (ValueError, TypeError):
        return value


# ============================================================ 启动
def can_bind(port: int) -> bool:
    """真的尝试绑定一下再放开 —— 比 connect 探测可靠。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def find_free_port(preferred: int = 5000, tries: int = 20) -> int:
    """从 5000 开始找一个「真能绑定」的端口。

    先 bind 再放开，比用 connect 探测可靠：既躲开被别人占用的端口，
    也躲开 Windows 的保留端口段（那种端口 connect 探不出来，绑定时才报错）。
    """
    for port in range(preferred, preferred + tries):
        if can_bind(port):
            return port
    raise RuntimeError(
        f"{preferred}–{preferred + tries - 1} 都被占用了，"
        "可以设环境变量 PORT=5001 指定一个空闲端口"
    )


def wait_until_listening(port: int, timeout: float = 20.0) -> bool:
    """轮询到端口真的能连上为止（服务就绪的信号）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def open_browser_when_ready(url: str, port: int) -> None:
    """等端口能连上了再开浏览器，避免打开一个「拒绝连接」的页面。"""

    def worker() -> None:
        if wait_until_listening(port):
            webbrowser.open(url)

    threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if os.environ.get("PORT"):
        port = int(os.environ["PORT"])
        # 重载出来的子进程直接信任父进程的选择：父进程刚创建的 server 可能还占着
        # 这个端口没释放，这时候再探测会误判成「已被占用」。
        if not is_reloader_child and not can_bind(port):
            raise SystemExit(f"[启动失败] 端口 {port} 已被占用，换一个空闲端口，例如 PORT=5001")
    else:
        try:
            port = find_free_port()
        except RuntimeError as exc:
            raise SystemExit(f"[启动失败] {exc}") from exc
        # 记下来：debug 模式会重启一次进程，子进程要复用同一个端口，
        # 否则可能出现「窗口打开了，服务其实在另一个端口」。
        os.environ["PORT"] = str(port)

    url = f"http://127.0.0.1:{port}"
    auto_open = os.environ.get("OPEN_BROWSER", "1") == "1"

    # 只在真正跑服务的那个进程里开浏览器，免得一次弹两个标签页
    if auto_open and (not debug or is_reloader_child):
        open_browser_when_ready(url, port)

    # 只在真正跑服务的进程里打印，debug 模式下就不会出现两遍横幅
    # flush=True：PyCharm 控制台/重定向时 stdout 是块缓冲，不刷就看不到地址
    if not debug or is_reloader_child:
        lines = [
            "=" * 56,
            f"  {content.SITE['name']}  已启动",
            f"  请访问：{url}",
        ]
        if port != 5000:
            lines.append(f"  （5000 被占用了，所以换到了 {port}）")
        lines += ["  按 Ctrl + C 停止服务", "=" * 56]
        print("\n".join(lines), flush=True)

    try:
        app.run(host="127.0.0.1", port=port, debug=debug)
    except OSError as exc:
        print(f"\n[启动失败] 端口 {port} 绑不上：{exc}", flush=True)
        print("多半是被别的程序占了，设环境变量 PORT=5001 再运行一次即可。", flush=True)
        raise SystemExit(1) from exc

