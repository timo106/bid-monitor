# -*- coding: utf-8 -*-
"""
中国招标投标公共服务平台 爬虫
http://www.cebpubservice.com/
"""

import logging
import json
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from config import MAX_RESULTS_PER_SOURCE
from .base import BaseScraper, BidItem

logger = logging.getLogger(__name__)


class CEBPubScraper(BaseScraper):
    """中国招标投标公共服务平台爬虫"""

    def __init__(self):
        super().__init__("中国招标投标公共服务平台", "http://www.cebpubservice.com")

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

        logger.info(f"[{self.source_name}] 共获取 {len(unique_results)} 条结果")
        return unique_results[:MAX_RESULTS_PER_SOURCE]

    def _search_keyword(self, keyword: str, region_keywords: list[str]) -> list[BidItem]:
        """搜索关键词"""
        items = []

        # 尝试 API 接口
        api_items = self._try_api_search(keyword, region_keywords)
        if api_items:
            return api_items

        # 降级到页面解析
        return self._try_page_search(keyword, region_keywords)

    def _try_api_search(self, keyword: str, region_keywords: list[str]) -> list[BidItem]:
        """尝试 API 接口"""
        items = []
        today = datetime.now()
        start_date = (today - timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        # 该平台常见的搜索 API
        api_url = "http://www.cebpubservice.com/ctpsp_search/searchBulletin"

        try:
            params = {
                "keyword": keyword,
                "bulletinType": "001",  # 招标公告
                "startTime": start_date,
                "endTime": end_date,
                "pageNo": 1,
                "pageSize": 20,
            }

            resp = self._request(api_url, params=params)
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    records = data.get("data", {}).get("list", [])
                    for record in records:
                        title = record.get("title", "").strip()
                        url = record.get("url", "")
                        pub_date = record.get("publishTime", "")
                        region = record.get("areaName", "")

                        # 检查地区
                        region_match = ""
                        for rk in region_keywords:
                            if rk in region or rk in title:
                                region_match = rk
                                break

                        item = BidItem(
                            title=title,
                            url=url,
                            source=self.source_name,
                            publish_date=pub_date,
                            region=region_match or region,
                        )
                        items.append(item)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug(f"[{self.source_name}] API 搜索失败: {e}")

        return items

    def _try_page_search(self, keyword: str, region_keywords: list[str]) -> list[BidItem]:
        """页面解析方式"""
        items = []

        search_url = "http://www.cebpubservice.com/jyxx/xxList"

        params = {
            "searchKeyWord": keyword,
            "bulletinType": "001",
        }

        resp = self._request(search_url, params=params)
        if not resp:
            return items

        soup = BeautifulSoup(resp.text, "lxml")

        for selector in ["ul.list li", "div.list-item", "table tbody tr"]:
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
                            url = f"http://www.cebpubservice.com{url}"

                        date_el = el.select_one("span.date, td:last-child")
                        pub_date = date_el.get_text(strip=True) if date_el else ""

                        item = BidItem(
                            title=title,
                            url=url,
                            source=self.source_name,
                            publish_date=pub_date,
                        )
                        items.append(item)
                    except Exception as e:
                        logger.warning(f"[{self.source_name}] 解析失败: {e}")
                break

        return items
