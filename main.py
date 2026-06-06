# -*- coding: utf-8 -*-
"""
招标信息监控 - 主程序
每天定时抓取昆明地区电力建设类招标信息并发送邮件通知
"""

import sys
import logging
from datetime import datetime

from config import KEYWORDS, REGION_KEYWORDS, SOURCES
from scrapers import (
    CCGPScraper,
    YunnanGGZYScraper,
    KunmingGGZYScraper,
    CEBPubScraper,
)
from scrapers.base import BidItem
from email_sender import send_email

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_scrapers() -> list[BidItem]:
    """运行所有启用的爬虫，收集招标信息"""
    all_items = []

    scrapers = {
        "ccgp": CCGPScraper,
        "yunnan_ggzy": YunnanGGZYScraper,
        "kunming_ggzy": KunmingGGZYScraper,
        "cebpub": CEBPubScraper,
    }

    for source_key, source_config in SOURCES.items():
        if not source_config.get("enabled", True):
            logger.info(f"跳过已禁用的数据源: {source_config['name']}")
            continue

        scraper_class = scrapers.get(source_key)
        if not scraper_class:
            logger.warning(f"未找到爬虫实现: {source_key}")
            continue

        try:
            logger.info(f"开始抓取: {source_config['name']}")
            scraper = scraper_class()
            items = scraper.scrape(KEYWORDS, REGION_KEYWORDS)
            logger.info(f"{source_config['name']} 获取到 {len(items)} 条结果")
            all_items.extend(items)
        except Exception as e:
            logger.error(f"{source_config['name']} 抓取失败: {e}")

    return all_items


def deduplicate_items(items: list[BidItem]) -> list[BidItem]:
    """全局去重"""
    seen = set()
    unique_items = []
    for item in items:
        key = item.unique_key
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    return unique_items


def filter_by_region(items: list[BidItem], region_keywords: list[str]) -> list[BidItem]:
    """按地区筛选（如果爬虫未筛选，这里兜底）"""
    filtered = []
    for item in items:
        # 如果已经有地区标记，直接保留
        if item.region:
            filtered.append(item)
            continue
        # 否则检查标题中是否包含地区关键词
        for rk in region_keywords:
            if rk in item.title:
                item.region = rk
                filtered.append(item)
                break
    return filtered


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info(f"招标信息监控 启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"关键词: {', '.join(KEYWORDS)}")
    logger.info(f"地区: {', '.join(REGION_KEYWORDS)}")
    logger.info("=" * 60)

    # 1. 运行爬虫
    all_items = run_scrapers()
    logger.info(f"爬虫共获取 {len(all_items)} 条原始数据")

    # 2. 去重
    unique_items = deduplicate_items(all_items)
    logger.info(f"去重后剩余 {len(unique_items)} 条")

    # 3. 地区筛选（兜底）
    filtered_items = filter_by_region(unique_items, REGION_KEYWORDS)
    logger.info(f"地区筛选后剩余 {len(filtered_items)} 条")

    # 4. 发送邮件
    if filtered_items:
        success = send_email(filtered_items)
        if success:
            logger.info("✅ 任务完成，邮件已发送")
        else:
            logger.error("❌ 邮件发送失败")
            sys.exit(1)
    else:
        logger.info("📭 今日无符合条件的招标信息，跳过邮件发送")
        # 也可以选择发送一封"无数据"的邮件
        # send_email([])

    logger.info("程序执行完毕")


if __name__ == "__main__":
    main()
