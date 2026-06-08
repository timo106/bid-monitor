# -*- coding: utf-8 -*-
"""
反爬虫策略模块
提供 User-Agent 轮换、随机延迟、请求头随机化、代理支持等功能
"""

import random
import time
import logging
import threading
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ============================================================
# User-Agent 池（真实浏览器 UA）
# ============================================================

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


# ============================================================
# 请求头模板
# ============================================================

ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
]

ACCEPT_LANGUAGES = [
    "zh-CN,zh;q=0.9,en;q=0.8",
    "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "zh-CN,zh;q=0.8,en;q=0.7",
    "zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7",
]

ACCEPT_ENCODINGS = [
    "gzip, deflate, br",
    "gzip, deflate",
    "gzip, deflate, br, zstd",
]


# ============================================================
# 频率限制器
# ============================================================

class RateLimiter:
    """每个域名独立的请求频率限制"""

    def __init__(self):
        self._lock = threading.Lock()
        self._domain_times: dict[str, list[float]] = {}

    def wait_if_needed(self, domain: str, max_per_minute: int = 20):
        """如果请求过于频繁，自动等待"""
        with self._lock:
            now = time.time()
            if domain not in self._domain_times:
                self._domain_times[domain] = []

            # 清理 60 秒前的记录
            self._domain_times[domain] = [
                t for t in self._domain_times[domain] if now - t < 60
            ]

            if len(self._domain_times[domain]) >= max_per_minute:
                # 计算需要等待的时间
                oldest = self._domain_times[domain][0]
                wait_time = 60 - (now - oldest) + 0.5
                if wait_time > 0:
                    logger.debug(f"[{domain}] 请求频率限制，等待 {wait_time:.1f}s")
                    time.sleep(wait_time)

            self._domain_times[domain].append(time.time())


# 全局频率限制器
rate_limiter = RateLimiter()


# ============================================================
# 核心函数
# ============================================================

def get_random_ua() -> str:
    """随机选择一个 User-Agent"""
    return random.choice(USER_AGENTS)


def get_random_headers(referer: str = None) -> dict:
    """生成随机化的请求头"""
    headers = {
        "User-Agent": get_random_ua(),
        "Accept": random.choice(ACCEPT_HEADERS),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": random.choice(ACCEPT_ENCODINGS),
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if not referer else "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": random.choice(["no-cache", "max-age=0"]),
    }
    if referer:
        headers["Referer"] = referer
    return headers


def random_delay(base: float = 1.5, jitter: float = 2.0, stop_event: Optional[threading.Event] = None):
    """
    随机延迟，模拟人类行为

    Args:
        base: 基础延迟（秒）
        jitter: 随机附加范围（0 到 jitter 秒）
        stop_event: 停止事件
    """
    delay = base + random.uniform(0, jitter)
    if stop_event:
        stop_event.wait(delay)
    else:
        time.sleep(delay)


def create_session(proxy: Optional[str] = None) -> requests.Session:
    """
    创建带反爬配置的 Session

    Args:
        proxy: 代理地址，如 "http://127.0.0.1:7897"

    Returns:
        配置好的 Session
    """
    session = requests.Session()

    # 设置默认请求头
    session.headers.update(get_random_headers())

    # 设置代理
    if proxy:
        session.proxies = {
            "http": proxy,
            "https": proxy,
        }

    # 禁用 urllib3 的重试警告
    session.verify = True

    return session


def smart_request(
    session: requests.Session,
    url: str,
    method: str = "GET",
    max_retries: int = 3,
    base_timeout: int = 15,
    stop_event: Optional[threading.Event] = None,
    **kwargs,
) -> Optional[requests.Response]:
    """
    智能请求：带指数退避重试、频率限制、随机 UA

    Args:
        session: requests.Session
        url: 请求 URL
        method: HTTP 方法
        max_retries: 最大重试次数
        base_timeout: 基础超时时间
        stop_event: 停止事件
        **kwargs: 传递给 requests 的参数

    Returns:
        Response 或 None
    """
    from urllib.parse import urlparse

    domain = urlparse(url).netloc

    # 频率限制
    rate_limiter.wait_if_needed(domain)

    kwargs.setdefault("timeout", base_timeout)

    for attempt in range(max_retries):
        if stop_event and stop_event.is_set():
            return None

        # 每次请求刷新随机 UA
        session.headers["User-Agent"] = get_random_ua()

        try:
            resp = session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 403:
                logger.warning(f"[反爬] 403 被拦截，等待后重试 ({attempt+1}/{max_retries})")
                # 403 通常意味着被反爬了，等更久
                wait = (2 ** attempt) * 3 + random.uniform(1, 3)
                _interruptible_sleep(wait, stop_event)
            elif status == 429:
                logger.warning(f"[反爬] 429 限速，等待后重试 ({attempt+1}/{max_retries})")
                wait = (2 ** attempt) * 5 + random.uniform(2, 5)
                _interruptible_sleep(wait, stop_event)
            elif status in (500, 502, 503, 504):
                logger.warning(f"[反爬] {status} 服务端错误，等待后重试 ({attempt+1}/{max_retries})")
                wait = (2 ** attempt) * 2
                _interruptible_sleep(wait, stop_event)
            else:
                logger.warning(f"[反爬] HTTP {status} 错误: {e}")
                return None

        except requests.exceptions.ConnectionError:
            logger.warning(f"[反爬] 连接失败 ({attempt+1}/{max_retries}): {url}")
            wait = (2 ** attempt) * 2 + random.uniform(0, 1)
            _interruptible_sleep(wait, stop_event)

        except requests.exceptions.Timeout:
            logger.warning(f"[反爬] 请求超时 ({attempt+1}/{max_retries}): {url}")
            # 超时后增加 timeout
            kwargs["timeout"] = base_timeout * (attempt + 2)

        except requests.exceptions.RequestException as e:
            logger.warning(f"[反爬] 请求异常 ({attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait = (2 ** attempt) * 1.5
                _interruptible_sleep(wait, stop_event)

    return None


def _interruptible_sleep(seconds: float, stop_event: Optional[threading.Event] = None):
    """可中断的等待"""
    if stop_event:
        stop_event.wait(seconds)
    else:
        time.sleep(seconds)
