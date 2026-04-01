# 算电通 — 当前进展总结

**更新时间：** 2026-04-01 09:15

---

## 一、方案演进

### 历史版本
- **v0.1** — 初版方案设计（20分钟爬取一次）
- **v1.0** — 产品方向转型：从"数据收集工具"升级为"智能决策工具"
- **v2.0** — 技术验证后调整：手动维护基础数据 + 自动检测变化
- **v4.0** — 纯本地 OpenClaw 驱动方案

### 当前方向（v1.0 已锁定）
- **目标用户**：居民 + 工商业双模式，默认展示居民电价
- **核心价值**：省钱（谷电时段）+ 绿色（绿电高发时段）+ 提醒（到点推送）
- **绿电信息**：方案C — 绿电装机比例（全局认知）+ 高发时段规律（行动指导）

---

## 二、已完成的工作

### 2.1 代码仓库
- GitHub: https://github.com/chzy36507-ux/suandiandong
- 最新 commit: `37f0e54` — 云端自动化方案（GitHub Actions）

### 2.2 本地爬虫（已写代码，未验证运行）

| 文件 | 功能 | 状态 |
|------|------|------|
| `crawler/db.py` | SQLite 数据库管理 | ⚠️ 代码已写，未运行验证 |
| `crawler/deepseek_crawler.py` | DeepSeek 价格爬虫 | ⚠️ 代码已写，未运行验证 |
| `crawler/electricity_crawler.py` | 工商业电价爬虫 | ⚠️ 代码已写，未运行验证 |
| `crawler/residential_electricity_crawler.py` | 居民电价爬虫 | ⚠️ 代码已写，未运行验证 |
| `crawler/email_notify.py` | QQ 邮件通知 | ⚠️ 代码已写，未运行验证 |
| `crawler/query.py` | 命令行查询工具 | ⚠️ 代码已写，未运行验证 |

**注意：以上代码都没有在本机实际运行过，不能声称"完成"。**

### 2.3 数据库设计（已定义，未验证）

```sql
electricity_prices        -- 工商业分时电价
residential_electricity   -- 居民分时电价
deepseek_prices           -- DeepSeek API 价格
green_energy_knowledge    -- 绿电知识库（待填充）
reminders                 -- 提醒记录
crawler_logs              -- 爬取日志
```

**注意：表结构已定义在 `db.py`，但 `init_db()` 没有实际运行过。**

### 2.4 GitHub Actions（已配置，未验证触发）

| Workflow | 触发条件 | 状态 |
|----------|---------|------|
| `update-deepseek.yml` | 每3天凌晨1点 UTC | ⚠️ 已配置，未验证实际运行 |
| `update-electricity.yml` | 每12天凌晨2点 UTC | ⚠️ 已配置，未验证实际运行 |

### 2.5 前端页面（已写代码，未验证）
- `frontend/index.html` — 静态展示页面
- 数据源：GitHub Raw JSON（`data_output/electricity.json` / `deepseek_prices.json`）

---

## 三、数据状态

### 3.1 已有数据文件

| 文件 | 内容 | 来源 |
|------|------|------|
| `data_output/electricity.json` | 20省工商业电价 | 手动生成（非爬虫运行结果）|
| `data_output/deepseek_prices.json` | 2个模型价格 | 手动生成（非爬虫运行结果）|

**重要：这些数据是手动构造的 JSON，不是爬虫实际运行输出的。**

### 3.2 本地 SQLite 数据库
- 路径：`data/suandiandong.db`
- 状态：**未验证是否存在、表是否创建成功**

---

## 四、未完成的工作

### 4.1 核心缺失
1. **爬虫没有在本机实际运行过** — 所有 `crawler/*.py` 只是代码文件
2. **数据库没有初始化** — `python db.py` 从未执行
3. **GitHub Actions 没有验证** — 不知道云端爬虫能否正常运行
4. **邮件通知没有测试** — 不知道 QQ 邮箱授权码是否有效

### 4.2 产品功能缺失
1. **居民电价数据** — 代码写了，没有运行爬取
2. **绿电知识库** — 表结构定义了，数据为零
3. **智能建议引擎** — 未开发
4. **提醒功能** — 未开发

### 4.3 产品方案文档中声称的"完成"

`RESIDENTIAL_CRAWLER_PROGRESS.md` 写着：
> "居民电价数据 — 完成（31省全覆盖）"

**这是不准确的。** 实际情况：
- 代码写了 `residential_electricity_crawler.py`
- **爬虫没有运行过**
- `data_output/electricity.json` 里的居民数据是手动整理的，不是爬虫输出

---

## 五、下一步行动

### 最高优先级（必须先做）
1. **在本机运行 `python crawler/db.py`** — 验证数据库能否初始化
2. **在本机运行 `python crawler/deepseek_crawler.py`** — 验证 DeepSeek 爬虫
3. **在本机运行 `python crawler/electricity_crawler.py`** — 验证电价爬虫
4. **验证爬虫输出** — 检查 SQLite 是否有数据

### 中优先级
5. 手动触发 GitHub Actions 验证云端运行
6. 测试邮件通知
7. 补充绿电知识库数据

### 低优先级
8. 开发智能建议引擎
9. 开发提醒功能
10. 前端界面美化

---

## 六、诚实的结论

**当前状态：代码框架已搭建，但所有核心功能都没有在本机实际验证过。**

| 功能 | 代码状态 | 运行验证 |
|------|---------|---------|
| 数据库初始化 | ✅ 已写 | ❌ 未运行 |
| DeepSeek 爬虫 | ✅ 已写 | ❌ 未运行 |
| 工商业电价爬虫 | ✅ 已写 | ❌ 未运行 |
| 居民电价爬虫 | ✅ 已写 | ❌ 未运行 |
| 邮件通知 | ✅ 已写 | ❌ 未运行 |
| GitHub Actions | ✅ 已配置 | ❌ 未触发 |
| 前端页面 | ✅ 已写 | ❌ 未部署 |

**下一步：先在本机跑通一个爬虫，再谈"完成"。**
