# -*- coding: utf-8 -*-
"""
中国政府采购网 爬虫
http://search.ccgp.gov.cn/bxsearch
"""

import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import MAX_RESULTS_PER_SOURCE
from .base import BaseScraper, BidItem

logger = logging.getLogger(__name__)


class CCGPScraper(BaseScraper):
    """中国政府采购网爬虫"""

    def __init__(self):
        super().__init__("中国政府采购网", "http://search.ccgp.gov.cn")

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
        """按关键词搜索"""
        items = []
        today = datetime.now()
        start_date = (today - timedelta(days=3)).strftime("%Y:%m:%d")  # 最近3天
        end_date = today.strftime("%Y:%m:%d")

        params = {
            "searchtype": 1,
            "page_index": 1,
            "bidSort": 0,
            "buyerName": "",
            "projectId": "",
            "pinMu": 0,
            "bidType": 1,  # 1=招标/采购公告
            "dbselect": "bidx",
            "kw": keyword,
            "start_time": start_date,
            "end_time": end_date,
            "timeType": 2,
            "displayZone": "",
            "zoneId": "",
            "pppStatus": 0,
            "agession": 0,
        }

        for page in range(1, 4):  # 最多3页
            params["page_index"] = page
            resp = self._request(
                "http://search.ccgp.gov.cn/bxsearch",
                params=params,
                headers={"Referer": "http://search.ccgp.gov.cn/"},
            )
            if not resp:
                break

            page_items = self._parse_list_page(resp.text, region_keywords)
            if not page_items:
                break

            items.extend(page_items)
            self._sleep()

        return items

    def _parse_list_page(self, html: str, region_keywords: list[str]) -> list[BidItem]:
        """解析搜索结果页面"""
        items = []
        soup = BeautifulSoup(html, "lxml")

        # 查找结果列表
        result_list = soup.select("ul.vT-srch-result-list-bid li")
        if not result_list:
            result_list = soup.select("ul.vT-srch-result-list li")

        for li in result_list:
            try:
                link_tag = li.select_one("a")
                if not link_tag:
                    continue

                title = link_tag.get_text(strip=True)
                url = link_tag.get("href", "")

                # 提取日期
                date_span = li.select_one("span")
                pub_date = date_span.get_text(strip=True) if date_span else ""

                # 提取地区信息
                region = ""
                region_text = li.get_text()
                for rk in region_keywords:
                    if rk in region_text:
                        region = rk
                        break

                # 也检查标题中是否包含地区
                if not region:
                    for rk in region_keywords:
                        if rk in title:
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
                logger.warning(f"[{self.source_name}] 解析条目失败: {e}")
                continue

        return items
