---
name: batch-link-import
version: 1.3.0
description: "批量导入 GitHub / Gitee 项目到飞书多维表格归档库。自动提取链接、采集 README 和 Stars、LLM 分析分类打分、写入飞书（支持 Wiki 链接直解析、并发采集分析）。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# Batch Link Import

从对话文本中提取 GitHub / Gitee 仓库链接，采集 README 和 Stars，LLM 分析分类打分后写入飞书多维表格，最后输出汇总报告。

> **关于「全自动」**：本项目只有一种使用方式——全自动。提供一条或多条 GitHub / Gitee 仓库地址，工具自动采集 README + Stars、LLM 阅读并分析、把结果回写到飞书表（或你指定的目标）。LLM 分析默认由**子代理**（隔离上下文）完成以免污染主会话；若提供 `BATCH_LLM_*` 则改调外部 LLM（见阶段三）。

---

## 触发规则

### 激活条件

用户表达明确的归档/评估意图时执行，例如包含以下关键词：
- "评估"、"归档"、"入库"、"导入飞书"、"打分"、"分析项目"
- "帮我看看这些项目" + 附带了仓库链接（GitHub 或 Gitee）
- "批量导入"、"收录"

### 不激活条件

以下情况**不要**调用此 skill，正常回答用户问题即可：
- 用户只是问"这个项目是干什么的"、"这个项目怎么样"
- 用户要求查看 README、分析代码、对比项目
- 用户只是给出仓库链接但没有说要评估/入库

> 判断不准时，默认不激活，先问用户是否需要执行评估归档流程。

---

## 安全约束

- 任何时候不要输出 `FEISHU_BASE_TOKEN` 和 `FEISHU_TABLE_ID` 的值
- 未确认用户意图前不要执行全流程
- 不要克隆仓库，只用 HTTP 请求获取公开数据

## 配置与环境变量（开源使用）

本工具无任何私有数据硬编码。`.env.example` 列出全部可配置项（占位符，**不含任何真实 token**），使用者复制为 `.env` 后填入自己的值即可：

```bash
cp .env.example .env   # 然后编辑 .env 填入你自己的 FEISHU_BASE_TOKEN / LLM 配置等
```

关键变量：

| 变量 | 说明 |
|------|------|
| `FEISHU_BASE_TOKEN` | 飞书裸 base token **或** Wiki/文档链接（自动辨别解析） |
| `FEISHU_TABLE_ID` | 表 id（用 wiki 链接且带 `?table=` 时可省略） |
| `FEISHU_FIELD_MAP` | 可选，覆盖字段映射；默认读 `feishu_fields.json`（本地私有，gitignore），仓库自带 `feishu_fields.example.json` 为占位模板 |
| `BATCH_LLM_API_KEY` / `BATCH_LLM_BASE_URL` / `BATCH_LLM_MODEL` | OpenAI 兼容 LLM 配置（DeepSeek / 通义等） |
| `BATCH_LLM_ANALYSIS_FILE` | 可选，离线分析 JSON 文件，跳过真实 API |
| `GITHUB_TOKEN` / `GITEE_TOKEN` | 可选，提升 API 限流 60→5000 次/小时 |
| `BATCH_MAX_WORKERS` | 并发采集分析的线程数，默认 5，上限为待处理仓库数 |

> 注意：`.gitignore` 已忽略 `.env`、`pending_results.json`、`debug.log`、`imported.txt`、`__pycache__`，私有数据不会误提交。

## 自动化规则（必须遵守）

以下规则适用于每次执行，无需征求用户同意：

### 规则一：启动时自动检测飞书环境变量

每次执行本 skill 时，**最先做**（在任何阶段之前）的一件事就是自动检测飞书环境变量：

1. 运行 Python 代码检测：`from assets.feishu_writer import is_feishu_configured; print(is_feishu_configured())`
2. 如果返回 `True`，直接告知用户"飞书环境变量已就绪，可直接入库"，**不要问用户是否已配置**
3. 如果返回 `False`，告知用户"未检测到飞书环境变量，结果将本地暂存"，并输出配置指引

> 关键：**不要问用户"是否已配置"**，直接自动检测并告知结果。用户新开会话后无需任何提醒，模型会自动检测。

### 规则二：`pending_results.json` 上传后自动清理，无需用户确认

`pending_results.json` 是唯一需要清理的临时文件——它记录待上传的评估结果，每次执行都会变化。
**清理逻辑已在 `pop_all()` 中内置**（取出记录后删除文件），因此：

- 当 `has_items()` 返回 `True` 时，直接调用 `pop_all()` 取出并删除，**无需询问用户"是否删除临时文件"**
- `pop_all()` 执行完毕即代表文件已删除，不需要额外操作
- 其他文件（`imported.txt`、`__pycache__`、`*.pyc` 等）是**持久化缓存或项目文件**，保留不变，不清理
- 总之：流程中**不会有任何"是否删除"的提问出现**

