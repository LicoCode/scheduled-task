# scheduled-task

参考 [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) 的「GitHub Actions 定时 + 邮件推送」模式，每天自动发送两封邮件：

1. **GitHub 每日热榜**：抓取 [GitHub Trending](https://github.com/trending?since=daily)，项目描述翻译为中文后推送  
2. **AI 前沿突破速览**：从 [arXiv](https://arxiv.org/) 筛选世界模型 / Agent / AI 机器人 / 大模型 / 社会智能等前沿方向，按「突破性与实际效果」精排，并做效果向中文解读  

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
2. **主题粗筛**：命中世界模型、Agent、AI 机器人/具身智能、大模型、社会智能、多模态等关键词（见 `src/topics.py`）  
3. **LLM 精排**：按突破性与实际效果打分，弱化纯刷榜 / 小改方法类工作  
4. **效果向解读**：写清解决什么问题、带来什么新能力、对产品/产业意味着什么；**不写**技术细节  

> arXiv 以预印本为主，内容未经正式同行评议。本邮件用于发现前沿线索，不构成已验证结论。

## 快速开始（GitHub Actions）

### 1. 推送代码并启用 Actions

将本仓库推送到 GitHub，在 **Settings → Actions → General** 中启用 Actions。

### 2. 配置 Secrets / Variables

路径：`Settings → Secrets and variables → Actions`

**原则：不必全配。** 未设置的项使用程序默认值；发信至少要有邮箱相关配置，LLM 强烈建议配置。

**发信需要（二选一）**

| 方式 | 配置 | 说明 |
|------|------|------|
| SMTP | `EMAIL_SENDER` + `EMAIL_PASSWORD` | QQ / 163 / Gmail；QQ 在 Actions 海外机房经常失败 |
| Resend（推荐用于 Actions） | `RESEND_API_KEY` + 可选 `RESEND_FROM` | HTTPS API，不走 QQ SMTP |

`EMAIL_RECEIVERS` 可选；不填则发给 `EMAIL_SENDER`。

**邮件可选（有默认）**

| 名称 | 默认 | 说明 |
|------|------|------|
| `EMAIL_SENDER_NAME` | `每日资讯助手` | 发件显示名 |
| `SMTP_HOST` / `SMTP_PORT` | 按发件箱推断 | 一般不用填；见下表 |
| `RESEND_FROM` | `EMAIL_SENDER` | Resend 发件地址；测试可用 `Name <onboarding@resend.dev>` |

**LLM（要用翻译 / 精排 / 解读时必须全部指定，无默认值）**

| 名称 | 说明 |
|------|------|
| `OPENAI_API_KEY` | API Key |
| `OPENAI_BASE_URL` | 兼容 OpenAI 的 Base URL，如 `https://api.deepseek.com/v1` |
| `OPENAI_MODEL` | 模型名，如 `deepseek-chat` |

三项缺一则视为未启用 LLM：热榜描述保留原文；论文按主题词得分排序，解读退化为摘要截断。任务仍可运行并发信。

**业务可选（均可不配，用默认）**

| 名称 | 默认 | 说明 |
|------|------|------|
| `GITHUB_LANGUAGES` | 空（全语言） | 如 `python,typescript` |
| `GITHUB_TRENDING_LIMIT` | `15` | 热榜条数 |
| `ARXIV_CATEGORIES` | `cs.AI,cs.LG,cs.CL,cs.CV,cs.RO,cs.NE,stat.ML` | arXiv 分类（含机器人 cs.RO） |
| `ARXIV_MAX_PAPERS` | `10` | 最终入选篇数 |
| `ARXIV_CANDIDATE_POOL` | `25` | 主题粗筛后送入 LLM 精排的候选数 |
| `ARXIV_TOPIC_KEYWORDS` | 内置名单 | 自定义主题词；不配则用 `src/topics.py` |

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
# 按需填写即可：未写/留空的项自动用默认值（LLM 除外）
# 正式发信需邮箱；启用 LLM 需同时指定 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
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

## 邮箱与 SMTP

未配置 `SMTP_HOST` / `SMTP_PORT` 时，按 `EMAIL_SENDER` 域名自动推断：

| 发件邮箱 | SMTP |
|----------|------|
| `*@qq.com` / `*@foxmail.com` | `smtp.qq.com:465` |
| `*@163.com` | `smtp.163.com:465` |
| `*@126.com` | `smtp.126.com:465` |
| `*@gmail.com` | `smtp.gmail.com:465` |

QQ / 163 使用邮箱授权码；Gmail 使用应用专用密码。需要时仍可手动覆盖 `SMTP_HOST` / `SMTP_PORT`。

### GitHub Actions 发信说明

GitHub 托管 Runner 多在海外，**QQ 邮箱 SMTP 经常直接断开或 535 失败**（与授权码无关的风控也很常见）。可选方案：

1. **推荐**：注册 [Resend](https://resend.com)，在 Secrets 配置 `RESEND_API_KEY`；测试阶段可设  
   `RESEND_FROM=每日资讯助手 <onboarding@resend.dev>`，收件人用你自己的邮箱。  
2. 改用 **Gmail 应用专用密码** 作为 `EMAIL_SENDER` / `EMAIL_PASSWORD`。  
3. 本地 SMTP 能通、仅 Actions 失败时，优先考虑换 Resend，而不是反复重置 QQ 授权码。

## License

MIT
