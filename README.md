# Espalier

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22075256.svg)](https://doi.org/10.5281/zenodo.22075256)

Espalier 是一层**衬底**,不是框架:一本 append-only 的账本,替你的 agent harness 记四笔账——

- **字节从哪来**:每个块带一个 `Origin`,两轴分开记"谁造的这些字节"与"从哪个口进来的";
- **发给谁看过**:每次模型调用落一份 `Manifest`(实发清单),精确到字节区间;
- **被什么盖掉**:压缩、替换、删除、折叠、排除,每一件都是账上的一条事件,不是消失;
- **地址与余量**:读了一半的文件、截断掉的工具结果,留 `ExternalAddress` 与 `Remainder`
  ——"余下那段在哪儿"是记录,不是猜。

记下的全是机械事实,按 id 取得回。循环、副作用、策略全在你手里。

## 它不做什么

- **不调模型、不调工具**。`served` / `returned` 只是调用前后的两笔账;中间那一步你自己做完,
  把结果交给库。`touched` / `Remainder.address` 只记地址,重读是 harness 的事。
- **除了自己的流水文件,不去世界里读任何东西**。环境依赖只有两处,都可以换成你自己的:
  事件时间戳用的时钟(`clock=`)与造 id 的 ULID 工厂(`ulids=`),`Ledger.create` / `open` / `fork` 都收。
- **不替你定策略**。压到多少、保留什么、要不要尊重某个字段——库给完整机制,阈值是你的事。
  `prune(Retention())` 给空策略剪掉的是零个块,不是全部。
- **不解释你放进 `annotations` 的约定值**。键名是文档约定,不是类型;想要闭词表自己校验。
- **`check_ledger` 只报不拦**。它返回一份报告,不抛异常,也不阻止任何写入。

## 安装

```sh
pip install -e .            # 或者不装:PYTHONPATH=src
```

Python ≥ 3.12,零依赖。三条版本线分开看:

| 线 | 现值 | 什么时候动 |
|---|---|---|
| 包版本 | `0.1.0` | 对外发包时才动,目前未发包 |
| git tag | `v1.3` | 里程碑;不保证每个 tag 都改了库 |
| 流水格式 `FORMAT_VERSION` | `5` | 落盘记录的键集或入哈希的瘦记录变了才动 |

旧格式的文件读回时报 `format_version_behind`,拒绝还是升级由 harness 决定。

## 五分钟心智模型

六个对象,认全就够开工了。

| 对象 | 它是什么 | 关键一点 |
|---|---|---|
| `Block` | 载荷 + 出身 + 注记 + 子块 / 引用 | 冻结值;改内容 = `replace` 一个新块 + 一条事件,旧块仍在账上;只改注记走 `annotate`(id 与 TreeHash 都不变) |
| `Origin` | 两轴:`made`(谁造的字节,十个变体)× `arrived`(从哪个口进来,九个通道) | `arrived` 没有默认值——真不知道要显式写 `Arrived.UNKNOWN`,那是证词不是省略 |
| `Ledger` | 只追加的事件流(十八种事件) | 删改也是事件;几乎所有查询都收 `at_seq` / `leaf`,问得出"那一刻是什么样" |
| `View` → `render` → `Rendering` | 视图 → 纯函数 → 文本 + `Manifest` | `render` 不落账;同一份视图换个规格再渲染一次,互不干扰 |
| `served` / `returned` | 一次模型调用的前后两笔 | 中间那步是你的;失败也该落一条 `Returned(outcome="error")`,别留没有回音的 `Called` |
| `retrieve` / `check_ledger` | 按 id 取回 / 给账本体检 | 两个都是纯查询:一个答"东西在哪",一个答"哪里说不通" |

一次模型调用的形状:

```
append ──► view ──► render ──► served ──► (你自己去调模型) ──► returned

  append    ledger.append(block)          落 Appended 事件
  view      ledger.view()                 纯值,不落账
  render    render(view, spec)            纯函数,给出文本 + Manifest,不落账
  served    ledger.served(rendering, …)   落 Called 事件,清单钉进账本
  (你的)    拿 rendering.text 去调模型     库不参与
  returned  ledger.returned(called, …)    落 Returned 事件,记用量 / 外部 id / 结果块
```

## 最小示例

建账本 → 追加两块 → 渲染一次 → `served` 落 `Called` → `manifest_of` 看模型见了什么 →
按 id 取回 → `check_ledger`。

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, BlockId, Injected, Ledger, LedgerHeader, LedgerId,
    Origin, RenderSpec, Uttered, check_ledger, is_ulid, render,
)