---

## 执行流程

> ⚡ 先执行「规则一：启动时自动检测飞书环境变量」（见上方自动化规则），**完成后再开始阶段一**。

> 💡 **推荐路径**（取决于是否配了 LLM Key）：
> - **已配 `BATCH_LLM_*`** → 一行命令全跑完（外部 LLM，HEADLESS，不进主会话）：
>   `python assets/main.py "含仓库链接的文本"`
> - **未配 `BATCH_LLM_*`（默认）** → 走**子代理分析**工作流，避免把 README 带进主会话（见阶段三）。以下分阶段说明供手动调用参考。

### 阶段一：链接提取 + 三层去重

```python
from assets.extractor import extract_repo_urls, batch_deduplicate, filter_imported, filter_pending

urls = extract_repo_urls(text)          # 同时支持 github.com 与 gitee.com（https / ssh 形式）
deduped = batch_deduplicate(urls)
new_urls, imported_skipped = filter_imported(deduped)
new_urls, pending_skipped = filter_pending(new_urls)
```

三重过滤：
1. 批次内重复的 URL 只留一个
2. 已入库（imported.txt）的跳过
3. 本地待上传（pending_results.json）的跳过

如果 `new_urls` 为空，直接输出报告后结束。

---

### 阶段二：数据采集

```python
from assets.extractor import parse_repo
from assets.collector import collect_project_data, stars_to_score

platform, owner, repo = parse_repo(url)              # platform ∈ {'github', 'gitee'}
readme, stars, error = collect_project_data(platform, owner, repo)
```

- README 源（多源兜底，逐源重试 3 次，间隔 1s）：
  - GitHub：`raw.githubusercontent.com/{owner}/{repo}/main` → `master` → API(base64)
  - Gitee：`gitee.com/{owner}/{repo}/raw/master` → `main` → API(base64)
- Stars：`api.github.com/repos/{owner}/{repo}` 或 `gitee.com/api/v5/repos/{owner}/{repo}` → `stargazers_count`
- 设置了 `GITHUB_TOKEN` / `GITEE_TOKEN` 会把匿名 60 次/小时限流提升到 5000 次/小时
- README 缺失则整条失败；Stars 失败仅记 0，不阻断流程

> 阶段二与阶段三（采集 + LLM 分析）在 `main.py` 中由 `ThreadPoolExecutor` **并发**执行，并发数由 `BATCH_MAX_WORKERS`（默认 5，上限为待处理仓库数）控制。阶段四入库保持串行，避免飞书写入竞态。

采集失败的记录失败原因，不中断流程。

---

### 阶段三：LLM 分析（默认由子代理完成，避免污染主会话）

**核心原则**：不要让「执行模型主会话」直接读 README 做分析——README 往往很长，塞进主会话会污染上下文、挤占窗口。两条干净的路径：

- **默认（未配 `BATCH_LLM_*`）：子代理分析**。由执行模型派生一个**子代理**（独立上下文）读 README 并产出结构化分析 JSON，主会话只收到紧凑的结果，不接触 README 原文。
- **可选（配了 `BATCH_LLM_*`）：外部 LLM**。直接调用 `BATCH_LLM_*` 指定的 OpenAI 兼容接口，HEADLESS，同样不进主会话。

#### 默认子代理工作流（推荐，不污染主会话）

1. 采集 README 到磁盘（主会话只看到摘要，README 不进上下文）：
   ```bash
   python -m assets.pipeline collect "含仓库链接的文本" collected_data.json
   # 可选：导出截断版 README 给子代理（大仓库更省 token）
   python -m assets.pipeline prompts collected_data.json analysis_prompts.txt
   ```
2. 派生子代理，把下面这段发给它（让它读 `collected_data.json` 或 `analysis_prompts.txt`）：
   > 读取 `collected_data.json`（每条含 owner/repo、stars、readme）。对**每一个**项目，基于其 README 完成评估，输出**一个 JSON 对象**，key 为 `"owner/repo"`，value 为：
   > `{ "summary": 一句话简介(20字内), "project_type": "MCP"|"Skill"|"Agent工具"|"项目", "run_form": "MCP-stdio"|"MCP-SSE"|"Skill"|"不适用", "target_user": "Agent调用"|"本地运行"|"两者皆可", "domain": "功能领域单选", "tags": [能力标签...], "highlights": 核心亮点, "doc_score": 1-10, "func_score": 1-10 }`
   > 只输出这个 JSON，不要输出 README 原文。
   子代理把结果写回 `analysis_results.json`。
