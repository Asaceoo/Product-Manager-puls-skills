#!/usr/bin/env python3
"""三视角对抗性审查器。

视角划分
--------
A. 工具实现者（builder）—— 这堆文件会不会把执行环境弄坏 / 能不能重复跑
B. 审查者（reviewer）—— 内容是否合规、完整、可署名分发
C. AI 使用方（consumer）—— Agent 拿到 77 个技能后能否正确选中并执行

严重度
------
P0 阻断：技能不可用（缺 SKILL.md、frontmatter 无法解析、交叉引用全断）
P1 缺陷：可用但会误导（未填充占位符、断链、触发条件缺失）
P2 建议：可读性 / 体量 / 一致性优化

CLI
---
    python tools/audit.py                     # 全量审查，控制台 + 退出码
    python tools/audit.py --json out.json     # 附 JSON 报告
    python tools/audit.py --perspective A     # 只看某个视角
    python tools/audit.py --fix               # 自动修复可修项（幂等）
    python tools/audit.py --strict            # P2 也计入失败
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

KNOWN_TYPES = {"workflow", "component", "interactive"}
KNOWN_THEMES = {
    "market-intelligence",
    "pm-artifacts",
    "finance-metrics",
    "discovery-research",
    "eol-transition",
    "career-leadership",
    "workshops-facilitation",
    "validation-experiments",
    "strategy-positioning",
    "stakeholder-comms",
    "ai-agents",
    "product-lifecycle",
    "meta-authoring",
}

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}

#: 未填充占位条目：整行形如 "- [ ... link here ]"，是作者创作残留。
#: 注意：``[Your name or team]`` 一类属于合法的模板填空槽位，不在本规则内。
PLACEHOLDER_LINE_RE = re.compile(
    r"^\s*[-*]\s*\[(?=[^\]]*(?:link here|if applicable|TODO|TBD|FIXME))[^\]]*\]\s*$",
    re.IGNORECASE,
)
PLACEHOLDER_INLINE_RE = re.compile(
    r"\[If (?:Dean|the author) has[^\]]*\]|\[Link to relevant[^\]]*\]|\bLorem ipsum\b|\[TODO:[^\]]*\]",
    re.IGNORECASE,
)
EMPTY_DEAN_SECTION_RE = re.compile(r"^###\s+Dean'?s Work\s*$", re.MULTILINE)

CROSS_REF_RE = re.compile(r"skills/([a-z0-9][a-z0-9-]*)/SKILL\.md")
RELATIVE_REF_RE = re.compile(r"\]\(\.\./([a-z0-9][a-z0-9-]*)/([^)]+)\)")
#: 正文里被要求执行的脚本路径。允许三种形态：
#: ``scripts/x.py``（仓库根）、``./scripts/x.sh``、``skills/<name>/scripts/y.py``（技能自带）。
#: 必须从匹配起点就吃掉可选前缀，否则 ``skills/a/scripts/b.py`` 会被截成 ``scripts/b.py`` 而误报。
SCRIPT_REF_RE = re.compile(
    r"(?:(?:python3?|bash)\s+|\./)?((?:\.\./[a-z0-9][a-z0-9-]*/)?(?:skills/[a-z0-9][a-z0-9-]*/)?"
    r"scripts/[A-Za-z0-9._-]+\.(?:py|sh))"
)
#: 正文里被点名的技能目录内文件（``template.md`` / ``examples/x.md``）
LOCAL_FILE_REF_RE = re.compile(r"`(template\.md|examples/[A-Za-z0-9._-]+\.md)`")

#: D 视角检查的文档（相对路径）
DOC_TARGETS: Tuple[str, ...] = (
    "README.md",
    "AGENTS.md",
    "NOTICE",
    "docs/USER-MANUAL.md",
    "docs/TECH-MANUAL.md",
)

#: 反引号里出现但不是技能名的常见标识符（字段名、主题名、文件名）
DOC_TOKEN_NOISE = {
    "skill-md", "argument-hint", "frontmatter", "anti-patterns", "common-pitfalls",
    "manifest-json", "versions-json", "readme-md", "agents-md", "tech-manual",
    "user-manual", "changelog-md", "notice-md", "license-md", "template-md",
    "pm-artifacts", "market-intelligence", "finance-metrics", "discovery-research",
    "eol-transition", "career-leadership", "workshops-facilitation",
    "validation-experiments", "strategy-positioning", "stakeholder-comms",
    "ai-agents", "product-lifecycle", "meta-authoring", "use-when",
    "non-commercial", "skill-creator", "dry-run", "no-bump", "allow-p2",
}

SECRET_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("AWS AccessKey", r"AKIA[0-9A-Z]{16}"),
    ("GitHub Token", r"gh[pousr]_[A-Za-z0-9]{36,}"),
    ("OpenAI Key", r"sk-[A-Za-z0-9]{32,}"),
    ("Private Key", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("硬编码密码", r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
)

DANGEROUS_CODE_RE = re.compile(
    r"rm\s+-rf\s+[/~]|shutil\.rmtree\(\s*['\"]?(?:/|[A-Za-z]:[\\/])\s*['\"]?\)|"
    r"os\.remove\(\s*['\"]?(?:/|[A-Za-z]:[\\/])\s*['\"]?\)|format\s+[a-z]:",
    re.IGNORECASE,
)

ABSOLUTE_PATH_RE = re.compile(r"(?<![\w])[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9_.-]+|/home/[a-z0-9_-]+/|/Users/[A-Za-z0-9_.-]+/")


@dataclass
class Finding:
    rule: str
    severity: str
    perspective: str
    path: str
    message: str
    line: Optional[int] = None
    fixable: bool = False
    #: (旧子串, 新子串) —— 与 fixable 互斥使用：fixable=删行，fix_replace=行内替换
    fix_replace: Optional[Tuple[str, str]] = None

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path


@dataclass
class AuditContext:
    """一次审查共享的只读上下文。"""

    root: Path
    skill_names: List[str] = field(default_factory=list)
    skill_dirs: Dict[str, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.skill_dirs:
            for skill_md in sorted((self.root / "skills").glob("*/SKILL.md")):
                self.skill_dirs[skill_md.parent.name] = skill_md.parent
            self.skill_names = sorted(self.skill_dirs)


# --------------------------------------------------------------------------- #
# 解析工具
# --------------------------------------------------------------------------- #
def read_text(path: Path) -> str:
    """统一 UTF-8 读取，异常字符替换而非崩溃。"""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> Optional[Dict[str, str]]:
    """解析 YAML frontmatter 的顶层标量字段（不做完整 YAML 依赖）。"""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    block = parts[1]
    data: Dict[str, str] = {}
    key: Optional[str] = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")):
            continue  # 续行 / 列表项，顶层标量不需要
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        data[key] = value.strip("\"'")
    return data


def body_of(text: str) -> str:
    """去掉 frontmatter 后的正文。"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


