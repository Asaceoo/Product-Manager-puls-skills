<div align="center">

<img src="docs/images/hero.png" alt="Product-Manager-puls-skills" width="100%">

<br>

**77 个产品经理技能，装进你的 AI Agent。**
从发现问题到产品退市，每一步都有可执行的方法论，而不是一段听起来很专业的聊天记录。

<br>

[![Release](https://img.shields.io/github/v/release/Asaceoo/Product-Manager-puls-skills?label=release&color=2F6BFF)](https://github.com/Asaceoo/Product-Manager-puls-skills/releases)
[![Skills](https://img.shields.io/badge/skills-77-12A47A)](#技能速查)
[![Themes](https://img.shields.io/badge/themes-13-7A5AF8)](#13-个主题)
[![License](https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-FF7A45)](LICENSE)

[快速开始](#30-秒上手) · [技能速查](#技能速查) · [用户手册](docs/USER-MANUAL.md) · [技术手册](docs/TECH-MANUAL.md)

</div>

---

## 这是什么

一套**面向 AI Agent 的产品经理方法论技能库**。每个技能是一份结构化的 `SKILL.md`：它规定这个任务该怎么问、按什么阶段推进、产出什么格式的文档、哪些地方必须标"假设"而不能写成结论。

它不是提示词模板合集。区别在于：提示词模板给你一段文字，技能库给 Agent 一套**受约束的流程**。

| | 普通提示词 | 本技能库 |
|---|---|---|
| 输入 | 你必须一次说清全部背景 | 空手也能开工，技能会逐项收敛 |
| 过程 | 一次生成，无法干预 | 分阶段推进，每步给编号选项 |
| 缺口 | 编造内容填空 | 显式标 `假设` / `待验证` |
| 产出 | 一段聊天记录 | 套 `template.md` 成型的文档 |
| 复用 | 每次重写提示词 | 斜杠命令 + `argument-hint` |

## 不是什么

- **不是原创方法论**。内容改编自 Dean Peters（Productside）的 [Product-Manager-Skills](https://github.com/deanpeters/Product-Manager-Skills)，本仓库是工程化再分发版，详见 [NOTICE](NOTICE)。
- **不是 SaaS 工具**。没有服务器、没有账号、不需要 API Key，纯本地 Markdown 文件。
- **不能替代你的判断**。技能会强制标注假设与待验证项，最终结论仍要你拿真实数据核对。

## 30 秒上手

```bash
git clone https://github.com/Asaceoo/Product-Manager-puls-skills.git
cd Product-Manager-puls-skills
python tools/install.py install
```

安装器会把 77 个技能复制到 `~/.workbuddy/skills/`，并写入安装记录，卸载时只删自己装的部分：

```bash
python tools/install.py list        # 看装了什么
python tools/install.py uninstall   # 按记录完整移除
```

<details>
<summary>只想装几个？用 <code>--only</code></summary>

```bash
python tools/install.py install --only prd-development,user-story,prioritization-advisor
python tools/install.py install --dry-run          # 先看计划，不落盘
python tools/install.py install --target D:/my/skills --force
```
</details>

装完后，在对话里直接说需求，Agent 会按 `description` 里的 `Use when …` 自动选中技能：

> 我需要给"自助开通工作区"这个功能写一份 PRD，手上有一份调研笔记和对应的 OKR。

## 四层架构

<img src="docs/images/architecture.png" alt="四层架构" width="100%">

**L1 调用入口** —— WorkBuddy、Claude Code、Codex 或终端 CLI，任何能读 Markdown 的 Agent 都能用。
**L2 路由层** —— 77 份 `description` 决定选中谁；`argument-hint` 决定斜杠调用时提示什么参数。
**L3 能力层** —— 13 个主题，3 种技能类型（workflow 20 / component 28 / interactive 29）。
**L4 交付物** —— PRD、用户故事、SWOT、Roadmap、定价分析、EOL 清单。

底部是工程链路：版本号、清单、审查、校验、打包、安装六环闭合，任何一环失败都不出包。

## 一次调用怎么走

<img src="docs/images/workflow.png" alt="五步流转" width="100%">

关键在第三步：**技能不要求你一次说清所有事**。它只问当前阶段缺的那几项，你已经给过的材料（笔记、Slack 记录、数据）会自动填进对应环节，不会重复问。

第二步的选中靠 `description` 里的触发语。这也是为什么本仓库对每个技能的描述都做了"`Use when …`"的强制要求——那是 Agent 唯一的路由依据。

## 13 个主题

<img src="docs/images/themes.png" alt="主题分布" width="100%">

| 主题 | 技能数 | 什么时候找它 |
|---|---:|---|
| 市场情报 | 18 | 调研竞品、看行业结构、算市场规模、盯竞品变化 |
| PM 交付物 | 8 | 写 PRD、拆用户故事、画故事地图、写新闻稿 |
| 财务指标 | 7 | 算 SaaS 指标、评定价、判断功能投资回报 |
| 发现与用户研究 | 7 | 跑发现周期、准备访谈、建 JTBD、画机会树 |
| 生命周期终止 | 6 | 决定是否退市、排期、写公告、内部赋能 |
| 职业与领导力 | 5 | PM 升总监、面试答题、30-60-90 天上任 |
| 工作坊引导 | 5 | 带定位工作坊、旅程地图工作坊、故事地图工作坊 |
| 验证与实验 | 5 | 设计廉价验证、选中该测什么、画 Lean UX Canvas |
| 策略与定位 | 5 | 定位陈述、优先级框架选型、跑策略会、排 Roadmap |
| 干系人与沟通 | 4 | 识别干系人、排优先级、拆解模糊需求 |
| AI 与 Agent | 3 | 设计多 Agent 工作流、评估 AI 就绪度、上下文工程 |
| 产品生命周期 | 2 | 判断处于哪个阶段、选延续还是替换 |
| 元技能 | 2 | 造新技能、把原始内容转成合规技能 |

## 技能速查

<details>
<summary><b>市场情报（18）</b> — 调研、竞品、行业结构</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `swot-analysis` | workflow | 带证据出处的 SWOT，收尾给 S-O / W-T 交叉策略 |
| `porters-five-forces` | workflow | 五力模型读行业结构，每力附信号 |
| `pestel-analysis` | component | 六类宏观因素分析 |
| `pestel-delta-monitor` | workflow | 季度重扫 PESTEL，只报变化 |
| `market-landscape-scan` | workflow | 市场分层、玩家、替代品、空白区 |
| `competitive-analysis-process` | workflow | 六步编排完整竞品分析 |
| `competitive-research-snapshot` | workflow | 带引用的竞品快照 + 对比矩阵 |
| `competitive-intel-watch` | workflow | 对历史快照做增量监控 |
| `battle-card-builder` | workflow | 销售对战卡，每条主张标证据等级 |
| `company-research` | component | 公司研究简报：高管言论、产品策略、组织 |
| `company-intel` | workflow | 公司/行业/竞品组研究，七种分析透镜 |
| `ansoff-matrix` | workflow | 安索夫矩阵排增长选项，带风险分级 |
| `tam-sam-som-calculator` | interactive | TAM/SAM/SOM，显式列出假设与方法 |
| `voice-of-customer-miner` | workflow | 挖评论、应用商店、论坛里的未满足需求 |
| `pricing-packaging-tracker` | workflow | 竞品定价与包装的可 diff 时间序列 |
| `intelligence-collection-disciplines` | component | 八种情报收集学科（OSINT 到 MASINT） |
| `intel-discipline-advisor` | interactive | 把问题分流到合适的情报学科与节奏 |
| `autonomous-investigation` | workflow | 自主调研协议：搜索计划关卡、证据分级 |

</details>

<details>
<summary><b>PM 交付物（8）</b> — PRD、用户故事、故事地图</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `prd-development` | workflow | 八阶段 PRD：从执行摘要到开放问题 |
| `epic-hypothesis` | component | 把 Epic 写成可验证假设 |
| `epic-breakdown-advisor` | interactive | Humanizing Work 九种拆分模式拆 Epic |
| `user-story` | component | Mike Cohn 格式 + Gherkin 验收标准 |
| `user-story-splitting` | component | 大故事拆小，按固定拆分模式 |
| `user-story-mapping` | component | 故事地图：活动 → 步骤 → 任务 → 发布切片 |
| `storyboard` | component | 六格分镜讲清用户从问题到解决 |
| `press-release` | component | 亚马逊式新闻稿，先定义客户价值 |

</details>

<details>
<summary><b>财务指标（7）</b> — SaaS 指标、定价、投资回报</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `finance-metrics-quickref` | component | 快速查指标定义、公式、基准值 |
| `saas-revenue-growth-metrics` | component | 收入、留存、增长指标计算 |
| `saas-economics-efficiency-metrics` | component | 单位经济学与资本效率 |
| `business-health-diagnostic` | interactive | 四维体检：增长、留存、效率、资本 |
| `finance-based-pricing-advisor` | interactive | 定价变动评估：ARPU、转化、流失、NRR、回本期 |
| `feature-investment-advisor` | interactive | 功能投资回报：收入影响、成本结构、ROI |
| `acquisition-channel-advisor` | interactive | 获客渠道评估：单位经济学、客户质量、可扩展性 |

</details>

<details>
<summary><b>发现与用户研究（7）</b> — 发现周期、访谈、JTBD</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `discovery-process` | workflow | 完整发现周期：问题假设到验证方案 |
| `discovery-interview-prep` | interactive | 访谈准备：目标、人群、约束、方法 |
| `jobs-to-be-done` | component | JTBD 格式梳理任务、痛点、收益 |
| `problem-framing-canvas` | interactive | MITRE 问题框定画布 |
| `problem-statement` | component | 问题陈述：谁被卡住、想做什么、卡在哪 |
| `proto-persona` | component | 从现有研究快速建原型画像 |
| `opportunity-solution-tree` | interactive | 机会解决方案树：结果 → 机会 → 方案 → 实验 |

</details>

<details>
<summary><b>生命周期终止（6）</b> — 退市决策与执行</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `eol-process` | workflow | 端到端退市：决定、对齐、规划、准备、公告、收尾 |
| `eol-readiness-advisor` | interactive | 退市 go/no-go 评估，按规模匹配投入 |
| `eol-checklist` | component | 分阶段退市清单，每项有责任人 |
| `eol-message` | component | 分档退市公告：从简讯到完整分阶段沟通 |
| `eol-internal-enablement` | component | 支持 FAQ、销售话术、异议处理 |
| `eol-stakeholder-sequence` | component | 该跟谁谈、什么顺序、每场谈什么 |

</details>

<details>
<summary><b>职业与领导力（5）</b> — 晋升、面试、上任</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `altitude-horizon-framework` | component | PM→总监的两个维度：高度与视野 |
| `director-readiness-advisor` | interactive | 总监过渡四阶段：准备、面试、落地、校准 |
| `vp-cpo-readiness-advisor` | interactive | VP/CPO 过渡四阶段 |
| `executive-onboarding-playbook` | workflow | 30-60-90 天上任诊断路径 |
| `product-sense-interview-answer` | component | 产品感面试答题结构：假设、分层、痛点、取舍 |

</details>

<details>
<summary><b>工作坊引导（5）</b> — 带会议、带共创</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `workshop-facilitation` | interactive | 通用引导协议：一步步来、进度可见、编号选项 |
| `positioning-workshop` | interactive | 定位工作坊：目标客户、未满足需求、品类、收益 |
| `customer-journey-map` | component | 旅程地图：阶段、触点、行为、情绪、指标 |
| `customer-journey-mapping-workshop` | interactive | 旅程地图工作坊完整引导 |
| `user-story-mapping-workshop` | interactive | 故事地图工作坊完整引导 |

</details>

<details>
<summary><b>验证与实验（5）</b> — 低成本试错</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `pol-probe` | component | Proof of Life 探针：用最小成本验证高风险假设 |
| `pol-probe-advisor` | interactive | 按假设、风险、资源选合适的 PoL 探针 |
| `derisk-measurement-advisor` | interactive | 决定该测什么、验证什么、盯什么 |
| `lean-ux-canvas` | interactive | Lean UX Canvas v2 引导 |
| `recommendation-canvas` | component | AI 产品想法评估：结果、假设、风险、定位 |

</details>

<details>
<summary><b>策略与定位（5）</b> — 定位、优先级、路线图</summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `positioning-statement` | component | Geoffrey Moore 式定位陈述 |
| `prioritization-advisor` | interactive | 按阶段、团队、干系人选优先级框架 |
| `product-strategy-session` | workflow | 端到端策略会：定位、发现、路线图 |
| `roadmap-planning` | workflow | 战略 Roadmap：优先级、Epic、对齐、排期 |
| `organic-growth-advisor` | interactive | 有机增长路径选择：新客群、新地域、新渠道 |

</details>

<details>
<summary><b>干系人与沟通（4）</b> · <b>AI 与 Agent（3）</b> · <b>产品生命周期（2）</b> · <b>元技能（2）</b></summary>

| 技能 | 类型 | 作用 |
|---|---|---|
| `stakeholder-identification` | component | 先列全干系人再谈沟通 |
| `stakeholder-mapping` | component | 双网格给干系人排优先级 |
| `stakeholder-engagement-advisor` | interactive | 针对单个干系人定沟通策略 |
| `incoming-request-advisor` | interactive | 拆解模糊需求，区分字面要求与真实意图 |
| `ai-shaped-readiness-advisor` | interactive | 判断你的工作方式是 AI-first 还是 AI-shaped |
| `context-engineering-advisor` | interactive | 诊断"堆上下文"与"上下文工程"的区别 |
| `agent-orchestration-advisor` | interactive | 多 Agent 工作流设计：边界、交接、监控 |
| `product-lifecycle-plays` | component | 判断生命周期阶段，选延续/替换/退出 |
| `lifecycle-play-advisor` | interactive | 按阶段推荐具体打法 |
| `pm-skill-creator` | interactive | 对话式设计新 PM 技能 |
| `skill-authoring-workflow` | workflow | 把原始内容转成合规可发布的技能 |

</details>

### 名字相近怎么选

`user-story` / `user-story-mapping` / `user-story-splitting` 三个只有前缀相同，用途完全不同：

| 你要做的事 | 用哪个 |
|---|---|
| 写一条带验收标准的用户故事 | `user-story` |
| 把一堆故事铺成发布切片的地图 | `user-story-mapping` |
| 一条故事太大，需要拆开 | `user-story-splitting` |
| 要带团队一起画这张地图 | `user-story-mapping-workshop` |

同理 `pol-probe` 是**单个探针的定义模板**，`pol-probe-advisor` 是**帮你选哪种探针**。

## 三个真实场景

**① 手上的需求很模糊**

> 「运营说要做个积分系统，让我下周给方案。」

先 `incoming-request-advisor` 拆解字面要求与真实意图，再 `problem-framing-canvas` 框定问题，最后 `prioritization-advisor` 判断该不该现在做。产出不是"好的我来做"，而是一页带证据的取舍建议。

**② 要写 PRD 但材料散在四处**

> 「把这周的调研笔记、OKR、客服工单整理成一份 PRD。」

`prd-development` 会分八个阶段推进，已给的材料自动进对应章节；没材料的地方标 `假设` 或 `待验证`，不会编数字。最后套 `template.md` 出文档。

**③ 竞品突然降价**

> 「A 公司降价 30%，我该怎么应对？」

`pricing-packaging-tracker` 先建可 diff 的定价时间序列，`battle-card-builder` 出销售对战卡，`finance-based-pricing-advisor` 算跟进降价的 ARPU 与流失影响。三步都有证据来源要求。

更多用法见 [用户手册](docs/USER-MANUAL.md)。

## 工程链路

这套技能库不是"一堆 Markdown 扔上去"。六个脚本构成闭环，每次发布都要过全部门禁：

| 脚本 | 职责 | 关键约束 |
|---|---|---|
| `tools/version.py` | 版本号单一事实源 | 包与三份文档版本自动注入，禁止手改 |
| `tools/manifest.py` | 生成 `MANIFEST.json` | 记录每个技能的文件数与目录摘要 sha256 |
| `tools/audit.py` | 三视角对抗审查 | 工具实现者 / 审查者 / AI 使用方，P0+P1 必须为 0 |
| `tools/validate.py` | 清单约束兜底 | 清单与磁盘必须同一份东西，版本必须对齐 |
| `tools/build.py` | 打包流水线 | 版本 → 清单 → 审查 → 校验 → CHANGELOG → 打包 |
| `tools/install.py` | 可逆安装 | 只删自己装的，冲突默认跳过 |

```bash
python tools/build.py            # 完整发布：版本 patch+1，过门禁，出 zip
python tools/audit.py            # 单独跑审查
python tools/validate.py         # 单独跑校验
python tools/make_figures.py     # 重绘 README 配图
```

规则细节（A1–A8 / B1–B16 / C1–C8 / L1–L9）见 [技术手册](docs/TECH-MANUAL.md)。

## 目录结构

```
Product-Manager-puls-skills/
├── skills/                  77 个技能（SKILL.md + template.md + examples/）
├── catalog/                 全量索引（skills-index.yaml）
├── docs/
│   ├── USER-MANUAL.md       用户手册
│   ├── TECH-MANUAL.md       技术手册
│   └── images/              README 配图
├── tools/                   版本、清单、审查、校验、打包、安装、配图
├── MANIFEST.json            技能清单（自动生成）
├── versions.json            包与文档版本
├── VERSION                  包版本
├── CHANGELOG.md             发布记录（自动追加）
├── NOTICE                   上游署名与修改声明
└── LICENSE                  CC BY-NC-SA 4.0
```

## 与上游的差异

本仓库在上游基础上只做工程性修复，方法论内容未改动。完整清单见 [NOTICE](NOTICE)，摘要：

- 修复 3 处失效交叉引用（`stakeholder-map` → `stakeholder-mapping`）
- 清理 13 处未填充的创作期占位条目与 27 处失效的 `Suggested placement` 元信息
- 为 4 个技能补齐 `argument-hint`
- 新增工具链、清单、三份文档、CI 发布流程

原作者署名与其 `Provenance` 段落全部保留（45 个技能含 `Provenance` / `Adapted from`）。

## 许可证

**CC BY-NC-SA 4.0** — Attribution-NonCommercial-ShareAlike 4.0 International，全文见 [LICENSE](LICENSE)。

| 可以 | 不可以 |
|---|---|
| 个人学习、内部培训、非营利使用 | 售卖、作为付费产品/服务的一部分 |
| 修改后以同一许可证分发 | 去掉原作者署名 |
| 用于自己的产品决策 | 换成更宽松的许可证再分发 |

商业授权需联系原作者 Dean Peters。

---

<div align="center">

| 文档 | 版本 |
|---|---|
| 包版本 | <!--VER:package-->1.0.0<!--/VER--> |
| README | <!--VER:readme-->1.0.0<!--/VER--> |
| [用户手册](docs/USER-MANUAL.md) | <!--VER:user_manual-->1.0.0<!--/VER--> |
| [技术手册](docs/TECH-MANUAL.md) | <!--VER:tech_manual-->1.0.0<!--/VER--> |

<sub>内容改编自 <a href="https://github.com/deanpeters/Product-Manager-Skills">Dean Peters / Product-Manager-Skills</a>，以 CC BY-NC-SA 4.0 分发。</sub>

</div>
