# -*- coding: utf-8 -*-
"""
爬虫基类
"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import requests

from config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY, PROXY, AI_CONFIG
from anti_crawl import (
    create_session,
    smart_request,
    random_delay,
    get_random_headers,
)
from ai_extractor import AIExtractor

logger = logging.getLogger(__name__)


@dataclass
class BidItem:
    """招标信息数据结构"""
    title: str                          # 标题
    url: str                            # 详情链接
    source: str                         # 来源网站
    publish_date: str = ""              # 发布日期
    region: str = ""                    # 地区
    amount: str = ""                    # 项目金额/预算
    category: str = ""                  # 类型（招标公告/中标公告等）
    bid_bond: str = ""                  # 投标保证金
    bid_start_time: str = ""            # 投标开始时间/开标时间
    bid_end_time: str = ""              # 投标截止时间
    contact: str = ""                   # 联系方式

    # 新增结构化字段
    bid_number: str = ""                # 招标编号
    project_name: str = ""              # 项目名称
    purchaser: str = ""                 # 招标人/采购人
    qualification: str = ""             # 资质要求
    open_location: str = ""             # 开标地点

    @property
    def unique_key(self) -> str:
        """去重用的唯一标识"""
        return f"{self.title}|{self.url}"


class BaseScraper(ABC):
    """爬虫基类"""

    def __init__(self, source_name: str, base_url: str, stop_event: Optional[threading.Event] = None):
        self.source_name = source_name
        self.base_url = base_url
        self.stop_event = stop_event
        # 使用反爬模块创建 Session（带代理、随机 UA）
        self.session = create_session(proxy=PROXY)
        # AI 提取器
        self.ai_extractor = AIExtractor(AI_CONFIG)

    def _request(self, url: str, method: str = "GET", **kwargs) -> Optional[requests.Response]:
        """发送请求，使用智能反爬策略"""
        return smart_request(
            self.session, url, method,
            max_retries=3,
            base_timeout=REQUEST_TIMEOUT,
            stop_event=self.stop_event,
            **kwargs,
        )

    @property
    def is_stopped(self) -> bool:
        """检查是否已请求停止"""
        return self.stop_event is not None and self.stop_event.is_set()

    def _sleep(self):
        """随机延迟，模拟人类行为"""
        random_delay(base=REQUEST_DELAY, jitter=2.0, stop_event=self.stop_event)

    def fetch_detail(self, item: BidItem) -> BidItem:
        """
        获取详情页信息（投标保证金、时间等）
        先用正则提取，如果关键字段缺失则用 AI 补充

        Args:
            item: 基本信息的 BidItem

        Returns:
            补充了详细信息的 BidItem
        """
        if not item.url:
            logger.debug(f"[{self.source_name}] 跳过详情获取: URL为空")
            return item

        try:
            logger.info(f"[{self.source_name}] 正在获取详情: {item.url}")
            # 使用随机化的请求头
            headers = get_random_headers(referer=self.base_url)
            resp = self._request(item.url, headers=headers)
            if not resp:
                logger.warning(f"[{self.source_name}] 详情页请求失败: {item.url}")
                return item

            logger.info(f"[{self.source_name}] 详情页获取成功, 长度: {len(resp.text)}")
            html = resp.text

            # 1. 先用正则提取
            item = self._parse_detail(html, item)

            # 2. 如果关键字段缺失，用 AI 补充
            if self.ai_extractor.is_available:
                missing = []
                if not item.bid_end_time:
                    missing.append("截止时间")
                if not item.amount:
                    missing.append("金额")
                if not item.contact:
                    missing.append("联系人")

                if missing:
                    logger.info(f"[{self.source_name}] 正则未提取到 {', '.join(missing)}，尝试 AI 提取")
                    self.ai_extractor.apply_to_item(item, html)

        except Exception as e:
            logger.warning(f"[{self.source_name}] 获取详情失败: {e}")

        return item

    def _parse_detail(self, html: str, item: BidItem) -> BidItem:
        """
        解析详情页，提取投标保证金、时间等信息
        子类应该重写此方法以适配不同网站结构

        Args:
            html: 详情页 HTML
            item: BidItem 对象

        Returns:
            补充了详细信息的 BidItem
        """
        from bs4 import BeautifulSoup
        import re

        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()

        # 提取投标保证金
        bond_patterns = [
            r"投标保证金[：:]\s*([^\n]+)",
            r"保证金[：:]\s*([^\n]+)",
            r"担保金额[：:]\s*([^\n]+)",
        ]
        for pattern in bond_patterns:
            match = re.search(pattern, text)
            if match:
                item.bid_bond = match.group(1).strip()[:100]
                break

        # 提取投标时间
        time_patterns = [
            r"投标截止时间[：:]\s*([^\n]+)",
            r"截止时间[：:]\s*([^\n]+)",
            r"报名截止[：:]\s*([^\n]+)",
        ]
        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                item.bid_end_time = match.group(1).strip()[:100]
                break

        start_patterns = [
            r"投标开始时间[：:]\s*([^\n]+)",
            r"开标时间[：:]\s*([^\n]+)",
            r"开启时间[：:]\s*([^\n]+)",
        ]
        for pattern in start_patterns:
            match = re.search(pattern, text)
            if match:
                item.bid_start_time = match.group(1).strip()[:100]
                break

        # 提取联系方式
        contact_patterns = [
            r"联系人[：:]\s*([^\n]+)",
            r"联系方式[：:]\s*([^\n]+)",
            r"联系电话[：:]\s*([^\n]+)",
            r"项目联系人[：:]\s*([^\n]+)",
        ]
        for pattern in contact_patterns:
            match = re.search(pattern, text)
            if match:
                item.contact = match.group(1).strip()[:100]
                break

        # ---------- 新增结构化字段 ----------

        # 招标编号
        bid_number_patterns = [
            r"招标编号[：:]\s*([A-Za-z0-9\-_/]+)",
            r"采购编号[：:]\s*([A-Za-z0-9\-_/]+)",
            r"项目编号[：:]\s*([A-Za-z0-9\-_/]+)",
            r"编\s*号[：:]\s*([A-Za-z0-9\-_/]+)",
            r"招标编[号碼][：:]\s*([^\n]+)",
        ]
        for pattern in bid_number_patterns:
            match = re.search(pattern, text)
            if match:
                item.bid_number = match.group(1).strip()[:80]
                break

        # 项目名称
        project_name_patterns = [
            r"项目名称[：:]\s*([^\n]+)",
            r"采购项目[：:]\s*([^\n]+)",
            r"招标项目[：:]\s*([^\n]+)",
        ]
        for pattern in project_name_patterns:
            match = re.search(pattern, text)
            if match:
                item.project_name = match.group(1).strip()[:120]
                break

        # 招标人/采购人
        purchaser_patterns = [
            r"招\s*标\s*人[：:]\s*([^\n]+)",
            r"采\s*购\s*人[：:]\s*([^\n]+)",
            r"招标单位[：:]\s*([^\n]+)",
            r"采购单位[：:]\s*([^\n]+)",
            r"业主单位[：:]\s*([^\n]+)",
        ]
        for pattern in purchaser_patterns:
            match = re.search(pattern, text)
            if match:
                item.purchaser = match.group(1).strip()[:100]
                break

        # 资质要求
        qualification_patterns = [
            r"资质要求[：:]\s*([^\n](?:[^\n]*[^\n])?)",
            r"资格要求[：:]\s*([^\n](?:[^\n]*[^\n])?)",
            r"投标人资格[：:]\s*([^\n](?:[^\n]*[^\n])?)",
            r"供应商资格[：:]\s*([^\n](?:[^\n]*[^\n])?)",
            r"具备[：]?\s*(.*?资质[^\n]*)",
        ]
        for pattern in qualification_patterns:
            match = re.search(pattern, text)
            if match:
                item.qualification = match.group(1).strip()[:200]
                break

        # 开标地点
        open_location_patterns = [
            r"开标地点[：:]\s*([^\n]+)",
            r"开标地址[：:]\s*([^\n]+)",
            r"投标地点[：:]\s*([^\n]+)",
            r"递交地点[：:]\s*([^\n]+)",
            r"采购地点[：:]\s*([^\n]+)",
        ]
        for pattern in open_location_patterns:
            match = re.search(pattern, text)
            if match:
                item.open_location = match.group(1).strip()[:150]
                break

        return item

    def enrich_items(self, items: list[BidItem], max_detail: int = 10) -> list[BidItem]:
        """
        批量获取详情信息

        Args:
            items: BidItem 列表
            max_detail: 最多获取详情的条数（避免请求过多）

        Returns:
            补充了详细信息的 BidItem 列表
        """
        enriched = []
        for i, item in enumerate(items):
            if self.is_stopped:
                logger.info(f"[{self.source_name}] 用户停止，跳过剩余详情获取")
                enriched.extend(items[i:])
                break
            if i < max_detail:
                logger.info(f"[{self.source_name}] 获取详情 ({i+1}/{min(len(items), max_detail)}): {item.title[:30]}...")
                item = self.fetch_detail(item)
                self._sleep()
            enriched.append(item)
        return enriched

    @abstractmethod
    def scrape(self, keywords: list[str], region_keywords: list[str]) -> list[BidItem]:
        """
        抓取招标信息

        Args:
            keywords: 关键词列表，如 ["电力", "电网", "供电"]
            region_keywords: 地区关键词，如 ["昆明", "云南"]

        Returns:
            BidItem 列表
        """
        pass
