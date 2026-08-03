import os
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from assets import extractor, collector, analyzer, tracker, storage


class ExtractorTest(unittest.TestCase):
    def test_extract_basic(self):
        text = "看看 https://github.com/langchain-ai/langchain-mcp-server 和 https://github.com/axios/axios"
        urls = extractor.extract_repo_urls(text)
        self.assertEqual(urls, [
            "https://github.com/axios/axios",
            "https://github.com/langchain-ai/langchain-mcp-server",
        ])

    def test_extract_gitee(self):
        text = "github https://github.com/foo/bar 与 gitee https://gitee.com/baz/qux 和 gitee ssh git@gitee.com:x/y.git"
        urls = extractor.extract_repo_urls(text)
        self.assertEqual(urls, [
            "https://gitee.com/baz/qux",
            "https://gitee.com/x/y",
            "https://github.com/foo/bar",
        ])

    def test_extract_dedup_in_batch(self):
        text = ("https://github.com/foo/bar https://github.com/foo/bar "
                "https://github.com/foo/bar.git")
        urls = extractor.extract_repo_urls(text)
        self.assertEqual(urls, ["https://github.com/foo/bar"])

    def test_ignores_non_repo_pages(self):
        text = ("https://github.com/settings/profile "
                "https://github.com/sponsors/foo "
                "https://github.com/trending")
        self.assertEqual(extractor.extract_repo_urls(text), [])

    def test_ssh_format(self):
        text = "git@github.com:owner/repo.git"
        self.assertEqual(extractor.extract_repo_urls(text),
                         ["https://github.com/owner/repo"])

    def test_parse_repo_platform(self):
        self.assertEqual(extractor.parse_repo("https://gitee.com/a/b"), ("gitee", "a", "b"))
        self.assertEqual(extractor.parse_repo("https://github.com/a/b"), ("github", "a", "b"))

    def test_filter_imported_and_pending(self):
        with tempfile.TemporaryDirectory() as d:
            imported = os.path.join(d, "imported.txt")
            pending = os.path.join(d, "pending.json")
            with open(imported, "w", encoding="utf-8") as f:
                f.write("foo/bar\n")
            with open(pending, "w", encoding="utf-8") as f:
                f.write('[{"_owner_repo": "baz/qux"}]')
            tracker.IMPORTED_FILE = __import__("pathlib").Path(imported)
            storage.PENDING_FILE = pending
            urls = [
                "https://github.com/foo/bar",
                "https://github.com/baz/qux",
                "https://github.com/new/repo",
            ]
            new, imp = extractor.filter_imported(urls)
            self.assertEqual(imp, ["https://github.com/foo/bar"])
            self.assertEqual(set(new), {
                "https://github.com/baz/qux",
                "https://github.com/new/repo",
            })
            new2, pend = extractor.filter_pending(new)
            self.assertEqual(pend, ["https://github.com/baz/qux"])
            self.assertEqual(new2, ["https://github.com/new/repo"])


class CollectorTest(unittest.TestCase):
    def test_stars_to_score(self):
        cases = [
            (0, 1), (10, 1), (11, 2), (100, 2), (101, 3),
            (500, 3), (1000, 4), (5000, 5), (10000, 6),
            (30000, 7), (100000, 8), (500000, 9), (500001, 10),
        ]
        for stars, expected in cases:
            self.assertEqual(collector.stars_to_score(stars), expected,
                             msg=f"stars={stars}")


class AnalyzerTest(unittest.TestCase):
    def test_parse_plain_json(self):
        r = analyzer.parse_llm_response('{"summary":"x","project_type":"MCP","doc_score":7,"func_score":8}')
        self.assertIsNotNone(r)
        self.assertEqual(r.project_type, "MCP")
        self.assertEqual(r.doc_score, 7)

    def test_parse_fenced_json(self):
        r = analyzer.parse_llm_response('```json\n{"summary":"y","doc_score":5}\n```')
        self.assertIsNotNone(r)
        self.assertEqual(r.summary, "y")

    def test_parse_invalid(self):
        self.assertIsNone(analyzer.parse_llm_response("not json at all"))
        self.assertIsNone(analyzer.parse_llm_response(""))

    def test_to_feishu_fields_all_mapped(self):
        # feishu_fields.json 已把全部字段映射到真实列，to_feishu_fields 应写出 15 列，
        # 包括此前为 null 的四个字段：项目类型 / 运行形式 / 社区评分 / 状态
        r = analyzer.AnalysisResult(
            summary="s", project_type="MCP", run_form="MCP-stdio",
            target_user="Agent调用", domain="通用工具",
            doc_score=7, func_score=8)
        fields = r.to_feishu_fields("repo", "https://github.com/o/repo", 300)
        # 15 个逻辑字段全部写出（无字段被跳过）
        self.assertEqual(len(fields), 15)
        self.assertEqual(fields["fldWipEsqn"], "repo")        # 项目名称
        self.assertEqual(fields["fld3urADAF"], "MCP")        # 项目类型（此前为 null）
        self.assertEqual(fields["fldtoRnPG9"], "MCP-stdio")  # 运行形式（此前为 null）
        self.assertEqual(fields["fldNXvEbeG"], "Agent调用")  # 给谁用
        self.assertEqual(fields["fldS6Xnn6h"], "通用工具")   # 功能领域
        self.assertEqual(fields["fldz26W1X4"], "已入库")     # 状态（此前为 null）
        # 评分
        self.assertEqual(fields["fldqHZ3KZt"], 3)            # 社区评分 = stars_to_score(300)=3（此前为 null）
        self.assertEqual(fields["fldOdZy7KC"], 7)            # 文档评分
        self.assertEqual(fields["fldCbpLXal"], 8)            # 功能评分
        self.assertEqual(fields["fldQIa5t33"], 18)           # 综合评分 = 3+7+8
        # 评估日期为完整 datetime 格式 YYYY-MM-DD HH:MM:SS
        self.assertRegex(fields["fldztznzza"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class TrackerTest(unittest.TestCase):
    def test_append_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "imported.txt")
            tracker.IMPORTED_FILE = __import__("pathlib").Path(p)
            tracker.append_to_imported_list("Foo/Bar")
            tracker.append_to_imported_list("foo/bar")  # 重复（大小写不敏感）
            tracker.append_to_imported_list("baz/qux")
            with open(p, encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(lines, ["foo/bar", "baz/qux"])


if __name__ == "__main__":
    unittest.main()
