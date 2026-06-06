# -*- coding: utf-8 -*-
"""
昆明市公共资源交易中心（新网站）爬虫
http://kmszbzx.gdtzb.com/v1/
使用 Playwright 绕过阿里云WAF
"""

import re
import logging
from datetime import datetime, timedelta

from config import MAX_RESULTS_PER_SOURCE
from .base import BaseScraper, BidItem

logger = logging.getLogger(__name__)


class KunmingTZBScraper(BaseScraper):
    """昆明市公共资源交易中心爬虫（使用Playwright）"""

    def __init__(self):
        super().__init__("昆明市公共资源交易中心", "http://kmszbzx.gdtzb.com/v1/")

    def scrape(self, keywords: list[str], region_keywords: list[str]) -> list[BidItem]:
        """使用 Playwright 抓取"""
        results = []

        try:
            from playwright.sync_api import sync_playwright
            results = self._scrape_with_playwright(keywords, region_keywords)
        except ImportError:
            logger.warning("[昆明市公共资源交易中心] Playwright 未安装，跳过此数据源")
            logger.warning("安装方法: pip install playwright && playwright install chromium")
        except Exception as e:
            logger.error(f"[昆明市公共资源交易中心] 抓取失败: {e}")

        # 获取详情信息
        if results:
            results = self.enrich_items(results[:MAX_RESULTS_PER_SOURCE], max_detail=5)

        logger.info(f"[{self.source_name}] 共获取 {len(results)} 条结果")
        return results

    def _scrape_with_playwright(self, keywords: list[str], region_keywords: list[str]) -> list[BidItem]:
        """使用 Playwright 浏览器抓取"""
        from playwright.sync_api import sync_playwright

        items = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # 访问首页，等待WAF验证通过
            logger.info("[昆明市公共资源交易中心] 正在访问首页...")
            page.goto(self.base_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)  # 等待JS执行

            # 尝试找到招标信息列表页面
            # 工程招标类型的URL可能是 /v1/project 或类似路径
            urls_to_try = [
                "http://kmszbzx.gdtzb.com/v1/project",
                "http://kmszbzx.gdtzb.com/v1/list",
                "http://kmszbzx.gdtzb.com/v1/bid",
            ]

            for url in urls_to_try:
                try:
                    logger.info(f"[昆明市公共资源交易中心] 尝试访问: {url}")
                    page.goto(url, wait_until="networkidle", timeout=15000)
                    page.wait_for_timeout(2000)

                    # 检查页面内容
                    content = page.content()
                    if "招标" in content or "公告" in content:
                        logger.info(f"[昆明市公共资源交易中心] 找到列表页面: {url}")
                        items = self._parse_page_content(page, keywords, region_keywords)
                        if items:
                            break
                except Exception as e:
                    logger.debug(f"[昆明市公共资源交易中心] 访问失败: {url} - {e}")
                    continue

            browser.close()

        return items

    def _parse_page_content(self, page, keywords: list[str], region_keywords: list[str]) -> list[BidItem]:
        """解析页面内容"""
        items = []

        try:
            # 等待列表加载
            page.wait_for_selector("table, .list, .items, ul", timeout=10000)

            # 尝试多种选择器
            selectors = [
                "table tbody tr",
                ".list-item",
                ".item",
                "ul li a",
                ".news-list li",
                ".bid-list li",
            ]

            for selector in selectors:
                elements = page.query_selector_all(selector)
                if elements:
                    logger.info(f"[昆明市公共资源交易中心] 找到 {len(elements)} 个元素 ({selector})")
                    for el in elements:
                        try:
                            # 提取标题和链接
                            link = el.query_selector("a")
                            if not link:
                                continue

                            title = link.inner_text().strip()
                            url = link.get_attribute("href") or ""

                            if url and not url.startswith("http"):
                                url = f"http://kmszbzx.gdtzb.com{url}"

                            # 提取日期
                            date_el = el.query_selector("span.date, .time, td:last-child")
                            pub_date = date_el.inner_text().strip() if date_el else ""

                            # 检查是否包含关键词
                            title_lower = title.lower()
                            keyword_match = any(kw in title for kw in keywords)

                            if keyword_match:
                                item = BidItem(
                                    title=title,
                                    url=url,
                                    source=self.source_name,
                                    publish_date=pub_date,
                                    region="昆明",
                                )
                                items.append(item)
                        except Exception as e:
                            logger.warning(f"[昆明市公共资源交易中心] 解析元素失败: {e}")
                    break

        except Exception as e:
            logger.warning(f"[昆明市公共资源交易中心] 页面解析失败: {e}")

        return items
