<p align="center">
  <h1 align="center">Batch Link Import</h1>
  <p align="center">将 GitHub 项目批量导入飞书多维表格进行归档和评估</p>
  <p align="center">
    <a href="#features">功能</a> ·
    <a href="#quick-start">快速开始</a> ·
    <a href="#usage">使用方式</a> ·
    <a href="#configuration">配置</a> ·
    <a href="#project-structure">项目结构</a>
  </p>
</p>

## What

Batch Link Import 是一个开源工具，用于**批量评估和归档 GitHub 项目到飞书多维表格**。它可以从对话文本中自动提取 GitHub 链接，采集 README 和 Stars 数据，通过 LLM 分析并分类（MCP / Skill / Agent工具 / 项目），打分后写入飞书，最后输出汇总报告。

## Features

- **自动链接提取** — 从自然语言文本中自动识别 GitHub 仓库链接（支持 `https://` 和 `git@` 格式）
- **智能去重** — 批次内去重 + 本地 `imported.txt` 持久化去重，避免重复入库
- **自动数据采集** — 获取 README 内容（raw.githubusercontent.com）和 Stars 数量（GitHub API）
- **LLM 分类评分** — 一次 Prompt 完成项目分类、功能领域、能力标签、核心亮点、文档/功能评分
- **飞书入库** — 自动写入飞书多维表格，评估结果结构化存储
- **汇总报告** — 处理完成后输出格式化统计报告（成功率/类型分布/失败明细）

## Quick Start

### Prerequisites

- **lark-cli** — 已安装并登录（[安装指南](https://open.feishu.cn/document/uAjLw4CM/ugTMyYjL4AjM24CMzQjN/lark-cli/overview)）
- **飞书多维表格** — 按[字段映射表](#field-mapping)创建好表格
- **Python >= 3.10** — 运行辅助脚本
- **GitHub API** — 无需 Token（公开仓库限流 60 req/h）

### Install

```bash
git clone https://github.com/JueJuez/batch_link_import.git
cd batch_link_import
pip install requests
```

### Configuration

```bash
export FEISHU_BASE_TOKEN="your_base_token"
export FEISHU_TABLE_ID="your_table_id"
```

## Usage

### As an AI Agent Skill (lark-cli)

加载此 skill 后，将包含 GitHub 链接的文本发给 AI Agent：

```
帮我评估这些工具：
https://github.com/langchain-ai/langchain-mcp-server
还有 https://github.com/axios/axios
```

AI Agent 会自动执行 5 阶段流程并返回汇总报告。

### As Python Scripts

```bash
# 方式一：一键运行（推荐）
python assets/main.py "https://github.com/owner/repo1 还有 https://github.com/owner/repo2"

# 方式二：分步调用各模块
python -c "
from assets.extractor import extract_github_urls, batch_deduplicate, filter_imported
from assets.collector import collect_project_data, stars_to_score
from assets.analyzer import build_analysis_prompt
from assets.reporter import ReportItem, build_report

# 1. 提取URL
urls = extract_github_urls('https://github.com/tensorflow/tensorflow')
new_urls, skipped = filter_imported(batch_deduplicate(urls))

# 2. 采集数据
owner, repo = 'tensorflow', 'tensorflow'
readme, stars, error = collect_project_data(owner, repo)
print(f'Stars: {stars}, Score: {stars_to_score(stars)}')

# 3. 构建 LLM Prompt
prompt = build_analysis_prompt(repo, stars, readme)
print(f'Prompt built: {len(prompt)} chars')
"
```

### LLM Prompt

在阶段三，将以下格式的 Prompt 发送给 LLM：

```
你是一个专业的开源项目评估分析师...

项目名称: {repo_name}
Stars 数量: {stars}

{README内容}

请以 JSON 格式输出以下字段：
- summary: 一句话简介
- project_type: MCP / Skill / Agent工具 / 项目
- run_form: MCP-stdio / MCP-SSE / Skill / 不适用
- target_user: Agent调用 / 本地运行 / 两者皆可
- domain: 功能领域（分类参考下方列表）
- tags: 能力标签数组
- highlights: 核心亮点
- doc_score: 文档评分（1-10）
- func_score: 功能评分（1-10）
```

完整的 Prompt 模板见 [SKILL.md](SKILL.md) 的阶段三部分。

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FEISHU_BASE_TOKEN` | Yes | 飞书多维表格的 Base Token |
| `FEISHU_TABLE_ID` | Yes | 飞书多维表格的 Table ID |

### Field Mapping

| 飞书字段 | 类型 | 说明 |
|---------|------|------|
| `项目名称` | 文本 | GitHub repo 名称 |
| `Git 地址` | 链接 | 标准化后的 GitHub URL |
| `项目类型` | 单选 | MCP / Skill / Agent工具 / 项目 |
| `项目描述` | 文本 | 一句话简介（LLM 输出） |
| `运行形式` | 单选 | MCP-stdio / MCP-SSE / Skill / 不适用 |
| `给谁用` | 单选 | Agent 调用 / 本地运行 / 两者皆可 |
| `功能领域` | 单选 | 主分类 |
| `能力标签` | 多选 | 自由标签描述具体能力 |
| `核心亮点` | 文本 | 独特优势 |
| `社区评分` | 数字 | 1-10（Stars 换算） |
| `文档评分` | 数字 | 1-10（LLM 评估） |
| `功能评分` | 数字 | 1-10（LLM 评估） |
| `综合评分` | 数字 | 三项之和（3-30） |
| `评估日期` | 日期 | 入库时间 |
| `状态` | 单选 | 已入库 |

## Project Structure

```
batch-link-import/
├── SKILL.md                 # AI Agent 主指令（含完整 Prompt 模板）
├── pyproject.toml           # Python 项目配置
├── imported.txt             # 已入库项目清单（自动维护）
├── references/
│   ├── spec.md              # 技术规格说明书
│   └── tasks.md             # 开发任务记录
└── assets/                  # Python 辅助脚本
    ├── extractor.py         # 链接提取 + 标准化 + 本地去重
    ├── collector.py         # 数据采集（README + GitHub API Stars）
    ├── analyzer.py          # LLM Prompt 模板 + 分析结果数据模型
    ├── feishu_writer.py     # 飞书多维表格写入
    ├── tracker.py           # imported.txt 本地清单维护
    ├── reporter.py          # 统计汇总与报告生成
    └── main.py              # 一体化编排入口
```

## How It Works

```
用户输入（含 GitHub URL 的文本）
    │
    ▼
阶段一：链接提取 + 本地去重
    │  正则匹配 GitHub URL → 标准化 → 查 imported.txt
    ▼
阶段二：数据采集
    │  HTTP GET → README（raw.githubusercontent.com）
    │  HTTP GET → Stars（api.github.com）
    ▼
阶段三：LLM 分析（一次 Prompt）
    │  分类 + 打标 + 评分 → JSON 输出
    ▼
阶段四：飞书入库 + 更新 imported.txt
    │  lark-cli base +create-record → 追加 owner/repo
    ▼
阶段五：输出汇总报告
    统计概要 + 类型分布 + 失败明细
```

## License

MIT