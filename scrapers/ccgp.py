# -*- coding: utf-8 -*-
"""
中国政府采购网 爬虫
http://search.ccgp.gov.cn/bxsearch
"""

import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import MAX_RESULTS_PER_SOURCE
from .base import BaseScraper, BidItem

logger = logging.getLogger(__name__)


class CCGPScraper(BaseScraper):
    """中国政府采购网爬虫"""

    def __init__(self, stop_event=None):
        super().__init__("中国政府采购网", "http://search.ccgp.gov.cn", stop_event=stop_event)

    def _parse_detail(self, html: str, item: BidItem) -> BidItem:
        """解析中国政府采购网详情页"""
        soup = BeautifulSoup(html, "lxml")

        # 方法1: 从概要表格中提取
        table = soup.select_one("div.table table")
        if table:
            rows = table.select("tr")
            for row in rows:
                cells = row.select("td")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)

                    if "预算金额" in label or "采购预算" in label:
                        item.amount = value
                    elif "开标时间" in label:
                        item.bid_start_time = value
                    elif "获取招标文件时间" in label:
                        if not item.bid_end_time:
                            # 提取结束时间
                            match = re.search(r"至(.+?)(?:\n|$)", value)
                            if match:
                                item.bid_end_time = match.group(1).strip()
                    elif "项目联系人" in label:
                        item.contact = value
                    elif "项目联系电话" in label or "联系方式" in label:
                        if item.contact:
                            item.contact = f"{item.contact} / {value}"
                        else:
                            item.contact = value

        # 方法2: 从正文内容中提取（更精确）
        content = soup.select_one("div.vF_detail_content")
        if content:
            text = content.get_text()

            # 提取投标截止时间
            deadline_patterns = [
                r"提交投标文件截止时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
                r"投标截止时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
                r"截止时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
            ]
            for pattern in deadline_patterns:
                match = re.search(pattern, text)
                if match:
                    item.bid_end_time = match.group(1).strip()
                    break

            # 提取开标时间
            open_patterns = [
                r"开标时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
            ]
            for pattern in open_patterns:
                match = re.search(pattern, text)
                if match:
                    item.bid_start_time = match.group(1).strip()
                    break

            # 提取投标保证金
            bond_patterns = [
                r"投标保证金[：:]\s*([^\n]+)",
                r"是否需要缴纳投标保证金[：:]\s*([^\n]+)",
                r"保证金金额[：:]\s*([^\n]+)",
                r"担保金额[：:]\s*([^\n]+)",
            ]
            for pattern in bond_patterns:
                match = re.search(pattern, text)
                if match:
                    item.bid_bond = match.group(1).strip()[:100]
                    break

            # 提取预算金额
            if not item.amount:
                budget_patterns = [
                    r"预算金额[（(]元[）)][：:]\s*([\d,.]+)",
                    r"预算金额[：:]\s*([\d,.]+万元?)",
                    r"采购预算[：:]\s*([\d,.]+万元?)",
                ]
                for pattern in budget_patterns:
                    match = re.search(pattern, text)
                    if match:
                        item.amount = match.group(1).strip()
                        break

            # 提取联系人
            if not item.contact:
                contact_patterns = [
                    r"项目联系人[：:]\s*([^\n]+)",
                    r"联系人[：:]\s*([^\n]+)",
                ]
                for pattern in contact_patterns:
                    match = re.search(pattern, text)
                    if match:
                        item.contact = match.group(1).strip()[:50]
                        break

        # 方法3: 从 samp 标签中提取（最精确）
        # 投标截止时间
        deadline_samp = soup.select_one("samp.code-23011")
        if deadline_samp:
            item.bid_end_time = deadline_samp.get_text(strip=True)

        # 开标时间
        open_samp = soup.select_one("samp.code-23013")
        if open_samp and not item.bid_start_time:
            item.bid_start_time = open_samp.get_text(strip=True)

        # 投标保证金
        bond_samp = soup.select_one("samp.code-tenderDepositInfo")
        if bond_samp:
            item.bid_bond = bond_samp.get_text(strip=True)

        # 预算金额
        budget_samp = soup.select_one("samp.code-AM01400034")
        if budget_samp and not item.amount:
            amount_text = budget_samp.get_text(strip=True)
            try:
                amount = float(amount_text)
                if amount >= 10000:
                    item.amount = f"{amount/10000:.2f}万元"
                else:
                    item.amount = f"{amount}元"
            except ValueError:
                item.amount = amount_text

        return item

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

                # 确保 URL 是完整地址
                if url and not url.startswith("http"):
                    url = f"http://www.ccgp.gov.cn{url}"

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
