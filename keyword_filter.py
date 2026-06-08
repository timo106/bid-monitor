# -*- coding: utf-8 -*-
"""
关键词筛选优化模块
支持模糊匹配、同义词扩展、排除词过滤
"""

import logging
import difflib
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 同义词表
# ============================================================

DEFAULT_SYNONYMS = {
    "电力": ["供配电", "电力工程", "电力系统", "电力设施", "电力设备", "电力改造", "电力线路"],
    "电网": ["输电网", "配电网", "电网建设", "电网改造", "电网工程"],
    "供电": ["配电", "供电服务", "供电工程", "供电系统"],
    "变电站": ["变电所", "开关站", "变电工程", "变电站建设"],
    "输变电": ["输变电工程", "输变电线路", "输电", "送电", "输电线路"],
}

# 排除词：标题包含这些词的认为不相关
DEFAULT_EXCLUDE_WORDS = [
    "电子商务", "电子商城", "电子招标", "电子投标",
    "电影", "电影院", "电视剧",
    "电脑", "电脑配件", "计算机耗材",
    "电话", "电话机", "电话会议",
    "电梯", "电梯维保",
    "电焊", "电焊机",
    "电池", "蓄电池", "锂电池",
    "电动汽车", "电动车",
    "电视", "电视机",
    "电磁", "电磁阀",
    "电气",  # 电气和电力不同，但可能相关，先不排除
]


def keyword_match(
    text: str,
    keywords: list[str],
    synonyms: Optional[dict[str, list[str]]] = None,
    exclude_words: Optional[list[str]] = None,
    threshold: float = 0.75,
) -> tuple[bool, list[str]]:
    """
    智能关键词匹配

    Args:
        text: 要匹配的文本（标题或正文）
        keywords: 关键词列表
        synonyms: 同义词表（可选）
        exclude_words: 排除词列表（可选）
        threshold: 模糊匹配相似度阈值（0-1）

    Returns:
        (是否匹配, 匹配到的关键词列表)
    """
    if not text or not keywords:
        return False, []

    # 使用默认值
    if synonyms is None:
        synonyms = DEFAULT_SYNONYMS
    if exclude_words is None:
        exclude_words = DEFAULT_EXCLUDE_WORDS

    text_lower = text.lower()
    matched = []

    # 1. 检查排除词
    for excl in exclude_words:
        if excl in text_lower:
            # 如果排除词匹配，但同时有精确关键词匹配，则不排除
            # 这是为了处理"电力电梯"这种情况
            has_exact = any(kw in text_lower for kw in keywords)
            if not has_exact:
                logger.debug(f"[关键词] 排除词命中: '{excl}' in '{text[:50]}...'")
                return False, []

    # 2. 精确匹配关键词
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)

    # 3. 同义词匹配
    for kw in keywords:
        if kw in synonyms:
            for syn in synonyms[kw]:
                if syn.lower() in text_lower and kw not in matched:
                    matched.append(kw)
                    break

    # 4. 模糊匹配（对较长的关键词做模糊匹配）
    if not matched:
        for kw in keywords:
            if len(kw) >= 2:
                # 在文本中滑动窗口查找相似词
                for i in range(len(text_lower) - len(kw) + 2):
                    window = text_lower[i:i + len(kw) + 1]
                    ratio = difflib.SequenceMatcher(None, kw.lower(), window).ratio()
                    if ratio >= threshold:
                        matched.append(f"{kw}(模糊)")
                        break

    is_match = len(matched) > 0
    return is_match, matched


def filter_items_by_keyword(
    items: list,
    keywords: list[str],
    synonyms: Optional[dict[str, list[str]]] = None,
    exclude_words: Optional[list[str]] = None,
) -> list:
    """
    对 BidItem 列表进行关键词筛选

    Args:
        items: BidItem 列表
        keywords: 关键词列表
        synonyms: 同义词表
        exclude_words: 排除词列表

    Returns:
        匹配的 BidItem 列表
    """
    filtered = []
    for item in items:
        # 检查标题
        title_match, title_kw = keyword_match(
            item.title, keywords, synonyms, exclude_words
        )
        # 也检查已有的一些文本字段
        extra_text = f"{getattr(item, 'category', '')} {getattr(item, 'region', '')}"
        extra_match, extra_kw = keyword_match(
            extra_text, keywords, synonyms, exclude_words
        )

        if title_match or extra_match:
            all_kw = list(set(title_kw + extra_kw))
            # 可以把匹配到的关键词记录下来
            if hasattr(item, '_matched_keywords'):
                item._matched_keywords = all_kw
            filtered.append(item)

    logger.info(f"[关键词筛选] {len(items)} 条 → {len(filtered)} 条匹配")
    return filtered
