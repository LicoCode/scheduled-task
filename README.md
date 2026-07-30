# scheduled-task

参考 [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) 的「GitHub Actions 定时 + 邮件推送」模式，每天自动：

1. **GitHub 每日热榜**：抓取 [GitHub Trending](https://github.com/trending?since=daily)，描述翻译为中文后邮件推送  
2. **AI 前沿突破速览**：从 arXiv 粗筛世界模型 / Agent / 大模型 / 社会智能等主题，再用 LLM 按「突破性与实际效果」精排并做效果向解读  

## 功能说明

| 任务 | 默认时间（北京时间） | 数据来源 |
|------|----------------------|----------|
| GitHub 热榜 | 每天 09:00 | 主源 `github.com/trending`，失败时回退社区备份 JSON |
| arXiv 解读 | 每天 10:00 | arXiv API；优先带期刊引用 / Accepted 等「同行评议信号」的论文 |

> **关于同行评议**：arXiv 以预印本为主，并不直接做同行评议。本项目会优先挑选带 `journal_ref` 或摘要/评论中含 Accepted、to appear 等信号的论文；不足时再用当日相关分类新文补齐。

## 快速开始（GitHub Actions）

### 1. 推送到 GitHub 仓库

创建仓库后把本项目代码推上去，并在仓库 **Settings → Actions → General** 中启用 Actions。

### 2. 配置 Secrets / Variables

路径：`Settings → Secrets and variables → Actions`

**必填**

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

**arXiv 解读推荐（LLM）**

| 名称 | 默认 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | — | 兼容 OpenAI Chat Completions 的 API Key |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | API Base URL |
| `OPENAI_MODEL` | `deepseek-chat` | 模型名 |

未配置 LLM 时，邮件仍会发送，解读部分改为截断摘要。

**业务可选**

| 名称 | 默认 | 说明 |
|------|------|------|
| `GITHUB_LANGUAGES` | 空（全语言） | 如 `python,typescript` |
| `GITHUB_TRENDING_LIMIT` | `15` | 热榜条数 |
| `ARXIV_CATEGORIES` | `cs.AI,cs.LG,cs.CL,cs.CV,cs.NE,stat.ML` | AI 相关分类 |
| `ARXIV_MAX_PAPERS` | `10` | 最终入选篇数 |
| `ARXIV_CANDIDATE_POOL` | `25` | 主题粗筛后送给 LLM 精排的候选数 |
| `ARXIV_TOPIC_KEYWORDS` | 内置名单 | 前沿主题词，逗号分隔；留空用默认 |

### 3. 手动试跑

打开 **Actions**，选择：

- `GitHub Daily Trending`
- `arXiv Daily Papers`

点击 **Run workflow**。成功后查收邮件；报告也会作为 Artifact 上传。

## 本地运行

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # 或 cp .env.example .env
# 编辑 .env 填入邮箱与（可选）LLM 配置
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

生成的预览文件在 `reports/`。

## 项目结构

```text
.
├── .github/workflows/
│   ├── daily-github-trending.yml
│   └── daily-arxiv.yml
├── src/
│   ├── main.py              # CLI 入口
│   ├── github_trending.py   # 热榜抓取
│   ├── arxiv_papers.py      # 论文抓取与解读
│   ├── email_sender.py      # SMTP 发送
│   ├── llm.py               # OpenAI 兼容调用
│   ├── templates.py         # 邮件模板
│   └── config.py
├── requirements.txt
└── .env.example
```

## QQ 邮箱授权码示例

1. QQ 邮箱 → 设置 → 账户 → 开启 POP3/SMTP  
2. 生成授权码，填入 `EMAIL_PASSWORD`  
3. `SMTP_HOST=smtp.qq.com`，`SMTP_PORT=465`

Gmail 请使用应用专用密码，并将 `SMTP_HOST` 设为 `smtp.gmail.com`。

## License

MIT