header = LedgerHeader(id=LedgerId("demo"), created_at=datetime(2026, 9, 8, tzinfo=timezone.utc))
with Ledger.create(None, header=header) as ledger:  # path=None 内存;给路径就写 JSONL 流水
    user = Block.create(
        "把 README 写短一点。", kind="message",
        origin=Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT),
    )
    hook = Block.create(
        "仓库约定:提交前先跑测试。", kind="attachment",
        origin=Origin(made=Injected(), arrived=Arrived.ATTACHMENT),  # Injected 是无字段标记
        annotations={"hook.injector": "before_prompt", "hook.blocking": "false"},
    )
    ledger.append(user)
    ledger.append(hook)

    rendering = render(ledger.view(), RenderSpec())               # 纯函数:文本 + 实发清单
    called = ledger.served(rendering, model="demo-model")         # 落 Called,清单钉进账本
    manifest = ledger.manifest_of(called.seq)                     # 模型这次看到了什么
    ids = [BlockId(e.source) for e in manifest.entries            # source 三型:BlockId / InlayKey / Absent
           if isinstance(e.source, str) and is_ulid(e.source)]
    got = ledger.retrieve(ids)                                    # 按 id 取回:present / lost / external / unknown
    assert [b.id for b in got.present] == [user.id, hook.id]
    assert got.present[1].annotations["hook.injector"] == "before_prompt"

    report = check_ledger(ledger)                                 # 纯查询,永不拦截
    assert report.ok, [f.rule for f in report]
