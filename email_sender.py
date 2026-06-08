# -*- coding: utf-8 -*-
"""
邮件发送模块
使用 QQ 邮箱 SMTP 服务发送招标信息日报
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from datetime import datetime

from config import EMAIL_CONFIG
from scrapers.base import BidItem

logger = logging.getLogger(__name__)


def _escape(text: str) -> str:
    """HTML 转义"""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_email_content(items: list[BidItem], date_str: str) -> str:
    """生成 HTML 格式的邮件内容，顶部包含结构化摘要表格"""

    # 按来源分组
    by_source = {}
    for item in items:
        source = item.source
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(item)

    # CSS 样式
    style = """
    <style>
        body { font-family: "Microsoft YaHei","微软雅黑",Arial,sans-serif; color: #333; max-width: 1100px; margin: 0 auto; padding: 20px; }
        h1 { color: #1a5276; border-bottom: 3px solid #2980b9; padding-bottom: 10px; }
        h2 { color: #2980b9; margin-top: 30px; }
        .summary { background: #eaf2f8; border-left: 4px solid #2980b9; padding: 15px; margin: 20px 0; border-radius: 4px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 12px; }
        th { background: #2980b9; color: white; padding: 8px 6px; text-align: left; font-size: 12px; white-space: nowrap; }
        td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 12px; vertical-align: top; }
        tr:nth-child(even) { background: #f8f9fa; }
        tr:hover { background: #eaf2f8; }
        a { color: #2980b9; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .highlight-table th { background: #1a5276; font-size: 11px; padding: 6px 5px; }
        .highlight-table td { font-size: 11px; padding: 5px; line-height: 1.4; }
        .highlight-table tr:nth-child(even) { background: #fdf2e9; }
        .tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; color: white; margin: 1px; }
        .tag-region { background: #27ae60; }
        .tag-source { background: #2980b9; }
        .amount { color: #e74c3c; font-weight: bold; }
        .deadline { color: #e67e22; font-weight: bold; }
        .section-label { background: #f0f4f8; font-weight: bold; color: #1a5276; }
        .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; color: #888; font-size: 12px; }
        .no-data { text-align: center; padding: 40px; color: #888; }
        .detail-table { margin-top: 25px; }
        .detail-table th { font-size: 13px; }
        .detail-table td { font-size: 13px; padding: 8px 6px; }
    </style>
    """

    # ---- 构建 HTML ----
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">{style}</head><body>
<h1>📋 招标信息日报</h1>
<p style="color:#666;">日期：{date_str}</p>
<div class="summary">
    <strong>📊 今日汇总：</strong>
    共 <strong>{len(items)}</strong> 条招标信息，
    来自 <strong>{len(by_source)}</strong> 个数据源
</div>
"""

    if not items:
        html += '<div class="no-data"><h3>🔍 今日暂无符合条件的招标信息</h3></div>'
    else:
        # ========== 第一栏：结构化摘要表格 ==========
        html += """
<h2>📝 结构化摘要</h2>
<div style="overflow-x:auto;">
<table class="highlight-table">
<thead><tr>
    <th style="width:3%;">#</th>
    <th style="width:14%;">项目名称</th>
    <th style="width:8%;">招标编号</th>
    <th style="width:10%;">招标人</th>
    <th style="width:7%;">预算</th>
    <th style="width:10%;">投标截止</th>
    <th style="width:10%;">开标时间</th>
    <th style="width:8%;">保证金</th>
    <th style="width:10%;">资质要求</th>
    <th style="width:8%;">开标地点</th>
    <th style="width:6%;">地区</th>
    <th style="width:6%;">来源</th>
</tr></thead><tbody>
"""
        for idx, item in enumerate(items, 1):
            name = _escape(item.project_name or item.title[:40])
            number = _escape(item.bid_number) or "-"
            purchaser = _escape(item.purchaser) or "-"
            budget = f'<span class="amount">{_escape(item.amount)}</span>' if item.amount else "-"
            deadline = f'<span class="deadline">{_escape(item.bid_end_time)}</span>' if item.bid_end_time else "-"
            open_time = _escape(item.bid_start_time) or "-"
            bond = f'<span class="amount">{_escape(item.bid_bond)}</span>' if item.bid_bond else "-"
            qual = _escape(item.qualification[:60] + "..." if len(item.qualification) > 60 else item.qualification) or "-"
            location = _escape(item.open_location) or "-"
            region = f'<span class="tag tag-region">{_escape(item.region)}</span>' if item.region else "-"
            source_tag = f'<span class="tag tag-source">{_escape(item.source[:6])}</span>'

            html += f"""<tr>
    <td>{idx}</td>
    <td><a href="{_escape(item.url)}" target="_blank">{name}</a></td>
    <td>{number}</td>
    <td>{purchaser}</td>
    <td>{budget}</td>
    <td>{deadline}</td>
    <td>{open_time}</td>
    <td>{bond}</td>
    <td>{qual}</td>
    <td>{location}</td>
    <td>{region}</td>
    <td>{source_tag}</td>
</tr>"""

        html += "</tbody></table></div>"

        # ========== 第二栏：按来源分组的详细列表 ==========
        for source, source_items in by_source.items():
            html += f"""
<h2 class="detail-table">📌 {source} ({len(source_items)}条)</h2>
<table>
    <thead><tr>
        <th style="width:30%;">标题</th>
        <th style="width:8%;">地区</th>
        <th style="width:10%;">保证金</th>
        <th style="width:13%;">投标截止时间</th>
        <th style="width:10%;">发布日期</th>
        <th style="width:15%;">链接</th>
    </tr></thead><tbody>
"""
            for item in source_items:
                region_html = f'<span class="tag tag-region">{_escape(item.region)}</span>' if item.region else "-"
                bond_html = f'<span class="amount">{_escape(item.bid_bond)}</span>' if item.bid_bond else "-"
                end_time_html = f'<span class="deadline">{_escape(item.bid_end_time)}</span>' if item.bid_end_time else "-"
                html += f"""<tr>
    <td><a href="{_escape(item.url)}" target="_blank">{_escape(item.title)}</a></td>
    <td>{region_html}</td>
    <td>{bond_html}</td>
    <td>{end_time_html}</td>
    <td>{item.publish_date or "-"}</td>
    <td><a href="{_escape(item.url)}" target="_blank">查看详情 →</a></td>
</tr>"""
            html += "</tbody></table>"

    # 页脚
    html += f"""
<div class="footer">
    <p>⚙️ 本邮件由「招标信息监控」自动发送</p>
    <p>关键词：电力、电网、供电、变电站、输变电 | 地区：昆明/云南</p>
    <p>数据来源：中国政府采购网、云南省公共资源交易中心、昆明市公共资源交易网</p>
</div>
</body></html>"""
    return html


def send_email(items: list[BidItem]) -> bool:
    """
    发送邮件

    Args:
        items: 招标信息列表

    Returns:
        是否发送成功
    """
    sender = EMAIL_CONFIG["sender"]
    sender_name = EMAIL_CONFIG.get("sender_name", "招标信息监控")
    password = EMAIL_CONFIG["password"]
    receiver = EMAIL_CONFIG["receiver"]

    if not all([sender, password, receiver]):
        logger.error("邮件配置不完整，请检查 EMAIL_USER, EMAIL_PASS, EMAIL_TO 环境变量")
        return False

    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"[招标日报] {date_str} 昆明电力建设招标信息 ({len(items)}条)"

    # 构建邮件
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8").encode()
    msg["From"] = formataddr((str(Header(sender_name, "utf-8")), sender))
    msg["To"] = receiver

    # HTML 内容
    html_content = build_email_content(items, date_str)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # 纯文本备用
    text_content = f"招标信息日报 {date_str}\n\n"
    text_content += f"共找到 {len(items)} 条招标信息\n\n"
    for item in items:
        text_content += f"[{item.source}] {item.title}\n"
        text_content += f"  地区: {item.region or '-'}\n"
        text_content += f"  投标保证金: {item.bid_bond or '-'}\n"
        text_content += f"  投标截止时间: {item.bid_end_time or '-'}\n"
        text_content += f"  发布日期: {item.publish_date}\n"
        text_content += f"  链接: {item.url}\n\n"
    msg.attach(MIMEText(text_content, "plain", "utf-8"))

    # 发送邮件
    try:
        logger.info(f"正在发送邮件到 {receiver}...")
        with smtplib.SMTP_SSL(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"]) as server:
            server.login(sender, password)
            server.sendmail(sender, [receiver], msg.as_string())
        logger.info("邮件发送成功！")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("邮件认证失败，请检查邮箱账号和授权码")
        return False
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        return False
