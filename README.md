# scheduled-task

参考 [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) 的「GitHub Actions 定时 + 邮件推送」模式，每天自动发送两封邮件：

1. **GitHub 每日热榜**：抓取 [GitHub Trending](https://github.com/trending?since=daily)，项目描述翻译为中文后推送  
2. **AI 前沿突破速览**：从 [arXiv](https://arxiv.org/) 筛选世界模型 / Agent / 大模型 / 社会智能等前沿方向，按「突破性与实际效果」精排，并做效果向中文解读  

## 功能说明

| 任务 | 默认时间（北京时间） | Workflow | 做了什么 |
|------|----------------------|----------|----------|
| GitHub 热榜 | 每天 09:00 | `GitHub Daily Trending` | 抓取日榜 → LLM 译描述 → 发邮件 |
| AI 前沿速览 | 每天 10:00 | `arXiv Daily Papers` | 主题粗筛 → LLM 影响力精排 → 效果解读 → 发邮件 |

### GitHub 热榜

- 主源：`github.com/trending?since=daily`
- 失败时回退：社区备份 JSON → GitHub Search API
- 描述默认译为简体中文（需配置 LLM；未配置则保留原文）

### AI 前沿突破速览（无同行评议过滤）

当前**不按**期刊引用 / Accepted 等同行评议信号筛选。流程是：

1. **拉取**近期 AI 相关分类论文（`cs.AI` / `cs.LG` / `cs.CL` / `cs.CV` 等）  
2. **主题粗筛**：命中世界模型、Agent、大模型、社会智能、多模态等关键词（见 `src/topics.py`）  
3. **LLM 精排**：按突破性与实际效果打分，弱化纯刷榜 / 小改方法类工作  
4. **效果向解读**：写清解决什么问题、带来什么新能力、对产品/产业意味着什么；**不写**技术细节  

> arXiv 以预印本为主，内容未经正式同行评议。本邮件用于发现前沿线索，不构成已验证结论。

## 快速开始（GitHub Actions）

### 1. 推送代码并启用 Actions

将本仓库推送到 GitHub，在 **Settings → Actions → General** 中启用 Actions。

### 2. 配置 Secrets / Variables

路径：`Settings → Secrets and variables → Actions`

**必填（邮件）**

| 名称 | 说明 |
|------|------|
| `EMAIL_SENDER` | 发件邮箱，如 `xxx@qq.com` |
| `EMAIL_PASSWORD` | SMTP 授权码（不是登录密码） |
| `EMAIL_RECEIVERS` | 收件人，多个用英文逗号分隔；可留空表示发给自己 |

**邮件可选**

| 名称 | 默认 | 说明 |
|------|------|------|
| `EMAIL_SENDER_NAME` | `每日资讯助手` | 发件显示名 |
| `SMTP_HOST` | `smtp.qq.com` | SMTP 服务器 |
| `SMTP_PORT` | `465` | SMTP 端口（SSL） |

**LLM（强烈推荐）**

用于：热榜描述翻译、论文突破性排序、效果向解读。

| 名称 | 默认 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | — | 兼容 OpenAI Chat Completions 的 API Key |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | API Base URL |
| `OPENAI_MODEL` | `deepseek-chat` | 模型名 |

未配置 LLM 时：邮件仍可发送；热榜描述保留原文；论文按主题词得分排序，解读退化为摘要截断。

**业务可选**

| 名称 | 默认 | 说明 |
|------|------|------|
| `GITHUB_LANGUAGES` | 空（全语言） | 如 `python,typescript` |
| `GITHUB_TRENDING_LIMIT` | `15` | 热榜条数 |
| `ARXIV_CATEGORIES` | `cs.AI,cs.LG,cs.CL,cs.CV,cs.NE,stat.ML` | arXiv 分类 |
| `ARXIV_MAX_PAPERS` | `10` | 最终入选篇数 |
| `ARXIV_CANDIDATE_POOL` | `25` | 主题粗筛后送入 LLM 精排的候选数 |
| `ARXIV_TOPIC_KEYWORDS` | 内置名单 | 自定义主题词，逗号分隔；留空用 `src/topics.py` |

### 3. 手动试跑

打开 **Actions**，选择 `GitHub Daily Trending` 或 `arXiv Daily Papers`，点击 **Run workflow**。  
成功后查收邮件；HTML 报告会作为 Artifact 上传。

## 本地运行

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # 或 cp .env.example .env
# 编辑 .env：邮箱必填；LLM 推荐填写
```

```bash
# 只抓取生成 HTML，不发信
python -m src.main github --dry-run
python -m src.main arxiv --dry-run

# 实际发送
python -m src.main github
python -m src.main arxiv
python -m src.main all
```

预览文件：`reports/github-trending.html`、`reports/arxiv-digest.html`。

## 项目结构

```text
.
├── .github/workflows/
│   ├── daily-github-trending.yml   # 热榜定时任务
│   └── daily-arxiv.yml             # AI 前沿速览定时任务
├── src/
│   ├── main.py                     # CLI 入口
│   ├── github_trending.py          # 热榜抓取与描述翻译
│   ├── arxiv_papers.py             # 论文抓取、精排、效果解读
│   ├── topics.py                   # 前沿主题关键词
│   ├── email_sender.py             # SMTP 发送
│   ├── llm.py                      # OpenAI 兼容调用
│   ├── templates.py                # 邮件 HTML 模板
│   └── config.py
├── reports/                        # 本地 / CI 预览输出
├── requirements.txt
├── .env.example
└── README.md
```

## QQ 邮箱授权码示例

1. QQ 邮箱 → 设置 → 账户 → 开启 POP3/SMTP  
2. 生成授权码，填入 `EMAIL_PASSWORD`  
3. `SMTP_HOST=smtp.qq.com`，`SMTP_PORT=465`  

Gmail 请使用应用专用密码，并将 `SMTP_HOST` 设为 `smtp.gmail.com`。

## License

MIT
