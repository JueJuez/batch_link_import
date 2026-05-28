# MCP/Skill 项目评估归档 Agent — 任务拆解清单

## 任务总览

| 阶段 | 任务数 | 状态 |
|------|--------|------|
| 阶段 0：环境准备 | 2 个 | ✅ 已完成 |
| 阶段 1：核心分析管线 | 3 个 | ✅ 已完成 |
| 阶段 2：飞书入库集成 | 2 个 | ✅ 已完成 |
| 阶段 3：报告输出 | 2 个 | ✅ 已完成 |
| 阶段 4：测试验证 | 2 个 | ✅ 已完成 |
| **总计** | **11 个** | **全部完成** |

---

## 阶段 0：环境准备与基础设施 ✅

### 任务 0.1：确认 web-access skill 可用性 ✅

**描述**：验证 web-access-2.5.1 skill 已安装并可用，能正常执行 WebFetch 操作。

**子步骤**：
1. 确认 `web-access-2.5.1` skill 已在环境中安装
2. 测试 WebFetch 访问 `https://raw.githubusercontent.com/` 和 `https://api.github.com/`
3. 验证可正常获取文本内容（README.md）和 JSON 数据（GitHub API）
4. 记录 WebFetch 返回格式和注意事项（如限流情况）

**验收条件**：
- ✅ web-access skill 可正常调用 WebFetch
- ✅ 能通过 raw.githubusercontent.com 获取文件内容
- ✅ 能通过 api.github.com 获取仓库元数据
- ✅ 明确无认证情况下的限流阈值（60 req/h）

---

### 任务 0.2：确认 lark-cli 和 lark-base 可用性 ✅

**描述**：确认环境中 lark-cli 已登录，且有权操作多维表格。

**子步骤**：
1. 确认 `lark-cli` 已安装并可正常登录
2. 确认 `lark-cli auth` 状态（已登录的用户身份）
3. 测试 `lark-cli base +create-record` 命令的可用性
4. 在飞书中创建目标多维表格，按 spec.md 中的字段 Schema 建好各列

**验收条件**：
- ✅ lark-cli 可正常调用 base 命令
- ✅ 目标多维表格已创建，各字段类型与 spec.md 一致
- ✅ 记下 `base_token` 和 `table_id`（需自行创建多维表格后获取）

---

### 任务 0.3：创建项目骨架 ✅

**描述**：搭建 lark-cli skill 项目的基本目录结构。

**子步骤**：
1. 创建 `batch-link-import/` 目录
2. 创建 `SKILL.md`（标准 skill 主文件，含 YAML frontmatter）
3. 移动 `spec.md` 和 `tasks.md` 到 `references/` 目录
4. 创建 `assets/` 目录（辅助脚本）

```
batch-link-import/
├── SKILL.md             # Skill 主指令（模型的 prompt，含 YAML 头）
├── pyproject.toml       # Python 项目配置
├── imported.txt         # 已入库项目清单
├── references/
│   ├── spec.md          # 设计规格
│   └── tasks.md         # 任务拆解
└── assets/              # Python 辅助脚本
    ├── __init__.py
    ├── extractor.py
    ├── collector.py
    ├── analyzer.py
    ├── feishu_writer.py
    ├── tracker.py
    ├── reporter.py
    └── main.py
```

**验收条件**：
- ✅ 目录结构符合标准 skill 规范
- ✅ SKILL.md 有完整的 YAML frontmatter（name, version, description, metadata）
- ✅ references/ 下已有 spec.md 和 tasks.md
- ✅ assets/ 下已有完整的辅助脚本

**交付物**：
- `SKILL.md`（标准 skill 主文件）
- `references/spec.md` 和 `references/tasks.md`（参考文档）
- `assets/` 下的 Python 辅助脚本

---

## 阶段 1：核心分析管线 ✅

### 任务 1.1：链接提取 + 本地去重模块 ✅

**描述**：实现从用户输入中提取 GitHub 仓库 URL，并通过本地 imported.txt 清单去重。

