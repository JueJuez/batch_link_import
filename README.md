<p align="center">
  <h1 align="center">Batch Link Import</h1>
  <p align="center">将 GitHub / Gitee 项目批量导入飞书多维表格进行归档和评估</p>
  <p align="center">
    <a href="#features">功能</a> ·
    <a href="#quick-start">快速开始</a> ·
    <a href="#usage">使用方式</a> ·
    <a href="#configuration">配置</a> ·
    <a href="#project-structure">项目结构</a>
  </p>
</p>

## What

Batch Link Import 是一个开源工具，用于**批量评估和归档 GitHub / Gitee 项目到飞书多维表格**。它可以从对话文本中自动提取仓库链接，采集 README 和 Stars 数据，通过 LLM 分析并分类（MCP / Skill / Agent工具 / 项目），打分后写入飞书，最后输出汇总报告。

## Features

- **自动链接提取** — 从自然语言文本中自动识别 GitHub / Gitee 仓库链接（支持 `https://` 和 `git@` 格式）
- **三层智能去重** — 批次内去重 + `imported.txt`（已入库）+ `pending_results.json`（待上传）联合去重
- **自动数据采集** — 获取 README 内容（raw / API 兜底）和 Stars 数量（GitHub / Gitee API）
- **LLM 分类评分** — 一次 Prompt 完成项目分类、功能领域、能力标签、核心亮点、文档/功能评分
- **飞书自动入库** — 有飞书配置直接入库，无配置自动本地暂存
- **Wiki 链接直解析** — `FEISHU_BASE_TOKEN` 可填飞书 Wiki/文档链接，自动解析成 Base Token + Table ID（自动从 `?table=` 读取表）
- **并发采集+分析** — 多个仓库的「采集+分析」并行执行（线程池，受 `BATCH_MAX_WORKERS` 控制）
- **本地暂存与增量上传** — 未配飞书时存本地 pending_results.json，配好后自动上传全部暂存记录
- **汇总报告** — 处理完成后输出格式化统计报告（成功率/类型分布/失败明细）

## Quick Start

### Prerequisites