```

## 我想做 X → 用什么

| 我想做 | 用什么 | 一句话 |
|---|---|---|
| 建账本 / 落盘 / 重开 | `Ledger.create` / `Ledger.open` / `load` | `path=None` 全在内存,给路径就每条事件一行 JSONL |
| 记一轮对话 | `Block.create` + `ledger.append` | 用户说的、模型吐的、工具还的,各写各的 `Origin` |
| 记一次模型调用 | `render` → `ledger.served` → `ledger.returned` | 库只记前后两笔,中间那步你自己调模型 |
| 问"模型那次看到了什么" | `ledger.manifest_of` / `ledger.saw` | CallHash / ManifestHash / Seq 三把键取回同一份清单 |
| 问"这块被哪几次调用发出去过" | `ledger.calls_showing` | 给 `Seq` 元组,没命中给空元组,不抛 |
| 核对"回话与当时实发对得上吗" | `ledger.verify` | 四值判决 `Verified` / `Stale` / `Mismatch` / `Unverifiable` |
| 控制这次发什么 | `RenderSpec` 的 `exclude` / `fold` / `absent` / `inlays` / `ids` / `fence` | 策略你定,库按规格渲染并把决定记进清单 |
| 压缩上下文 | `ledger.prepare_compact` → `ledger.commit_with_receipt` | 两段式:先定影再落账,中间隔多久都行 |
| 删 / 改 / 合 / 撤销 | `remove` / `replace` / `merge` / `restore` / `prune` / `revoke` | 全是事件;`supersedes` 问"这块顶掉了谁" |
| 把一轮包成一个块 | `ledger.open_composite` → `close` | id 开那一刻就分配,轮没结束也渲染得出来 |
| 开子账本 / 记检查点 / 记续接 | `ledger.fork` / `checkpoint` / `resumed` | fork 重放父账本前缀;续接要自己记,`open()` 不自动写 |
| 存会话级配置 | `ledger.configure` / `ledger.setting(name, at_seq=…)` | 值是纯字符串,末条生效,可按任意时刻求值 |
| 解析技能 / 记忆这类 Markdown 文件 | `parse_tree` / `render_authoring` / `frontmatter_entries` | 往返按规范形 `c1` 逐字节成立,不是与原始文本逐字相等 |
| 按形状读技能 / 记忆 / 工具结果 | `Skill` / `Memory` / `ToolResult` / `SkillFlow` | `.of` 不合形就抛,`.check` 不抛只报,两者判定一致 |
| 大载荷不进账本 | `Text.of(ref)` / `Blob` / `MemoryContentStore` | 字节进 CAS 或留外部地址,块上只留引用 |
| 按 id 把信息取回来 | `ledger.retrieve(ids)` | 四桶 present / lost / external / unknown,"没听说过"不冒充"丢了" |
| 给账本做体检 | `check_ledger`(= `ledger.check()`) | `.ok` 只看 error 级;warning 是事实陈述,不改变 `.ok` |
| 自己重算哈希做独立校验 | `espalier.expert` 的 `chain_hash` / `seal` / `state_hash` | 逐事件重放链比对 `.link`,不必信任账本自己的记账 |

下面六段是最常用的配方,都能直接跑。

### 记一轮带工具调用的对话

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, FileAddress, Ledger, LedgerHeader, LedgerId, Origin,
    Remainder, ToolReturned, Uttered, tool_call_hash,
)

led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("turn"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
led.append(Block.create("列一下 src/ 下的文件。", kind="message",
                        origin=Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)))
# 模型的回话不在这一段记:自己循环里调的模型,回话块要写 LlmDerived(call=called.call, …)
# 绑住那次调用,见下一段。(摄入别家 harness 的转录、手上没有当时的实发清单时,才用
# Uttered(role="model")——那个变体说的是"另一本账的模型"。)

# 工具结果被截断:手上这段在账上,余下那段留个地址等人去重读(库自己不去读)
where = FileAddress(path="src/espalier", offset=0, limit=5, total=18, unit="line", base=0)
result = Block.create(
    "block.py\ncalls.py\ncheck.py\ncodec.py\ncompact.py\n...(还有 13 个)",
    kind="tool_result",
    origin=Origin(
        made=ToolReturned(
            call=tool_call_hash("Read", {"path": "src/espalier"}),
            tool="Read",
            touched=(where,),                       # 这次工具碰了世界的哪里
            remainder=Remainder(address=where, have=((0, 5),), total=18,
                                unit="line", hit=frozenset({"limit"})),
        ),
        arrived=Arrived.TOOL_RESULT_SLOT,
    ),
)
led.append(result)

got = led.retrieve([result.id])
assert [b.id for b in got.present] == [result.id]
assert got.external == ((result.id, where),)        # 余下那段的地址,按 id 问得出来
```

`Remainder.unit` 只收 `str`,`None` 会抛 `ValueError`:真不知道单位就别构造它,
库不会替你编一个。`touched`(碰了世界的哪里)与 `remainder.address`(截断掉的那段去哪儿重读)
是两个槽,可以只有一个。

### 调模型一次的前后

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, LlmDerived, Origin,
    RenderSpec, Uttered, Verified, render,
)

led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("call"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
led.append(Block.create("2+2 等于几?", kind="message",
                        origin=Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)))

rendering = render(led.view(), RenderSpec())                  # 发出去的文本 + 实发清单
called = led.served(rendering, model="m1", params={"temperature": 0})

# ——这一步 harness 自己拿 rendering.text 去调模型,库不参与——
reply = led.append(Block.create(
    "4", kind="text",
    origin=Origin(made=LlmDerived(call=called.call, model=called.model),
                  arrived=Arrived.ASSISTANT_SLOT),   # 这一笔要自己写,库不替你打标记
)).block_value
returned = led.returned(called, outcome="ok", output=reply.id,
                        usage={"input": 12, "output": 1},
                        external_ids={"request_id": "req-42"})

