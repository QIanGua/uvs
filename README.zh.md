# uvs

自动将 [PEP 723](https://peps.python.org/pep-0723/) 内联脚本元数据注入 Python 脚本，让脚本可以直接用 `uv run` 运行，无需手动管理依赖。

---

## Claude Code Skill

在 [Claude Code](https://claude.ai/code) 中通过 `/uvs` 命令直接使用。

**安装到当前项目**：

```bash
mkdir -p .claude/skills/uvs
curl -fsSL https://raw.githubusercontent.com/QIanGua/uvs/main/.claude/skills/uvs/SKILL.md \
  -o .claude/skills/uvs/SKILL.md
```

**全局安装**（所有项目可用）：

```bash
mkdir -p ~/.claude/skills/uvs
curl -fsSL https://raw.githubusercontent.com/QIanGua/uvs/main/.claude/skills/uvs/SKILL.md \
  -o ~/.claude/skills/uvs/SKILL.md
```

安装后在 Claude Code 中使用：

```
/uvs script.py
/uvs --dry-run script.py
```

---

## 功能说明

`uvs` 读取 Python 脚本，通过 AST 解析所有 `import` 语句，将每个模块分类为**标准库 / 本地模块 / 第三方库**，然后在文件顶部写入（或更新）`# /// script` 块。

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

之后直接运行 `uv run script.py`，无需 venv，无需 `pip install`，一切由 `uv` 自动处理。

---

## 安装

`uvs` 是单文件、零外部依赖的脚本，推荐直接用 `uv` 运行：

```bash
# 无需安装，直接运行
uv run uvs.py script.py

# 或者赋予执行权限并放到 PATH
chmod +x uvs.py
cp uvs.py ~/.local/bin/uvs
```

文件本身携带 `# /// script` 头部，`uv` 会自动解析所有运行时依赖。

---

## 用法

```
uvs [选项] script.py [script2.py ...]
```

### 选项

| 参数 | 说明 |
|------|------|
| `--python SPEC` | 写入头部的 `requires-python` 版本约束（默认：`>=3.12`） |
| `--dry-run` | 仅分析并打印结果，不修改任何文件 |
| `-v, --verbose` | 同时显示检测到的标准库和本地模块 |
| `--version` | 打印版本号并退出 |
| `-h, --help` | 显示帮助信息并退出 |

### 示例

```bash
# 为单个脚本注入 / 更新依赖
uvs script.py

# 批量处理多个脚本
uvs a.py b.py c.py

# 预览变更，不写入文件
uvs --dry-run script.py

# 指定最低 Python 版本为 3.11
uvs --python ">=3.11" script.py

# 显示所有检测到的模块（标准库、本地、第三方）
uvs --verbose script.py

# 查看版本
uvs --version
```

### 输出示例

```
script.py
  deps      httpx, rich
  updated   PEP 723 header written

done  1 updated
```

使用 `--verbose` 时：

```
script.py
  stdlib    ast, pathlib, sys
  local     utils
  deps      httpx, rich
  updated   PEP 723 header written
```

---

## 依赖分类逻辑

1. **标准库** — 通过 `sys.stdlib_module_names` 识别（Python 3.10+）。旧版本退化为检查 `spec.origin == "built-in"`。
2. **本地模块** — 顶级模块名在脚本同目录下能找到对应 `.py` 文件或包目录（含 `__init__.py`）的，视为本地模块。
3. **第三方库** — 其余所有模块，写入 `dependencies`。

相对导入（`from .foo import bar`）始终视为本地模块，不会被加入 `dependencies`。

---

## 更新已有头部

如果脚本已有 `# /// script` 块，`uvs` **只替换 `dependencies` 列表**，其他字段——`requires-python`、`[tool.uv]`、自定义 index 源等——保持不变。

---

## 环境要求

- Python 3.10+（使用 `sys.stdlib_module_names`；3.8+ 可运行但标准库识别能力降级）
- [`uv`](https://github.com/astral-sh/uv)（用于运行转换后的脚本）

---

## 许可证

MIT
