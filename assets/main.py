import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)


def _import_module(module_path: str):
    module_cache = {}
    if module_path in module_cache:
        return module_cache[module_path]
    module = __import__(module_path, fromlist=[""])
    module_cache[module_path] = module
    return module


def phase1_extract(text: str):
    ext = _import_module("assets.extractor")
    urls = ext.extract_github_urls(text)
    if not urls:
        print("未发现有效的 GitHub 仓库链接")
        return [], []
    deduped = ext.batch_deduplicate(urls)
    new_urls, skipped = ext.filter_imported(deduped)
    print(f"\U0001f4e5 阶段一：链接提取完成")
    print(f"  提取到 {len(urls)} 个链接，去重后 {len(deduped)} 个")
    print(f"  新项目：{len(new_urls)} 个，已入库跳过：{len(skipped)} 个")
    for url in skipped:
        print(f"    \u23ed {url}")
    return new_urls, skipped


def phase2_collect(url: str):
    ext = _import_module("assets.extractor")
    col = _import_module("assets.collector")
    owner, repo = ext.parse_owner_repo(url)
    print(f"\n\U0001f50d 阶段二：采集数据 [{owner}/{repo}]")
    readme, stars, error = col.collect_project_data(owner, repo)
    if error:
        print(f"  \u274c 采集失败: {error}")
        return None, None, error
    print(f"  \u2705 README 获取成功 ({len(readme)} 字符)")
    print(f"  \u2b50 Stars: {stars}")
    return readme, stars, None


def phase3_analyze(repo_name: str, readme: str, stars: int):
    an = _import_module("assets.analyzer")
    print(f"\n\U0001f9e0 阶段三：LLM 分析 [{repo_name}]")
    prompt = an.build_analysis_prompt(repo_name, stars, readme)
    print(f"  Prompt 已构建 ({len(prompt)} 字符)")
    print(f"  \u2139 请将以上 Prompt 发送给 LLM 进行分析")
    print(f"  预期输出：结构化 JSON（类型/分类/标签/评分）")
    return prompt


def phase4_feishu_or_local(completed_items: list, failed_items: list) -> dict:
    fw = _import_module("assets.feishu_writer")
    st = _import_module("assets.storage")
    rp = _import_module("assets.reporter")

    has_feishu = fw.is_feishu_configured()
    all_items = []
    local_saved = False

    if not has_feishu:
        print(f"\n\U0001f4e6 阶段四：未检测到飞书配置，本地暂存")
        for url, owner_repo, stars, readme in completed_items:
            print(f"  \U0001f4e5 暂存 [{owner_repo}]")
            all_items.append(rp.ReportItem(url, owner_repo, "skipped",
                                           error_reason="本地暂存（未上传）"))
        local_saved = True
    else:
        print(f"\n\U0001f4e5 阶段四：已检测到飞书配置")
        pending_count = st.count_items()
        if pending_count > 0:
            print(f"  \U0001f4e5 检测到 {pending_count} 条本地待上传记录，将一并上传")
        for url, owner_repo, stars, readme in completed_items:
            print(f"  \u2705 可上传 [{owner_repo}]")
            all_items.append(rp.ReportItem(url, owner_repo, "success"))

    for url, owner_repo, error in failed_items:
        all_items.append(rp.ReportItem(url, owner_repo, "failed",
                                       error_reason=error))

    return {"items": all_items, "local_saved": local_saved}


def phase5_report(report_data: dict):
    rp = _import_module("assets.reporter")
    report = rp.build_report(report_data["items"])
    print("\n" + report.generate())
    if report_data["local_saved"]:
        print()
        print("  \u2139 提示：配置飞书环境变量后重新运行此工具")
        print("       export FEISHU_BASE_TOKEN=\"your_base_token\"")
        print("       export FEISHU_TABLE_ID=\"your_table_id\"")
        print("       \u2192 配置后会自动将本地暂存记录 + 新结果一并上传到飞书")


def main():
    if len(sys.argv) < 2:
        print("用法: python assets/main.py \"https://github.com/owner/repo ...\"")
        print("示例: python assets/main.py \"我找到一个好用的PPT MCP https://github.com/A/B\"")
        return 1

    input_text = " ".join(sys.argv[1:])
    print("=" * 50)
    print("  Batch Link Import - 批量导入工具")
    print("=" * 50)

    new_urls, skipped = phase1_extract(input_text)

    if not new_urls:
        print("\n无新项目需要处理。")
        report = _build_empty_report(skipped)
        print(report.generate())
        return 0

    ext = _import_module("assets.extractor")
    completed = []
    failed = []

    for url in new_urls:
        owner, repo = ext.parse_owner_repo(url)
        readme, stars, error = phase2_collect(url)
        if error:
            failed.append((url, f"{owner}/{repo}", error))
            continue

        phase3_analyze(repo, readme, stars)
        completed.append((url, f"{owner}/{repo}", stars, readme))

    print(f"\n\U0001f4ca 采集完成：{len(completed)} 个成功，{len(failed)} 个失败")

    report_data = phase4_feishu_or_local(completed, failed)
    phase5_report(report_data)

    return 0


def _build_empty_report(skipped):
    rp = _import_module("assets.reporter")
    items = []
    for url in skipped:
        ext = _import_module("assets.extractor")
        key = ext.owner_repo_key(url)
        items.append(rp.ReportItem(url, key, "skipped"))
    return rp.build_report(items)


if __name__ == "__main__":
    sys.exit(main())