# --------------------------------------------------------------------------- #
# A. 工具实现者视角
# --------------------------------------------------------------------------- #
def check_builder(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    # tools/ 是交付链路，scripts/ 面向用户执行；两者都必须能跑、能重复跑
    py_files = sorted((ctx.root / "tools").glob("*.py"))
    if (ctx.root / "scripts").is_dir():
        py_files += sorted((ctx.root / "scripts").glob("*.py"))

    for py in py_files:
        rel = py.relative_to(ctx.root).as_posix()
        text = read_text(py)

        # A1 语法可编译（用 compile 而非 import，避免副作用）
        try:
            compile(text, str(py), "exec")
        except SyntaxError as exc:
            findings.append(
                Finding("A1", "P0", "A", rel, f"语法错误：{exc.msg}", exc.lineno)
            )

        # A2 禁止硬编码开发者本机路径
        for m in ABSOLUTE_PATH_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            findings.append(
                Finding("A2", "P1", "A", rel, f"硬编码本机路径：{m.group(0)}", line)
            )

        # A3 禁止危险删除指令
        for m in DANGEROUS_CODE_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            findings.append(
                Finding("A3", "P0", "A", rel, f"疑似危险文件操作：{m.group(0)}", line)
            )

        # A4 构建期禁止外网依赖
        if re.search(r"^\s*(?:import|from)\s+(?:requests|httpx|aiohttp)\b", text, re.MULTILINE):
            findings.append(Finding("A4", "P1", "A", rel, "构建脚本引入外网 HTTP 依赖，离线不可构建"))

        # A5 必须有 __main__ 守卫（保证可被安全导入复用）
        if not re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]", text) and py.name != "__init__.py":
            findings.append(Finding("A5", "P2", "A", rel, "缺少 __main__ 守卫"))

    # A6 文件编码：禁止 BOM 与非法 UTF-8
    for path in _iter_text_files(ctx.root):
        raw = path.read_bytes()
        rel = path.relative_to(ctx.root).as_posix()
        if raw.startswith(b"\xef\xbb\xbf"):
            findings.append(Finding("A6", "P1", "A", rel, "文件含 UTF-8 BOM"))
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(Finding("A6", "P0", "A", rel, f"非 UTF-8 编码：{exc.reason}"))

    # A7 技能目录结构完整（每目录必须有 SKILL.md）
    for child in sorted((ctx.root / "skills").iterdir()):
        if child.is_dir() and not (child / "SKILL.md").exists():
            findings.append(
                Finding("A7", "P0", "A", child.relative_to(ctx.root).as_posix(), "技能目录缺少 SKILL.md")
            )

    # A8 无残留临时/备份文件
    junk_patterns = ("*.orig", "*.rej", "*.bak", "*~", ".DS_Store", "Thumbs.db", "*.tmp")
    for pattern in junk_patterns:
        for hit in ctx.root.rglob(pattern):
            if ".git" in hit.parts:
                continue
            findings.append(
                Finding("A8", "P2", "A", hit.relative_to(ctx.root).as_posix(), "残留临时文件")
            )

    return findings


