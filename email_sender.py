# -*- coding: utf-8 -*-
"""
邮件发送模块
使用 QQ 邮箱 SMTP 服务发送招标信息日报
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from config import EMAIL_CONFIG
from scrapers.base import BidItem

logger = logging.getLogger(__name__)


def build_email_content(items: list[BidItem], date_str: str) -> str:
    """生成 HTML 格式的邮件内容"""

    # 按来源分组
    by_source = {}
    for item in items:
        source = item.source
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(item)

    # 构建 HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: "Microsoft YaHei", "微软雅黑", Arial, sans-serif;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #1a5276;
            border-bottom: 3px solid #2980b9;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2980b9;
            margin-top: 30px;
        }}
        .summary {{
            background: #eaf2f8;
            border-left: 4px solid #2980b9;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th {{
            background: #2980b9;
            color: white;
            padding: 12px 10px;
            text-align: left;
            font-size: 14px;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
            font-size: 13px;
        }}
        tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        tr:hover {{
            background: #eaf2f8;
        }}
        a {{
            color: #2980b9;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .source-tag {{
            background: #2980b9;
            color: white;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
        }}
        .region-tag {{
            background: #27ae60;
            color: white;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
            color: #888;
            font-size: 12px;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #888;
        }}
    </style>
</head>
<body>
    <h1>📋 招标信息日报</h1>
    <p style="color: #666;">日期：{date_str}</p>

    <div class="summary">
        <strong>📊 今日汇总：</strong>
        共找到 <strong>{len(items)}</strong> 条招标信息，
        来自 <strong>{len(by_source)}</strong> 个数据源
    </div>
"""

    if not items:
        html += """
    <div class="no-data">
        <h3>🔍 今日暂无符合条件的招标信息</h3>
        <p>未找到与「电力、电网、供电、变电站、输变电」相关的昆明地区招标公告</p>
    </div>
"""
    else:
        for source, source_items in by_source.items():
            html += f"""
    <h2>📌 {source} ({len(source_items)}条)</h2>
    <table>
        <thead>
            <tr>
                <th style="width: 35%;">标题</th>
                <th style="width: 10%;">地区</th>
                <th style="width: 12%;">投标保证金</th>
                <th style="width: 15%;">投标截止时间</th>
                <th style="width: 10%;">发布日期</th>
                <th style="width: 18%;">链接</th>
            </tr>
        </thead>
        <tbody>
"""
            for item in source_items:
                region_html = f'<span class="region-tag">{item.region}</span>' if item.region else "-"
                bond_html = f'<span style="color: #e74c3c; font-weight: bold;">{item.bid_bond}</span>' if item.bid_bond else "-"
                end_time_html = f'<span style="color: #e67e22; font-weight: bold;">{item.bid_end_time}</span>' if item.bid_end_time else "-"
                html += f"""
            <tr>
                <td><a href="{item.url}" target="_blank">{item.title}</a></td>
                <td>{region_html}</td>
                <td>{bond_html}</td>
                <td>{end_time_html}</td>
                <td>{item.publish_date or "-"}</td>
                <td><a href="{item.url}" target="_blank">查看详情 →</a></td>
            </tr>
"""
            html += """
        </tbody>
    </table>
"""

    html += f"""
    <div class="footer">
        <p>⚙️ 本邮件由「招标信息监控」自动发送</p>
        <p>关键词：电力、电网、供电、变电站、输变电 | 地区：昆明/云南</p>
        <p>数据来源：中国政府采购网、云南省公共资源交易中心、昆明市公共资源交易网、中国招标投标公共服务平台</p>
    </div>
</body>
</html>
"""
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
    password = EMAIL_CONFIG["password"]
    receiver = EMAIL_CONFIG["receiver"]

    if not all([sender, password, receiver]):
        logger.error("邮件配置不完整，请检查 EMAIL_USER, EMAIL_PASS, EMAIL_TO 环境变量")
        return False

    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"[招标日报] {date_str} 昆明电力建设招标信息 ({len(items)}条)"

    # 构建邮件
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
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
