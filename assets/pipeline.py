import json
from typing import Dict, List, Tuple, Optional

from assets.analyzer import AnalysisResult
from assets.feishu_writer import write_record_with_retry, is_feishu_configured
from assets.tracker import append_to_imported_list


def export_analysis_prompts(
    collected_file: str,
    output_file: str = "analysis_prompts.txt",
    max_readme_chars: int = 4000,
) -> int:
    """从采集数据导出截断后的 README 到文本文件，供 LLM 批量分析使用。

    Args:
        collected_file: collected_data.json 的路径
        output_file: 输出文本文件路径
        max_readme_chars: README 截断长度（默认 4000 字符）

    Returns:
        成功导出的项目数量
    """
    with open(collected_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    with open(output_file, "w", encoding="utf-8") as out:
        for i, d in enumerate(data):
            if d.get("error"):
                out.write(
                    f"=== [{i}] {d['owner']}/{d['repo']} === FAILED: {d['error']}\n"
                    f"===END===\n\n"
                )
                continue

            readme = d.get("readme") or ""
            truncated = readme[:max_readme_chars]
            if len(readme) > max_readme_chars:
                truncated += "...[truncated]"

            out.write(f"=== [{i}] {d['owner']}/{d['repo']} (stars={d.get('stars', 0)}) ===\n")
            out.write(truncated + "\n")
            out.write("===END===\n\n")
            count += 1

    print(f"导出完成：{count} 个项目 → {output_file}")
    return count


def batch_upload_from_files(
    collected_file: str,
    analysis_file: str,
    base_token: str = "",
    table_id: str = "",
) -> Dict:
    """从采集数据和分析结果批量上传到飞书多维表格。

    Args:
        collected_file: collected_data.json 的路径
        analysis_file: analysis_results.json 的路径（dict，key 为 owner/repo）
        base_token: 飞书 Base Token（为空则从环境变量读取）
        table_id: 飞书 Table ID（为空则从环境变量读取）

    Returns:
        {"success": int, "failed": int, "skipped": int, "items": List[ReportItem]}
    """
    if not is_feishu_configured() and (not base_token or not table_id):
        print("飞书未配置，无法上传")
        return {"success": 0, "failed": 0, "skipped": 0, "items": []}

    with open(collected_file, "r", encoding="utf-8") as f:
        collected = json.load(f)
    with open(analysis_file, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    from assets.reporter import ReportItem, build_report

    report_items: List[ReportItem] = []
    success_count = 0
    fail_count = 0
    skip_count = 0

    for d in collected:
        owner = d["owner"]
        repo = d["repo"]
        owner_repo = f"{owner}/{repo}"
        url = d["url"]

        if d.get("error"):
            report_items.append(ReportItem(url, owner_repo, "failed", error_reason=d["error"]))
            fail_count += 1
            continue

        if owner_repo not in analysis:
            report_items.append(
                ReportItem(url, owner_repo, "failed", error_reason="Analysis not found")
            )
            fail_count += 1
            continue

        ar = analysis[owner_repo]
        stars_val = d.get("stars") or 0

        result = AnalysisResult(
            summary=ar["summary"],
            project_type=ar["project_type"],
            run_form=ar["run_form"],
            target_user=ar["target_user"],
            domain=ar["domain"],
            tags=ar["tags"],
            highlights=ar["highlights"],
            doc_score=ar["doc_score"],
            func_score=ar["func_score"],
        )
        fields = result.to_feishu_fields(repo, url, stars_val)

        print(f"  [{owner_repo}] ... ", end="", flush=True)
        if write_record_with_retry(fields, base_token=base_token, table_id=table_id):
            append_to_imported_list(owner_repo)
            print("OK")
            success_count += 1
            report_items.append(
                ReportItem(url, owner_repo, "success", project_type=ar["project_type"])
            )
        else:
            print("FAILED")
            fail_count += 1
            report_items.append(
                ReportItem(url, owner_repo, "failed", error_reason="Feishu write failed")
            )

    report = build_report(report_items)
    print("\n" + report.generate())
    print(f"\n上传完成: {success_count} 成功, {fail_count} 失败, {skip_count} 跳过")

    return {
        "success": success_count,
        "failed": fail_count,
        "skipped": skip_count,
        "items": report_items,
    }