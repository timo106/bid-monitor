# -*- coding: utf-8 -*-
"""
爬虫基类
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import requests

from config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY

logger = logging.getLogger(__name__)


@dataclass
class BidItem:
    """招标信息数据结构"""
    title: str                          # 标题
    url: str                            # 详情链接
    source: str                         # 来源网站
    publish_date: str = ""              # 发布日期
    region: str = ""                    # 地区
    amount: str = ""                    # 金额
    category: str = ""                  # 类型（招标公告/中标公告等）

    @property
    def unique_key(self) -> str:
        """去重用的唯一标识"""
        return f"{self.title}|{self.url}"


class BaseScraper(ABC):
    """爬虫基类"""

    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    def _request(self, url: str, method: str = "GET", **kwargs) -> Optional[requests.Response]:
        """发送请求，带重试和错误处理"""
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        for attempt in range(3):
            try:
                resp = self.session.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                logger.warning(f"[{self.source_name}] 请求失败 (第{attempt+1}次): {e}")
                if attempt < 2:
                    time.sleep(REQUEST_DELAY * (attempt + 1))
        return None

    def _sleep(self):
        """请求间隔"""
        time.sleep(REQUEST_DELAY)

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
