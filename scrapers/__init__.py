# -*- coding: utf-8 -*-
"""
爬虫模块
"""

from .ccgp import CCGPScraper
from .yunnan_ggzy import YunnanGGZYScraper
from .kunming_ggzy import KunmingGGZYScraper
from .kunming_tzb import KunmingTZBScraper
from .cebpub import CEBPubScraper

__all__ = [
    "CCGPScraper",
    "YunnanGGZYScraper",
    "KunmingGGZYScraper",
    "KunmingTZBScraper",
    "CEBPubScraper",
]
