"""Check portable skill links and optional source-symbol evidence using only the stdlib."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def check_package(skill: Path, repo: Path | None = None) -> tuple[list[str], dict[str, int]]:
    skill = skill.resolve()
    errors: list[str] = []
    counts = {"files": 0, "local_links": 0, "source_symbols": 0}
    required = ("SKILL.md", "LICENSE.txt", "references/implementation-map.md")
    for name in required:
        if not (skill / name).is_file():
            errors.append(f"Missing required package file: {name}")
    if not skill.is_dir():
        return errors, counts

    for path in sorted(skill.rglob("*")):
        if path.is_symlink():
            errors.append(f"Symlinks are not portable package resources: {path.relative_to(skill)}")
            continue
        if not path.is_file():
            continue
        counts["files"] += 1
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        if "/Users/" in text or "plugin://" in text or "us.cloud.langfuse.com/project/" in text:
            errors.append(f"Private or machine-specific dependency: {path.relative_to(skill)}")
        for raw in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = raw.strip().removeprefix("<").removesuffix(">")
            parts = urlsplit(target)
            if parts.scheme or not parts.path:
                continue
            counts["local_links"] += 1
            destination = (path.parent / unquote(parts.path)).resolve()
            if not destination.is_relative_to(skill):
                errors.append(f"Link escapes package: {path.relative_to(skill)} -> {target}")
            elif not destination.is_file():
                errors.append(f"Broken link: {path.relative_to(skill)} -> {target}")

    if repo is not None:
        repo = repo.resolve()
        mapping = skill / "references/implementation-map.md"
        if mapping.is_file():
            for cell in mapping.read_text(encoding="utf-8").split("|"):
                current: Path | None = None
                symbols: set[str] = set()
                for item in re.findall(r"`([^`]+)`", cell):
                    if item.startswith(("src/", "tests/")) and ".py" in item:
                        relative, separator, name = item.partition("::")
                        current = (repo / relative).resolve()
                        if not current.is_relative_to(repo) or not current.is_file():
                            errors.append(f"Missing evidence file: {relative}")
                            current = None
                            continue
                        tree = ast.parse(current.read_text(encoding="utf-8"))
                        symbols = set()
                        for node in tree.body:
                            if isinstance(
                                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                            ):
                                symbols.add(node.name)
                            elif isinstance(node, ast.Assign):
                                symbols.update(
                                    t.id for t in node.targets if isinstance(t, ast.Name)
                                )
                        if separator:
                            counts["source_symbols"] += 1
                            if name not in symbols:
                                errors.append(f"Missing source symbol: {relative}::{name}")
                    elif current is not None and re.fullmatch(r"[A-Za-z_]\w*", item):
                        counts["source_symbols"] += 1
                        if item not in symbols:
                            errors.append(
                                f"Missing source symbol: {current.relative_to(repo)}::{item}"
                            )
    return errors, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "skills/mcp-architecture",
    )
    parser.add_argument("--repo-root", type=Path, help="Also verify implementation-map symbols.")
    args = parser.parse_args()
    errors, counts = check_package(args.skill_dir, args.repo_root)
    for error in errors:
        print(f"ERROR: {error}")
    print("; ".join(f"{key}={value}" for key, value in counts.items()))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
