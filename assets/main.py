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

    print(f"\n\U0001f4ca 处理完成：{len(completed)} 个成功，{len(failed)} 个失败")
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