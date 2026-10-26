# 技术手册

> 面向**维护者**：数据契约、工具链内部逻辑、审查规则、发布门禁、扩展方法。
> 只想知道怎么用，请读 [用户手册](USER-MANUAL.md)。

| 文档 | 版本 |
|---|---|
| 技术手册 | <!--VER:tech_manual-->1.0.0<!--/VER--> |
| 技能包 | <!--VER:package-->1.0.0<!--/VER--> |

---

## 目录

1. [设计原则](#1-设计原则)
2. [目录与文件职责](#2-目录与文件职责)
3. [数据契约](#3-数据契约)
4. [工具链](#4-工具链)
5. [审查规则：A 视角](#5-审查规则a-视角工具实现者)
6. [审查规则：B 视角](#6-审查规则b-视角审查者)
7. [审查规则：C 视角](#7-审查规则c-视角ai-使用方)
8. [校验规则：L 系列](#8-校验规则l-系列清单约束)
9. [构建流水线与门禁](#9-构建流水线与门禁)
10. [版本策略](#10-版本策略)
11. [扩展指南](#11-扩展指南)
12. [真机验证记录](#12-真机验证记录)
13. [已知限制](#13-已知限制)

---

## 1. 设计原则

**① 单一事实源。**
版本只在 `versions.json` 里写一次，其余位置靠注入；技能清单只在 `MANIFEST.json` 里记一次，其余靠生成。任何需要手工同步两处的地方都视为缺陷。

**② 门禁前置，失败即停。**
`build.py` 按 版本 → 清单 → 审查 → 校验 → 打包 的顺序执行，前一步非零退出立即中止。不存在"先出包再修"的路径。

**③ 误报优先修规则，而不是放宽阈值。**
首轮审查发现 12 处 `[Your name or team]` 被误判为未填充占位符。处理方式不是提高阈值放过，而是把规则收紧为"整行形如 `- [ ... link here ]` 的条目"——那才是真正的创作期残留。规则收紧后误报归零，真问题仍被捕获。

**④ 修复必须可验证，且幂等。**
`--fix` 每轮执行后重新审查；同一输入连跑两次，第二次必须零改动。这条约束抓出了两个真实缺陷（见 [第 12 节](#12-真机验证记录)）。

**⑤ 只修工程缺陷，不动方法论。**
技能正文是他人作品（CC BY-NC-SA 4.0）。可改动范围限于：失效链接、未填充占位、失效元信息、缺失的 frontmatter 字段。任何涉及方法论主张的修改都必须写进 `NOTICE`。

**⑥ 卸载可逆。**
安装写记录，卸载按记录。没有记录就不删——避免"一键清理"把用户自己的技能删掉。

---

## 2. 目录与文件职责

```
Product-Manager-puls-skills/
├── skills/<name>/            技能单元
│   ├── SKILL.md              必需。frontmatter + 正文
│   ├── template.md           可选。填充模板
│   └── examples/*.md         可选。示例产出
├── catalog/                  上游索引（skills-index.yaml + 分类说明）
├── docs/
│   ├── USER-MANUAL.md        用户手册
│   ├── TECH-MANUAL.md        本文件
│   └── images/*.png          README 配图（由 tools/make_figures.py 生成）
├── tools/
│   ├── version.py            版本号读写与注入
│   ├── manifest.py           清单生成
│   ├── audit.py              三视角审查
│   ├── validate.py           清单约束校验
│   ├── build.py              打包流水线
│   ├── install.py            可逆安装
│   └── make_figures.py       配图生成
├── MANIFEST.json             自动生成，勿手改
├── versions.json             版本单一事实源
├── VERSION                   自动同步自 versions.json
├── CHANGELOG.md              自动追加
├── README.md                 含 4 个版本标记
├── NOTICE                    上游署名与修改清单
└── LICENSE                   CC BY-NC-SA 4.0
```

**依赖方向**：`build.py` → `version.py` / `manifest.py` / `audit.py` / `validate.py`；`validate.py` → `version.py` / `manifest.py`。全部单向，无循环。所有脚本仅用标准库。

---

## 3. 数据契约

### 3.1 SKILL.md frontmatter

```yaml
---
name: prd-development          # 必填，必须与父目录名完全一致
argument-hint: "[feature]"     # 推荐，斜杠调用参数提示
description: "…"               # 必填，40–400 字符，必须含 "Use when/for/to"
intent: >-                     # 可选，展开式意图说明
type: workflow                 # 必填，workflow | component | interactive
theme: pm-artifacts            # 必填，13 个主题之一
best_for:                      # 可选，适用场景列表
  - "…"
scenarios:                     # 可选，示例触发语句
  - "…"
estimated_time: "60-120 min"   # 可选
---
```

**为什么强约束 `name` = 目录名**：Agent 路由可能用任一方作键。两者不一致时，斜杠调用与自然语言选中会指向不同目标。

**为什么强约束 `description` 含 `Use when/for/to`**：Agent 只读 `description` 决定是否调用。缺少触发语的描述会退化为"主题词堆砌"，导致该调不调、不该调乱调。

### 3.2 MANIFEST.json

```json
{
  "schema": 1,
  "generated_at": "2026-10-26T16:38:11+08:00",
  "package_version": "1.0.0",
  "skill_count": 77,
  "total_files": 241,
  "total_bytes": 2086496,
  "themes": { "market-intelligence": 18, "…": 0 },
  "types": { "interactive": 29, "component": 28, "workflow": 20 },
  "skills": [
    {
      "name": "swot-analysis",
      "type": "workflow",
      "theme": "market-intelligence",
      "description": "Build an evidence-cited SWOT …",
      "files": 4,
      "bytes": 11324,
      "sha256": "3f9c…"
    }
  ]
}
```

`sha256` 的算法（`manifest.dir_digest`）：

```
对目录内每个文件按相对路径排序 →
对每个文件取 sha256 →
拼成 "relpath␠␠filehash" 行，用 \n 连接 →
对整体再取 sha256
```

任一文件内容变化、增删文件、重命名目录都会改变摘要。这让 `L4` 能判断"磁盘内容变了但清单没重建"。

### 3.3 versions.json

```json
{
  "package": "1.0.0",
  "readme": "1.0.0",
  "user_manual": "1.0.0",
  "tech_manual": "1.0.0",
  "released_at": "2026-10-26"
}
```

四个键均为 `MAJOR.MINOR.PATCH`，`version.py` 会校验格式。`VERSION` 文件是 `package` 的镜像，由 `sync()` 写入，**不是**事实源。

### 3.4 文档版本标记

```markdown
<!--VER:package-->1.0.0<!--/VER-->
```

单行、无空格、可被任何 Markdown 渲染器忽略（渲染结果只剩 `1.0.0`）。`version.py` 用正则 `<!--VER:(?P<key>[a-z_]+)-->.*?<!--/VER-->` 精确替换内层内容。

**禁止手改标记内层**。`version.py check` 会报不一致，`build.py` 会拒绝出包。

### 3.5 安装记录

写入目标目录 `.pm-skills-installed.json`：

```json
{
  "version": "1.0.0",
  "installed_at": "2026-10-26T16:40:12+08:00",
  "target": "C:\\Users\\<user>\\.workbuddy\\skills",
  "skills": ["prd-development", "user-story", "…"]
}
```

卸载只遍历 `skills` 数组。名字里含路径分隔符或为 `.` / `..` 的条目被忽略（目录穿越防护），且只操作 `target` 的直接子目录。

---

## 4. 工具链

### 4.1 version.py

| 子命令 | 行为 | 退出码 |
|---|---|---|
| `show` | 打印四个版本 | 0 |
| `bump [--part] [--keys]` | 递增并落盘，随后 `sync()` | 0 / 2 |
| `sync` | 写 `VERSION` + 注入全部文档标记 | 0 / 2 |
| `check` | 一致性校验 | 0 通过 / 1 不一致 / 2 读取失败 |

```bash
python tools/version.py bump --part patch
python tools/version.py bump --part minor --keys package,readme
```

**幂等性**：`sync()` 写入前比对内容，相同则不写文件（避免无意义 mtime 变化）。

**原子写**：写 `.tmp` 后 `Path.replace()`，中途崩溃不会留下半个文件。

### 4.2 manifest.py

| 子命令 | 行为 |
|---|---|
| `generate` | 重建 `MANIFEST.json` |
| `show` | 打印版本、技能数、主题分布 |

生成时若发现某技能目录缺 `SKILL.md`，直接 `SystemExit`，不产出半个清单。

### 4.3 audit.py

| 参数 | 说明 |
|---|---|
| `--perspective ABC` | 只跑指定视角，默认全跑 |
| `--json <path>` | 输出结构化报告 |
| `--fix` | 自动修复可修项，循环直到无可修 |
| `--strict` | P2 也计入失败 |
| `--max-print N` | 每个视角最多打印 N 条（默认 25） |

退出码：`0` 无 P0/P1（`--strict` 时也无 P2）；`1` 存在失败项；`2` 环境错误。

`--fix` 的循环：审查 → 取 `fixable` 项 → 按文件聚合行号 → 删除这些行 → 清理因此变空的章节 → 重审。最多循环至 `changed == 0`。

### 4.4 validate.py

| 参数 | 说明 |
|---|---|
| `--warn-as-error` | 警告也计为失败 |
| `--json <path>` | 输出结构化报告 |

退出码：`0` 全 PASS；`1` 存在 FAIL。

### 4.5 build.py

| 参数 | 说明 |
|---|---|
| `--part patch\|minor\|major` | 版本递增类型，默认 patch |
| `--no-bump` | 不递增，直接重打包 |
| `--skip-audit` | 跳过审查（仅调试，发布禁用） |
| `--dry-run` | 只跑门禁，不产 zip |
| `--allow-p2` | 显式确认接受 P2 |

产出：

```
dist/Product-Manager-puls-skills-v1.0.1.zip
dist/SHA256SUMS.txt          # 多版本累积，同名行被替换
```

zip 内顶层目录为 `Product-Manager-puls-skills-v{version}/`，解压不散落。

打包排除：`__pycache__`、`.git`、`.pytest_cache`、`reports`、`dist`，以及 `.pyc/.pyo/.tmp/.log`。

### 4.6 install.py

| 子命令 | 说明 |
|---|---|
| `install` | 复制技能到目标目录，写安装记录 |
| `uninstall` | 按记录删除 |
| `list` | 对比记录与磁盘 |

| 参数 | 说明 |
|---|---|
| `--target` | 目标目录，默认 `~/.workbuddy/skills` |
| `--only a,b` | 只装指定技能，未知名直接报错 |
| `--force` | 覆盖同名技能 |
| `--dry-run` | 只打印计划 |

默认行为是**跳过同名**而非覆盖——保护用户已有技能与之前装的上游版本。

### 4.7 make_figures.py

| 产出 | 尺寸 | 内容 |
|---|---|---|
| `hero.png` | 1600×560 | 封面；77 个点阵隐喻 77 个技能 |
| `architecture.png` | 1600×920 | 四层架构 + 六段工程链路 |
| `workflow.png` | 1600×640 | 五步流转 + 两条约束 |
| `themes.png` | 1600×（动态） | 13 主题真实分布 |

无 matplotlib 依赖，用 Pillow 直接绘制。字体按平台探测（msyh → simhei → PingFang → Noto），全部缺失时退化为 Pillow 默认字体（中文会缺字，但不崩溃）。

**不要在图里用 emoji**：主流中文字体不含 emoji 字形，会渲染成方块。需要色标时画圆点。

---

## 5. 审查规则：A 视角（工具实现者）

关注点：**这套脚本会不会把执行环境弄坏、能不能重复跑**。

| 编号 | 严重度 | 检查项 | 实现 |
|---|---|---|---|
| A1 | P0 | `tools/*.py` 语法可编译 | `compile(text, path, "exec")`，不 import（避免副作用） |
| A2 | P1 | 无硬编码本机路径 | 正则匹配 `C:\Users\<name>`、`/home/<name>/`、`/Users/<name>/` |
| A3 | P0 | 无危险文件操作 | 匹配 `rm -rf /`、`shutil.rmtree("/")`、`os.remove("C:\")`、`format c:` |
| A4 | P1 | 构建期无外网依赖 | 匹配 `import requests/httpx/aiohttp` |
| A5 | P2 | 有 `if __name__ == "__main__"` 守卫 | 保证可被其他脚本安全 import |
| A6 | P0/P1 | 全仓 UTF-8 无 BOM | 非 UTF-8 为 P0，BOM 为 P1 |
| A7 | P0 | 每个技能目录有 `SKILL.md` | — |
| A8 | P2 | 无 `.orig/.rej/.bak/~/.DS_Store/.tmp` | — |

**A1 为什么用 `compile` 而不是 `import`**：import 会执行模块顶层代码。审查器不能被被审对象影响。

**A6 为什么 BOM 是 P1 而不是 P0**：BOM 不会让 Python 报错，但会让 frontmatter 解析失败（`---` 前多了三个不可见字节），属于"静默错误"，必须报但不阻断。

---

## 6. 审查规则：B 视角（审查者）

关注点：**内容是否合规、完整、可署名分发**。

| 编号 | 严重度 | 检查项 | 阈值/模式 |
|---|---|---|---|
| B1 | P0 | frontmatter 可解析 | 以 `---` 开头且存在第二个 `---` |
| B2 | P0 | 含 `name`/`description`/`type`/`theme` | 空值视为缺失 |
| B3 | P1 | `name` 等于目录名 | 完全相等 |
| B4 | P1 | `type` 合法 | `workflow` / `component` / `interactive` |
| B5 | P1 | `theme` 合法 | 13 个已知主题 |
| B6 | P1/P2 | `description` 长度 | <40 为 P1；>400 为 P2 |
| B7 | P1 | 无未填充占位符 | 见下方说明，可自动修复 |
| B8 | P1 | `skills/<x>/SKILL.md` 引用存在 | 目录必须存在 |
| B9 | P1 | `../<x>/<file>` 相对链接存在 | `Path.resolve()` 后必须存在 |
| B10 | P0 | 无秘密泄露 | AWS Key / GitHub Token / OpenAI Key / 私钥 / 硬编码密码 |
| B11 | P2 | `SKILL.md` ≤ 200 KB | — |
| B12 | P1 | `template.md` 非空 | 0 字节为缺陷 |
| B13 | P1 | 正文 `##` 章节 ≥ 2 | 结构过薄无法承载流程 |
| B14 | P0 | `LICENSE` 与 `NOTICE` 存在 | 分发合规底线 |
| B15 | P1 | ≥10 个技能保留来源声明 | 含 `Provenance` 或 `Adapted from` |
| B16 | P1 | 无 `Suggested filename/placement` | 与扁平布局冲突，可自动修复 |

### B7 的判定边界

这条规则最容易误报，因此分两层，且**只认明确残留**：

```python
# 第一层：整行是一个空条目的清单项
^\s*[-*]\s*\[(?=[^\]]*(?:link here|if applicable|TODO|TBD|FIXME))[^\]]*\]\s*$

# 第二层：行内的特定残留
\[If (?:Dean|the author) has[^\]]*\] | \[Link to relevant[^\]]*\] | \bLorem ipsum\b | \[TODO:[^\]]*\]
```

**不在规则内**的（都是合法模板槽位，必须放过）：

| 形态 | 为什么合法 |
|---|---|
| `Prepared by: [Your name or team]` | 模板填空位，用户会替换 |
| `[Insert quote that emphasizes customer value]` | 模板填空位，语义明确 |
| `[If GO]` / `[If successful → scale]` | 正文里的分支说明，不是待办 |
| ``` `TBD` ```（行内代码） | 正文在教用户"日期未知写 TBD" |

判断依据：**占位符后面的句子还成不成立**。`- [If Dean has PRD templates, link here]` 删掉后句子消失、信息量为零；`Prepared by: [Your name]` 是句子的一部分。

### B15 的阈值为什么是 10

77 个技能中 45 个含 `Provenance`/`Adapted from`（其余是通用框架梳理，无单一上游）。阈值定 10 是为了捕获"批量删署名"这一事故形态，而非要求每个技能都有出处。

---

## 7. 审查规则：C 视角（AI 使用方）

关注点：**Agent 拿到 77 个技能后能否正确选中并执行**。

| 编号 | 严重度 | 检查项 | 说明 |
|---|---|---|---|
| C1 | P1 | `description` 含 `Use when/for/to` | Agent 唯一的路由依据 |
| C2 | P1 | 声明了输入要求 | 匹配 `## Input` 或 `Arriving empty-handed` 等等价表述 |
| C3 | P2 | 显式产出章节 | `## Output/Deliverable/Application/Workflow/Process` 或 `### Outputs` |
| C4 | P2 | 名称无前缀歧义 | 与同级技能互为前缀时提示（按技能聚合，不按对重复） |
| C5 | P2 | `SKILL.md` ≤ 40 KB | 单次加载即占上下文 |
| C6 | P1 | 无阻塞式索取凭据 | 匹配 `ask the user for their api key/token/password` |
| C7 | P2 | 有 `argument-hint` | 斜杠调用参数提示 |
| C8 | P0 | 技能名全局唯一 | 重复会导致路由不确定 |

### C1 为什么是 P1

这不是风格问题。Agent 判断"要不要调用某技能"只读 `description`。缺失 `Use when …` 时，描述退化为功能罗列，模型只能靠语义相似度猜——在 77 个技能里猜错的概率显著上升。

**修复方式不是改规则，是改内容**：给描述补一句"Use when …"。本仓库 77 个技能全部通过此规则。

### C4 为什么不修

`user-story` / `user-story-mapping` / `user-story-splitting` 是刻意分层的三个粒度，改名会破坏与上游的一致性。缓解措施放在文档层：README 与用户手册给出"名字相近怎么选"对照表。

### C5 为什么保留 42 KB 的技能

`ai-shaped-readiness-advisor`（42 KB）是交互式评估，流程长但内聚，拆分会破坏引导连续性。P2 仅提示，不阻断。

---

## 8. 校验规则：L 系列（清单约束）

与 `audit.py` 的分工：审查看**内容质量**，校验看**交付一致性**。

| 编号 | 检查项 | 失败后果 |
|---|---|---|
| L1 | 14 个必需文件存在且非空 | 包不完整 |
| L2 | `MANIFEST.json` 可解析且 `schema` 匹配 | 清单不可信 |
| L3 | 名字集合双向一致、无重复、`skill_count` 相符 | 清单与磁盘脱节 |
| L4 | 每个技能目录摘要与清单一致 | 内容已改但清单未重建 |
| L5 | `VERSION` == `versions.json.package` == 清单 == 文档标记 | 版本错乱 |
| L6 | 技能内容总字节 ≤ 8 MB | 混入构建产物或大二进制 |
| L7 | `skills/` 只有目录、无游离文件、无空目录 | 布局污染 |

**L4 是最重要的一条**。它保证 release 上的 zip 与 `MANIFEST.json` 描述的是同一份东西。手工改了技能内容却忘了 `manifest.py generate`，L4 会精确指出是哪几个技能（附文件数变化）。

**L5 的完整链条**：`versions.json` → `VERSION` → `MANIFEST.package_version` → 三份文档的 `<!--VER:-->` 标记。任一环脱节即失败。

---

## 9. 构建流水线与门禁

```
python tools/build.py
    │
    ├─[1/6] version.bump        递增 package / readme / user_manual / tech_manual
    │                           写 versions.json、VERSION、注入三份文档标记
    ├─[2/6] manifest.generate   重建 MANIFEST.json（含 package_version 与全部摘要）
    ├─[3/6] audit               A+B+C 三视角，P0+P1 必须为 0，否则 ABORT
    ├─[4/6] validate            L1–L7 全 PASS，否则 ABORT
    ├─[5/6] changelog           追加 v{version} 条目（必须在打包前）
    └─[6/6] package             生成 dist/*.zip + SHA256SUMS.txt
```

**顺序不可调换的原因**：

- 递增必须在清单生成之前——清单里要记录新版本号
- 清单生成必须在审查之前——B11/C5 依赖文件的实际大小
- 审查必须在校验之前——内容问题比一致性问题更该先暴露
- 校验必须在打包之前——校验的对象就是要打包的那份磁盘状态
- **CHANGELOG 必须在打包之前**——否则 zip 里缺本版记录。这一条是首次打包时由真实报错 `FileNotFoundError: 打包清单中的路径不存在：CHANGELOG.md` 暴露出来的：原设计把 CHANGELOG 排在打包之后，首包必然失败。

**失败即停**，不产出 zip。已递增的版本号不回滚（保留递增记录，下次打包继续向上），这是有意的：回滚版本号会让 CHANGELOG 与 tag 对不上。

**P2 的处理**：默认警告但不阻断，因为 P2 多为"体量偏大""命名歧义"这类需要人工判断的取舍。`--allow-p2` 用于在 CI 里显式声明"已知并接受"。

---

## 10. 版本策略

### 10.1 语义化映射

| 变更类型 | 递增位 | 例子 |
|---|---|---|
| 破坏性：技能改名、删技能、frontmatter 契约变更 | major | `1.x.x → 2.0.0` |
| 新增：加技能、加工具、加文档章节 | minor | `x.1.x → x.2.0` |
| 修复：修断链、修占位、补字段 | patch | `x.x.1 → x.x.2` |

### 10.2 四套版本的关系

| 键 | 对应文件 | 独立递增场景 |
|---|---|---|
| `package` | `VERSION` / release tag | 技能内容或工具变更 |
| `readme` | `README.md` | 仅 README 改动 |
| `user_manual` | `docs/USER-MANUAL.md` | 仅用户手册改动 |
| `tech_manual` | `docs/TECH-MANUAL.md` | 仅技术手册改动 |

独立递增用 `version.py bump --keys user_manual`；完整发布用 `build.py`（四者同增）。

### 10.3 Git tag 约定

```
v1.0.1          与 VERSION 一致，用于 release
```

tag 名必须与 `VERSION` 完全相同（含 `v` 前缀）。release 附件名必须为 `Product-Manager-puls-skills-v{version}.zip`，与 `build.py` 产出的一致——这样 `SHA256SUMS.txt` 才能直接被使用者校验。

---

## 11. 扩展指南

### 11.1 新增一个技能

```bash
# 1. 建目录
mkdir -p skills/my-new-skill

# 2. 写 SKILL.md（必须含下列 frontmatter）
```

```yaml
---
name: my-new-skill
argument-hint: "[what the user should provide]"
description: Do X for Y. Use when the user needs Z.
type: workflow
theme: pm-artifacts
---
```

```bash
# 3. 加模板与示例（推荐）
#    skills/my-new-skill/template.md
#    skills/my-new-skill/examples/sample.md

# 4. 重建清单 + 审查
python tools/manifest.py generate
python tools/audit.py

# 5. 校验 + 打包
python tools/build.py --part minor
```

**必须自己确认的四件事**（审查器会拦其中三项）：

1. `description` 里有一句 `Use when …`（C1）
2. 有 `## Input` 段落或等价表述（C2）
3. 正文有 ≥2 个 `##` 章节（B13）
4. **它和你已有的技能不重叠** —— 这条审查器查不出来，只能人判断

### 11.2 加一条审查规则

在 `tools/audit.py` 中：

```python
def check_reviewer(ctx: AuditContext) -> List[Finding]:
    ...
    # B17 你的规则
    for m in re.finditer(r"你的模式", body):
        findings.append(
            Finding("B17", "P1", "B", rel, "问题描述", line, fixable=False)
        )
```

注意事项：

- **规则编号不得复用**，新规则接在现有最大号之后
- `fixable=True` 仅当修复动作是"删除整行"且不会破坏语义时才设（`apply_fixes` 只会删行）
- 新规则加完必须**跑一次全量**，看误报率。误报超过 5% 说明模式太宽，收紧模式而不是调阈值
- 严重度要能自圆其说：P0 = 技能不可用，P1 = 可用但会误导，P2 = 建议

### 11.3 加一条校验规则

在 `tools/validate.py` 的 `run_all()` 里挂新函数，编号接 `L8`。校验规则只做"确定性的、二元可判"的检查；需要判断力的放 `audit.py`。

---

## 12. 真机验证记录

以下均为实际执行结果，非推演。

### 12.1 审查收敛过程

| 轮次 | 动作 | P0 | P1 | P2 | 关键发现 |
|---|---|---:|---:|---:|---|
| R1 | 首次全量审查 | 1 | 27 | 10 | 3 处真实断链（`stakeholder-map`）；12 处 `[Your …]` **误报**；NOTICE 缺失 |
| R1a | 收紧 B7 规则（排除模板槽位）、C4 按技能聚合 | — | — | — | 误报清零，规则仍需验证 |
| R2 | 修 3 处断链后复审 | 1 | 13 | 8 | 剩余全部为真残留 |
| R3 | `--fix` 自动清理 | 1 | 13 | 8 | **修复缺陷**：删占位行后 `### Dean's Work` 变成悬空标题，吞掉后续元信息块 |
| R3a | 修 `_drop_empty_dean_sections` 边界（`---` 视为章节结束） | — | — | — | 边界修正 |
| R4 | `--fix` 重跑（含新增 B16） | 1 | 0 | 8 | 27 文件 / 54 行清理完成；`--fix` 二次执行零改动（幂等通过） |
| R5 | 补 4 个 `argument-hint` | 1 | 0 | 4 | C7 清零 |
| R6 | 补 `NOTICE` | **0** | **0** | 4 | 收敛完成 |

**两个被真机抓出的自身缺陷**：

1. **R1 的误报**：`[Your name or team]` 被判为未填充占位。若不看真实输出，这条规则会误删 12 处合法模板槽位，直接损坏技能内容。修复方式是重写判定模式，不是提高阈值。
2. **R3 的破坏性修复**：`### Dean's Work` 下方的 `---` 被当作章节内容，导致删掉空章节时连带吞掉后续内容，且标题残留。这个缺陷在单轮审查里看不出来——必须先执行 `--fix`、再验证产物、再重跑，才能暴露。

### 12.2 最终状态

```
技能数：77    视角：工具实现者/审查者/AI 使用方
结果：P0=0  P1=0  P2=4

[A] 工具实现者：通过
[B] 审查者：通过
[C] AI 使用方：4 项（均为 P2）
  - ai-shaped-readiness-advisor 42 KB（内聚长流程，不拆）
  - pol-probe / user-story-mapping / user-story 名称前缀歧义（设计如此，文档层缓解）
```

### 12.3 安装器验证（8 项）

在临时目录 `_pm_install_test/` 上实测，不触碰真实技能目录：

| # | 场景 | 命令 | 实测输出 |
|---|---|---|---|
| 1 | 全量安装 | `install --target <tmp>` | 新装 77 / 覆盖 0 / 跳过 0；磁盘 77 个目录 |
| 2 | 查记录 | `list` | 包版本 v1.0.0，记录 77，缺失 0 |
| 3 | 重复安装 | `install --target <tmp>` | 新装 0 / 覆盖 0 / **跳过 77**（冲突保护生效） |
| 4 | 空跑卸载 | `uninstall --dry-run` | 打印"将移除 77 个"，磁盘无变化 |
| 5 | 执行卸载 | `uninstall` | 已移除 77，剩余目录 `[]` |
| 6 | 卸载后查记录 | `list` | 退出码 1，"无安装记录" |
| 7 | 选择性安装 | `install --only prd-development,user-story` | 新装 2，磁盘仅 2 个目录 |
| 8 | 非法技能名 | `install --only not-exist` | 退出码 1，"未知技能：not-exist" |

第 3 项是关键：默认跳过而非覆盖，保证用户已有技能与之前安装的上游版本不被误改。

### 12.4 校验器验证（故障注入 5 场景）

在仓库副本上逐项注入故障，确认 `validate.py` 能捕获且指出位置：

| 注入的故障 | 预期规则 | 实测输出 |
|---|---|---|
| 基线（无故障） | 全 PASS | 退出码 0，L1–L7 全 PASS |
| 往 `swot-analysis/SKILL.md` 追加一行 | L4 | 退出码 1，`1 个技能内容已变更但清单未重建：swot-analysis(文件 4→4)` |
| 把 README 的 package 标记改成 9.9.9 | L5 | 退出码 1，`README.md 的 package 标记为 9.9.9，应为 1.0.0` |
| 删除 `skills/storyboard/` | L3 | 退出码 1，`清单有但磁盘无（1）：storyboard` + `skill_count=77，磁盘实际 76` |
| 在 `skills/` 下放一个 `stray.md` | L7 | 退出码 1，`skills/ 根下存在游离文件：stray.md` |

故障可叠加，后续场景累积前面的失败项——说明校验不会"遇错即停"，一次扫出全部偏差。

### 12.5 版本机制验证（6 项）

| 操作 | 结果 |
|---|---|
| `bump --part patch` | 四键全部 1.0.0 → 1.0.1，`check` 通过 |
| `bump --part minor` | 1.0.1 → 1.1.0，`check` 通过 |
| `bump --keys user_manual` | 仅 `user_manual` 1.1.0 → 1.1.1；README 内四个标记分别显示 1.1.0/1.1.0/1.1.1/1.1.0，`check` 通过 |
| `VERSION` 文件 | 同步为 1.1.0 |
| `bump --keys nope` | 退出码 2，`未知版本键：nope` |
| `versions.json` 损坏 | 退出码 1，`versions.json 缺少键：readme, user_manual, tech_manual` |

第三项验证了独立版本能力：三份文档可以有各自的版本号，同时 README 里的汇总表正确反映差异。

### 12.6 发布包验证

| 检查 | 结果 |
|---|---|
| zip 条目数 | 267（含 `AGENTS.md`、`CHANGELOG.md`） |
| 顶层目录 | 单一 `Product-Manager-puls-skills-v1.0.0/`，解压不散落 |
| 解压后 `validate.py` | 退出码 0，7 通过 / 0 失败 |
| 解压后 `version.py check` | `[OK] 版本号一致` |
| 解压后 `install --dry-run` | 正确识别 77 个已安装、跳过 77（冲突检测在包内同样生效） |
| SHA256 核对 | 与 `SHA256SUMS.txt` 完全一致 |

**这一组的意义**：证明发布包是自包含的——解压后不依赖仓库、不依赖网络，工具链在包内可独立跑通校验与安装。

> 首轮打包时 `AGENTS.md` 未进包（`INCLUDE` 列表遗漏），是靠"源文件数从 266 变成 266"这个异常发现的：删掉 4 KB 的 `START_HERE.md`、重写 9 KB 的 `AGENTS.md` 后总数没变，说明这两个文件都不在打包范围内。

### 12.7 跨机一致性验证

`MANIFEST.json` 的摘要基于文件字节，一旦换行被转换（LF→CRLF），所有技能摘要都会失配。因此在真机上做了一次完整克隆验证：

| 检查 | 结果 |
|---|---|
| `git clone` 后文本文件换行 | 262 个文件，**CRLF 0 个 / LF 262 个** |
| 克隆后 `validate.py` | 7 通过 / 0 失败，含 `L4 内容摘要全部匹配（77 个技能）` |
| 克隆后 `audit.py` | P0=0 / P1=0 / P2=4 |

前提是本机 `core.autocrlf=true`（Windows 默认常见配置）。为此在仓库根加了 `.gitattributes`：

```gitattributes
* text=auto eol=lf
*.png binary
*.zip binary
```

`.gitattributes` 的 `eol=lf` 优先级高于 `core.autocrlf`，保证任何平台检出后都是 LF，摘要稳定。

**若不做这一步**：Linux/macOS 用户克隆后 `validate.py` 会报 77 个技能全部失配，看起来像"清单被篡改"，实际只是换行差异。

---

## 13. 已知限制

**① 审查器不做语义审查。**
能查"有没有 `Use when`"，不能查"这句 `Use when` 说得对不对"。方法论的正确性靠人审。

**② B7 与模板槽位靠模式区分，存在边界风险。**
新增技能若写出 `- [待补充说明]` 这类整行占位，不会被 B7 捕获（模式只认 `link here|if applicable|TODO|TBD|FIXME`）。需要时在 `PLACEHOLDER_LINE_RE` 里加词。

**③ C4 只能提示前缀歧义，无法判断语义重叠。**
`swot-analysis` 与 `competitive-analysis-process` 是否重叠，只有人知道。

**④ 技能内容 2 MB，全量安装后技能清单约 12K 字符。**
对上下文紧张的模型，建议 `--only` 精选安装。

**⑤ CC BY-NC-SA 4.0 限制商业使用。**
这是许可证约束，不是技术限制。工具链本身可复用于其他技能包，但技能内容不可商用。

**⑥ 上游方法论内容不做本地化改造。**
正文保持英文原文，以避免翻译引入的语义漂移。中文只出现在本手册、README 与配图中。

---

<div align="center">
<sub>本手册随技能包发布，版本 <!--VER:tech_manual-->1.0.0<!--/VER--> · 技能包 <!--VER:package-->1.0.0<!--/VER--></sub>
</div>