**实现位置**：[assets/extractor.py](file:///d:/Code/Skills/batch_link_import/assets/extractor.py)

**子步骤**：
1. 实现 `extract_github_urls(text)` — 正则匹配 + `_NON_REPO_OWNERS` 黑名单过滤非仓库页面
2. 实现 `normalize_url(url)` — 统一输出 `https://github.com/{owner}/{repo}` 格式
3. 实现 `batch_deduplicate(urls)` — 基于 `{owner}/{repo}` 指纹做批次内去重（大小写不敏感）
4. 实现 `load_imported_list()` / `filter_imported(urls)` — 本地 imported.txt O(1) 查重

**输入输出**：
```
输入: "我找到一个好用的PPT MCP https://github.com/A/B 还有 https://github.com/C/D"
输出: 新项目: ["https://github.com/C/D"]
      已入库跳过: ["https://github.com/A/B"]
      （假设 A/B 已在 imported.txt 中）
```

**验收条件**：
- ✅ 支持文本段落中提取多个 URL
- ✅ 支持 `https://` 和 `git@` 两种格式
- ✅ 非仓库页面（settings/profile、notifications 等）被 `_NON_REPO_OWNERS` 黑名单过滤
- ✅ 批次内去重正确（`A/B.git` 和 `A/B` 视为同一个）
- ✅ 本地 imported.txt 去重正确（大小写不敏感）
- ✅ imported.txt 不存在时优雅处理（视为空清单）

---

### 任务 1.2：数据采集模块 ✅

**描述**：对给定仓库，通过 HTTP 请求获取 README 和 Stars 数。无需 git clone，无需配置文件。

**实现位置**：[assets/collector.py](file:///d:/Code/Skills/batch_link_import/assets/collector.py)

**子步骤**：
1. 实现 `collect_project_data(owner, repo)` — 自动采集完整数据
   - README：`https://raw.githubusercontent.com/{owner}/{repo}/main/README.md`
   - Stars：`https://api.github.com/repos/{owner}/{repo}`（JSON API）
   - 失败降级：README 不存在则尝试 master 分支
   - 重试机制：最多 3 次，间隔 1s

**验收条件**：
- ✅ 能正确读取任意公开仓库的 README（已验证 tensorflow/tensorflow ✅）
- ✅ 能通过 GitHub API 正确获取 Stars 数（已验证 tensorflow/tensorflow: 195K Stars ✅）
- ✅ README 不存在时优雅降级（404 → 标记失败 ✅）
- ✅ 自动重试机制（3 次，间隔 1s ✅）

---

### 任务 1.3：LLM 综合分析模块 ✅

**描述**：基于 README + Stars，通过一次 LLM Prompt 完成项目分类、打标和评分。

**实现位置**：[assets/analyzer.py](file:///d:/Code/Skills/batch_link_import/assets/analyzer.py)

**子步骤**：
1. 定义 `AnalysisResult` 数据模型（dataclass + Feishu 字段映射）
2. 定义 `ANALYSIS_PROMPT` 模板（含评分维度说明）
3. 实现 `parse_llm_response(response)` — 解析 LLM 返回的 JSON（含 code block 剥离）

**设计要点**：
- 以上所有评估项合并为**一次 LLM Prompt 调用**
- Prompt 输入：README 全文 + Stars 数
- Prompt 输出：结构化 JSON，包含所有字段
- 社区评分不在 LLM 中计算，调用方根据 Stars 本地换算（`collector.stars_to_score()`）
- 所有项目不分类型都走此分析，由 LLM 自行判断类型

**验收条件**：
- ✅ 一次 Prompt 正确输出所有评估字段
- ✅ 输出格式为结构化 JSON，可直接映射到飞书字段
- ✅ LLM Prompt 模板清晰可复用，已在 SKILL.md 中完整记录
- ✅ JSON 解析器可处理带 ` ```json ` 代码块的 LLM 输出

---

## 阶段 2：飞书入库集成 ✅

### 任务 2.1：飞书多维表格写入 + 本地清单更新 ✅

**描述**：将评估结果批量写入飞书多维表格，写入成功后更新本地 imported.txt。

**实现位置**：[assets/feishu_writer.py](file:///d:/Code/Skills/batch_link_import/assets/feishu_writer.py)

**子步骤**：
1. 实现 `write_record(fields)` — 调用 `lark-cli base +create-record`
2. 实现 `write_record_with_retry(fields)` — 失败后重试 3 次，间隔 1s
3. 字段映射：`AnalysisResult.to_feishu_fields()` 将评估结果转换为飞书字段格式
4. 写入成功后调用 `tracker.append_to_imported_list()` 追加到 imported.txt

**验收条件**：
- ✅ 单条飞书写入接口已实现（`write_record` / `write_record_with_retry`）
- ✅ 字段映射完整（`AnalysisResult.to_feishu_fields()` 输出 15 个字段）
- ✅ 单条失败不阻塞整体
- ✅ 重试逻辑已实现（3 次，间隔 1s）
- ✅ lark-cli 不可用时优雅降级（不崩溃）

---

### 任务 2.2：本地 imported.txt 维护 ✅

**描述**：实现 imported.txt 的读写、追加管理。

**实现位置**：[assets/tracker.py](file:///d:/Code/Skills/batch_link_import/assets/tracker.py)

**子步骤**：
1. 实现 `load_imported_list()` — 逐行读取为 Set（大小写不敏感）
2. 实现 `append_to_imported_list(owner_repo)` — 追加写入
3. 实现 `init_imported_file()` — 文件不存在时创建并写入注释头

**验收条件**：
- ✅ 成功读取和解析 imported.txt（已验证 ✅）
- ✅ 写入后清单正确更新
- ✅ 空文件/不存在时优雅处理

---

## 阶段 3：报告输出 ✅

### 任务 3.1：统计汇总 ✅

**描述**：计算汇总统计信息。

**实现位置**：[assets/reporter.py](file:///d:/Code/Skills/batch_link_import/assets/reporter.py)

**子步骤**：
1. `Report` 数据模型自动统计：总输入、已入库跳过、成功入库、失败条数
2. 按项目类型统计分布：MCP / Skill / Agent工具 / 项目
3. 收集失败记录明细（`ReportItem` 含 error_reason）

**验收条件**：
- ✅ 统计数据准确（已验证 ✅）
- ✅ 明细信息可追溯

---

### 任务 3.2：报告生成 ✅

**描述**：格式化输出汇总报告。

**实现位置**：[assets/reporter.py](file:///d:/Code/Skills/batch_link_import/assets/reporter.py)

**子步骤**：
1. `Report.generate()` 按 spec.md 中的报告格式生成文本
2. 报告包含：统计概要 + 按类型分布 + 失败明细 + 入库完成信息

**验收条件**：
- ✅ 报告格式清晰完整已验证（纯文本控制台输出 ✅）
- ✅ 包含所有必要信息：统计概要 + 类型分布 + 失败明细 + 飞书链接 + 日期
- ✅ 失败和跳过的原因可读

---

## 阶段 4：测试验证 ✅

### 任务 4.1：端到端流程验证 ✅

**描述**：用真实项目跑通完整流程。

**实现位置**：[assets/main.py](file:///d:/Code/Skills/batch_link_import/assets/main.py)

**测试用例**：

| 用例 | 项目 | 预期结果 | 验证状态 |
|------|------|---------|---------|
| 真实数据采集 | tensorflow/tensorflow | README + Stars 获取成功 | ✅ |
| 真实数据采集 | axios/axios | README + Stars 获取成功 | ✅ |
| 不存在的仓库 | thisrepo/doesnotexist12345 | 404 错误，记录失败原因 | ✅ |
| 多链接入场 | 2 新 + 1 无效 | 新项目正确采集，无效报错 | ✅ |

**验收条件**：
- ✅ 管线 5 阶段无异常（main.py 执行已验证 ✅）
- ✅ 数据采集正确（README + Stars ✅）
- ✅ 失败处理正确（404/超时等异常 ✅）
- ✅ 汇总报告格式正确（reporter.py 已验证 ✅）

---

### 任务 4.2：边界条件验证 ✅

**描述**：验证系统在边界条件下的稳定性。

**实现位置**：单元测试验证，记录在 [spec.md §13](file:///d:/Code/Skills/batch_link_import/references/spec.md#L506)

**测试用例**：
1. 空输入（无有效链接）→ 提示用户后优雅退出 ✅
2. 重复链接（同一条出现 3 次）→ 去重后只处理 1 次 ✅
3. 飞书多维表格连接失败 → 优雅降级，不崩溃 ✅
4. 网络中断 → 超时重试逻辑正常（3 次重试 ✅）

---

---

## 阶段 5：优化与重构 ✅

### 任务 5.1：本地暂存 + 增量上传机制 ✅

**描述**：未配置飞书环境变量时，评估结果暂存到本地 `pending_results.json`，配置后自动全部上传。

**子步骤**：
1. 创建 `assets/storage.py` — 本地暂存读写管理
2. `feishu_writer.py` 新增 `is_feishu_configured()` — 检测环境变量
3. 更新 SKILL.md 阶段四 — 分场景 A（已配飞书→上传）和场景 B（未配飞书→本地暂存）
4. 更新 `main.py` — 编排阶段四/五，自动检测飞书配置走对应分支

**验收条件**：
- ✅ 未配飞书时结果自动追加到 `pending_results.json`，提示配置
- ✅ 已配飞书时先上传本地暂存记录，再传本次新结果
- ✅ 上传成功后清空本地暂存，写入 `imported.txt`

---

### 任务 5.2：消除 imported.txt 和 pending_results.json 功能重叠 ✅

**描述**：优化全流程去重逻辑，两个文件职责分明、互补，消除冗余。

**子步骤**：
1. 删除 `extractor.py` 中重复的 `IMPORTED_FILE` / `load_imported_list()`（复用 tracker.py）
2. `storage.py` 新增 `owner_repo_keys()` — 提取暂存记录的 owner/repo 集合
3. `extractor.py` 新增 `filter_pending()` — 阶段一也检查 pending_results.json
4. `reporter.py` 新增 `local_count` / `not_uploaded` — 本地暂存独立统计
5. 更新 `main.py` 阶段一 — 三层去重（批次内 → imported → pending）

**验收条件**：
- ✅ `extractor.py` 不再定义 `IMPORTED_FILE`，从 `tracker.py` 导入
- ✅ 阶段一同时查 `imported.txt` 和 `pending_results.json`
- ✅ 报告区分"已入库跳过"、"待上传跳过"和"成功入库"

## 依赖关系图

```
0.1 web-access 可用性 ───┐
                          │
0.2 lark-cli 可用性 ──────┤
                          │
0.3 项目骨架 ─────────────┤
    ├── 1.1 链接提取 ──────┤
    ├── 1.2 数据采集 ──────┤
    │                     ├──▶ 1.3 LLM 分析 ──▶ 2.1 飞书入库 ──▶ 3.1 统计 ──▶ 3.2 报告
    │                     │                         │
    └─────────────────────┘                         │
      2.2 imported.txt 维护 ◀────────────────────────┘
```

**关键路径**：0.3 → 1.1 → 1.2 → 1.3 → 2.1 → 3.1 → 3.2

---

## 总任务清单（汇总视图）

| # | 任务 | 前置依赖 | 优先级 | 状态 |
|---|------|---------|--------|------|
| 0.1 | 确认 web-access skill 可用性 | 无 | P0 | ✅ |
| 0.2 | 确认 lark-cli 可用性 | 无 | P0 | ✅ |
| 0.3 | 创建项目骨架 | 无 | P0 | ✅ |
| 1.1 | 链接提取 + 本地去重模块 | 0.3 | P0 | ✅ |
| 1.2 | 数据采集模块 | 0.1, 0.3 | P0 | ✅ |
| 1.3 | LLM 综合分析模块 | 1.2 | P0 | ✅ |
| 2.1 | 飞书入库 + 本地清单更新 | 0.2, 1.3 | P0 | ✅ |
| 2.2 | 本地 imported.txt 维护 | 0.3 | P1 | ✅ |
| 3.1 | 统计汇总 | 2.1 | P0 | ✅ |
| 3.2 | 报告生成 | 3.1 | P0 | ✅ |
| 4.1 | 端到端流程验证 | 全部 | P0 | ✅ |
| 4.2 | 边界条件验证 | 4.1 | P1 | ✅ |
| 5.1 | 本地暂存 + 增量上传机制 | 2.1 | P1 | ✅ |
| 5.2 | 消除 imported.txt 和 pending_results.json 功能重叠 | 5.1 | P1 | ✅ |

---

## 技能使用指南（开发时调用）

以下指引说明在开发过程中，何时应调用当前环境中的内置 skill 来辅助开发：

### 从 GitHub 获取仓库内容时

```
调用：web-access-2.5.1 skill
场景：
  - 任务 1.2：用 WebFetch 拉取 README、配置文件、GitHub 元数据
```

### 操作飞书多维表格时

```
调用：lark-base skill
场景：
  - 任务 0.2：确认 lark-cli 可用性后，用此 skill 搜索或创建多维表格
  - 任务 2.1：写入评估记录时，用 `lark-cli base +create-record`
```

### 首次创建 Agent 项目时

```
调用：skill-creator skill
场景：
  - 任务 0.3：生成标准的 lark-cli skill 项目骨架
```