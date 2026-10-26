#!/usr/bin/env python3
"""生成 README 配图（PNG）。纯 Pillow 绘制，不依赖 matplotlib，文字精确可控。

产物写入 ``docs/images/``：
    hero.png           封面
    architecture.png   四层架构 + 工程链路
    workflow.png       单次调用的五步流转
    themes.png         13 个主题的真实分布

CLI
---
    python tools/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import argparse

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "images"

# 色板
INK = "#12151C"
INK_SOFT = "#5A6371"
LINE = "#E3E7EE"
CARD = "#F6F8FB"
BLUE = "#2F6BFF"
BLUE_DARK = "#1B45B8"
ORANGE = "#FF7A45"
GREEN = "#12A47A"
PURPLE = "#7A5AF8"
WHITE = "#FFFFFF"

THEME_PALETTE = [
    "#2F6BFF", "#3E8BFF", "#00A3B5", "#12A47A", "#5FB13C",
    "#C9A227", "#FF7A45", "#E24B4B", "#C4519E", "#7A5AF8",
    "#5468C4", "#8A96A8", "#B0B8C4",
]

#: 中文优先、按平台依次探测
FONT_CANDIDATES: Tuple[Tuple[str, int], ...] = (
    ("C:/Windows/Fonts/msyhbd.ttc", 1),
    ("C:/Windows/Fonts/msyh.ttc", 0),
    ("C:/Windows/Fonts/simhei.ttf", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
)


def pick_font_path() -> Optional[Tuple[str, int]]:
    for path, index in FONT_CANDIDATES:
        if Path(path).exists():
            return path, index
    return None


_FONT_CACHE: Dict[int, ImageFont.FreeTypeFont] = {}


def font(size: int) -> ImageFont.FreeTypeFont:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    chosen = pick_font_path()
    if chosen:
        path, index = chosen
        try:
            f = ImageFont.truetype(path, size=size, index=index)
        except Exception:
            f = ImageFont.load_default()
    else:
        f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def canvas(width: int, height: int, bg: str = WHITE) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (width, height), bg)
    return img, ImageDraw.Draw(img)


def vertical_gradient(img: Image.Image, top: str, bottom: str) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    t = tuple(int(top[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5))
    for y in range(h):
        ratio = y / max(h - 1, 1)
        color = tuple(int(t[k] + (b[k] - t[k]) * ratio) for k in range(3))
        draw.line([(0, y), (w, y)], fill=color)


def text_width(draw: ImageDraw.ImageDraw, s: str, f: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(s, font=f))


def rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill: str, outline: Optional[str] = None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def load_manifest() -> dict:
    path = ROOT / "MANIFEST.json"
    if not path.exists():
        return {"themes": {}, "types": {}, "skill_count": 0}
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# hero
# --------------------------------------------------------------------------- #
def make_hero(version: str, skill_count: int) -> None:
    W, H = 1600, 560
    img, _ = canvas(W, H)
    vertical_gradient(img, "#0B1220", "#16233A")
    draw = ImageDraw.Draw(img)

    # 背景点阵（右侧装饰）
    palette_cycle = THEME_PALETTE
    rows, cols = 7, 11
    cell = 34
    start_x, start_y = 980, 84
    idx = 0
    for r in range(rows):
        for c in range(cols):
            cx = start_x + c * cell
            cy = start_y + r * cell
            color = palette_cycle[idx % len(palette_cycle)]
            radius = 5 if (r + c) % 3 else 7
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
            idx += 1

    # 标题
    draw.text((90, 150), "Product-Manager", font=font(78), fill=WHITE)
    draw.text((90, 240), "puls-skills", font=font(78), fill="#7FA8FF")
    draw.line([(92, 344), (392, 344)], fill=BLUE, width=4)
    draw.text(
        (90, 372),
        f"{skill_count} 个产品经理技能 · 面向 AI Agent 的开箱即用工作流",
        font=font(30),
        fill="#C8D3E4",
    )
    draw.text(
        (90, 420),
        "发现 → 策略 → 交付 → 市场情报 → 生命周期 → 职业成长",
        font=font(24),
        fill="#8C9BB3",
    )

    # 能力标识（不写版本号：配图不随版本变动）
    label = f"{skill_count} skills · 13 themes"
    tw = text_width(draw, label, font(22))
    rounded(draw, (90, 470, 90 + tw + 36, 470 + 42), 21, "#1E3A8A", "#3B6FE0")
    draw.text((90 + 18, 470 + 9), label, font=font(22), fill="#BFD2FF")

    # 右上角标记
    draw.text((1230, 40), "CC BY-NC-SA 4.0", font=font(20), fill="#5C7291")

    img.save(OUT_DIR / "hero.png", optimize=True)


# --------------------------------------------------------------------------- #
# architecture
# --------------------------------------------------------------------------- #
def make_architecture(version: str, skill_count: int, themes: Dict[str, int], types: Dict[str, int]) -> None:
    W, H = 1600, 920
    img, draw = canvas(W, H, WHITE)

    draw.text((80, 56), "四层架构", font=font(40), fill=INK)
    draw.text((80, 112), "从上到下：谁在用 → 怎么选中 → 有什么能力 → 交付出什么", font=font(22), fill=INK_SOFT)

    layers = [
        {
            "tag": "L1",
            "title": "调用入口",
            "desc": "Agent 对话 · 斜杠命令 · CLI",
            "color": BLUE,
            "items": ["WorkBuddy Agent", "Claude Code", "Codex", "终端 CLI"],
            "y": 168,
        },
        {
            "tag": "L2",
            "title": "路由层",
            "desc": "77 份 description + argument-hint 决定选中谁",
            "color": PURPLE,
            "items": [f"{skill_count} × SKILL.md", "argument-hint", "theme 分类", "名称前缀消歧"],
            "y": 322,
        },
        {
            "tag": "L3",
            "title": "能力层",
            "desc": f"13 个主题 · 3 种技能类型",
            "color": GREEN,
            "items": [
                f"workflow {types.get('workflow', 0)}",
                f"component {types.get('component', 0)}",
                f"interactive {types.get('interactive', 0)}",
                "template + examples",
            ],
            "y": 476,
        },
        {
            "tag": "L4",
            "title": "交付物",
            "desc": "可直接进评审会的文档，不是聊天记录",
            "color": ORANGE,
            "items": ["PRD / 用户故事", "SWOT / PESTEL", "Roadmap / 定价", "EOL 清单"],
            "y": 630,
        },
    ]

    for layer in layers:
        y = layer["y"]
        rounded(draw, (80, y, 1520, y + 130), 18, CARD, LINE)
        # 左侧色条
        rounded(draw, (80, y, 92, y + 130), 6, layer["color"])
        draw.text((116, y + 22), layer["tag"], font=font(20), fill=layer["color"])
        draw.text((116, y + 50), layer["title"], font=font(32), fill=INK)
        draw.text((116, y + 96), layer["desc"], font=font(19), fill=INK_SOFT)

        # 右侧胶囊
        x = 700
        for item in layer["items"]:
            tw = text_width(draw, item, font(20))
            box_w = tw + 44
            if x + box_w > 1490:
                break
            rounded(draw, (x, y + 46, x + box_w, y + 88), 21, WHITE, layer["color"])
            draw.text((x + 22, y + 55), item, font=font(20), fill=INK)
            x += box_w + 16

    # 底部工程链路
    draw.text((80, 792), "工程链路", font=font(24), fill=INK)
    chain = ["version.py", "manifest.py", "audit.py", "validate.py", "build.py", "install.py"]
    x = 236
    for i, item in enumerate(chain):
        tw = text_width(draw, item, font(19))
        box_w = tw + 40
        rounded(draw, (x, 784, x + box_w, 826), 21, "#EDF2FF", "#B9CBFF")
        draw.text((x + 20, 792), item, font=font(19), fill=BLUE_DARK)
        x += box_w
        if i < len(chain) - 1:
            draw.text((x + 6, 792), "→", font=font(19), fill=INK_SOFT)
            x += 32

    draw.text((80, 862), "版本 → 清单 → 审查 → 校验 → 打包 → 安装，六环全部通过才出包",
              font=font(19), fill=INK_SOFT)

    img.save(OUT_DIR / "architecture.png", optimize=True)


# --------------------------------------------------------------------------- #
# workflow
# --------------------------------------------------------------------------- #
def make_workflow() -> None:
    W, H = 1600, 640
    img, draw = canvas(W, H, WHITE)

    draw.text((80, 56), "一次调用的五步流转", font=font(40), fill=INK)
    draw.text((80, 112), "技能不是问答模板：它先收敛输入，再按阶段推进，最后自检产出",
              font=font(22), fill=INK_SOFT)

    steps = [
        ("1", "提出问题", "带着模糊想法或一堆\n零散材料进来", BLUE),
        ("2", "选中技能", "description 里的\nUse when 命中场景", PURPLE),
        ("3", "收敛输入", "只问缺的那几项\n已有材料直接复用", "#00A3B5"),
        ("4", "分阶段执行", "Phase 逐个推进\n每步给编号选项", GREEN),
        ("5", "产出与自检", "套 template 成型\n再核对缺口与假设", ORANGE),
    ]

    n = len(steps)
    margin = 80
    gap = 26
    box_w = (W - margin * 2 - gap * (n - 1)) // n
    y = 220
    box_h = 250

    for i, (num, title, desc, color) in enumerate(steps):
        x = margin + i * (box_w + gap)
        rounded(draw, (x, y, x + box_w, y + box_h), 18, CARD, LINE)
        draw.text((x + 24, y + 22), num, font=font(46), fill=color)
        draw.text((x + 24, y + 88), title, font=font(28), fill=INK)
        draw.multiline_text((x + 24, y + 138), desc, font=font(19), fill=INK_SOFT, spacing=10)

        if i < n - 1:
            ax = x + box_w + 4
            draw.line([(ax, y + box_h // 2), (ax + gap - 10, y + box_h // 2)], fill="#C3CCDA", width=3)
            draw.polygon(
                [
                    (ax + gap - 10, y + box_h // 2 - 6),
                    (ax + gap - 2, y + box_h // 2),
                    (ax + gap - 10, y + box_h // 2 + 6),
                ],
                fill="#C3CCDA",
            )

    # 底部两条约束（色点代替 emoji：字体不含 emoji 会渲染成方块）
    notes = [
        ("输入可空手", "没有材料也能开工，技能会从问题定义开始补齐", "#EDF2FF", BLUE_DARK, [BLUE]),
        ("缺口显式标注", "假设 / 待验证分别标记，不会把猜测写成结论", "#FFF2EA", "#B23B12", [ORANGE, "#2F8FFF"]),
    ]
    x = 80
    for title, desc, bg, fg, dots in notes:
        tw = text_width(draw, desc, font(20))
        title_w = text_width(draw, title, font(22))
        dots_w = len(dots) * 20
        box_w2 = max(tw + title_w + dots_w + 96, 640)
        rounded(draw, (x, 520, x + box_w2, 580), 14, bg)
        dot_x = x + 24
        for color in dots:
            draw.ellipse([dot_x, 542, dot_x + 12, 554], fill=color)
            dot_x += 20
        draw.text((x + 24 + dots_w, 536), title, font=font(22), fill=fg)
        draw.text((x + 24 + dots_w + title_w + 20, 540), desc, font=font(20), fill=INK_SOFT)
        x += box_w2 + 24

    img.save(OUT_DIR / "workflow.png", optimize=True)


# --------------------------------------------------------------------------- #
# themes
# --------------------------------------------------------------------------- #
def make_themes(themes: Dict[str, int]) -> None:
    labels = {
        "market-intelligence": "市场情报",
        "pm-artifacts": "PM 交付物",
        "finance-metrics": "财务指标",
        "discovery-research": "发现与用户研究",
        "eol-transition": "生命周期终止（EOL）",
        "career-leadership": "职业与领导力",
        "workshops-facilitation": "工作坊引导",
        "validation-experiments": "验证与实验",
        "strategy-positioning": "策略与定位",
        "stakeholder-comms": "干系人与沟通",
        "ai-agents": "AI 与 Agent",
        "product-lifecycle": "产品生命周期",
        "meta-authoring": "元技能（造技能）",
    }
    items = sorted(themes.items(), key=lambda kv: (-kv[1], kv[0])) if themes else []
    rows = len(items) or 13

    W = 1600
    row_h = 52
    top = 176
    H = top + rows * row_h + 120
    img, draw = canvas(W, H, WHITE)

    draw.text((80, 56), "13 个主题的能力分布", font=font(40), fill=INK)
    total = sum(v for _, v in items) or 1
    draw.text((80, 112), f"共 {total} 个技能，覆盖产品经理从发现到退市的完整链路",
              font=font(22), fill=INK_SOFT)

    max_val = max((v for _, v in items), default=1)
    label_w = 300
    bar_x = 80 + label_w
    bar_max = W - bar_x - 180

    for i, (key, value) in enumerate(items):
        y = top + i * row_h
        color = THEME_PALETTE[i % len(THEME_PALETTE)]
        draw.text((80, y + 8), labels.get(key, key), font=font(21), fill=INK)
        bar_w = int(bar_max * value / max_val)
        rounded(draw, (bar_x, y + 6, bar_x + bar_w, y + 36), 15, color)
        draw.text((bar_x + bar_w + 16, y + 8), str(value), font=font(21), fill=INK_SOFT)

    draw.text((80, H - 62), "数据来源：MANIFEST.json，由 tools/manifest.py 生成",
              font=font(18), fill="#9AA4B2")

    img.save(OUT_DIR / "themes.png", optimize=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="生成 README 配图（PIL 绘制，无 matplotlib 依赖）")
    parser.add_argument("--only", default=None,
                        help="只生成指定图：hero / architecture / workflow / themes / convergence / decision-tree")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    version_file = ROOT / "VERSION"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "0.0.0"

    data = load_manifest()
    skill_count = int(data.get("skill_count") or len(list((ROOT / "skills").glob("*/SKILL.md"))))
    themes = dict(data.get("themes") or {})
    types = dict(data.get("types") or {})

    if not themes:
        print("[WARN] MANIFEST.json 无主题数据，先运行 tools/manifest.py generate")

    jobs = {
        "hero": lambda: make_hero(version, skill_count),
        "architecture": lambda: make_architecture(version, skill_count, themes, types),
        "workflow": make_workflow,
        "themes": lambda: make_themes(themes),
        "convergence": make_convergence,
        "decision-tree": make_decision_tree,
        "perspectives": make_perspectives,
    }
    selected = [args.only] if args.only else list(jobs)
    unknown = [s for s in selected if s not in jobs]
    if unknown:
        print(f"[ERROR] 未知图名：{', '.join(unknown)}（可选 {', '.join(jobs)}）", file=sys.stderr)
        return 2
    for name in selected:
        jobs[name]()

    for name in selected:
        path = OUT_DIR / f"{name}.png"
        print(f"[OK] {path.relative_to(ROOT).as_posix()}  {path.stat().st_size / 1024:.0f} KB")
    return 0



# --------------------------------------------------------------------------- #
# convergence — 两代审查的真实收敛曲线
# --------------------------------------------------------------------------- #
CONVERGENCE = {
    "labels": ["G1·R1", "G1·R2", "G1·R3", "G1·R4", "G1·R5", "G1·R6",
               "G2·R1", "G2·R2", "G2·R3"],
    "P0": [1, 1, 1, 1, 1, 0, 40, 0, 0],
    "P1": [27, 13, 13, 0, 0, 0, 4, 4, 0],
    "P2": [10, 8, 8, 8, 4, 4, 4, 4, 4],
}


def make_convergence() -> None:
    """对数纵轴折线：P0 从 1 跳到 40 时线性刻度会压扁其余曲线。"""
    import math

    W, H = 1600, 760
    img, draw = canvas(W, H, WHITE)
    draw.text((80, 50), "两代审查的收敛过程", font=font(40), fill=INK)
    draw.text((80, 106), "第一代收敛到 0 之后，第二代规则更严 —— P0 反而从 0 跳到 40",
              font=font(21), fill=INK_SOFT)

    left, right = 150, W - 120
    top, bottom = 200, H - 130
    labels = CONVERGENCE["labels"]
    n = len(labels)
    max_v = 40

    def y_of(v: float) -> float:
        ratio = math.log10(v + 1) / math.log10(max_v + 1)
        return bottom - ratio * (bottom - top)

    def x_of(i: int) -> float:
        return left + i * (right - left) / (n - 1)

    # 网格与刻度
    for tick in (0, 1, 3, 10, 40):
        y = y_of(tick)
        draw.line([(left, y), (right, y)], fill=LINE, width=1)
        draw.text((60, y - 11), str(tick), font=font(17), fill=INK_SOFT)

    # 两代之间的分隔
    split = 6
    draw.line([(x_of(split) - (x_of(1) - x_of(0)) / 2, top - 16),
               (x_of(split) - (x_of(1) - x_of(0)) / 2, bottom)],
              fill="#D8DEE9", width=2)
    draw.text((left, top - 44), "第一代 · 26 条规则", font=font(19), fill=BLUE_DARK)
    draw.text((x_of(split) + 10, top - 44), "第二代 · +B17/B18/B19，A 视角扩到 scripts/",
              font=font(19), fill="#B23B12")

    series = [("P0", CONVERGENCE["P0"], "#D64545"), ("P1", CONVERGENCE["P1"], ORANGE),
              ("P2", CONVERGENCE["P2"], "#8A96A8")]
    for name, values, color in series:
        pts = [(x_of(i), y_of(v)) for i, v in enumerate(values)]
        draw.line(pts, fill=color, width=3, joint="curve")
        for (x, y), v in zip(pts, values):
            draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=WHITE, outline=color, width=3)
        # 末端数值
        draw.text((pts[-1][0] + 12, pts[-1][1] - 10), name, font=font(19), fill=color)

    # X 轴标签
    for i, lab in enumerate(labels):
        draw.text((x_of(i) - 24, bottom + 18), lab, font=font(16), fill=INK_SOFT)

    # 关键注释（避开图例与 X 轴标签）
    draw.text((x_of(6) + 14, y_of(40) + 14), "40 处脚本引用失效", font=font(18), fill="#B23B12")
    draw.text((x_of(5) - 30, bottom - 46), "P0 归零", font=font(18), fill=GREEN)

    img.save(OUT_DIR / "convergence.png", optimize=True)


# --------------------------------------------------------------------------- #
# decision tree — 我该用哪个技能
# --------------------------------------------------------------------------- #
def make_decision_tree() -> None:
    W, H = 1600, 960
    img, draw = canvas(W, H, WHITE)
    draw.text((80, 50), "我该用哪个技能", font=font(40), fill=INK)
    draw.text((80, 106), "先按「我要产出什么」定位分支，再看分支下的首选技能",
              font=font(21), fill=INK_SOFT)

    branches = [
        ("问题还没定清", ["discovery-process", "problem-framing-canvas"], "#00A3B5"),
        ("要交一份文档", ["prd-development", "user-story", "press-release"], BLUE),
        ("要判断做不做", ["feature-investment-advisor", "prioritization-advisor"], "#12A47A"),
        ("要看清外面", ["swot-analysis", "competitive-research-snapshot", "tam-sam-som-calculator"], "#C9A227"),
        ("要停掉一条线", ["eol-readiness-advisor", "eol-process"], ORANGE),
        ("要长本事", ["product-sense-interview-answer", "director-readiness-advisor"], PURPLE),
    ]

    top = 180
    row_h = 116
    left_w = 270
    mid_x = 370

    for i, (question, skills, color) in enumerate(branches):
        y = top + i * row_h
        # 问题节点
        rounded(draw, (80, y, 80 + left_w, y + 74), 14, CARD, LINE)
        rounded(draw, (80, y, 92, y + 74), 6, color)
        draw.text((108, y + 24), question, font=font(23), fill=INK)

        # 连线
        draw.line([(80 + left_w, y + 37), (mid_x - 16, y + 37)], fill=color, width=2)
        draw.polygon([(mid_x - 16, y + 32), (mid_x - 6, y + 37), (mid_x - 16, y + 42)], fill=color)

        # 技能胶囊
        x = mid_x
        for j, skill in enumerate(skills):
            tw = text_width(draw, skill, font(19))
            w = tw + 36
            if x + w > W - 80:
                break
            fill_white = j == 0
            rounded(draw, (x, y + 14, x + w, y + 58), 22,
                    color if fill_white else WHITE, color)
            draw.text((x + 18, y + 23), skill, font=font(19),
                      fill=WHITE if fill_white else INK)
            x += w + 12

    # 底部提示
    rounded(draw, (80, H - 96, W - 80, H - 30), 14, "#EDF2FF")
    draw.text((108, H - 82), "实心 = 首选", font=font(20), fill=BLUE_DARK)
    draw.text((260, H - 82),
              "名字相近的几组（user-story / -mapping / -splitting）见用户手册 5.2 节对照表",
              font=font(19), fill=INK_SOFT)

    img.save(OUT_DIR / "decision-tree.png", optimize=True)

# --------------------------------------------------------------------------- #
# perspectives — 四视角审查全景
# --------------------------------------------------------------------------- #
def make_perspectives() -> None:
    """四象限：每个视角看什么、几条规则、抓过什么真问题。"""
    W, H = 1600, 1150
    img, draw = canvas(W, H, WHITE)
    draw.text((80, 50), "五个视角各看什么", font=font(40), fill=INK)
    draw.text((80, 106), "同一个仓库，五种问法。规则持续加严——每换一个视角，都能挖出之前所有视角看不到的问题",
              font=font(21), fill=INK_SOFT)

    quads = [
        {
            "tag": "A", "title": "工具实现者", "count": "8 条",
            "ask": "这堆脚本能不能跑、能不能重复跑？",
            "caught": "抓过：语法错误、BOM、危险删除、缺 __main__ 守卫",
            "color": BLUE, "x": 80, "y": 180,
        },
        {
            "tag": "B", "title": "审查者", "count": "19 条",
            "ask": "内容合规吗？署名还在吗？链接是活的吗？",
            "caught": "抓过：40 处死脚本引用、3 处断链、13 处占位残留",
            "color": GREEN, "x": 820, "y": 180,
        },
        {
            "tag": "C", "title": "AI 使用方", "count": "8 条",
            "ask": "Agent 拿到 77 个技能，能选对、能跑通吗？",
            "caught": "抓过：描述缺触发语、缺 argument-hint、名称歧义",
            "color": PURPLE, "x": 80, "y": 500,
        },
        {
            "tag": "D", "title": "文档一致性", "count": "4 条",
            "ask": "文档说的和磁盘上的是同一回事吗？",
            "caught": "抓过：README 声称的数量与 MANIFEST 脱节",
            "color": ORANGE, "x": 820, "y": 500,
        },
        {
            "tag": "E", "title": "安装布局", "count": "2 条",
            "ask": "装到 Agent 目录之后，这些路径还有效吗？",
            "caught": "抓过：334 处根相对引用，安装后全部失效",
            "color": "#0E9488", "x": 80, "y": 820,
        },
    ]

    for q in quads:
        x, y = q["x"], q["y"]
        rounded(draw, (x, y, x + 700, y + 280), 18, CARD, LINE)
        rounded(draw, (x, y, x + 10, y + 280), 5, q["color"])
        draw.text((x + 36, y + 24), q["tag"], font=font(44), fill=q["color"])
        draw.text((x + 96, y + 34), q["title"], font=font(30), fill=INK)
        rounded(draw, (x + 590, y + 34, x + 664, y + 72), 19, WHITE, q["color"])
        tw = text_width(draw, q["count"], font(19))
        draw.text((x + 627 - tw // 2, y + 42), q["count"], font=font(19), fill=INK)
        draw.text((x + 36, y + 108), q["ask"], font=font(22), fill=INK)
        draw.multiline_text((x + 36, y + 160), q["caught"], font=font(19), fill=INK_SOFT, spacing=10)
        draw.text((x + 36, y + 236), "规则明细见技术手册", font=font(17), fill="#9AA4B2")

    x, y = 820, 820
    rounded(draw, (x, y, x + 700, y + 280), 18, "#FFF7ED", "#F0C9A8")
    draw.text((x + 36, y + 30), "41 条审查 + 9 条校验", font=font(28), fill="#9A3412")
    draw.multiline_text((x + 36, y + 92),
                        "审查看内容质量（写得对不对）；\n校验看交付一致性（清单和磁盘\n是不是同一份东西）。两者都过才出包。",
                        font=font(20), fill=INK, spacing=12)
    draw.text((x + 36, y + 226), "四代收敛轨迹见 convergence.png", font=font(17), fill="#B08050")

    img.save(OUT_DIR / "perspectives.png", optimize=True)


if __name__ == "__main__":
    raise SystemExit(main())
