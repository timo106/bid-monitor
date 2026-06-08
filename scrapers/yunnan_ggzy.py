# -*- coding: utf-8 -*-
"""
云南省公共资源交易中心 爬虫
https://ggzy.yn.gov.cn
"""

import logging
import re
import json
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from config import MAX_RESULTS_PER_SOURCE
from .base import BaseScraper, BidItem

logger = logging.getLogger(__name__)


class YunnanGGZYScraper(BaseScraper):
    """云南省公共资源交易中心爬虫"""

    def __init__(self, stop_event=None):
        super().__init__("云南省公共资源交易中心", "https://ggzy.yn.gov.cn", stop_event=stop_event)
        self.session.headers.update({
            "Referer": "https://ggzy.yn.gov.cn/",
        })

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
        items = []

        # 尝试 API 接口方式
        api_items = self._try_api_search(keyword, region_keywords)
        if api_items:
            return api_items

        # 降级到页面解析
        page_items = self._try_page_search(keyword, region_keywords)
        return page_items

    def _try_api_search(self, keyword: str, region_keywords: list[str]) -> list[BidItem]:
        """尝试通过 API 接口获取数据"""
        items = []
        today = datetime.now()
        start_date = (today - timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        # 公共资源交易中心常见的 API 路径
        api_urls = [
            "https://ggzy.yn.gov.cn/inteligentsearch/rest/ticketinfotable",
            "https://ggzy.yn.gov.cn/jyxx/queryListData",
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
                    "inc_wd": "",
                    "exc_wd": "",
                    "fields": "title",
                    "cnum": "001",
                    "sort": "{\"showdate\":\"0\"}",
                }

                resp = self._request(api_url, method="POST", json=payload)
                if resp and resp.status_code == 200:
                    try:
                        data = resp.json()
                        items = self._parse_api_response(data, region_keywords)
                        if items:
                            return items
                    except json.JSONDecodeError:
                        continue

            except Exception as e:
                logger.debug(f"[{self.source_name}] API 尝试失败: {e}")
                continue

        return items

    def _parse_api_response(self, data: dict, region_keywords: list[str]) -> list[BidItem]:
        """解析 API 返回的 JSON 数据"""
        items = []
        records = data.get("result", {}).get("records", [])
        if isinstance(records, list):
            for record in records:
                try:
                    title = record.get("title", "").strip()
                    url = record.get("url", "")
                    if url and not url.startswith("http"):
                        url = f"https://ggzy.yn.gov.cn{url}"

                    pub_date = record.get("showdate", "")

                    # 地区筛选
                    region = ""
                    text = f"{title} {record.get('districtname', '')} {record.get('tradetype', '')}"
                    for rk in region_keywords:
                        if rk in text:
                            region = rk
                            break

                    item = BidItem(
                        title=title,
                        url=url,
                        source=self.source_name,
                        publish_date=pub_date,
                        region=region,
                    )
                    items.append(item)
                except Exception as e:
                    logger.warning(f"[{self.source_name}] 解析记录失败: {e}")
        return items

    def _try_page_search(self, keyword: str, region_keywords: list[str]) -> list[BidItem]:
        """通过页面解析获取数据"""
        items = []
        search_url = f"https://ggzy.yn.gov.cn/search/index.html"

        params = {
            "keywords": keyword,
            "category": "GGZY_JYXX",
        }

        resp = self._request(search_url, params=params)
        if not resp:
            return items

        soup = BeautifulSoup(resp.text, "lxml")

        # 尝试多种选择器
        selectors = [
            "ul.search-list li",
            "div.search-list li",
            "ul.list li",
            "table tbody tr",
        ]

        for selector in selectors:
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
                            url = f"https://ggzy.yn.gov.cn{url}"

                        date_el = el.select_one("span.date, span.time, td:last-child")
                        pub_date = date_el.get_text(strip=True) if date_el else ""

                        item = BidItem(
                            title=title,
                            url=url,
                            source=self.source_name,
                            publish_date=pub_date,
                        )
                        items.append(item)
                    except Exception as e:
                        logger.warning(f"[{self.source_name}] 解析元素失败: {e}")
                break

        return items
