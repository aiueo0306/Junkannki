from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from urllib.parse import urljoin
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://iryohokenjyoho.service-now.com/csm?id=csm_index"
DEFAULT_LINK = "https://iryohokenjyoho.service-now.com/csm?id=kb_search&kb_knowledge_base=..."  # ← 実際のURLに書き換えてください

def generate_rss(items, output_path):
    fg = FeedGenerator()
    fg.title("医療機関向等総合ポータルサイト")
    fg.link(href=DEFAULT_LINK)
    fg.description("医療機関向等総合ポータルサイトページの更新履歴")
    fg.language("ja")
    fg.generator("python-feedgen")
    fg.docs("http://www.rssboard.org/rss-specification")
    fg.lastBuildDate(datetime.now(timezone.utc))

    for item in items:
        entry = fg.add_entry()
        entry.title(item['title'])
        entry.link(href=item['link'])
        entry.description(item['description'])
        guid_value = f"{item['link']}#{item['pub_date'].strftime('%Y%m%d')}"
        entry.guid(guid_value, permalink=False)
        entry.pubDate(item['pub_date'])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fg.rss_file(output_path)
    print(f"\n✅ RSSフィード生成完了！📄 保存先: {output_path}")

def extract_items(page):
    page.goto(DEFAULT_LINK, timeout=30000)
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("div.summary-templates", timeout=10000)

    selector = "div.summary-templates > div.kb-template.ng-scope > div:nth-child(2) > div > div > div"
    rows = page.locator(selector)
    count = rows.count()
    print(f"📦 発見した更新情報行数: {count}")
    items = []

    for i in range(count):
        row = rows.nth(i)
        try:
            time_elem = row.locator("sn-time-ago > time")
            time_str = time_elem.get_attribute("title")
            if time_str:
                pub_date = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            else:
                pub_date = datetime.now(timezone.utc)

            description_html = row.locator("div.kb-description").inner_text().strip()

            a_links = row.locator("a")
            first_link = DEFAULT_LINK
            if a_links.count() > 0:
                href = a_links.first.get_attribute("href")
                if href:
                    first_link = urljoin(BASE_URL, href)

            items.append({
                "title": f"更新情報: {pub_date.strftime('%Y-%m-%d')}",
                "link": first_link,
                "description": description_html,
                "pub_date": pub_date
            })

        except Exception as e:
            print(f"⚠ 行{i+1}の解析に失敗: {e}")
            continue

    return items

# ===== 実行ブロック =====
with sync_playwright() as p:
    print("▶ ブラウザを起動中...")
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        print("▶ ページにアクセス中...")
        page.goto(DEFAULT_LINK, timeout=30000)
        page.wait_for_load_state("load", timeout=30000)
    except PlaywrightTimeoutError:
        print("⚠ ページの読み込みに失敗しました。")
        browser.close()
        exit()

    print("▶ 更新情報を抽出しています...")
    items = extract_items(page)

    if not items:
        print("⚠ 抽出できた更新情報がありません。HTML構造が変わっている可能性があります。")

    rss_path = "rss_output/IryokikanPortal.xml"
    generate_rss(items, rss_path)
    browser.close()
