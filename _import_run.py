from assets.analyzer import AnalysisResult
from assets.collector import collect_project_data
from assets.feishu_writer import write_record_with_retry
from assets.storage import has_items, pop_all
from assets.tracker import append_to_imported_list

# Phase 4 pre: upload any pending items first
if has_items():
    pending = pop_all()
    for item in pending:
        fields = {k: v for k, v in item.items() if not k.startswith("_")}
        if write_record_with_retry(fields):
            append_to_imported_list(item["_owner_repo"])
            print(f"[PENDING UPLOADED] {item['_owner_repo']}")
        else:
            print(f"[PENDING FAILED] {item['_owner_repo']}")
else:
    print("[PENDING] No pending items.")

results = [
    {
        "owner": "hugohe3",
        "repo": "ppt-master",
        "url": "https://github.com/hugohe3/ppt-master",
        "analysis": {
            "summary": "AI驱动从文档生成原生可编辑PPTX",
            "project_type": "项目",
            "run_form": "不适用",
            "target_user": "本地运行",
            "domain": "PPT/演示文稿生成",
            "tags": ["AI生成PPT", "PPTX导出", "文档转PPT", "原生可编辑", "多格式支持"],
            "highlights": "从任意文档（PDF/Word/Markdown等）一键生成原生可编辑的PPTX文件，支持自定义模板和主题",
            "doc_score": 8,
            "func_score": 8,
        }
    },
    {
        "owner": "zarazhangrui",
        "repo": "frontend-slides",
        "url": "https://github.com/zarazhangrui/frontend-slides",
        "analysis": {
            "summary": "AI Agent驱动的HTML演示文稿生成技能",
            "project_type": "Skill",
            "run_form": "Skill",
            "target_user": "Agent调用",
            "domain": "PPT/演示文稿生成",
            "tags": ["AI生成幻灯片", "HTML演示文稿", "Skill", "Claude Code插件", "PPT转换", "网页演示"],
            "highlights": "专为AI编程Agent设计的幻灯片生成技能，零CSS/JS知识即可创建精美网页演示，采用show-dont-tell交互方式",
            "doc_score": 8,
            "func_score": 8,
        }
    },
]

for r in results:
    readme, stars, error = collect_project_data(r["owner"], r["repo"])
    if error:
        print(f"[FAILED] {r['owner']}/{r['repo']}: {error}")
        continue

    result = AnalysisResult(**r["analysis"])
    fields = result.to_feishu_fields(r["repo"], r["url"], stars)
    print(f"Fields for {r['repo']}:", fields)

    if write_record_with_retry(fields):
        append_to_imported_list(f"{r['owner']}/{r['repo']}")
        print(f"[OK] {r['owner']}/{r['repo']} written to Feishu")
    else:
        print(f"[FAILED] {r['owner']}/{r['repo']} write failed")