assert led.manifest_of(called.call) == rendering.manifest   # CallHash / ManifestHash / Seq 同一份清单
assert returned.usage == {"input": 12, "output": 1}         # 用量只落 Returned:不进 CallHash,但随记录入审计链
assert isinstance(led.verify(reply.id), Verified)           # 回话块与当时的实发对得上
```

回话块要日后"可验证",`origin.made` 必须自己写成 `LlmDerived(call=called.call, …)`——
库不会替你打这个标记。

### 事后追问

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, LlmDerived, Origin,
    Stale, Unverifiable, Uttered, render,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("audit"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
first = led.append(Block.create("排期定在周四。", kind="text", origin=USER)).block_value
rendering = render(led.view())
called = led.served(rendering, model="m1")
reply = led.append(Block.create(
    "记下了。", kind="text",
    origin=Origin(made=LlmDerived(call=called.call, model="m1"), arrived=Arrived.ASSISTANT_SLOT),
)).block_value

# 往回问:这块的作者当时看到了什么
assert led.saw(reply.id) == rendering.manifest
assert led.saw(first.id) is None                       # 出身不是 LlmDerived ⇒ 这问题对它无意义
# 往前问:哪些调用把这块发出去过
assert led.calls_showing(first.id) == (called.seq,)

# 来源后来被改了 ⇒ Stale(四值判决之一,另三值:Verified / Mismatch / Unverifiable)
led.replace(first.id, Block.create("排期改到周五。", kind="text", origin=USER))
verdict = led.verify(reply.id)
assert isinstance(verdict, Stale) and verdict.changed == (first.id,)
assert isinstance(led.verify(first.id), Unverifiable)
assert led.get_block(first.id).payload.body == "排期定在周四。"   # 旧块仍在账上取得回
```

`Stale`(来源被替换 / 删除,账本往前走了)与 `Mismatch`(记录自相矛盾)是两种不同的"有问题",
判据不同;`Unverifiable` 只说"这个问题在这里问不出答案",不是出错。

### 渲染控制:排除 / 折叠 / absent

```python
from datetime import datetime, timezone

from espalier import (
    Absent, Arrived, Block, Ledger, LedgerHeader, LedgerId, Origin,
    RenderSpec, Uttered, render,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("render"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
kept = led.append(Block.create("正文", kind="text", origin=USER)).block_value
secret = led.append(Block.create("内心独白", kind="thinking", origin=USER)).block_value
long_leaf = led.append(Block.create("很长的一段\n第二行", kind="text", origin=USER)).block_value
comp = led.open_composite(kind="turn", origin=USER)
comp.append(Block.create("轮内容", kind="text", origin=USER))
comp.close()

spec = RenderSpec(
    exclude_why={secret.id: "thinking 块,不发给模型"},        # 排除,并记下理由
    fold=frozenset({long_leaf.id, comp.id}),                   # 折叠成一行摘要
    absent=((kept.id, Absent(reason="附件在转录里丢了")),),    # 发出去了、但账本上没有
)
rendering = render(led.view(), spec)

assert "内心独白" not in rendering.text
assert rendering.manifest.excluded_why == {secret.id: "thinking 块,不发给模型"}
assert long_leaf.id in rendering.manifest.expandable()         # 折叠成功的才进这个集合
# 怎么知道"请求折叠但没折成":差集非空。只有运行面的叶块吃 fold;复合块与编写面的块都不吃,也不报错。
assert frozenset(spec.fold) - rendering.manifest.expandable() == {comp.id}
assert any(isinstance(e.source, Absent) for e in rendering.manifest.entries)
```

排除有两个入口——视图层的 `View.without_` 与规格层的 `RenderSpec.exclude` / `exclude_why`
——render 把它们合成一个集合再渲染,不会出现"清单说排除了、字节却发了出去"。

