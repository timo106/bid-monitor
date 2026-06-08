# -*- coding: utf-8 -*-
"""
昆明市公共资源交易网 爬虫
http://ggzy.km.gov.cn
"""

import logging
import json
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from config import MAX_RESULTS_PER_SOURCE
from .base import BaseScraper, BidItem

logger = logging.getLogger(__name__)


class KunmingGGZYScraper(BaseScraper):
    """昆明市公共资源交易网爬虫"""

    def __init__(self, stop_event=None):
        super().__init__("昆明市公共资源交易网", "http://ggzy.km.gov.cn", stop_event=stop_event)

    def scrape(self, keywords: list[str], region_keywords: list[str]) -> list[BidItem]:
        results = []

        for keyword in keywords:
            logger.info(f"[{self.source_name}] 搜索关键词: {keyword}")
            items = self._search_keyword(keyword, region_keywords)
            results.extend(items)
            self._sleep()

        # 去重
        seen = set()
        unique_results = []
        for item in results:
            if item.unique_key not in seen:
                seen.add(item.unique_key)
                unique_results.append(item)

        # 获取详情信息
        unique_results = self.enrich_items(unique_results[:MAX_RESULTS_PER_SOURCE], max_detail=5)

        logger.info(f"[{self.source_name}] 共获取 {len(unique_results)} 条结果")
        return unique_results

    def _search_keyword(self, keyword: str, region_keywords: list[str]) -> list[BidItem]:
        """按关键词搜索"""
        # 尝试 API 方式
        api_items = self._try_api_search(keyword)
        if api_items:
            return api_items

        # 降级到页面解析
        return self._try_page_search(keyword)

    def _try_api_search(self, keyword: str) -> list[BidItem]:
        """尝试 API 接口"""
        items = []
        today = datetime.now()
        start_date = (today - timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        # 昆明公共资源交易中心可能的 API
        api_urls = [
            "http://ggzy.km.gov.cn/inteligentsearch/rest/ticketinfotable",
            "http://ggzy.km.gov.cn/jyxx/queryListData",
        ]

        for api_url in api_urls:
            try:
                payload = {
                    "token": "",
                    "pn": 1,
                    "rn": 20,
                    "sdt": start_date,
                    "edt": end_date,
                    "wd": keyword,
                    "fields": "title",
                    "sort": "{\"showdate\":\"0\"}",
                }

                resp = self._request(api_url, method="POST", json=payload)
                if resp and resp.status_code == 200:
                    try:
                        data = resp.json()
                        items = self._parse_api_response(data)
                        if items:
                            return items
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                logger.debug(f"[{self.source_name}] API 尝试失败: {e}")

        return items

    def _parse_api_response(self, data: dict) -> list[BidItem]:
        """解析 API 响应"""
        items = []
        records = data.get("result", {}).get("records", [])
        if isinstance(records, list):
            for record in records:
                try:
                    title = record.get("title", "").strip()
                    url = record.get("url", "")
                    if url and not url.startswith("http"):
                        url = f"http://ggzy.km.gov.cn{url}"

                    pub_date = record.get("showdate", "")

                    item = BidItem(
                        title=title,
                        url=url,
                        source=self.source_name,
                        publish_date=pub_date,
                        region="昆明",
                    )
                    items.append(item)
                except Exception as e:
                    logger.warning(f"[{self.source_name}] 解析记录失败: {e}")
        return items

    def _try_page_search(self, keyword: str) -> list[BidItem]:
        """页面解析方式"""
        items = []
        search_url = "http://ggzy.km.gov.cn/search/index.html"

        resp = self._request(search_url, params={"keywords": keyword})
        if not resp:
            return items

        soup = BeautifulSoup(resp.text, "lxml")

        for selector in ["ul.search-list li", "ul.list li", "table tbody tr"]:
            elements = soup.select(selector)
            if elements:
                for el in elements:
                    try:
                        link = el.select_one("a")
                        if not link:
                            continue

                        title = link.get_text(strip=True)
                        url = link.get("href", "")
                        if url and not url.startswith("http"):
                            url = f"http://ggzy.km.gov.cn{url}"

                        date_el = el.select_one("span.date, span.time")
                        pub_date = date_el.get_text(strip=True) if date_el else ""

                        item = BidItem(
                            title=title,
                            url=url,
                            source=self.source_name,
                            publish_date=pub_date,
                            region="昆明",
                        )
                        items.append(item)
                    except Exception as e:
                        logger.warning(f"[{self.source_name}] 解析失败: {e}")
                break

        return items
