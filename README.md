# Espalier

**The dependency map method** — a structure-first engineering standard for codebases co-developed by humans and AI agents.

## 中文摘要

设计文档通常止步于组件层之上,留白处的每一条关系都会在实现时被临场发挥,而临场关系正是耦合灾难的源头;当开发者是上下文随会话消失的 AI agent 时,「有人记得」这一保障层彻底归零。Espalier 用七条规则关闭这最后一公里:担保阶梯(结构 > 机器检查 > 人的记忆,每条不变量必须尽力上移)、依赖与派生之分(一处声明、处处派生,派生物不可能悄然漂移)、五类依赖各配各的执法机制(代码/数据/契约/时序/治理)、双层地图(手写意图小图 + 机器实测大图,二者之差即工作清单)、模块清单必填字段无默认值(残缺即启动失败)、注册即单一声明而暴露是受治投影(绝非第二份手写清单)、每条规则点名它的执行者。三级符合性(已测绘/已检查/已派生)使采纳可渐进、声明可检验。

## Documents

| Document | Version | Status | Role |
|---|---|---|---|
| [SPEC](SPEC.md) | 1.0.0-draft.2 | Working Draft | The standard. Normative. |
| [CAPABILITY_HOST](CAPABILITY_HOST.md) | 0.1.0-draft.1 | Working Draft | Companion, normative within its scope: capability systems served to a model. |
| [AGENT_DEBUG](AGENT_DEBUG.md) | 0.1.0-draft.1 | Working Draft | Companion, normative within its scope: debugging agent misbehaviour by lookup. |
| [RATIONALE](RATIONALE.md) | — | Informative | Where each rule comes from, what supports it, and where the evidence is thin. |
| [TEMPLATES](TEMPLATES.md) | — | Informative | Fill-in adoption artifacts, including a runnable layer-B generator. |
| [CHANGELOG](CHANGELOG.md) | — | — | Version history. |

## How to adopt

Read `SPEC.md` sections 4 through 11 (the seven rules and the conformance levels), then work through `TEMPLATES.md` T6, the adoption runbook. Level 1 (Mapped) took the reference implementation a day; expect days for larger codebases. It is a mapping exercise, not a refactor: measure the real import graph with the T5 generator, write the small intent map against the measurement, assign every component to a node, label the edges, and number the violations. The refactoring backlog falls out of the diff.

## Evidence and honest limits

Normative requirements carry inline evidence recitations naming the experiment and the measured result each obligation rests on. Requirements resting on reasoning rather than measurement are marked **design inference, not yet measured**, and say so in the same sentence that states the obligation.

Refutations are published at the same strength as confirmations. Rule 6 in particular records that derivation of exposure produced no significant completeness advantage in the controlled trial; the rule rests on measured propagation cost and on a failure-mode split, and 9.1.8 forbids citing that evidence as a completeness gain.

`RATIONALE.md` section 5 states what the evidence base does not establish. Citation confidence is marked per source: **[P]** primary source fetched and read directly, **[S]** secondary-mediated.

## Provenance

Espalier was authored by Yu-Chi TSOU (Liamour). It was forged in a production system built by the author directing AI agent sessions, and shaped by three research rounds against primary sources where reachable, with every citation carrying a confidence mark.

AI agent sessions were used throughout the drafting of these documents, under the author's direction and disclosed here as a matter of record. The design decisions, the rulings that settled them, and the ratification of every normative sentence are the author's.

## License

© 2026 Yu-Chi TSOU (Liamour).

The standards and all prose in this repository are licensed under the [Creative Commons Attribution 4.0 International License](LICENSE) (CC BY 4.0). You may share and adapt this material for any purpose, including commercially, provided you give appropriate credit to the author, link to the license, and indicate if changes were made.

The code sketches in `TEMPLATES.md` are additionally available under the [MIT License](LICENSE-CODE), so that they can be pasted into a codebase without carrying an attribution obligation into source files.

Patent and trademark rights are not licensed (CC BY 4.0 section 2(b)(2)).

## Citation

See [CITATION.cff](CITATION.cff). Cite by exact version; this is a Working Draft and may be updated, replaced, or obsoleted at any time.
