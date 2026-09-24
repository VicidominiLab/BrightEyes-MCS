"""Check local documentation targets; optionally report external URL failures."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)")
REFERENCE_LINK = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
CODE_REFERENCE = re.compile(
    r"`((?:brighteyes_mcs|scripts|test|docs|\.github)/[^`\n]+)`"
)


def documents(root: Path) -> list[Path]:
    return sorted({
        root / "README.md", root / "CONTRIBUTING.md",
        *root.joinpath("docs").rglob("*.md"),
        *root.joinpath("docs").rglob("*.txt"),
        *root.joinpath("brighteyes_mcs", "plugins").rglob("README.md"),
    })


def anchors(text: str) -> set[str]:
    """GitHub-style heading IDs, including duplicate heading suffixes."""
    result = set(re.findall(r'<(?:a|\w+)\b[^>]*(?:id|name)=["\']([^"\']+)', text))
    counts: dict[str, int] = {}
    text = re.sub(r"(?ms)^\s*```.*?^\s*```[^\n]*", "", text)
    for heading in re.findall(r"(?m)^#{1,6}\s+(.+?)(?:\s+#+)?$", text):
        heading = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def check_document(path: Path, root: Path) -> tuple[list[str], set[str]]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    external: set[str] = set()
    # Commands and example output are not Markdown links.
    prose = re.sub(r"(?ms)^\s*```.*?^\s*```[^\n]*", "", text)
    targets = [*LINK.findall(prose), *REFERENCE_LINK.findall(prose)]
    for target in targets:
        target = target.strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme in ("http", "https"):
            external.add(target)
            continue
        if parsed.scheme or target.startswith("//"):
            continue
        relative = unquote(parsed.path)
        destination = (path.parent / relative).resolve() if relative else path
        if not destination.exists():
            errors.append(f"{path.relative_to(root)}: missing link target {target}")
        elif parsed.fragment and destination.suffix.lower() == ".md":
            if unquote(parsed.fragment) not in anchors(destination.read_text(encoding="utf-8")):
                errors.append(f"{path.relative_to(root)}: missing heading {target}")

    for reference in CODE_REFERENCE.findall(text):
        # Root-qualified inline paths are references; prose/code fragments are not.
        if any(char.isspace() for char in reference) or "=" in reference:
            continue
        if not list(root.glob(reference)):
            errors.append(f"{path.relative_to(root)}: missing repository path {reference}")
    return errors, external


def external_failure(url: str) -> str | None:
    try:
        request = Request(url, headers={"User-Agent": "BrightEyes-MCS-docs-check"})
        with urlopen(request, timeout=10) as response:
            if response.status >= 400:
                return f"{url}: HTTP {response.status}"
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        return f"{url}: {error}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true", help="Report URL failures (non-blocking)")
    args = parser.parse_args()
    errors: list[str] = []
    external: set[str] = set()
    for path in documents(ROOT):
        found, urls = check_document(path, ROOT)
        errors.extend(found)
        external.update(urls)
    for error in errors:
        print(error)
    print(f"Local documentation: {len(errors)} error(s)")
    if args.external:
        with ThreadPoolExecutor(max_workers=8) as pool:
            failures = [failure for failure in pool.map(external_failure, sorted(external)) if failure]
        for failure in failures:
            print(f"External link warning: {failure}")
        print(f"External links: {len(failures)} warning(s); network results are non-blocking")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