3. 主会话拿到 `analysis_results.json` 后入库：
   ```bash
   python -m assets.pipeline upload collected_data.json analysis_results.json
   ```
   该命令按 `owner/repo` 匹配采集结果与分析，逐条写飞书（已入库/待上传的会自动跳过）。

#### 配了 `BATCH_LLM_*` 时的一键路径

直接一行命令，`llm_analyze` 走外部接口，无需子代理：
```bash
python assets/main.py "含仓库链接的文本"
```

`llm_analyze`（代码层）的分析来源优先级：
1. `--analysis-file` / `BATCH_LLM_ANALYSIS_FILE` → 直接读分析 JSON（子代理产出的结果即走这条）
2. `BATCH_LLM_API_KEY`（或 `OPENAI_API_KEY`）+ `BATCH_LLM_BASE_URL` + `BATCH_LLM_MODEL` → 调外部接口
3. 都没配 → 返回 `None` 并报提示（**已移除「交互粘贴」模式**，因为它本质上也会把 README 带进主会话）

LLM 返回的枚举字段（`project_type` / `run_form` / `target_user` / `domain`）会经 `analyzer.coerce_choice` 校验与纠偏：精确匹配 → 大小写不敏感 → 子串匹配 → 回退默认值，避免脏值写入飞书。

分析 JSON 字段（`--analysis-file` / 子代理产出均用此结构）：
- `summary`：一句话简介（20字内）
- `project_type`：MCP / Skill / Agent工具 / 项目
- `run_form`：MCP-stdio / MCP-SSE / Skill / 不适用
- `target_user`：Agent调用 / 本地运行 / 两者皆可
- `domain`：功能领域
- `tags`：能力标签数组
- `highlights`：核心亮点
- `doc_score`：文档评分（1-10）
- `func_score`：功能评分（1-10）

社区评分由 `stars_to_score(stars)` 本地计算，不占用 LLM。

---

### 阶段四：飞书入库 / 本地暂存

```python
from assets.feishu_writer import is_feishu_configured, write_record_with_retry
from assets.storage import has_items, pop_all, append_items
from assets.tracker import append_to_imported_list
```

`FEISHU_BASE_TOKEN` 支持两种形态，工具**自动辨别**：
- **裸 base token**：直接作为 token 使用，需另外提供 `FEISHU_TABLE_ID`
- **飞书 Wiki / 文档链接**：含 `feishu.cn/wiki` 或 `feishu.cn/base`，写入时自动调 `lark-cli base +url-resolve` 解析成真实 base_token；表 id 从链接的 `?table=` 参数读取（未显式提供时）。`is_feishu_configured()` 对 wiki 链接只要 base 端就绪即返回 `True`

也可在命令行用 `--feishu <wiki链接或token>` + `--table <id>` 覆盖环境变量（命令行优先）。

先检测环境变量 / 命令行传入的 `FEISHU_BASE_TOKEN` 和 `FEISHU_TABLE_ID`：

#### 已配置 → 上传飞书

1. 如果 `has_items()`，用 `pop_all()` 取出全部本地暂存记录，逐条写入飞书
2. 写入成功后，将 `_owner_repo` 标记写入 `imported.txt`
3. 再上传本次分析的新结果
4. 本次结果写入成功后也追加到 `imported.txt`

```python
if has_items():
    pending = pop_all()
    for item in pending:
        fields = {k: v for k, v in item.items() if not k.startswith("_")}
        if write_record_with_retry(fields):
            append_to_imported_list(item["_owner_repo"])

fields = result.to_feishu_fields(repo, url, stars)
if write_record_with_retry(fields):
    append_to_imported_list(f"{owner}/{repo}")
```

#### 未配置 → 本地暂存

1. 用 `append_items()` 将本次结果追加到 `pending_results.json`
2. 输出配置提示，告知用户设置环境变量后会自动上传

---

### 阶段五：输出汇总报告 + 自动清理

```python
from assets.reporter import ReportItem, build_report

items = [
    ReportItem(url, owner_repo, "success", project_type=result.project_type),
    ReportItem(url, owner_repo, "failed", error_reason="原因"),
    ReportItem(url, owner_repo, "skipped", error_reason="已入库/待上传"),
]
report = build_report(items)
print(report.generate())
```

本地暂存的项目状态标记为 `"success"` + `not_uploaded=True`。

**报告输出后，无需任何手动清理操作**（遵循规则二，`pending_results.json` 的上传和删除已由 `pop_all()` 自动完成）。

---

## 错误处理

- 单条采集或写入失败不中断流程，继续处理下一条
- 飞书写入失败最多重试 3 次，间隔 1s
- 失败的记录在报告中列出原因
- lark-cli 不可用时 `write_record_with_retry` 返回 False，不崩溃