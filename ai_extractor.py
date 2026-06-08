# -*- coding: utf-8 -*-
"""
AI 智能信息提取模块
使用 Claude / OpenAI API 从招标页面中提取结构化信息
"""

import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ============================================================
# 提取 Prompt
# ============================================================

EXTRACT_PROMPT = """你是一个专业的招标信息分析师。请从以下招标公告文本中提取结构化信息。

要求：
1. 只提取文本中明确写明的信息，不要猜测
2. 如果某个字段找不到，返回空字符串 ""
3. 金额统一转换为"万元"单位，保留2位小数
4. 时间格式统一为 "YYYY年MM月DD日 HH:MM"
5. 返回严格的 JSON 格式，不要添加任何其他文字

提取字段：
- amount: 项目预算/金额
- bid_bond: 投标保证金
- bid_end_time: 投标截止时间
- bid_start_time: 开标时间/投标开始时间
- contact: 联系人姓名
- phone: 联系电话
- category: 公告类型（招标公告/中标公告/竞争性谈判/询价公告/其他）
- project_type: 项目类型（工程/货物/服务）

招标公告文本：
{text}

请返回 JSON 格式（不要包含 ```json 标记）："""


# ============================================================
# AI 提取器
# ============================================================

class AIExtractor:
    """AI 智能信息提取器"""

    def __init__(self, config: dict):
        """
        初始化 AI 提取器

        Args:
            config: AI 配置字典，包含 provider, api_key, model 等
        """
        self.provider = config.get("provider", "claude")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.enabled = config.get("enabled", False)
        self.max_calls = config.get("max_calls_per_run", 20)
        self._call_count = 0
        self._client = None

        if self.enabled and self.api_key:
            self._init_client()

    # 各提供商的 API 地址
    PROVIDER_ENDPOINTS = {
        "doubao": "https://ark.cn-beijing.volces.com/api/v3",   # 火山引擎
        "deepseek": "https://api.deepseek.com",                  # DeepSeek
        "openai": "https://api.openai.com/v1",                   # OpenAI
    }

    def _init_client(self):
        """初始化 API 客户端"""
        try:
            if self.provider == "claude":
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            elif self.provider in ("openai", "doubao", "deepseek"):
                import openai
                base_url = self.PROVIDER_ENDPOINTS.get(self.provider)
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                )
            else:
                logger.error(f"不支持的 AI 提供商: {self.provider}，支持: claude/openai/doubao/deepseek")
                self.enabled = False
        except ImportError as e:
            logger.error(f"AI 库未安装: {e}")
            self.enabled = False

    @property
    def is_available(self) -> bool:
        """AI 提取器是否可用"""
        return self.enabled and self._client is not None and self._call_count < self.max_calls

    def extract_from_html(self, html: str) -> dict:
        """
        从 HTML 页面中提取结构化信息

        Args:
            html: 招标详情页 HTML

        Returns:
            提取结果字典
        """
        if not self.is_available:
            return {}

        # 清洗 HTML 为纯文本
        text = self._clean_html(html)
        if not text or len(text) < 50:
            logger.debug("[AI] 文本太短，跳过提取")
            return {}

        # 截断过长的文本（节省 token）
        if len(text) > 4000:
            text = text[:4000] + "\n...(文本已截断)"

        # 调用 API
        prompt = EXTRACT_PROMPT.format(text=text)
        result = self._call_api(prompt)

        if result:
            self._call_count += 1
            logger.info(f"[AI] 提取成功 (第{self._call_count}次调用)")

        return result

    def extract_from_text(self, text: str) -> dict:
        """
        从纯文本中提取结构化信息

        Args:
            text: 招标公告纯文本

        Returns:
            提取结果字典
        """
        if not self.is_available:
            return {}

        if not text or len(text) < 50:
            return {}

        if len(text) > 4000:
            text = text[:4000] + "\n...(文本已截断)"

        prompt = EXTRACT_PROMPT.format(text=text)
        result = self._call_api(prompt)

        if result:
            self._call_count += 1
            logger.info(f"[AI] 提取成功 (第{self._call_count}次调用)")

        return result

    def _call_api(self, prompt: str) -> dict:
        """
        调用 AI API

        Args:
            prompt: 完整的 prompt

        Returns:
            解析后的字典，失败返回空字典
        """
        try:
            if self.provider == "claude":
                return self._call_claude(prompt)
            elif self.provider in ("openai", "doubao", "deepseek"):
                return self._call_openai(prompt)
        except Exception as e:
            logger.error(f"[AI] API 调用失败: {e}")
            return {}

    def _call_claude(self, prompt: str) -> dict:
        """调用 Claude API"""
        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return self._parse_json(text)

    def _call_openai(self, prompt: str) -> dict:
        """调用 OpenAI API"""
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content
        return self._parse_json(text)

    def _parse_json(self, text: str) -> dict:
        """从 AI 返回的文本中解析 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"[AI] 无法解析返回的 JSON: {text[:200]}")
        return {}

    def _clean_html(self, html: str) -> str:
        """
        清洗 HTML，提取正文文本

        Args:
            html: 原始 HTML

        Returns:
            清洗后的纯文本
        """
        soup = BeautifulSoup(html, "lxml")

        # 移除不需要的标签
        for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                                   "aside", "iframe", "noscript"]):
            tag.decompose()

        # 尝试找到正文区域
        content = (
            soup.select_one("div.vF_detail_content") or
            soup.select_one("div.content") or
            soup.select_one("div.article-content") or
            soup.select_one("div.detail-content") or
            soup.select_one("div.main-content") or
            soup.select_one("article") or
            soup.select_one("main")
        )

        if content:
            text = content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # 清理多余空行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        return text

    def apply_to_item(self, item, html: str):
        """
        将 AI 提取结果应用到 BidItem

        Args:
            item: BidItem 对象
            html: 详情页 HTML
        """
        result = self.extract_from_html(html)
        if not result:
            return

        # 只填充空字段（不覆盖已有的正则提取结果）
        if not item.amount and result.get("amount"):
            item.amount = result["amount"]
        if not item.bid_bond and result.get("bid_bond"):
            item.bid_bond = result["bid_bond"]
        if not item.bid_end_time and result.get("bid_end_time"):
            item.bid_end_time = result["bid_end_time"]
        if not item.bid_start_time and result.get("bid_start_time"):
            item.bid_start_time = result["bid_start_time"]
        if not item.contact and result.get("contact"):
            contact = result["contact"]
            if result.get("phone"):
                contact = f"{contact} / {result['phone']}"
            item.contact = contact
        if not item.category and result.get("category"):
            item.category = result["category"]
