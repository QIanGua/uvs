# uvs

[中文文档](README.zh.md)

Automatically inject [PEP 723](https://peps.python.org/pep-0723/) inline script metadata into Python scripts so they can be run with `uv run` without any manual dependency management.

---

## Claude Code Skill

Use `uvs` directly from [Claude Code](https://claude.ai/code) via the `/uvs` slash command.

**Project-level** (current repo only):

```bash
mkdir -p .claude/skills/uvs
curl -fsSL https://raw.githubusercontent.com/QIanGua/uvs/main/.claude/skills/uvs/SKILL.md \
  -o .claude/skills/uvs/SKILL.md
```

**Global** (all projects):

```bash
mkdir -p ~/.claude/skills/uvs
curl -fsSL https://raw.githubusercontent.com/QIanGua/uvs/main/.claude/skills/uvs/SKILL.md \
  -o ~/.claude/skills/uvs/SKILL.md
```

Then in Claude Code:

```
/uvs script.py
/uvs --dry-run script.py
```

---

## What it does

`uvs` reads a Python script, parses every `import` statement with the AST, classifies each module as **stdlib / local / third-party**, then writes (or updates) the `# /// script` block at the top of the file.

```
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx",
#   "rich",
# ]
# ///
import httpx
from rich import print
```

After that, `uv run script.py` handles everything — no venv, no `pip install`.

---

## Installation

`uvs` is a single-file, zero-dependency script. The recommended way is to run it directly with `uv`:

```bash
# run without installing
uv run uvs.py script.py

# or make it executable and put it on your PATH
chmod +x uvs.py
cp uvs.py ~/.local/bin/uvs
```

Because the file carries its own `# /// script` header, `uv` resolves all runtime requirements automatically.

---

## Usage

```
uvs [options] script.py [script2.py ...]
```

### Options

| Flag | Description |
|------|-------------|
| `--python SPEC` | `requires-python` specifier written into the header (default: `>=3.12`) |
| `--dry-run` | Analyse and print results without modifying any file |
| `-v, --verbose` | Also show detected stdlib and local modules |
| `--version` | Print version and exit |
| `-h, --help` | Show help message and exit |

### Examples

```bash
# Inject / update dependencies in a single script
uvs script.py

# Batch process several scripts at once
uvs a.py b.py c.py

# Preview what would change — no files written
uvs --dry-run script.py

# Target Python 3.11+
uvs --python ">=3.11" script.py

# Show all detected modules (stdlib, local, third-party)
uvs --verbose script.py

# Check version
uvs --version
```

### Output

```
script.py
  deps      httpx, rich
  updated   PEP 723 header written

done  1 updated
```

With `--verbose`:

```
script.py
  stdlib    ast, pathlib, sys
  local     utils
  deps      httpx, rich
  updated   PEP 723 header written
```

---

## How dependency classification works

1. **Standard library** — detected via `sys.stdlib_module_names` (Python 3.10+). Falls back to checking `spec.origin == "built-in"` on older versions.
2. **Local modules** — any top-level name that resolves to a `.py` file or a package directory (`__init__.py`) in the same folder as the script.
3. **Third-party** — everything else. These are written into `dependencies`.

Relative imports (`from .foo import bar`) are always treated as local and never added to `dependencies`.

---

## Updating an existing header

If the script already has a `# /// script` block, `uvs` **only replaces the `dependencies` list**. All other fields — `requires-python`, `[tool.uv]`, custom index sources, etc. — are left untouched.

---

## Requirements

- Python 3.10+ (for `sys.stdlib_module_names`; works on 3.8+ with degraded stdlib detection)
- [`uv`](https://github.com/astral-sh/uv) to run the converted scripts

---

## License

MIT