def _iter_text_files(root: Path) -> Iterable[Path]:
    exts = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".gitignore"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() in exts:
            yield path


# --------------------------------------------------------------------------- #
# B. 审查者视角
# --------------------------------------------------------------------------- #
def check_reviewer(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []

    for name, path in sorted(ctx.skill_dirs.items()):
        skill_md = path / "SKILL.md"
        rel = skill_md.relative_to(ctx.root).as_posix()
        text = read_text(skill_md)
        fm = parse_frontmatter(text)

        if fm is None:
            findings.append(Finding("B1", "P0", "B", rel, "缺少或损坏的 YAML frontmatter"))
            continue

        # B2 必填字段
        for key in ("name", "description", "type", "theme"):
            if not fm.get(key):
                findings.append(Finding("B2", "P0", "B", rel, f"frontmatter 缺少 {key}"))

        # B3 name 与目录名一致
        if fm.get("name") and fm["name"] != name:
            findings.append(
                Finding("B3", "P1", "B", rel, f"name={fm['name']!r} 与目录名 {name!r} 不一致")
            )

        # B4 type / B5 theme 取值合法
        if fm.get("type") and fm["type"] not in KNOWN_TYPES:
            findings.append(Finding("B4", "P1", "B", rel, f"未知 type={fm['type']!r}"))
        if fm.get("theme") and fm["theme"] not in KNOWN_THEMES:
            findings.append(Finding("B5", "P1", "B", rel, f"未知 theme={fm['theme']!r}"))

        # B6 description 长度窗口
        desc = fm.get("description", "")
        if desc:
            if len(desc) < 40:
                findings.append(Finding("B6", "P1", "B", rel, f"description 过短（{len(desc)} 字符），缺少触发语境"))
            elif len(desc) > 400:
                findings.append(Finding("B6", "P2", "B", rel, f"description 过长（{len(desc)} 字符），易被截断"))

        # B7 未填充占位符
        findings.extend(_scan_placeholders(rel, text))

        # B8 交叉引用断链
        body = body_of(text)
        for m in CROSS_REF_RE.finditer(body):
            target = m.group(1)
            if target not in ctx.skill_dirs:
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    Finding("B8", "P1", "B", rel, f"引用不存在的技能：{target}", line)
                )

        # B9 相对链接断链
        for m in RELATIVE_REF_RE.finditer(body):
            target, rest = m.group(1), m.group(2)
            resolved = (path / ".." / target / rest).resolve()
            if not resolved.exists():
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    Finding("B9", "P1", "B", rel, f"相对链接失效：../{target}/{rest}", line)
                )

        # B10 秘密泄露
        findings.extend(_scan_secrets(rel, text))

        # B11 体量
        size = skill_md.stat().st_size
        if size > 200_000:
            findings.append(Finding("B11", "P2", "B", rel, f"SKILL.md 达 {size//1024} KB，超出单文件可读阈值"))

        # B12 空文件
        for sub in ("template.md",):
            target = path / sub
            if target.exists() and target.stat().st_size == 0:
                findings.append(
                    Finding("B12", "P1", "B", target.relative_to(ctx.root).as_posix(), "空文件")
                )

        # B13 正文有实际章节
        if len(re.findall(r"^##\s+\S", body, re.MULTILINE)) < 2:
            findings.append(Finding("B13", "P1", "B", rel, "正文一级章节少于 2 个，结构过薄"))

        # B16 创作期残留元信息：声明的落位与真实布局（扁平 skills/<name>/）不一致，会误导 Agent
        for m in re.finditer(r"^\*\*(?:Suggested placement|Suggested filename):\*\*.*$", text, re.MULTILINE):
            line = text[: m.start()].count("\n") + 1
            findings.append(
                Finding("B16", "P1", "B", rel, f"创作期残留元信息：{m.group(0)[:60]}", line, fixable=True)
            )

        # B17 有 examples/ 目录，但正文从未告诉 Agent 它们存在
        examples_dir = path / "examples"
        if examples_dir.is_dir() and any(examples_dir.iterdir()) and "examples/" not in text:
            findings.append(
                Finding("B17", "P1", "B", rel, "examples/ 目录存在但正文未引用，Agent 无法利用已有示例")
            )

        # B18 引用了技能目录内不存在的本地文件
        for m in LOCAL_FILE_REF_RE.finditer(body):
            if not (path / m.group(1)).exists():
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    Finding("B18", "P1", "B", rel, f"引用不存在的本地文件：{m.group(1)}", line)
                )

        # B19 要求执行 scripts/ 下的脚本，但该路径解析不到真实文件
        for m in SCRIPT_REF_RE.finditer(body):
            script = m.group(1)
            if script.startswith("../"):
                resolved = (path / script).resolve()
            else:
                resolved = ctx.root / script
            if not resolved.exists():
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    Finding("B19", "P0", "B", rel, f"引用的脚本不存在：{script}", line)
                )

    # B14 许可证与署名
    for required in ("LICENSE", "NOTICE"):
        if not (ctx.root / required).exists():
            findings.append(Finding("B14", "P0", "B", required, "分发包缺少许可证/署名文件"))

    # B15 Provenance 未被破坏（CC BY-NC-SA 的署名义务）
    adapted = 0
    for name, path in sorted(ctx.skill_dirs.items()):
        text = read_text(path / "SKILL.md")
        if "Provenance" in text or "Adapted from" in text:
            adapted += 1
    if adapted < 10:
        findings.append(
            Finding("B15", "P1", "B", "skills/", f"仅 {adapted} 个技能保留来源声明，可能破坏署名要求")
        )

    return findings


