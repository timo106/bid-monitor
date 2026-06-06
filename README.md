# 📋 招标信息监控

每天早上自动抓取昆明地区电力建设类招标信息，通过邮件推送通知。

## 📊 数据源

| 数据源 | 网址 |
|--------|------|
| 中国政府采购网 | http://www.ccgp.gov.cn |
| 云南省公共资源交易中心 | https://ggzy.yn.gov.cn |
| 昆明市公共资源交易网 | http://ggzy.km.gov.cn |
| 中国招标投标公共服务平台 | http://www.cebpubservice.com |

## 🔍 筛选条件

- **关键词**: 电力、电网、供电、变电站、输变电
- **地区**: 昆明 / 云南
- **类型**: 招标公告

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置邮箱

#### 获取 QQ 邮箱授权码

1. 登录 [QQ邮箱](https://mail.qq.com/)
2. 进入「设置」→「账户」
3. 找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」
4. 开启「POP3/SMTP服务」
5. 按提示获取授权码（16位字母）

#### 设置环境变量

**Windows (PowerShell)**:
```powershell
$env:EMAIL_USER = "your_email@qq.com"
$env:EMAIL_PASS = "your_smtp_authorization_code"
$env:EMAIL_TO = "receiver@example.com"
```

**Windows (CMD)**:
```cmd
set EMAIL_USER=your_email@qq.com
set EMAIL_PASS=your_smtp_authorization_code
set EMAIL_TO=receiver@example.com
```

**Linux/Mac**:
```bash
export EMAIL_USER="your_email@qq.com"
export EMAIL_PASS="your_smtp_authorization_code"
export EMAIL_TO="receiver@example.com"
```

### 3. 本地测试

```bash
python main.py
```

### 4. 部署到 GitHub Actions

#### 4.1 创建 GitHub 仓库

```bash
git init
git add .
git commit -m "初始化招标信息监控项目"
git remote add origin https://github.com/your_username/bid-monitor.git
git push -u origin main
```

#### 4.2 配置 Secrets

进入 GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret

添加以下 Secrets：

| Name | Value |
|------|-------|
| `EMAIL_USER` | 你的QQ邮箱地址 |
| `EMAIL_PASS` | QQ邮箱SMTP授权码 |
| `EMAIL_TO` | 接收通知的邮箱地址 |

#### 4.3 手动测试

进入 GitHub 仓库 → Actions → 招标信息监控 → Run workflow

## ⏰ 定时说明

- 默认每天北京时间 **09:00** 运行
- GitHub Actions 的 cron 可能有最多 15 分钟延迟
- 可以通过 `workflow_dispatch` 手动触发

## 📁 项目结构

```
bid-monitor/
├── main.py              # 主程序入口
├── config.py            # 配置文件
├── email_sender.py      # 邮件发送模块
├── requirements.txt     # Python 依赖
├── scrapers/
│   ├── __init__.py
│   ├── base.py          # 爬虫基类
│   ├── ccgp.py          # 中国政府采购网
│   ├── yunnan_ggzy.py   # 云南省公共资源交易中心
│   ├── kunming_ggzy.py  # 昆明市公共资源交易网
│   └── cebpub.py        # 中国招标投标公共服务平台
└── .github/
    └── workflows/
        └── bid-monitor.yml
```

## ⚠️ 注意事项

1. **请求频率**: 脚本已内置请求间隔，避免对目标网站造成压力
2. **网站变化**: 政府网站结构可能调整，如遇到问题请提 Issue
3. **授权码安全**: 不要将邮箱授权码提交到代码仓库，使用 GitHub Secrets
4. **合规使用**: 仅用于个人学习和信息收集，请遵守相关网站使用条款

## 🔧 自定义

### 修改关键词

编辑 `config.py` 中的 `KEYWORDS` 列表：

```python
KEYWORDS = [
    "电力",
    "电网",
    "供电",
    "变电站",
    "输变电",
    # 添加更多关键词...
]
```

### 修改地区

编辑 `config.py` 中的 `REGION_KEYWORDS` 列表：

```python
REGION_KEYWORDS = ["昆明", "云南"]
```

### 添加新数据源

1. 在 `scrapers/` 目录下创建新的爬虫文件
2. 继承 `BaseScraper` 基类
3. 实现 `scrape()` 方法
4. 在 `config.py` 的 `SOURCES` 中添加配置
5. 在 `scrapers/__init__.py` 中导入新爬虫
6. 在 `main.py` 的 `scrapers` 字典中注册

## 📄 License

MIT