- **lark-cli** — 已安装并登录（[安装指南](https://open.feishu.cn/document/uAjLw4CM/ugTMyYjL4AjM24CMzQjN/lark-cli/overview)）
- **飞书多维表格** — 按[字段映射表](#field-mapping)创建好表格；或直接提供飞书 Wiki/文档链接（自动解析）
- **Python >= 3.10** — 运行辅助脚本
- **GitHub / Gitee API** — 无 Token 限流 60 req/h；批量使用建议设置 `GITHUB_TOKEN` / `GITEE_TOKEN` 提升到 5000 req/h（少量导入可不填）
- **LLM（全自动模式必填）** — 配置 `BATCH_LLM_API_KEY` 后阶段三自动调用外部模型分析；不配置则默认由**子代理**分析（执行模型隔离出的独立上下文，避免把 README 带进主会话）

### Install

```bash
git clone https://github.com/JueJuez/batch_link_import.git
cd batch_link_import
pip install requests
```

### Configuration

复制 `.env.example` 为 `.env` 并填入你自己的值（`.env` 已被 `.gitignore` 忽略，不会上传）：

```bash
cp .env.example .env
# 然后编辑 .env
```

飞书目标有两种填法（二选一）：

```bash
# 方式 A：裸 Base Token + Table ID
export FEISHU_BASE_TOKEN="your_base_token"
export FEISHU_TABLE_ID="your_table_id"

# 方式 B：飞书 Wiki / 文档链接（推荐，自动解析成 Base Token + Table ID）
export FEISHU_BASE_TOKEN="https://xxx.feishu.cn/wiki/xxxx?table=tblXXXX&view=vewXXXX"
# 表 id 从链接 ?table= 自动读取，无需再填 FEISHU_TABLE_ID
```

> 未配置飞书时，评估结果会自动保存到本地 `pending_results.json`，配置后再运行会自动上传。
> 也可用命令行参数临时覆盖：`python assets/main.py "..." --feishu "<wiki链接或token>" --table "<id>"`

## Usage

### As an AI Agent Skill (lark-cli)

加载此 skill 后，将包含 GitHub / Gitee 仓库链接的文本发给 AI Agent（两者可混排）：

```
帮我评估这些工具：
https://github.com/langchain-ai/langchain-mcp-server
还有 https://gitee.com/mirrors/axios
```

AI Agent 会自动执行 5 阶段流程并返回汇总报告。

### As Python Scripts

```bash
# 方式一：端到端运行（推荐，全自动）
# 自动完成：提取 → 并发采集 → LLM 分析 → 入库/本地暂存
python assets/main.py "https://github.com/owner/repo1 还有 https://gitee.com/owner/repo2"

# 飞书目标可临时用参数指定（wiki 链接或裸 token）：
python assets/main.py "https://github.com/owner/repo" --feishu "https://xxx.feishu.cn/wiki/xxxx?table=tblXXXX"

# 阶段三的 LLM 分析来源（代码层优先级）：
#   1) --analysis-file / BATCH_LLM_ANALYSIS_FILE 指向的分析 JSON（子代理产出的结果即走这条）
#   2) 配置了 BATCH_LLM_API_KEY → 自动调用 OpenAI 兼容接口（HEADLESS，干净）
#   3) 都没配 → 返回 None 并报提示（已移除「交互粘贴」模式，避免 README 进主会话）
python assets/main.py "https://github.com/owner/repo" --analysis-file analysis.json

# 并发：采集+分析默认 5 线程并行（BATCH_MAX_WORKERS 可调，不超过仓库数）
# 未配置飞书时结果暂存到 pending_results.json；配置后重跑自动上传并清空

# 默认子代理工作流（未配 BATCH_LLM_* 时推荐，避免把 README 带进主会话）：
#   1) 采集 README 到磁盘（主会话只看到摘要）
python -m assets.pipeline collect "https://github.com/owner/repo ..." collected_data.json
#   2) 可选：导出截断版 README 给子代理（大仓库更省 token）
python -m assets.pipeline prompts collected_data.json analysis_prompts.txt
#   3) 派生子代理读 collected_data.json / analysis_prompts.txt，产出 analysis_results.json
#      （analysis_results.json 为 dict：{"owner/repo": {summary, project_type, ...}}）
#   4) 主会话拿到结果后入库
python -m assets.pipeline upload collected_data.json analysis_results.json

# 方式二：分步调用各模块
python -c "
from assets.extractor import extract_repo_urls, batch_deduplicate, filter_imported, filter_pending
from assets.collector import collect_project_data, stars_to_score
from assets.analyzer import build_analysis_prompt
from assets.reporter import ReportItem, build_report

# 1. 提取URL（三层去重：批次内 → imported → pending；支持 github / gitee）
urls = extract_repo_urls('https://github.com/tensorflow/tensorflow')
deduped = batch_deduplicate(urls)
new_urls, imported_skipped = filter_imported(deduped)
new_urls, pending_skipped = filter_pending(new_urls)

# 2. 采集数据（platform: 'github' / 'gitee'）
platform, owner, repo = __import__('assets.extractor', fromlist=['parse_repo']).parse_repo(new_urls[0])
readme, stars, error = collect_project_data(platform, owner, repo)
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

完整的 Prompt 模板见 [assets/analyzer.py](assets/analyzer.py) 中的 `ANALYSIS_PROMPT` 常量。

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FEISHU_BASE_TOKEN` | No | 飞书 Base Token **或** Wiki/文档链接（链接自动解析；未配置时本地暂存） |
| `FEISHU_TABLE_ID` | No | 飞书 Table ID（用 Wiki 链接时可省略，从 `?table=` 读取） |
| `GITHUB_TOKEN` | No | GitHub PAT，提升 API 限流（60 → 5000 req/h）；少量导入可不填 |
| `GITEE_TOKEN` | No | Gitee 私有 Token，提升 API 限流；公开仓库可不填 |
| `BATCH_LLM_API_KEY` / `OPENAI_API_KEY` | No | LLM API Key，配置后阶段三**自动**分析（推荐） |
| `BATCH_LLM_BASE_URL` / `OPENAI_BASE_URL` | No | OpenAI 兼容接口地址（默认 `https://api.openai.com/v1`，国内可用 DeepSeek/通义等） |
| `BATCH_LLM_MODEL` / `OPENAI_MODEL` | No | 模型名（默认 `gpt-4o-mini`） |
| `BATCH_LLM_ANALYSIS_FILE` | No | 指向一个分析 JSON 文件，直接读取（测试/离线用） |
| `BATCH_MAX_WORKERS` | No | 采集+分析并发线程数（默认 5，不超过待处理仓库数） |
| `FEISHU_FIELD_MAP` | No | JSON 字符串，覆盖飞书字段映射（见 [Field Mapping](#field-mapping)） |

> **字段映射可配置**：飞书列名/field id 由项目根目录的 `feishu_fields.json` 管理，
> 可被环境变量 `FEISHU_FIELD_MAP` 覆盖。仓库自带 `feishu_fields.example.json` 是占位模板；
> 复制为 `feishu_fields.json`（已被 `.gitignore` 忽略，不会提交）并改成你自己的列 id 即可。
> 作者自用的 `feishu_fields.json` 已映射到其「开源项目库」全部 15 列；空缺/`null` 的字段
> 不会被写入，也不会报错。

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

> **字段映射可配置（重要）**：上表中的列名是逻辑名，实际写入飞书时用的
> field id（或列名）由项目根目录的 `feishu_fields.json` 决定，可被环境变量
> `FEISHU_FIELD_MAP` 覆盖。仓库自带 `feishu_fields.example.json` 是占位模板，
> 复制为 `feishu_fields.json`（本地私有、已被 gitignore）并改成你自己的列 id；
> 作者自用的 `feishu_fields.json` 已映射到其「开源项目库」的全部 15 列；空缺/为 `null`
> 的字段不会被写入，也不会报错。

## Scoring

项目评估有三个维度，加起来总分 30：

| 维度 | 分值 | 怎么算的 |
|------|------|---------|
| 社区评分 | 1-10 | 根据 GitHub Stars 数量换算，Stars 越多分越高 |
| 文档评分 | 1-10 | LLM 看 README 写得完不完善来打分 |
| 功能评分 | 1-10 | LLM 看项目功能完不完整来打分 |

**Stars 和社区评分对照：**

| Stars 数量 | 分数 |
|-----------|------|
| 0 - 10 | 1 |
| 11 - 100 | 2 |
| 101 - 500 | 3 |
| 501 - 1000 | 4 |
| 1001 - 5000 | 5 |
| 5001 - 10000 | 6 |
| 10001 - 30000 | 7 |
| 30001 - 100000 | 8 |
| 100001+ | 9-10 |

## Design

- **不做多余的事** — 每个阶段只做它该做的事，不乱加功能
- **不管什么类型都入库** — MCP、Skill、工具、普通项目，通通入库，类型让 LLM 自己判断
- **本地去重，不查飞书** — 用本地文件记录已入库和待上传的项目，不和飞书比对
- **一次 LLM 搞定** — 所有分析字段一次 Prompt 输出，不分多次调
- **不 clone 代码** — 只用 HTTP 请求拿公开数据，不 git clone
- **没配飞书也能用** — 结果先存本地，配好飞书后自动上传

## Project Structure

```
batch-link-import/
├── SKILL.md                 # AI Agent 执行指令（触发规则 + 流程控制）
├── pyproject.toml           # Python 项目配置
├── imported.txt             # 已入库项目清单（自动维护，只增不减）
├── pending_results.json     # 待上传暂存记录（自动维护，上传即清）
├── references/
│   ├── spec.md              # 技术规格说明书
│   └── tasks.md             # 开发任务记录
└── assets/                  # Python 辅助脚本
    ├── extractor.py         # 链接提取 + 标准化 + 本地去重
    ├── collector.py         # 数据采集（README + GitHub API Stars）
    ├── analyzer.py          # LLM Prompt 模板 + 分析结果数据模型
    ├── feishu_writer.py     # 飞书多维表格写入
    ├── storage.py           # 本地待上传记录管理（pending_results.json）
    ├── tracker.py           # imported.txt 已入库清单维护
    ├── reporter.py          # 统计汇总与报告生成
    └── main.py              # 一体化编排入口
```

## How It Works

```
用户输入（含 GitHub URL 的文本）
    │
    ▼
阶段一：三层去重
    │  正则匹配 → 批次内去重 → 查 imported.txt → 查 pending_results.json
    ▼
阶段二：数据采集
    │  HTTP GET → README（raw.githubusercontent.com）
    │  HTTP GET → Stars（api.github.com）
    ▼
阶段三：LLM 分析（一次 Prompt）
    │  分类 + 打标 + 评分 → JSON 输出
    ▼
阶段四：飞书入库 / 本地暂存
    ├─ 已配飞书 → 上传本地暂存 + 本次结果 → 写入 imported.txt
    └─ 未配飞书 → 追加到 pending_results.json → 提示配置
    ▼
阶段五：输出汇总报告
    统计概要 + 类型分布 + 失败明细
```

## License

MIT