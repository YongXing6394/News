import os
import requests
import feedparser
from datetime import datetime, timezone, timedelta

# ── 配置 ──────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# 只抓过去 24 小时以内的新闻
HOURS_BACK = 24
NEWS_LIMIT = 8   # 每个来源最多显示几条

# RSS 源列表（可自由增减）
RSS_FEEDS = [
    {
        "name": "Hacker News Top",
        "url": "https://hnrss.org/frontpage?count=20",
    },
    {
        "name": "Google News · 科技",
        "url": "https://news.google.com/rss/search?q=technology&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
    {
        "name": "Google News · AI",
        "url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
]

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def parse_entry_time(entry) -> datetime | None:
    """尝试从 RSS entry 中解析发布时间，返回 UTC aware datetime。"""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_news(feeds: list[dict], hours_back: int, limit: int) -> list[dict]:
    """
    抓取多个 RSS 源中过去 N 小时的文章，去重后按时间倒序返回。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    seen_titles: set[str] = set()
    results: list[dict] = []

    for feed_cfg in feeds:
        try:
            feed = feedparser.parse(feed_cfg["url"])
        except Exception as e:
            print(f"[WARN] 无法解析 {feed_cfg['name']}: {e}")
            continue

        count = 0
        for entry in feed.entries:
            if count >= limit:
                break

            title = entry.get("title", "").strip()
            link  = entry.get("link", "").strip()
            pub   = parse_entry_time(entry)

            if not title or not link:
                continue
            if title in seen_titles:
                continue
            # 如果能解析时间，只保留 cutoff 之后的；解析不到则保留（兜底）
            if pub and pub < cutoff:
                continue

            seen_titles.add(title)
            results.append({
                "source": feed_cfg["name"],
                "title":  title,
                "link":   link,
                "pub":    pub,
            })
            count += 1

    # 按时间倒序；没有时间的排最后
    results.sort(key=lambda x: x["pub"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return results


def fetch_gold_price() -> dict | None:
    """
    调用 gold-api.com 获取实时金价（XAU/USD）。
    完全免费、无需 API Key、无频率限制。
    """
    try:
        resp = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data
    except Exception as e:
        print(f"[WARN] 获取金价失败: {e}")
        return None


def build_message(news: list[dict], gold: dict | None) -> str:
    """拼装最终推送的 Telegram 消息（Markdown 格式）。"""
    tz_cst = timezone(timedelta(hours=8))
    now_str = datetime.now(tz_cst).strftime("%Y-%m-%d %H:%M CST")

    lines: list[str] = []
    lines.append(f"🌅 *每日早报* | {now_str}")
    lines.append("")

    # ── 金价板块 ──────────────────────────────────────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🥇 *实时金价（XAU/USD）*")

    if gold:
        price  = gold.get("price", "N/A")
        change = gold.get("ch", None)      # 价格变化
        chp    = gold.get("chp", None)     # 百分比变化

        if isinstance(price, (int, float)):
            price_str = f"${price:,.2f} / 盎司"
        else:
            price_str = str(price)

        arrow = ""
        if isinstance(chp, (int, float)):
            arrow = "📈" if chp >= 0 else "📉"
            chp_str = f"{'+' if chp >= 0 else ''}{chp:.2f}%"
            lines.append(f"  {arrow} {price_str}   {chp_str}")
        else:
            lines.append(f"  {price_str}")
    else:
        lines.append("  ⚠️ 金价数据暂时不可用")

    lines.append("")

    # ── 科技资讯板块 ──────────────────────────────────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📡 *过去 {HOURS_BACK}h 科技资讯*")

    if news:
        prev_source = None
        for item in news:
            if item["source"] != prev_source:
                lines.append(f"\n*{item['source']}*")
                prev_source = item["source"]

            title = item["title"].replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
            link  = item["link"]
            lines.append(f"• [{title}]({link})")
    else:
        lines.append("  ⚠️ 暂无最新资讯")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("_由 GitHub Actions 自动推送_")

    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str) -> None:
    """通过 Telegram Bot API 发送消息。"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "Markdown",
        # 超长消息自动分段（Telegram 单条上限 4096 字符）
        "disable_web_page_preview": True,
    }

    # 若消息超过 4096 字符，分段发送
    MAX_LEN = 4000
    if len(text) <= MAX_LEN:
        chunks = [text]
    else:
        # 按换行符切分，每块不超过 MAX_LEN
        chunks, current = [], []
        for line in text.split("\n"):
            if sum(len(l) + 1 for l in current) + len(line) > MAX_LEN:
                chunks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            chunks.append("\n".join(current))

    for chunk in chunks:
        payload["text"] = chunk
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"[OK] 消息已发送 (长度 {len(chunk)} 字符)")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    print(">> 抓取科技资讯...")
    news = fetch_news(RSS_FEEDS, HOURS_BACK, NEWS_LIMIT)
    print(f"   共获得 {len(news)} 条新闻")

    print(">> 获取实时金价...")
    gold = fetch_gold_price()
    if gold:
        print(f"   XAU/USD = {gold.get('price')}")

    print(">> 构建消息并推送 Telegram...")
    message = build_message(news, gold)
    send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
    print(">> 完成！")


if __name__ == "__main__":
    main()
