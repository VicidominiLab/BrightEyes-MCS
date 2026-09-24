"""The documentation gate must reject bad local references without network access."""

import importlib.util
from pathlib import Path
from collections import Counter
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "check_docs", Path(__file__).resolve().parents[1] / "scripts" / "check_docs.py",
)
check_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_docs)

lint_spec = importlib.util.spec_from_file_location(
    "check_lint", Path(__file__).resolve().parents[1] / "scripts" / "check_lint.py",
)
check_lint = importlib.util.module_from_spec(lint_spec)
lint_spec.loader.exec_module(check_lint)


def test_local_links_anchors_and_repository_references(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "target.md").write_text("# A heading\n", encoding="utf-8")
    page = tmp_path / "README.md"
    page.write_text(
        "[good](docs/target.md#a-heading)\n"
        "[bad](docs/missing.md)\n"
        "[heading](docs/target.md#missing)\n"
        "`brighteyes_mcs/removed.py`\n"
        "[online](https://example.com/guide)\n",
        encoding="utf-8",
    )
    errors, external = check_docs.check_document(page, tmp_path)
    assert len(errors) == 3
    assert external == {"https://example.com/guide"}


def test_relative_links_and_duplicate_headings(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    page = docs / "guide.md"
    page.write_text(
        "# Repeated\n# Repeated\n"
        "[root](../README.md#root)\n[second](#repeated-1)\n"
        "```text\n[example](missing.md)\n```\n",
        encoding="utf-8",
    )
    assert check_docs.check_document(page, tmp_path) == ([], set())


def test_lint_gate_rejects_new_findings_and_allows_removals(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        '[{"key": ["legacy.py", "F401", "Unused", "import os"], "count": 1}]',
        encoding="utf-8",
    )
    with patch.object(check_lint, "BASELINE", baseline), patch("sys.argv", ["check_lint"]):
        with patch.object(check_lint, "findings", return_value=Counter()):
            assert check_lint.main() == 0
        with patch.object(check_lint, "findings", return_value=Counter({
            ("new.py", "F401", "Unused", "import os"): 1,
        })):
            assert check_lint.main() == 1


def test_lint_baseline_cannot_accept_dirty_extracted_modules(tmp_path):
    baseline = tmp_path / "baseline.json"
    with patch.object(check_lint, "BASELINE", baseline), patch(
        "sys.argv", ["check_lint", "--write-baseline"],
    ), patch.object(check_lint, "findings", return_value=Counter({
        ("brighteyes_mcs/ui/controllers/statistics.py", "F401", "Unused", "import os"): 1,
    })):
        assert check_lint.main() == 1
        assert not baseline.exists()


def test_external_link_failures_do_not_block_local_documentation(tmp_path):
    page = tmp_path / "README.md"
    page.write_text("[online](https://example.com/guide)\n", encoding="utf-8")
    with patch.object(check_docs, "ROOT", tmp_path), patch.object(
        check_docs, "documents", return_value=[page],
    ), patch.object(check_docs, "external_failure", return_value="offline"), patch(
        "sys.argv", ["check_docs", "--external"],
    ):
        assert check_docs.main() == 0
