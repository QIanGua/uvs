#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
uvs - uv Script Dependency Injector

Automatically converts plain Python scripts into PEP 723-compliant inline
dependency scripts for the `uv` package manager.

Usage:
    uvs script.py [script2.py ...]
    uvs --dry-run script.py
    uvs --python ">=3.11" script.py

自动将普通 Python 脚本转换为符合 PEP 723 规范的 uv 内联依赖脚本。
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

__version__ = "0.2.0"

# ---------------------------------------------------------------------------
# Terminal colors (no external deps)
# ---------------------------------------------------------------------------

_NO_COLOR = not sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def red(t: str) -> str:
    return _c("31", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


# ---------------------------------------------------------------------------
# Stdlib detection
# ---------------------------------------------------------------------------

if hasattr(sys, "stdlib_module_names"):
    STDLIB_MODULES: set[str] = set(sys.stdlib_module_names)
else:
    STDLIB_MODULES = set()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DependencyAnalysisResult:
    """Result of dependency analysis for a single script."""

    third_party: list[str] = field(default_factory=list)
    stdlib: list[str] = field(default_factory=list)
    local: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _top(name: str) -> str:
    """Return the top-level package name from a dotted module path."""
    return name.split(".", maxsplit=1)[0]


def iter_imports(tree: ast.AST) -> Iterable[str]:
    """Yield top-level module names from all import statements in *tree*.

    Relative imports (``from .foo import bar``) are skipped — they are
    always local.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    yield _top(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                yield _top(node.module)


def is_stdlib(name: str) -> bool:
    """Return True if *name* is a standard-library module."""
    top = _top(name)
    if STDLIB_MODULES:
        return top in STDLIB_MODULES
    # Fallback for Python < 3.10: only trust built-ins
    try:
        spec = importlib.util.find_spec(top)
    except (ImportError, ValueError):
        return False
    return bool(spec and spec.origin == "built-in")


def analyze(source: str, script_path: Path | None = None) -> DependencyAnalysisResult:
    """Classify every imported module in *source* into stdlib / local / third-party."""
    tree = ast.parse(source)
    seen = sorted(set(iter_imports(tree)))

    result = DependencyAnalysisResult()
    for mod in seen:
        top = _top(mod)
        if is_stdlib(top):
            result.stdlib.append(top)
            continue
        if script_path:
            d = script_path.parent
            if (d / f"{top}.py").exists() or (d / top / "__init__.py").exists():
                result.local.append(top)
                continue
        result.third_party.append(top)

    result.third_party = sorted(set(result.third_party))
    result.stdlib = sorted(set(result.stdlib))
    result.local = sorted(set(result.local))
    return result


# ---------------------------------------------------------------------------
# PEP 723 header manipulation
# ---------------------------------------------------------------------------

_HDR_START = "# /// script"
_HDR_END = "# ///"


def _has_header(text: str) -> bool:
    return _HDR_START in text and _HDR_END in text


def _build_header(deps: Iterable[str], python: str) -> str:
    lines = [
        _HDR_START,
        f'# requires-python = "{python}"',
        "# dependencies = [",
        *[f'#   "{d}",' for d in sorted(set(deps))],
        "# ]",
        _HDR_END,
    ]
    return "\n".join(lines) + "\n\n"


def inject_header(original: str, deps: Iterable[str], python: str) -> str:
    """Insert or update the PEP 723 ``# /// script`` block in *original*.

    When a block already exists only the ``dependencies`` list is replaced;
    all other fields (``tool.uv``, ``index``, …) are preserved.
    """
    deps_list = sorted(set(deps))

    if not _has_header(original):
        return _build_header(deps_list, python) + original

    lines = original.splitlines()

    # Locate the existing block
    start = next((i for i, l in enumerate(lines) if _HDR_START in l), None)
    if start is None:
        return _build_header(deps_list, python) + original

    end = next((i for i in range(start + 1, len(lines)) if _HDR_END in lines[i]), None)
    if end is None:
        return _build_header(deps_list, python) + original

    block = lines[start : end + 1]

    # Find and replace the dependencies section inside the block
    dep_s = dep_e = None
    for i, line in enumerate(block):
        s = line.strip()
        if s.startswith("#") and "dependencies" in s and "[" in s:
            dep_s = i
            for j in range(i + 1, len(block)):
                if block[j].strip().startswith("# ]"):
                    dep_e = j
                    break
            break

    new_dep = ["# dependencies = [", *[f'#   "{d}",' for d in deps_list], "# ]"]

    if dep_s is not None and dep_e is not None:
        block = block[:dep_s] + new_dep + block[dep_e + 1 :]
    else:
        block = block[:-1] + new_dep + [block[-1]]

    return "\n".join(lines[:start] + block + lines[end + 1 :]) + "\n"


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------


def process_file(
    path: Path,
    *,
    python: str,
    dry_run: bool,
    verbose: bool,
) -> bool:
    """Analyse *path* and write the updated source.  Returns True on success."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  {red('error')} {exc}")
        return False

    try:
        result = analyze(source, script_path=path)
    except SyntaxError as exc:
        print(f"  {red('syntax error')} {exc}")
        return False

    if verbose:
        if result.stdlib:
            print(f"  {dim('stdlib  ')} {dim(', '.join(result.stdlib))}")
        if result.local:
            print(f"  {dim('local   ')} {dim(', '.join(result.local))}")

    deps_str = ", ".join(result.third_party) if result.third_party else dim("none")
    print(f"  {cyan('deps    ')} {deps_str}")

    new_source = inject_header(source, result.third_party, python)

    if dry_run:
        print(f"  {yellow('dry-run ')} no changes written")
        return True

    if new_source == source:
        print(f"  {dim('skip    ')} already up-to-date")
        return True

    try:
        path.write_text(new_source, encoding="utf-8")
    except OSError as exc:
        print(f"  {red('error')} {exc}")
        return False

    print(f"  {green('updated ')} PEP 723 header written")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_EPILOG = """
examples:
  uvs script.py                    # inject / update dependencies
  uvs a.py b.py c.py               # batch process
  uvs --dry-run script.py          # preview without writing
  uvs --python ">=3.11" script.py  # set minimum Python version
  uvs --verbose script.py          # show stdlib & local modules too

after conversion run your script with:
  uv run script.py
"""


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="uvs",
        description=bold("uvs") + "  —  inject PEP 723 inline dependencies into uv scripts",
        epilog=_EPILOG,
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "scripts",
        metavar="script.py",
        nargs="*",
        help="one or more Python scripts to process",
    )
    parser.add_argument(
        "--python",
        metavar="SPEC",
        default=">=3.12",
        help='requires-python specifier (default: ">=3.12")',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="analyse and print results without modifying files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="also show stdlib and local modules",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"uvs {__version__}",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.scripts:
        parser.print_help()
        raise SystemExit(0)

    ok = errors = skipped = 0

    for arg in args.scripts:
        path = Path(arg)
        print(bold(str(path)))

        if not path.exists():
            print(f"  {yellow('warn    ')} file not found, skipping")
            skipped += 1
            continue
        if path.suffix != ".py":
            print(f"  {yellow('warn    ')} not a .py file, skipping")
            skipped += 1
            continue

        success = process_file(
            path,
            python=args.python,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        if success:
            ok += 1
        else:
            errors += 1

    # Summary line
    parts = [green(f"{ok} updated")]
    if skipped:
        parts.append(yellow(f"{skipped} skipped"))
    if errors:
        parts.append(red(f"{errors} failed"))
    print(f"\n{bold('done')}  {' · '.join(parts)}")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
