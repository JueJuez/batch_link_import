---
name: batch-link-import
version: 1.0.0
description: "批量导入 GitHub 项目到飞书多维表格归档库。自动提取链接、采集 README 和 Stars、LLM 分析分类打分、写入飞书。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# Batch Link Import

从对话文本中提取 GitHub 链接，采集 README 和 Stars，LLM 分析分类打分后写入飞书多维表格，最后输出汇总报告。

---

## 触发规则

### 激活条件

用户表达明确的归档/评估意图时执行，例如包含以下关键词：
- "评估"、"归档"、"入库"、"导入飞书"、"打分"、"分析项目"
- "帮我看看这些项目" + 附带了 GitHub 链接
- "批量导入"、"收录"

### 不激活条件

以下情况**不要**调用此 skill，正常回答用户问题即可：
- 用户只是问"这个项目是干什么的"、"这个项目怎么样"
- 用户要求查看 README、分析代码、对比项目
- 用户只是给出 GitHub 链接但没有说要评估/入库

> 判断不准时，默认不激活，先问用户是否需要执行评估归档流程。

---

## 安全约束

- 任何时候不要输出 `FEISHU_BASE_TOKEN` 和 `FEISHU_TABLE_ID` 的值
- 未确认用户意图前不要执行全流程
- 不要克隆仓库，只用 HTTP 请求获取公开数据

---

## 执行流程

### 阶段一：链接提取 + 三层去重

```python
from assets.extractor import extract_github_urls, batch_deduplicate, filter_imported, filter_pending

urls = extract_github_urls(text)
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
from assets.collector import collect_project_data, stars_to_score

readme, stars, error = collect_project_data(owner, repo)
```

- README：`raw.githubusercontent.com/{owner}/{repo}/main/README.md`
- Stars：`api.github.com/repos/{owner}/{repo}` → JSON 的 `stargazers_count`
- 失败自动重试 3 次，间隔 1s
- README 取 main 失败后降级尝试 master

采集失败的记录失败原因，不中断流程。

---

### 阶段三：LLM 分析

用 `build_analysis_prompt` 构建 Prompt 发给 LLM：

```python
from assets.analyzer import build_analysis_prompt, parse_llm_response

prompt = build_analysis_prompt(repo_name, stars, readme)
# 将 prompt 发送给 LLM，获取 JSON 响应
result = parse_llm_response(llm_response)
```

Prompt 要求 LLM 输出 JSON，包含：
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

先检测环境变量 `FEISHU_BASE_TOKEN` 和 `FEISHU_TABLE_ID`：

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

### 阶段五：输出汇总报告

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

---

## 错误处理

- 单条采集或写入失败不中断流程，继续处理下一条
- 飞书写入失败最多重试 3 次，间隔 1s
- 失败的记录在报告中列出原因
- lark-cli 不可用时 `write_record_with_retry` 返回 False，不崩溃