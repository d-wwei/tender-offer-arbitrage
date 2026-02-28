# 在 NanoClaw / ZeroClaw / OpenClaw 中使用本 Skill

本 skill 为 AgentSkills 兼容格式，可用于 OpenClaw、NanoClaw、ZeroClaw 等 AI Agent 平台。

## 安装方式

### OpenClaw

```
~/.openclaw/skills/
└── tender-offer-arbitrage/
    ├── SKILL.md
    ├── _meta.json
    ├── config/
    │   └── config.json  (从 config.example.json 复制并配置)
    ├── scripts/
    │   ├── scan_tender_offers.py
    │   ├── verify_filings.py
    │   ├── generate_report.py
    │   ├── send_email.py
    │   ├── scheduler.py
    │   ├── run_pipeline.py
    │   └── requirements.txt
    └── templates/
        └── report_template.md
```

### NanoClaw / ZeroClaw

```
你的项目/
└── .claude/
    └── skills/
        └── tender-offer-arbitrage/
            ├── SKILL.md
            └── ...（同上）
```

## 环境准备

1. **安装依赖**
```bash
pip install -r scripts/requirements.txt
```

2. **配置文件**
```bash
cp config/config.example.json config/config.json
# 编辑 config.json 设置邮箱和运行时间
```

3. **邮箱设置**（Gmail 为例）
   - 前往 https://myaccount.google.com/apppasswords
   - 创建应用专用密码
   - 将密码填入 config.json 的 `email.password`

## 平台差异

| 特性 | OpenClaw | NanoClaw | ZeroClaw |
|------|----------|----------|----------|
| 目录 | `~/.openclaw/skills/` | `.claude/skills/` | `.zeroclaw/skills/` |
| 配置 | `openclaw.json` | 环境变量 | `zeroclaw.json` |
| 执行 | 主机进程 | 容器内 | 主机/容器 |
| 定时 | 系统 cron/launchd | 容器内 cron | 平台调度器 |

本 skill 不依赖任何平台专有功能，仅需 Python 3.9+ 和网络访问即可运行。

## 快速验证

```bash
# 使用样例数据测试全流程（不需要网络）
cd /path/to/tender-offer-arbitrage/
python3 scripts/run_pipeline.py --dry-run --skip-email
```
