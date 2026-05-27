---
name: batch-link-import
version: 1.0.0
description: "批量导入 GitHub 项目到飞书多维表格归档库。自动提取链接、采集 README 和 Stars、LLM 分析分类打分、写入飞书。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# Batch Link Import

将 GitHub 项目批量导入飞书多维表格进行归档和评估。

自动从对话/文本中提取 GitHub 链接，采集 README 和 Stars 数据，通过 LLM 分析并分类（MCP / Skill / Agent工具 / 项目），打分后写入飞书多维表格，最后输出汇总报告。

---

## 快速开始

### 前置条件

1. **lark-cli** — 已安装并登录
2. **飞书多维表格** — 按 [字段 Schema](#字段映射) 创建好各列
3. **Python >= 3.10** — 运行辅助脚本
4. **GitHub API** — 无需 Token（公开仓库限流 60 req/h）

### 配置

```bash
# 设置飞书多维表格信息
export FEISHU_BASE_TOKEN="your_base_token_here"
export FEISHU_TABLE_ID="your_table_id_here"
```

### 使用方式

```bash
# 方式一：直接调用 Agent（加载此 skill）
# 将以下文本发给 AI Agent：
"帮我评估 https://github.com/owner/repo1 和 https://github.com/owner/repo2"

# 方式二：使用辅助脚本
python assets/main.py "https://github.com/owner/repo1 还有 https://github.com/owner/repo2"
```

---

## 辅助脚本

| 脚本 | 用途 | 调用方式 |
|------|------|---------|
| `extractor.py` | 链接提取、标准化、本地去重 | `from assets.extractor import extract_github_urls` |
| `collector.py` | HTTP 采集 README + Stars，社区评分换算 | `from assets.collector import collect_project_data` |
| `analyzer.py` | LLM Prompt 构建、结果解析、飞书字段映射 | `from assets.analyzer import build_analysis_prompt` |
| `feishu_writer.py` | 飞书多维表格写入（环境变量配置 Token） | `from assets.feishu_writer import write_record_with_retry` |
| `tracker.py` | imported.txt 本地清单读写 | `from assets.tracker import load_imported_list` |
| `reporter.py` | 统计汇总与报告生成 | `from assets.reporter import build_report` |
| `main.py` | 一体化编排入口 | `python assets/main.py "链接文本"` |

---

## 核心流程

```
阶段一：链接提取 + 本地去重
    ↓
阶段二：数据采集（README + Stars）
    ↓
阶段三：LLM 分析（一次 Prompt）
    ↓
阶段四：飞书入库 + 更新 imported.txt
    ↓
阶段五：输出汇总报告
```

---

## 阶段一：链接提取 + 本地去重

### 操作步骤

1. **提取所有 GitHub 仓库 URL**
   - 匹配 `https://github.com/{owner}/{repo}` 和 `git@github.com:{owner}/{repo}.git`
   - 自动过滤非仓库页面（settings、notifications 等 GitHub 内部页面）
   - 标准化为 `https://github.com/{owner}/{repo}` 格式

2. **批次内去重**
   - `A/B.git` 和 `A/B` 视为同一个（基于 `owner/repo` 指纹，大小写不敏感）
   - 同一批次出现多次只保留一次

3. **查本地 `imported.txt` 已入库清单**
   - 读取 `imported.txt`（每行一个 `owner/repo`）
   - 文件不存在时视为空清单
   - 已在清单中的标记"已入库跳过"
   - 不在清单中的进入阶段二

```python
from assets.extractor import extract_github_urls, batch_deduplicate, filter_imported

urls = extract_github_urls("https://github.com/owner/repo 还有别的项目")
deduped = batch_deduplicate(urls)
new_urls, skipped = filter_imported(deduped)
```

---

## 阶段二：数据采集

对每条未入库的新链接，采集 README 和 Stars 数据：

```python
from assets.collector import collect_project_data, stars_to_score

readme, stars, error = collect_project_data("owner", "repo")
if error:
    print(f"采集失败: {error}")
else:
    community_score = stars_to_score(stars)
```

| 数据 | 获取方式 | URL |
|------|---------|-----|
| README 内容 | HTTP GET → raw.githubusercontent.com | `https://raw.githubusercontent.com/{owner}/{repo}/main/README.md` |
| Stars 数量 | HTTP GET → GitHub REST API | `https://api.github.com/repos/{owner}/{repo}` |

### 要点
- 无需 `git clone`，无需拉取配置文件
- README 获取失败时自动降级尝试 `master` 分支
- Stars 通过 GitHub API 获取（JSON 响应解析 `stargazers_count` 字段）
- 失败自动重试最多 3 次，间隔 1s
- 阶段二不做过滤，所有有效项目都进入阶段三

---

## 阶段三：LLM 分析

### Prompt 模板

将以下 Prompt 发送给 LLM，一次完成所有分析字段的输出：

```
你是一个专业的开源项目评估分析师。请根据以下 GitHub 项目的 README 内容和
Stars 数量，完成一次全面的项目评估分析。

项目名称: {repo_name}
Stars 数量: {stars}

{readme_content}

请以 JSON 格式输出以下字段：

1. "summary": 一句话简介（20字以内）
2. "project_type": 项目类型（MCP / Skill / Agent工具 / 项目）
3. "run_form": 运行形式（MCP-stdio / MCP-SSE / Skill / 不适用）
4. "target_user": 给谁用（Agent调用 / 本地运行 / 两者皆可）
5. "domain": 功能领域（PPT/演示文稿生成 | 学习资料/课程制作 | 音频生成/处理 |
   AI 视频生成/编辑 | AI 写作辅助 | 代码安全防御 | 代码测试/调试 |
   项目管理/CI | 架构/设计 | 数据分析与可视化 | AI 模型交互/编排 |
   通用工具 | 其他）
6. "tags": 能力标签数组
7. "highlights": 核心亮点文本
8. "doc_score": 文档评分（1-10）
9. "func_score": 功能评分（1-10）

仅输出一个 JSON 对象，不要包含 markdown 代码块标记或其他文字。
```

### 评分模型

| 维度 | 分值范围 | 计算方式 |
|------|---------|---------|
| 社区评分 | 1-10 | 本地换算：Stars 分档换算 |
| 文档评分 | 1-10 | LLM 评估 README 完善度 |
| 功能评分 | 1-10 | LLM 评估功能完整度 |

**社区评分换算表：**

| Stars 范围 | 分数 |
|-----------|------|
| 0-10 | 1 |
| 11-100 | 2 |
| 101-500 | 3 |
| 501-1000 | 4 |
| 1001-5000 | 5 |
| 5001-10000 | 6 |
| 10001-30000 | 7 |
| 30001-100000 | 8 |
| 100001+ | 9-10 |

**综合评分 = 社区评分 + 文档评分 + 功能评分**（总分 30 分）

---

## 阶段四：飞书入库 + 本地清单更新

### 飞书配置

配置方式一：设置环境变量

```bash
export FEISHU_BASE_TOKEN="your_base_token"
export FEISHU_TABLE_ID="your_table_id"
```

配置方式二：在代码中传入参数

```python
from assets.feishu_writer import write_record_with_retry

write_record_with_retry(
    fields={"项目名称": "xxx", ...},
    base_token="your_base_token",
    table_id="your_table_id"
)
```

### 字段映射

| 飞书字段 | 值来源 |
|---------|-------|
| `项目名称` | repo 名称 |
| `Git 地址` | 标准化后的 GitHub URL |
| `项目类型` | LLM 输出 |
| `项目描述` | LLM 输出 |
| `运行形式` | LLM 输出 |
| `给谁用` | LLM 输出 |
| `功能领域` | LLM 输出 |
| `能力标签` | LLM 输出 |
| `核心亮点` | LLM 输出 |
| `社区评分` | Stars 换算所得 |
| `文档评分` | LLM 输出 |
| `功能评分` | LLM 输出 |
| `综合评分` | 三项求和 |
| `评估日期` | 当前日期 |
| `状态` | 固定为"已入库" |

### 飞书写入命令

```bash
export FEISHU_BASE_TOKEN="your_base_token"
export FEISHU_TABLE_ID="your_table_id"

lark-cli base +create-record $FEISHU_BASE_TOKEN $FEISHU_TABLE_ID \
  --fields '{"项目名称":"...", "Git 地址":{"link":"https://..."}, ...}'
```

### 错误处理
- 单条失败不中断，继续处理下一条
- 最多重试 3 次，间隔 1s
- 记录失败原因

### 本地清单更新

写入飞书成功后立即追加到 `imported.txt`：

```python
from assets.tracker import append_to_imported_list
append_to_imported_list("owner/repo")
```

---

## 阶段五：输出汇总报告

```python
from assets.reporter import ReportItem, build_report

items = [
    ReportItem("https://github.com/owner/repo", "owner/repo", "success"),
    ReportItem("https://github.com/owner/repo2", "owner/repo2", "failed",
               error_reason="仓库不存在"),
]
report = build_report(items, feishu_base_url="your_feishu_url")
print(report.generate())
```

输出示例：

```
==================================================
  MCP/Skill 项目评估归档 — 汇总报告
==================================================

📊 统计概要
───────────────────────────────────
  总输入条数：      6
  已入库跳过：       2
  成功入库数：       3
  失败条数：         1

📋 按类型分布
───────────────────────────────────
  MCP：              2 个
  Skill：            1 个

❌ 失败明细
───────────────────────────────────
  [https://github.com/xxx/yyy] → 原因：仓库不存在

✅ 入库完成
───────────────────────────────────
  评估日期：2026-05-27
```

---

## 可用技能

| Skill | 用途 |
|-------|------|
| `web-access-2.5.1` | WebFetch 获取 README（备选数据采集方式） |
| `lark-base` | 飞书多维表格读写操作 |

> **提示**：数据采集优先使用辅助脚本（`assets/collector.py`）直接 HTTP 请求。GitHub API 返回结构化 JSON，比 WebFetch 爬取 HTML 页面更可靠。web-access skill 作为备选方案。

---

## 设计原则

1. **如无需要，不必新增**：每个阶段只做必要操作，不做过度分析
2. **全量入库**：MCP、Skill、Agent 工具、普通项目全部入库，类型由 LLM 区分
3. **本地去重**：以 `imported.txt` 为准，不与飞书比对（飞书数据可自由过滤）
4. **一次 LLM**：所有分析字段在一次 Prompt 中完成，不拆分多次调用
5. **不 clone**：只用 HTTP 请求拉取公开内容，不 git clone