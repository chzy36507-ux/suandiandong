# 算电通 ⚡🤖

> 全国分时电价 × DeepSeek API 价格 — 自动采集、本地存储、智能查询

## 项目简介

算电通是一个运行在本地的数据采集工具，通过 OpenClaw AI Agent 定期自动获取：

- **全国31省分时电价**（峰/平/谷，工商业用电）
- **DeepSeek API 最新定价**（deepseek-chat / deepseek-reasoner）

数据存储在本地 SQLite，无需云端服务，完全离线可用。

## 功能特性

- ✅ 每3天自动爬取 DeepSeek 官方定价页面
- ✅ 每12天自动搜索更新全国电价（ProSearch + AI解析）
- ✅ QQ邮件通知（数据更新后自动发送）
- ✅ 命令行查询工具

## 快速开始

```bash
# 安装依赖
pip install requests beautifulsoup4

# 初始化数据库
python crawler/db.py

# 手动触发爬虫
python crawler/deepseek_crawler.py
python crawler/electricity_crawler.py

# 查询数据
python crawler/query.py all
python crawler/query.py electricity 广东
python crawler/query.py deepseek
```

## 文件结构

```
suandiandong/
├── crawler/
│   ├── db.py                  # 数据库管理
│   ├── deepseek_crawler.py    # DeepSeek价格爬虫
│   ├── electricity_crawler.py # 全国电价爬虫
│   ├── email_notify.py        # 邮件通知
│   └── query.py               # 查询工具
├── data/                      # 数据目录（.gitignore排除）
└── logs/                      # 日志目录（.gitignore排除）
```

## 数据说明

- 电价数据来源：各省发改委/电网公告（通过搜索引擎获取）
- DeepSeek价格来源：https://api-docs.deepseek.com/quick_start/pricing
- 数据仅供参考，以官方最新公告为准

## 技术栈

- Python 3.x
- SQLite（本地存储）
- BeautifulSoup4（HTML解析）
- OpenClaw ProSearch（搜索引擎）
- DeepSeek API（AI解析）

## License

MIT