def _scan_placeholders(rel: str, text: str) -> List[Finding]:
    out: List[Finding] = []
    for idx, line_text in enumerate(text.splitlines(), 1):
        if PLACEHOLDER_LINE_RE.match(line_text):
            out.append(
                Finding("B7", "P1", "B", rel, f"未填充占位条目：{line_text.strip()[:70]}", idx, fixable=True)
            )
            continue
        for m in PLACEHOLDER_INLINE_RE.finditer(line_text):
            out.append(
                Finding("B7", "P1", "B", rel, f"未填充占位符：{m.group(0)[:70]}", idx, fixable=True)
            )
    return out


def _scan_secrets(rel: str, text: str) -> List[Finding]:
    out: List[Finding] = []
    for label, pattern in SECRET_PATTERNS:
        for m in re.finditer(pattern, text):
            line = text[: m.start()].count("\n") + 1
            out.append(Finding("B10", "P0", "B", rel, f"疑似 {label} 泄露", line))
    return out


# --------------------------------------------------------------------------- #
# C. AI 使用方视角
# --------------------------------------------------------------------------- #
def check_consumer(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []

    for name, path in sorted(ctx.skill_dirs.items()):
        skill_md = path / "SKILL.md"
        rel = skill_md.relative_to(ctx.root).as_posix()
        text = read_text(skill_md)
        fm = parse_frontmatter(text) or {}
        body = body_of(text)

        # C1 description 必须给出「何时用」的触发语
        desc = fm.get("description", "")
        if desc and not re.search(r"\b(?:[Uu]se (?:when|for|to|this|it)\b|Use in\b)", desc):
            findings.append(
                Finding("C1", "P1", "C", rel, "description 缺少 'Use when/for/to' 触发语，Agent 难以判定调用时机")
            )

        # C2 必须声明输入要求或明确可空手启动
        if not re.search(r"^##\s+Input|Arriving empty-handed|no input needed|paste whatever", body, re.MULTILINE):
            findings.append(
                Finding("C2", "P1", "C", rel, "未声明输入要求，Agent 不知道需要用户提供什么")
            )

        # C3 必须有可执行产出定义
        if not re.search(r"^##\s+(?:Output|Deliverable|Application|Workflow|Process)", body, re.MULTILINE) \
           and not re.search(r"^###\s+Outputs?\b", body, re.MULTILINE):
            findings.append(
                Finding("C3", "P2", "C", rel, "未显式定义产出物章节，执行结果边界模糊")
            )

        # C4 技能名歧义：互为前缀（如 user-story / user-story-mapping）—— 每个技能只报一次
        neighbours = [o for o in ctx.skill_names if o != name and o.startswith(name + "-")]
        if neighbours:
            findings.append(
                Finding("C4", "P2", "C", rel, f"名称与 {', '.join(neighbours)} 互为前缀，存在选中歧义")
            )

        # C5 单技能体积超出单次读取预算
        if skill_md.stat().st_size > 40_000:
            findings.append(
                Finding("C5", "P2", "C", rel, f"SKILL.md {skill_md.stat().st_size//1024} KB，单次加载即占用较多上下文")
            )

        # C6 阻塞式索取凭据
        if re.search(r"(?i)ask the user for (?:their )?(?:api[_ ]key|token|password|credential)", body):
            findings.append(
                Finding("C6", "P1", "C", rel, "要求用户提供凭据，构成执行阻塞")
            )

        # C7 缺少斜杠调用提示
        if not fm.get("argument-hint"):
            findings.append(
                Finding("C7", "P2", "C", rel, "frontmatter 缺 argument-hint，斜杠调用无参数提示")
            )

    # C8 全局技能名唯一
    dupes = {n for n in ctx.skill_names if ctx.skill_names.count(n) > 1}
    if dupes:
        findings.append(Finding("C8", "P0", "C", "skills/", f"技能名重复：{sorted(dupes)}"))

    return findings




# --------------------------------------------------------------------------- #
# E. 安装布局视角（路径在"装好后"还有效吗）
# --------------------------------------------------------------------------- #
#: SKILL.md 正文里的根相对引用。安装器把技能复制成扁平目录后，
#: ``skills/<name>/...`` 会解析到 ``<安装根>/skills/<name>/...``——不存在。
#: 唯一在两种布局下都成立的形式是 ``../<name>/...``。
#: 命令行调用（``python3 skills/...``）以用户当前目录为基准，不在本规则范围。
ROOT_REL_REF_RE = re.compile(
    r"(?<!python3 )(?<!python )(?<![\w./-])skills/([a-z0-9][a-z0-9-]*/(?:SKILL\.md|template\.md|"
    r"examples/[A-Za-z0-9._-]+\.md|scripts/[A-Za-z0-9._-]+))"
)

#: 行内代码形式的相对引用（B9 只查 Markdown 链接形态，这里补行内代码）
INLINE_REL_REF_RE = re.compile(
    r"`(\.\./[a-z0-9][a-z0-9-]*/[A-Za-z0-9._/-]+)`"
)


def check_install_layout(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    for name, path in sorted(ctx.skill_dirs.items()):
        skill_md = path / "SKILL.md"
        rel = skill_md.relative_to(ctx.root).as_posix()
        text = read_text(skill_md)

        # E1 根相对引用 → 应为 ../<name>/...
        for m in ROOT_REL_REF_RE.finditer(text):
            old = m.group(0)
            new = "../" + m.group(1)
            line = text[: m.start()].count("\n") + 1
            findings.append(
                Finding("E1", "P1", "E", rel,
                        f"根相对引用安装后失效：{old}（应为 {new}）",
                        line, fixable=True, fix_replace=(old, new))
            )

        # E2 行内代码形式的 ../ 引用必须能从技能目录解析
        for m in INLINE_REL_REF_RE.finditer(text):
            target = (path / m.group(1)).resolve()
            if not target.exists():
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    Finding("E2", "P1", "E", rel,
                            f"相对引用解析不到文件：{m.group(1)}", line)
                )
    return findings


# --------------------------------------------------------------------------- #
# 修复
# --------------------------------------------------------------------------- #
def apply_fixes(ctx: AuditContext, findings: Sequence[Finding]) -> Tuple[int, int]:
    """处理可自动修复项。

    两类修复：
    - ``fixable``（行删除）：未填充占位条目，删除后若章节变空一并清理
    - ``fix_replace``（行内替换）：根相对引用改为相对引用，语义不变、布局通吃

    返回 (处理文件数, 变更次数)。
    """
    line_targets: Dict[Path, set] = {}
    replace_targets: Dict[Path, set] = {}
    for f in findings:
        if f.fix_replace and f.line:
            replace_targets.setdefault(ctx.root / f.path, set()).add(f.fix_replace)
        elif f.fixable and f.line:
            line_targets.setdefault(ctx.root / f.path, set()).add(f.line)

    files_changed = 0
    changes = 0

    for path, pairs in replace_targets.items():
        original = read_text(path)
        updated = original
        for old, new in pairs:
            updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            files_changed += 1
            changes += len(pairs)

    for path, lines in line_targets.items():
        original = read_text(path)
        rows = original.split("\n")
        kept: List[str] = []
        for idx, row in enumerate(rows, 1):
            if idx in lines:
                changes += 1
                continue
            kept.append(row)
        updated = "\n".join(kept)
        updated = _drop_empty_dean_sections(updated)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            files_changed += 1
    return files_changed, changes


def _drop_empty_dean_sections(text: str) -> str:
    """删除内容为空（仅剩占位/空行）的 ### Dean's Work 章节。

    边界判定：遇到下一个标题 **或 `---` 分隔线** 即视为章节结束。
    若把 `---` 当作内容继续吞并，后面的正文会被错误地并入该标题下。
    """
    rows = text.split("\n")
    out: List[str] = []
    i = 0
    while i < len(rows):
        if EMPTY_DEAN_SECTION_RE.match(rows[i]):
            j = i + 1
            content: List[str] = []
            while j < len(rows) and not re.match(r"^#{1,3}\s", rows[j]) and rows[j].strip() != "---":
                content.append(rows[j])
                j += 1
            meaningful = [c for c in content if c.strip()]
            if not meaningful:
                i = j  # 整段丢弃（含因空章节留下的分隔线前的空行）
                continue
        out.append(rows[i])
        i += 1
    return "\n".join(out)




# --------------------------------------------------------------------------- #
# D. 文档一致性视角（跨文件）
# --------------------------------------------------------------------------- #
def _levenshtein(a: str, b: str) -> int:
    """两个字符串的编辑距离（短字符串足够用，无需第三方库）。"""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _doc_token_misrefs(doc: str, text: str, skill_names: Sequence[str]) -> List[Finding]:
    """反引号里形如技能名、但只差一两个字符的标识符——大概率是拼错。"""
    out: List[Finding] = []
    known = set(skill_names)
    seen = set()
    for m in re.finditer(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+){1,5})`", text):
        token = m.group(1)
        if token in known or token in DOC_TOKEN_NOISE or token in seen:
            continue
        # 只报"近似于某个真实技能名"的：距离 <= 2 且长度相近
        near = [
            n for n in skill_names
            if abs(len(n) - len(token)) <= 2 and _levenshtein(token, n) <= 2
        ]
        if not near:
            continue
        seen.add(token)
        line = text[: m.start()].count("\n") + 1
        out.append(
            Finding("D1", "P1", "D", doc,
                    f"`{token}` 不存在，最接近的是 {', '.join(sorted(near)[:3])}", line)
        )
    return out


def check_docs(ctx: AuditContext) -> List[Finding]:
    """跨文件一致性：文档里的技能名、图片、相对链接必须能落到真实文件。"""
    findings: List[Finding] = []

    for rel in DOC_TARGETS:
        path = ctx.root / rel
        if not path.exists():
            findings.append(Finding("D2", "P1", "D", rel, "文档清单中声明但文件不存在"))
            continue
        text = read_text(path)

        # D1 技能名拼写
        findings.extend(_doc_token_misrefs(rel, text, ctx.skill_names))

        # D2 图片路径
        for m in re.finditer(r'(?:src="|!\[[^\]]*\]\()([^")\s]+)', text):
            ref = m.group(1)
            if ref.startswith(("http://", "https://")):
                continue
            if not ref.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                continue
            target = (path.parent / ref).resolve()
            if not target.exists():
                line = text[: m.start()].count("\n") + 1
                findings.append(Finding("D2", "P1", "D", rel, f"图片不存在：{ref}", line))

        # D3 相对 Markdown 链接
        for m in re.finditer(r"\]\(([^)#\s][^)\s]*\.md)(?:#[^)]*)?\)", text):
            ref = m.group(1)
            if ref.startswith(("http://", "https://", "mailto:")):
                continue
            target = (path.parent / ref).resolve()
            if not target.exists():
                line = text[: m.start()].count("\n") + 1
                findings.append(Finding("D3", "P1", "D", rel, f"文档链接失效：{ref}", line))

    # D4 文档引用的技能总数与 MANIFEST 一致（防止文档停在旧规模）
    readme = ctx.root / "README.md"
    if readme.exists():
        manifest = ctx.root / "MANIFEST.json"
        if manifest.exists():
            try:
                count = int(json.loads(read_text(manifest)).get("skill_count", -1))
            except (json.JSONDecodeError, TypeError, ValueError):
                count = -1
            if count > 0:
                readme_text = read_text(readme)
                # 只认"声称总数"的两种语境：徽章 skills-N- 与首屏标语「N 个产品经理技能」。
                # 不能匹配宽泛的「N 个技能」——「45 个技能含 Provenance」也会命中。
                claimed = re.findall(r"skills-(\d+)-", readme_text)
                claimed += re.findall(r"(\d+)\s*个产品经理技能", readme_text)
                wrong = sorted({c for c in claimed if c != str(count)})
                if wrong:
                    findings.append(
                        Finding("D4", "P1", "D", "README.md",
                                f"README 声称技能数为 {', '.join(wrong)}，MANIFEST 实际 {count}")
                    )

    return findings


# --------------------------------------------------------------------------- #
# 汇总与输出
# --------------------------------------------------------------------------- #
def run_audit(ctx: AuditContext, perspectives: Sequence[str]) -> List[Finding]:
    findings: List[Finding] = []
    if "A" in perspectives:
        findings.extend(check_builder(ctx))
    if "B" in perspectives:
        findings.extend(check_reviewer(ctx))
    if "C" in perspectives:
        findings.extend(check_consumer(ctx))
    if "D" in perspectives:
        findings.extend(check_docs(ctx))
    if "E" in perspectives:
        findings.extend(check_install_layout(ctx))
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.perspective, f.path, f.line or 0))
    return findings


def summarize(findings: Sequence[Finding]) -> Dict[str, int]:
    stats = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        stats[f.severity] += 1
    return stats


def group_by_rule(findings: Sequence[Finding]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for f in findings:
        counts[f.rule] = counts.get(f.rule, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="三视角对抗性审查")
    parser.add_argument("--perspective", default="ABCDE", help="组合：A/B/C/D/E 任意拼接")
    parser.add_argument("--json", dest="json_out", default=None, help="JSON 报告输出路径")
    parser.add_argument("--fix", action="store_true", help="自动修复可修项")
    parser.add_argument("--strict", action="store_true", help="P2 也计入失败")
    parser.add_argument("--max-print", type=int, default=25, help="每个视角最多打印条数")
    args = parser.parse_args(argv)

    perspectives = [p for p in "ABCDE" if p in args.perspective.upper()]
    if not perspectives:
        print("[ERROR] --perspective 需包含 A/B/C/D/E", file=sys.stderr)
        return 2

    ctx = AuditContext(ROOT)
    if not ctx.skill_dirs:
        print("[ERROR] skills/ 下没有找到任何 SKILL.md", file=sys.stderr)
        return 2

    rounds = 0
    findings = run_audit(ctx, perspectives)
    if args.fix:
        while True:
            fixable = [f for f in findings if f.fixable]
            if not fixable:
                break
            changed, removed = apply_fixes(ctx, fixable)
            rounds += 1
            print(f"[FIX] 第 {rounds} 轮：改动 {changed} 个文件，删除 {removed} 行")
            if changed == 0:
                break
            findings = run_audit(ctx, perspectives)

    stats = summarize(findings)
    names = {"A": "工具实现者", "B": "审查者", "C": "AI 使用方", "D": "文档一致性",
             "E": "安装布局"}
    print()
    print(f"技能数：{len(ctx.skill_names)}    视角：{'/'.join(names[p] for p in perspectives)}")
    print(f"结果：P0={stats['P0']}  P1={stats['P1']}  P2={stats['P2']}")
    if findings:
        print(f"规则命中：{group_by_rule(findings)}")
    print()

    for p in perspectives:
        subset = [f for f in findings if f.perspective == p]
        if not subset:
            print(f"[{p}] {names[p]}：通过")
            continue
        print(f"[{p}] {names[p]}：{len(subset)} 项")
        for f in subset[: args.max_print]:
            print(f"  {f.severity} {f.rule:<4} {f.location}  {f.message}")
        if len(subset) > args.max_print:
            print(f"  ... 其余 {len(subset) - args.max_print} 项见 JSON 报告")
        print()

    if args.json_out:
        payload = {
            "skills": len(ctx.skill_names),
            "perspectives": perspectives,
            "summary": stats,
            "by_rule": group_by_rule(findings),
            "fix_rounds": rounds,
            "findings": [asdict(f) for f in findings],
        }
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 报告：{out}")

    fail = stats["P0"] > 0 or stats["P1"] > 0 or (args.strict and stats["P2"] > 0)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
