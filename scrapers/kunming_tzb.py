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
        from urllib.parse import quote

        items = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # 使用搜索功能搜索每个关键词，筛选云南地区(area_id=25)
            for keyword in keywords:
                logger.info(f"[昆明市公共资源交易中心] 搜索关键词: {keyword}")
                # areaid=25 是云南，type=10 是工程招标
                search_url = f"http://www.gdtzb.com/zb/search.php?kw={quote(keyword)}&areaid=25&type=10"

                try:
                    page.goto(search_url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(5000)  # 增加等待时间，让验证码自动通过

                    # 解析搜索结果
                    keyword_items = self._parse_search_results(page, keyword, region_keywords)
                    items.extend(keyword_items)
                    logger.info(f"[昆明市公共资源交易中心] 关键词 '{keyword}' 找到 {len(keyword_items)} 条结果")
                except Exception as e:
                    logger.warning(f"[昆明市公共资源交易中心] 搜索 '{keyword}' 失败: {e}")

            browser.close()

        return items

    def _parse_page_content(self, page, keywords: list[str], region_keywords: list[str]) -> list[BidItem]:
        """解析页面内容"""
        items = []

        try:
            # 等待列表加载
            page.wait_for_selector("div.pdbox ul li", timeout=10000)

            # 获取所有列表项
            list_items = page.query_selector_all("div.pdbox ul li")
            logger.info(f"[昆明市公共资源交易中心] 找到 {len(list_items)} 个列表项")

            for li in list_items:
                try:
                    # 提取链接和标题
                    link = li.query_selector("a")
                    if not link:
                        continue

                    title = link.inner_text().strip()
                    url = link.get_attribute("href") or ""

                    if url and not url.startswith("http"):
                        url = f"http://kmszbzx.gdtzb.com{url}"

                    # 提取日期
                    date_span = li.query_selector("span.fr")
                    pub_date = date_span.inner_text().strip() if date_span else ""

                    # 检查是否包含关键词
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
                        logger.info(f"[昆明市公共资源交易中心] 找到匹配: {title[:50]}...")
                except Exception as e:
                    logger.warning(f"[昆明市公共资源交易中心] 解析元素失败: {e}")

        except Exception as e:
            logger.warning(f"[昆明市公共资源交易中心] 页面解析失败: {e}")

        return items

    def _parse_search_results(self, page, keyword: str, region_keywords: list[str]) -> list[BidItem]:
        """解析搜索结果"""
        items = []

        try:
            # 等待搜索结果加载，增加超时时间
            page.wait_for_selector("li.tender-list", timeout=30000)

            # 获取所有搜索结果
            result_elements = page.query_selector_all("li.tender-list")
            logger.info(f"[昆明市公共资源交易中心] 找到 {len(result_elements)} 个搜索结果")

            for el in result_elements:
                try:
                    # 提取标题和链接
                    title_link = el.query_selector("div.tender-title a")
                    if not title_link:
                        continue

                    title = title_link.inner_text().strip()
                    url = title_link.get_attribute("href") or ""

                    # 只处理招标公告链接
                    if not url or "g-zb-" not in url:
                        continue

                    # 提取日期
                    date_el = el.query_selector("div.tender-other p.date")
                    pub_date = date_el.inner_text().strip() if date_el else ""

                    item = BidItem(
                        title=title,
                        url=url,
                        source=self.source_name,
                        publish_date=pub_date,
                        region="云南",
                    )
                    items.append(item)
                    logger.info(f"[昆明市公共资源交易中心] 找到: {title[:50]}...")
                except Exception as e:
                    logger.warning(f"[昆明市公共资源交易中心] 解析搜索结果失败: {e}")

        except Exception as e:
            # 如果超时，尝试直接解析页面内容
            logger.warning(f"[昆明市公共资源交易中心] 搜索结果解析失败，尝试直接解析页面: {e}")
            try:
                # 获取页面HTML内容
                html = page.content()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'lxml')

                # 查找所有招标链接
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    title = a.get_text(strip=True)

                    if 'g-zb-' in href and title and len(title) > 10:
                        # 检查是否包含关键词
                        if any(kw in title for kw in ['电力', '电网', '供电', '变电站', '输变电']):
                            item = BidItem(
                                title=title,
                                url=href,
                                source=self.source_name,
                                region="云南",
                            )
                            items.append(item)
                            logger.info(f"[昆明市公共资源交易中心] 找到(备用): {title[:50]}...")
            except Exception as e2:
                logger.warning(f"[昆明市公共资源交易中心] 备用解析也失败: {e2}")

        return items