### 压缩两段式

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, LlmDerived, Origin, RenderSpec, Uttered,
    render,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("compact"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
first = led.append(Block.create("第一条很长的消息", kind="text", origin=USER)).block_value
second = led.append(Block.create("第二条很长的消息", kind="text", origin=USER)).block_value

# 第一段:纯读、零事件。定影"压哪些块"与"要发给模型的 prompt",隔几分钟再 commit 也行。
req = led.prepare_compact([first.id, second.id])
assert req.targets == (first.id, second.id) and isinstance(req.prompt, str)

# ——harness 拿 req.prompt 自己调模型,拿回摘要文本——
# 第二段:一次落四条事件(Called / Appended / Returned / Compacted)。
receipt = led.commit_with_receipt(
    req, "用户发了两条长消息,都在谈排期。", model="m1",
    usage={"input_tokens": 120, "output_tokens": 12},
)
assert receipt.targets_match and receipt.conflicts == ()      # 两段之间没有新块写进来
assert receipt.summary.origin.made == LlmDerived(
    call=receipt.called.call, model="m1", sources=(first.id, second.id))
assert dict(receipt.returned.usage) == {"input_tokens": 120, "output_tokens": 12}
assert led.get_block(first.id).payload.body == "第一条很长的消息"   # 被压掉的块仍在账上

# 压缩不是替换:默认视图里被压块照样在、摘要排在最末。下次渲染要自己把被压块排除掉。
assert led.view().block_ids() == (first.id, second.id, receipt.summary.id)
spec = RenderSpec(exclude_why={block_id: "已压缩" for block_id in req.targets})
text = render(led.view(), spec).text
assert "第一条很长的消息" not in text and "都在谈排期" in text
```

`prepare_compact` 与 `commit` 之间账本照常能写;新写进来的块不在覆盖范围里,
`CommitReceipt.conflicts` 会把它们点名。`ledger.commit()` 是同一条实现,只是不给回执。

压缩路径上最先撞到的三件事:**压缩不是替换**(上面最后几行;重开账本后"盖掉了谁"从
`ledger.compactions()` 读);带 `instruction=` 时**指令块必须先 `append`**,否则摘要块的血缘边悬空、
`check` 报 error;拿**复合块**当压缩目标时 `targets_match` 恒为 `False`——那是预期(等式按 id 做差,
嵌套子块全算进去),库会把目标显式记在 `Compacted.targets` 里。`Compacted.targets` 为 `None` 表示
等式成立,"盖掉了谁"按定义重算:`base_seq` 那一刻在场、seq 落在 `covers` 内、再减去 `kept` 的块。

### 落盘与重开

```python
from datetime import datetime, timezone
from pathlib import Path

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, Origin, Uttered, load,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
path = Path("session.jsonl")

led = Ledger.create(path, header=LedgerHeader(         # 给路径 = track:每条事件一行 JSONL
    id=LedgerId("sess"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)), fsync=False)
note = led.append(Block.create("接着上次说。", kind="message", origin=USER)).block_value
led.close()

report = load(path)                                    # 格式类问题不抛,诊断全在报告里
assert report.ok and report.errors == ()

again = Ledger.open(path)                              # 默认 strict=True:致命诊断抛 LoadError
assert again.block_ids() == (note.id,)
assert again.get_block(note.id).payload.body == "接着上次说。"
resumed = again.resumed()                              # "会话从这里续上"要自己记,库不自动写
assert resumed.tip_before == again.tip - 1
again.close()
```

内存模式与落盘模式是同一套 API,同一份记录之上行为相同——开发时用 `None`,
上线时给路径,代码不用分叉。`Ledger.create` 不覆盖已存在的非空账本(抛 `FileExistsError`)。
`load` 不抛的是**格式类**问题(坏 JSON、半截尾行——包括崩溃时撕在一个多字节字符中间的尾行、
版本不对……都进 `LoadReport`);文件不存在这类 IO 异常照常抛,自己在外面接。

## 信息放哪:类型化字段还是 `annotations`

一句话规则:**库自己要解释的信息才有字段,其余走 `annotations`**。`annotations` 的键名是
文档约定不是类型,库存着它、带着它、不解释它——想要闭词表,自己校验。

举个真实的例子:模型厂商回给你的 usage 里,有些分项是整数,有些不是。整数分项展平进
`Returned.usage`(它的类型就是 `Mapping[str, int]`),其余的落进那次响应的 `annotations`
——信息一处不丢,库也不必为每家厂商的记录形状各长一个字段。

hook 的六件事实走同一条路。`Injected` 是无字段的标记变体(它的类型仍决定信任档 THIRD_PARTY),
六件事实记在持有者(块或事件)的 `annotations` 上:

| 键 | 值 |
|---|---|
| `hook.injector` | 哪个 hook / 事件名注入的 |
| `hook.configured_by` | 由谁配置(user / project / plugin / …,harness 原词,开域) |
| `hook.blocking` | `"true"` / `"false"`;缺键 = 记录未说 |
| `hook.decision` | harness 原词(deny / block / ask / allow / continue:false / …) |
| `hook.decision_scope` | call / turn / task / session … |
| `hook.decision_reason` | 原因原文 |

旧记录(v0.18–v0.21)把这六件事实写成 `Injected` 的类型字段,读回时库会把它们搬进
`annotations`(同名键已存在则不覆盖),一个字节不丢。

### `None` 的读法

**"记录未说"与"已知为空"不是一回事**,库在类型上把它们分开了。`Transformed.sources` 是三值:
`None` = 这份记录没说来源,`()` = 说了、来源就是空的,非空元组 = 构成关系。`origin_sources`
对前两者都不出边,但那是两个不同的事实——要分辨得看字段本身,不能看"有没有边"。

同一把尺子在别处也成立:`Remainder` 这一格的 `None` 由持有者决定读什么——挂在 `ToolReturned` /
`Parsed` / `Recalled` 上读"未截断",挂在 `LlmDerived` 上读"没有证词"(模型轴上 stop_reason
常在手,没记下不等于没截断)。写通用代码扫各变体的 `remainder` 槽时,别把两种读法合并。

## 库的承诺

1. **不丢、不编造**(A9)。旧记录读回一个字节不丢;记录没说的就是 `None` / 缺键,库不补默认值,
   也不把"没听说过这个 id"塞进"它丢了"那一桶。
2. **机制不塞策略**(A0)。默认**值**可以有,默认**动作**不可以有:`check_ledger` 只报不拦,
   `render` 是纯函数,空的保留策略剪掉零个块。
3. **库不调模型、不调工具**(A8)。它在调用前备料、调用后记账;一切副作用由你执行。
4. **字段只为库要解释的信息而设**(A10)。库有函数读的字段不退注记;其余的走 `annotations`,
   库存它带它不解释它。
5. **无损保底是构造保证**(A5)。解析器不认识的结构原样包成 opaque 块,不靠解析器聪明。

库的 docstring 里出现的 A0 / A5 / A8 / A9 / A10,指的就是这五条。

## 三层导入

公开面分三层:

| 层 | 导入 | 名 | 给谁 |
|---|---|---|---|
| lite | `from espalier import Ledger, Block, render, …` | 175 | 日常所需:账本、块、出身、事件、渲染、清单、取回、检查 |
| expert | `from espalier.expert import Lens, Shape, chain_hash, seal, …` | 29 | 透镜扩展点;写验证器 / 取回工具的作者用的哈希与流水函数 |
| internal | `espalier.hashes.BYTES_HASH_PREFIX`、`espalier.persist.event_line`、… | 41 | 只经模块路径;前缀常量、行级编解码、ULID 内部 |

九个 `Ledger` 方法(`served` / `returned` / `manifest_of` / `saw` / `verify` / `calls_showing` /
`prepare_compact` / `commit` / `commit_with_receipt`)是方法不是名字,不在 `__all__` 里——
公开 API 是 `ledger.served(…)` 那一形。

## 规范、许可与作者

- `spec/` 是这套方法的规范文本(规则、证据、模板);本库是它在 agent 上下文账本上的实现。
- 许可:本库(`src/`、本 README、`pyproject.toml`)以 MIT 许可发布,见 `LICENSE-CODE`;`spec/` 下的文档以 CC BY 4.0 发布,见 `LICENSE`。
- 引用:DOI [10.5281/zenodo.22075256](https://doi.org/10.5281/zenodo.22075256)(见 `CITATION.cff`)。
- 作者:Yu-Chi TSOU (Liamour)。
