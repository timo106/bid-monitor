# -*- coding: utf-8 -*-
"""
招标信息监控 - 主程序
每天定时抓取昆明地区电力建设类招标信息并发送邮件通知
"""

import sys
import logging
import threading
from datetime import datetime
from typing import Optional

from config import KEYWORDS, REGION_KEYWORDS, SOURCES, KEYWORD_SYNONYMS, EXCLUDE_WORDS
from scrapers import (
    CCGPScraper,
    YunnanGGZYScraper,
    KunmingGGZYScraper,
    KunmingTZBScraper,
    CEBPubScraper,
)
from scrapers.base import BidItem
from keyword_filter import keyword_match
from email_sender import send_email

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_scrapers(stop_event: Optional[threading.Event] = None) -> list[BidItem]:
    """运行所有启用的爬虫，收集招标信息"""
    all_items = []

    scrapers = {
        "ccgp": CCGPScraper,
        "yunnan_ggzy": YunnanGGZYScraper,
        "kunming_ggzy": KunmingGGZYScraper,
        "kunming_tzb": KunmingTZBScraper,
        "cebpub": CEBPubScraper,
    }

    for source_key, source_config in SOURCES.items():
        if stop_event and stop_event.is_set():
            logger.info("用户请求停止，中断爬取")
            break

        if not source_config.get("enabled", True):
            logger.info(f"跳过已禁用的数据源: {source_config['name']}")
            continue

        scraper_class = scrapers.get(source_key)
        if not scraper_class:
            logger.warning(f"未找到爬虫实现: {source_key}")
            continue

        try:
            logger.info(f"开始抓取: {source_config['name']}")
            scraper = scraper_class(stop_event=stop_event)
            items = scraper.scrape(KEYWORDS, REGION_KEYWORDS)
            logger.info(f"{source_config['name']} 获取到 {len(items)} 条结果")
            all_items.extend(items)
        except Exception as e:
            logger.error(f"{source_config['name']} 抓取失败: {e}")

    return all_items


def deduplicate_items(items: list[BidItem]) -> list[BidItem]:
    """全局去重"""
    seen = set()
    unique_items = []
    for item in items:
        key = item.unique_key
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    return unique_items


def filter_by_region(items: list[BidItem], region_keywords: list[str]) -> list[BidItem]:
    """按地区筛选，只保留目标地区的招标信息"""
    filtered = []
    for item in items:
        # 检查标题或已有地区标记中是否包含目标地区关键词
        for rk in region_keywords:
            if rk in item.title or rk in item.region:
                item.region = rk
                filtered.append(item)
                break
    return filtered


def filter_by_keywords(items: list[BidItem], keywords: list[str]) -> list[BidItem]:
    """使用智能关键词筛选（同义词扩展 + 排除词过滤）"""
    filtered = []
    for item in items:
        match, matched_kw = keyword_match(
            item.title, keywords,
            synonyms=KEYWORD_SYNONYMS,
            exclude_words=EXCLUDE_WORDS,
        )
        if match:
            filtered.append(item)
    logger.info(f"[关键词筛选] {len(items)} 条 → {len(filtered)} 条匹配")
    return filtered


def sort_by_region(items: list[BidItem], region_keywords: list[str]) -> list[BidItem]:
    """按地区排序，目标地区的排在前面"""
    def sort_key(item):
        # 如果是目标地区，排在前面（返回0），否则排在后面（返回1）
        for rk in region_keywords:
            if rk in item.region:
                return 0
        return 1
    return sorted(items, key=sort_key)


def _enrich_items(items: list[BidItem], stop_event: Optional[threading.Event] = None):
    """
    对邮件中的条目提取结构化信息
    - ccgp 条目：HTTP 请求直接提取
    - gdtzb 条目：Playwright 渲染后提取
    """
    from scrapers.base import BaseScraper
    from anti_crawl import create_session, smart_request, get_random_headers
    from config import PROXY
    from bs4 import BeautifulSoup

    # 分组：需要 HTTP 提取的 和 需要 Playwright 提取的
    http_items = []
    pw_items = []
    skip_count = 0

    for item in items:
        if stop_event and stop_event.is_set():
            break
        if item.bid_number or item.purchaser or item.amount:
            skip_count += 1
            continue
        if not item.url:
            continue
        if "gdtzb.com" in item.url:
            pw_items.append(item)
        else:
            http_items.append(item)

    logger.info(f"需提取: HTTP {len(http_items)} 条, Playwright {len(pw_items)} 条, 已有数据 {skip_count} 条")

    # --- HTTP 提取（ccgp 等） ---
    enrich_count = 0
    if http_items:
        sess = create_session(proxy=PROXY)
        for item in http_items:
            if stop_event and stop_event.is_set():
                break
            try:
                resp = smart_request(sess, item.url, headers=get_random_headers(referer="http://search.ccgp.gov.cn/"))
                if resp:
                    soup = BeautifulSoup(resp.text, "lxml")
                    content = soup.select_one("div.vF_detail_content") or soup
                    BaseScraper._parse_detail(None, str(content), item)
                    enrich_count += 1
            except Exception as e:
                logger.debug(f"HTTP提取失败: {item.title[:30]}... {e}")
        logger.info(f"HTTP提取完成: {enrich_count}/{len(http_items)} 条")

    # --- Playwright 提取（gdtzb.com） ---
    if pw_items:
        pw_count = _enrich_with_playwright(pw_items, stop_event)
        logger.info(f"Playwright提取完成: {pw_count}/{len(pw_items)} 条")


