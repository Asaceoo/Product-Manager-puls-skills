# AGENTS.md — 给 AI Agent 的仓库说明

本文件写给**要在这个仓库里工作的 Agent**，不是写给使用技能的人。使用者看 [README.md](README.md)，维护者看 [docs/TECH-MANUAL.md](docs/TECH-MANUAL.md)。

## 仓库是什么

77 个产品经理技能（`skills/<name>/SKILL.md`），加一套工程化交付链路（`tools/`）。技能内容改编自 Dean Peters 的 Product-Manager-Skills，本仓库只做工程性修复与封装，署名与修改清单见 [NOTICE](NOTICE)。

## 你要遵守的一条原则

上游作者的治理原则叫 **ABC — Always Be Coaching**：技能既服务"完成任务"，也服务"让使用者学会判断"。对你的直接约束：

- **不要为简洁牺牲解释。** 删掉技能里的推理脚手架是缺陷，不是优化。
- **反模式是承重结构。** `Common Pitfalls` 之类的章节教人在真实场景里识别陷阱，不要删。
- **示例要展示思考过程，不只是结果。** 短而藏起推理的示例比长而透明的示例更差。
- **双读者始终同时存在：** 建判断力的人，和执行任务的 Agent。不要为了一方牺牲另一方。

要压缩就压废话，别压教学。分不清时，留着。

## 目录职责

| 路径 | 内容 | 谁来改 |
|---|---|---|
| `skills/<name>/SKILL.md` | 单个技能的定义 | 人工编辑，需过审查 |
| `skills/<name>/template.md` | 填充模板 | 人工编辑 |
| `skills/<name>/examples/` | 示例产出 | 人工编辑 |
| `catalog/skills-index.yaml` | 上游索引 | 一般不动 |
| `tools/*.py` | 工程链路 | 人工编辑，仅标准库 |
| `MANIFEST.json` | 自动生成 | **禁止手改**，跑 `manifest.py generate` |
| `versions.json` | 版本单一事实源 | **禁止手改**，跑 `version.py bump` |
| `VERSION` | 自动同步 | **禁止手改** |
| `CHANGELOG.md` | 自动追加 | **禁止手改**，由 `build.py` 写 |
| `docs/images/` | 自动生成 | **禁止手改**，跑 `make_figures.py` |

## 改动技能时的硬约束

改任何 `SKILL.md` 后必须：

```bash
python tools/manifest.py generate   # 重建清单（否则 L4 会失败）
python tools/audit.py               # 三视角审查，P0/P1 必须为 0
python tools/validate.py            # 清单约束，必须全 PASS
```

frontmatter 的五个必填/推荐字段不得缺失：

```yaml
name: <必须与目录名完全一致>
argument-hint: "[用户该提供什么]"
description: <40-400 字符，必须含 "Use when/for/to" 一句>
type: workflow | component | interactive
theme: <13 个已知主题之一>
```

`description` 是 Agent 唯一的路由依据。写它的时候想一件事：**用户在什么场景下会说这句话**。

## 不要做的事

| 禁止 | 原因 |
|---|---|
| 手改 `MANIFEST.json` / `VERSION` / `CHANGELOG.md` | 会被下一次 `build.py` 覆盖，且会触发 L4/L5 失败 |
| 改 `<!--VER:xxx-->` 标记内的数字 | L5 会拦，且造成版本错乱 |
| 删除 `Provenance` / `Adapted from` 段落 | 违反 CC BY-NC-SA 4.0 的署名义务 |
| 删除 `Common Pitfalls` / `Anti-Patterns` 章节 | 违反 ABC 原则 |
| 在 `tools/` 里引入第三方依赖 | 构建期必须能离线运行，且只用标准库 |
| 在配图里用 emoji | 中文字体不含 emoji 字形，会渲染成方块 |
| 把版本号硬编码进配图 | 配图必须与版本解耦，否则每次发版都要重画 |

## 发布流程

```bash
python tools/build.py              # 完整流程：递增版本 → 清单 → 审查 → 校验 → CHANGELOG → 打包
python tools/build.py --dry-run    # 只跑门禁，不产包
python tools/build.py --part minor # 新增技能时用
```

产出在 `dist/`，附 `SHA256SUMS.txt`。tag 名必须与 `VERSION` 一致（`v1.0.0` 形式），release 附件名必须与 zip 文件名一致。

## 需要人判断的三件事

工具查不出来，只能人看：

1. **技能之间是否语义重叠** —— `swot-analysis` 与 `competitive-analysis-process` 是否该合并，审查器不知道
2. **`description` 的触发语写得对不对** —— 审查器只查"有没有 `Use when`"，不查说得准不准
3. **方法论主张是否失真** —— 任何改动上游观点的编辑都必须写进 NOTICE

## 相关文档

- [README.md](README.md) — 项目定位与技能速查
- [docs/USER-MANUAL.md](docs/USER-MANUAL.md) — 面向使用者
- [docs/TECH-MANUAL.md](docs/TECH-MANUAL.md) — 规则全表、工具细节、真机验证记录
- [NOTICE](NOTICE) — 上游署名与本仓库的每一处修改
- [LICENSE](LICENSE) — CC BY-NC-SA 4.0