def _enrich_with_playwright(items: list[BidItem], stop_event=None) -> int:
    """用 Playwright 渲染 gdtzb.com 详情页并提取结构化信息"""
    from scrapers.base import BaseScraper
    from bs4 import BeautifulSoup

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright 未安装，跳过 gdtzb 提取")
        return 0

    count = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            # 注入反检测脚本
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                window.chrome = { runtime: {} };
            """)
            page = context.new_page()

            for item in items:
                if stop_event and stop_event.is_set():
                    break
                try:
                    logger.info(f"[Playwright] 提取: {item.title[:40]}...")
                    page.goto(item.url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(3000)

                    # 检查是否遇到验证码
                    html = page.content()
                    if "滑动验证" in html or "访问验证" in html:
                        logger.warning(f"[Playwright] 遇到验证码，跳过: {item.title[:30]}...")
                        continue

                    soup = BeautifulSoup(html, "lxml")

                    # 尝试找正文区域
                    content = (
                        soup.select_one("div.detail-content") or
                        soup.select_one("div.content") or
                        soup.select_one("div.article-content") or
                        soup.select_one("div.main-content") or
                        soup.select_one("article") or
                        soup.select_one("main") or
                        soup
                    )

                    BaseScraper._parse_detail(None, str(content), item)
                    count += 1
                    logger.info(f"[Playwright] 成功: 编号={item.bid_number or '-'}, 招标人={item.purchaser or '-'}")
                except Exception as e:
                    logger.warning(f"[Playwright] 提取失败: {item.title[:30]}... {e}")

            browser.close()
    except Exception as e:
        logger.error(f"[Playwright] 浏览器启动失败: {e}")

    return count


def main(stop_event: Optional[threading.Event] = None):
    """
    主函数

    Args:
        stop_event: 可选的停止事件，用于从 GUI 中断执行

    Returns:
        dict: 运行结果摘要
    """
    logger.info("=" * 60)
    logger.info(f"招标信息监控 启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"关键词: {', '.join(KEYWORDS)}")
    logger.info(f"地区: {', '.join(REGION_KEYWORDS)}")
    logger.info("=" * 60)

    result = {"total": 0, "filtered": 0, "email_sent": False, "stopped": False}

    # 1. 运行爬虫
    all_items = run_scrapers(stop_event)
    result["total"] = len(all_items)
    logger.info(f"爬虫共获取 {len(all_items)} 条原始数据")

    if stop_event and stop_event.is_set():
        result["stopped"] = True
        logger.info("程序已被用户停止")
        return result

    # 2. 去重
    unique_items = deduplicate_items(all_items)
    logger.info(f"去重后剩余 {len(unique_items)} 条")

    # 3. 智能关键词筛选（同义词扩展 + 排除词过滤）
    keyword_items = filter_by_keywords(unique_items, KEYWORDS)
    logger.info(f"关键词筛选后剩余 {len(keyword_items)} 条")

    # 4. 地区筛选（只保留云南/昆明）
    filtered_items = filter_by_region(keyword_items, REGION_KEYWORDS)
    result["filtered"] = len(filtered_items)
    logger.info(f"地区筛选后剩余 {len(filtered_items)} 条")

    # 5. 结构化信息提取（只提取邮件中的条目）
    if filtered_items:
        logger.info("开始提取结构化信息...")
        _enrich_items(filtered_items, stop_event)

    # 6. 发送邮件
    if stop_event and stop_event.is_set():
        result["stopped"] = True
        logger.info("程序已被用户停止")
        return result

    if filtered_items:
        success = send_email(filtered_items)
        if success:
            result["email_sent"] = True
            logger.info("✅ 任务完成，邮件已发送")
        else:
            logger.error("❌ 邮件发送失败")
    else:
        logger.info("📭 今日无符合条件的招标信息，跳过邮件发送")

    logger.info("程序执行完毕")
    return result


if __name__ == "__main__":
    main()
