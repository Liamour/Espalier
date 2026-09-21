# Espalier

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22075256.svg)](https://doi.org/10.5281/zenodo.22075256)

[English](README.md) | 中文

Espalier 是给自己搭 agent harness 的开发者用的 Python 库。它是一层衬底,不是框架:一本只追加的账本,替 harness 记下四类信息。

- 字节从哪来:每个块带一个 `Origin`,分两轴记录"谁造的这些字节"和"从哪个口进来的"。
- 发给谁看过:每次模型调用记一份 `Manifest`(实发清单),精确到字节区间。
- 被什么盖掉:压缩、替换、删除、折叠、排除,每一件都在账上留一条事件。
- 地址与余量:文件只读了一半、工具结果被截断时,用 `ExternalAddress` 和 `Remainder` 记下余下那段在哪儿。

这些都是机械记录的事实,可以按 id 取回。循环、副作用和策略由你的 harness 负责。

## 它不做什么

- 不调模型,不调工具。`served` / `returned` 只记调用前后的两笔,中间那一步你自己做完,再把结果交给库。`touched` / `Remainder.address` 只记地址,重读由 harness 做。
- 除了自己的流水文件,不读外部的任何东西。环境依赖只有两处,都可以换成你自己的:事件时间戳用的时钟(`clock=`)和造 id 的 ULID 工厂(`ulids=`),`Ledger.create` / `open` / `fork` 都接受这两个参数。
- 不替你定策略。压到多少、保留什么、要不要尊重某个字段,库只给机制,阈值由你定。`prune(Retention())` 传空策略时一个块都不剪。
- 不解释你放进 `annotations` 的值。键名只是文档约定,库不校验;想要闭词表,自己校验。
- `check_ledger` 只报告,不拦截。它返回一份报告,不抛异常,也不阻止任何写入。

## 安装

```sh
pip install -e .            # 或者不装:PYTHONPATH=src
```

Python ≥ 3.12,零依赖。有三个版本号,各管各的:

| 线 | 现值 | 什么时候动 |
|---|---|---|
| 包版本 | `0.1.0` | 对外发包时才动,目前未发包 |
| git tag | `v1.3.1` | 里程碑;不保证每个 tag 都改了库 |
| 流水格式 `FORMAT_VERSION` | `5` | 落盘记录的键集或入哈希的瘦记录变了才动 |

旧格式的文件读回时报 `format_version_behind`,拒绝还是升级由 harness 决定。

## 核心对象

先认这六个对象。

| 对象 | 它是什么 | 要点 |
|---|---|---|
| `Block` | 载荷 + 出身 + 注记 + 子块 / 引用 | 冻结值。改内容用 `replace`:写一个新块加一条事件,旧块仍在账上。只改注记用 `annotate`,id 与 TreeHash 都不变 |
| `Origin` | 两轴:`made`(谁造的字节,十个变体)× `arrived`(从哪个口进来,九个通道) | `arrived` 没有默认值,不知道就显式写 `Arrived.UNKNOWN` |
| `Ledger` | 只追加的事件流(十八种事件) | 删改也是事件;几乎所有查询都接受 `at_seq` / `leaf`,可以查"那一刻是什么样" |
| `View` → `render` → `Rendering` | 视图 → 纯函数 → 文本 + `Manifest` | `render` 不写账本;同一份视图换个规格再渲染一次,互不影响 |
| `served` / `returned` | 一次模型调用的前后两笔 | 中间那步由你做;调用失败也要写一条 `Returned(outcome="error")`,否则分不清"失败了"和"还没回来" |
| `retrieve` / `check_ledger` | 按 id 取回 / 给账本体检 | 都是纯查询:前者回答"东西在哪",后者回答"哪里对不上" |

一次模型调用的流程:

```
append ──► view ──► render ──► served ──► (你自己去调模型) ──► returned

  append    ledger.append(block)          写一条 Appended 事件
  view      ledger.view()                 纯值,不写账本
  render    render(view, spec)            纯函数,给出文本 + Manifest,不写账本
  served    ledger.served(rendering, …)   写一条 Called 事件,清单随事件记进账本
  (你的)    拿 rendering.text 去调模型     库不参与
  returned  ledger.returned(called, …)    写一条 Returned 事件,记用量 / 外部 id / 结果块
```

## 最小示例

建账本,追加两块,渲染一次,用 `served` 记下这次调用,用 `manifest_of` 看模型见了什么,按 id 取回,最后跑 `check_ledger`。

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, BlockId, Injected, Ledger, LedgerHeader, LedgerId,
    Origin, RenderSpec, Uttered, check_ledger, is_ulid, render,
)

header = LedgerHeader(id=LedgerId("demo"), created_at=datetime(2026, 9, 8, tzinfo=timezone.utc))
with Ledger.create(None, header=header) as ledger:  # path=None 在内存里;给路径就写 JSONL 流水
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
    called = ledger.served(rendering, model="demo-model")         # 写一条 Called,清单随事件记进账本
    manifest = ledger.manifest_of(called.seq)                     # 模型这次看到了什么
    ids = [BlockId(e.source) for e in manifest.entries            # source 三型:BlockId / InlayKey / Absent
           if isinstance(e.source, str) and is_ulid(e.source)]
    got = ledger.retrieve(ids)                                    # 按 id 取回:present / lost / external / unknown
    assert [b.id for b in got.present] == [user.id, hook.id]
    assert got.present[1].annotations["hook.injector"] == "before_prompt"

    report = check_ledger(ledger)                                 # 纯查询,只报告不拦截
    assert report.ok, [f.rule for f in report]
```

## 我想做 X,用什么

| 我想做 | 用什么 | 说明 |
|---|---|---|
| 建账本 / 落盘 / 重开 | `Ledger.create` / `Ledger.open` / `load` | `path=None` 全在内存,给路径就每条事件写一行 JSONL |
| 记一轮对话 | `Block.create` + `ledger.append` | 用户说的、模型回的、工具返回的,各写各的 `Origin` |
| 记一次模型调用 | `render` → `ledger.served` → `ledger.returned` | 库只记前后两笔,中间那步你自己调模型 |
| 查"模型那次看到了什么" | `ledger.manifest_of` / `ledger.saw` | 用 CallHash、ManifestHash 或 Seq 都能取回同一份清单 |
| 查"这块被哪几次调用发出去过" | `ledger.calls_showing` | 返回 `Seq` 元组,没命中返回空元组,不抛 |
| 核对"回话与当时实发对得上吗" | `ledger.verify` | 四种判决:`Verified` / `Stale` / `Mismatch` / `Unverifiable` |
| 控制这次发什么 | `RenderSpec` 的 `exclude` / `fold` / `absent` / `inlays` / `ids` / `fence` | 策略你定,库按规格渲染,并把这些决定记进清单 |
| 压缩上下文 | `ledger.prepare_compact` → `ledger.commit_with_receipt` | 分两段:先定下要压什么,再写账本,中间隔多久都行 |
| 删 / 改 / 合 / 撤销 | `remove` / `replace` / `merge` / `restore` / `prune` / `revoke` | 全是事件;`supersedes` 查"这块顶掉了谁" |
| 把一轮包成一个块 | `ledger.open_composite` → `close` | 开的时候就分配 id,这一轮没结束也能渲染 |
| 开子账本 / 记检查点 / 记续接 | `ledger.fork` / `checkpoint` / `resumed` | fork 重放父账本的前缀;续接要自己记,`open()` 不自动写 |
| 存会话级配置 | `ledger.configure` / `ledger.setting(name, at_seq=…)` | 值是纯字符串,最后一条生效,可以按任意时刻求值 |
| 解析技能 / 记忆这类 Markdown 文件 | `parse_tree` / `render_authoring` / `frontmatter_entries` | 往返按规范形 `c1` 逐字节成立,与原始文本不一定逐字相等 |
| 按形状读技能 / 记忆 / 工具结果 | `Skill` / `Memory` / `ToolResult` / `SkillFlow` | `.of` 不合形就抛,`.check` 不抛只报告,两者判定一致 |
| 大载荷不进账本 | `Text.of(ref)` / `Blob` / `MemoryContentStore` | 字节进 CAS 或留在外部地址,块上只留引用 |
| 按 id 把信息取回来 | `ledger.retrieve(ids)` | 分四类:present / lost / external / unknown;没见过的 id 归 unknown,不会算成 lost |
| 给账本做体检 | `check_ledger`(= `ledger.check()`) | `.ok` 只看 error 级;warning 只陈述事实,不影响 `.ok` |
| 自己重算哈希做独立校验 | `espalier.expert` 的 `chain_hash` / `seal` / `state_hash` | 逐事件重放链、比对 `.link`,不用信任账本自己记的值 |

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
# 模型的回话不在这一段记。自己循环里调的模型,回话块要写 LlmDerived(call=called.call, …),
# 绑定那次调用,见下一段。摄入别家 harness 的转录、手上没有当时的实发清单时,才用
# Uttered(role="model"),那个变体指的是"另一本账的模型"。

# 工具结果被截断:手上这段在账上,余下那段留一个地址,之后由 harness 去重读
where = FileAddress(path="src/espalier", offset=0, limit=5, total=18, unit="line", base=0)
result = Block.create(
    "block.py\ncalls.py\ncheck.py\ncodec.py\ncompact.py\n...(还有 13 个)",
    kind="tool_result",
    origin=Origin(
        made=ToolReturned(
            call=tool_call_hash("Read", {"path": "src/espalier"}),
            tool="Read",
            touched=(where,),                       # 这次工具读写了外部的哪里
            remainder=Remainder(address=where, have=((0, 5),), total=18,
                                unit="line", hit=frozenset({"limit"})),
        ),
        arrived=Arrived.TOOL_RESULT_SLOT,
    ),
)
led.append(result)

got = led.retrieve([result.id])
assert [b.id for b in got.present] == [result.id]
assert got.external == ((result.id, where),)        # 余下那段的地址,按 id 查得到
```

`Remainder.unit` 只接受 `str`,传 `None` 会抛 `ValueError`。不知道单位就不要构造 `Remainder`,库不会替你填一个。`touched`(这次工具读写了外部的哪里)和 `remainder.address`(被截断的那段去哪儿重读)是两个槽,可以只填一个。

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

# 这一步由 harness 自己拿 rendering.text 去调模型,库不参与
reply = led.append(Block.create(
    "4", kind="text",
    origin=Origin(made=LlmDerived(call=called.call, model=called.model),
                  arrived=Arrived.ASSISTANT_SLOT),   # 这个出身要自己写,库不会替你标
)).block_value
returned = led.returned(called, outcome="ok", output=reply.id,
                        usage={"input": 12, "output": 1},
                        external_ids={"request_id": "req-42"})

assert led.manifest_of(called.call) == rendering.manifest   # CallHash / ManifestHash / Seq 取回同一份清单
assert returned.usage == {"input": 12, "output": 1}         # 用量只记在 Returned 上:不进 CallHash,但随记录入审计链
assert isinstance(led.verify(reply.id), Verified)           # 回话块与当时的实发对得上
```

回话块以后要能验证,`origin.made` 必须由你写成 `LlmDerived(call=called.call, …)`,库不会替你标。

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

# 往回查:产出这块的那次调用当时看到了什么
assert led.saw(reply.id) == rendering.manifest
assert led.saw(first.id) is None                       # 出身不是 LlmDerived,这个问题对它不适用
# 往前查:哪些调用把这块发出去过
assert led.calls_showing(first.id) == (called.seq,)

# 来源后来被改了,判 Stale(四种判决之一,另三种:Verified / Mismatch / Unverifiable)
led.replace(first.id, Block.create("排期改到周五。", kind="text", origin=USER))
verdict = led.verify(reply.id)
assert isinstance(verdict, Stale) and verdict.changed == (first.id,)
assert isinstance(led.verify(first.id), Unverifiable)
assert led.get_block(first.id).payload.body == "排期定在周四。"   # 旧块仍在账上,取得回
```

`Stale` 表示来源后来被替换或删除了;`Mismatch` 表示记录自相矛盾。两者判据不同。`Unverifiable` 只表示这个问题在这里查不出答案。

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
# 请求了折叠但没折成的,用差集查。fold 只对运行面的叶块生效;复合块和编写面的块不折叠,也不报错。
assert frozenset(spec.fold) - rendering.manifest.expandable() == {comp.id}
assert any(isinstance(e.source, Absent) for e in rendering.manifest.entries)
```

排除有两个入口:视图层的 `View.without_`,规格层的 `RenderSpec.exclude` / `exclude_why`。`render` 先把它们合成一个集合再渲染,所以清单上写着排除的块,字节一定没发出去。

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

# 第一段:只读,不写事件。定下"压哪些块"和"要发给模型的 prompt",隔几分钟再 commit 也行。
req = led.prepare_compact([first.id, second.id])
assert req.targets == (first.id, second.id) and isinstance(req.prompt, str)

# 这里由 harness 拿 req.prompt 自己调模型,拿回摘要文本
# 第二段:一次写四条事件(Called / Appended / Returned / Compacted)。
receipt = led.commit_with_receipt(
    req, "用户发了两条长消息,都在谈排期。", model="m1",
    usage={"input_tokens": 120, "output_tokens": 12},
)
assert receipt.targets_match and receipt.conflicts == ()      # 两段之间没有新块写进来
assert receipt.summary.origin.made == LlmDerived(
    call=receipt.called.call, model="m1", sources=(first.id, second.id))
assert dict(receipt.returned.usage) == {"input_tokens": 120, "output_tokens": 12}
assert led.get_block(first.id).payload.body == "第一条很长的消息"   # 被压掉的块仍在账上

# 压缩不会替换原块:默认视图里被压的块还在,摘要排在最末。下次渲染要自己把被压的块排除掉。
assert led.view().block_ids() == (first.id, second.id, receipt.summary.id)
spec = RenderSpec(exclude_why={block_id: "已压缩" for block_id in req.targets})
text = render(led.view(), spec).text
assert "第一条很长的消息" not in text and "都在谈排期" in text
```

`prepare_compact` 和 `commit` 之间账本照常能写。这期间新写进来的块不在覆盖范围里,`CommitReceipt.conflicts` 会把它们列出来。`ledger.commit()` 是同一套实现,只是不返回回执。

用压缩时先知道三件事:

1. 压缩不会替换原块(见上面代码的最后几行)。重开账本后,"这次压缩盖掉了谁"从 `ledger.compactions()` 读。
2. 传 `instruction=` 时,指令块必须先 `append`。否则摘要块的血缘边指向一个不在账上的块,`check` 会报 error。
3. 拿复合块当压缩目标时,`targets_match` 恒为 `False`。这是预期行为:等式按 id 做差,嵌套的子块都会算进去。这种情况下库会把目标显式记在 `Compacted.targets` 里。`Compacted.targets` 为 `None` 表示等式成立,"盖掉了谁"按定义重算:`base_seq` 那一刻在场、seq 在 `covers` 内、再减去 `kept` 的块。

### 落盘与重开

```python
from datetime import datetime, timezone
from pathlib import Path

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, Origin, Uttered, load,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
path = Path("session.jsonl")

led = Ledger.create(path, header=LedgerHeader(         # 给路径就落盘:每条事件一行 JSONL
    id=LedgerId("sess"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)), fsync=False)
note = led.append(Block.create("接着上次说。", kind="message", origin=USER)).block_value
led.close()

report = load(path)                                    # 格式类问题不抛,诊断都在报告里
assert report.ok and report.errors == ()

again = Ledger.open(path)                              # 默认 strict=True:有致命诊断就抛 LoadError
assert again.block_ids() == (note.id,)
assert again.get_block(note.id).payload.body == "接着上次说。"
resumed = again.resumed()                              # "会话从这里续上"要自己记,库不自动写
assert resumed.tip_before == again.tip - 1
again.close()
```

内存模式和落盘模式用同一套 API,在同一份记录上行为相同。开发时传 `None`,上线时传路径,代码不用改。`Ledger.create` 不覆盖已存在的非空账本,会抛 `FileExistsError`。

`load` 对格式类问题不抛异常,都写进 `LoadReport`:坏 JSON、版本不对、半截尾行(包括崩溃时从一个多字节字符中间断开的尾行)。文件不存在这类 IO 异常照常抛出,由调用方处理。

## 信息放哪:类型化字段还是 `annotations`

规则:库自己要解释的信息才有字段,其余放 `annotations`。`annotations` 的键名只是文档约定,库只存储和携带这些值,不解释;想要闭词表,自己校验。

例如模型厂商返回的 usage 里,有的分项是整数,有的不是。整数分项展平后放进 `Returned.usage`(类型是 `Mapping[str, int]`),其余的放进那次响应的 `annotations`。信息都在,库也不用为每家厂商的记录形状各加一个字段。

hook 的六项信息也这样处理。`Injected` 是无字段的标记变体(它的类型仍决定信任档 THIRD_PARTY),六项信息记在持有者(块或事件)的 `annotations` 上:

| 键 | 值 |
|---|---|
| `hook.injector` | 哪个 hook / 事件名注入的 |
| `hook.configured_by` | 由谁配置(user / project / plugin / …,harness 原词,开域) |
| `hook.blocking` | `"true"` / `"false"`;缺键 = 记录未说 |
| `hook.decision` | harness 原词(deny / block / ask / allow / continue:false / …) |
| `hook.decision_scope` | call / turn / task / session … |
| `hook.decision_reason` | 原因原文 |

旧记录(v0.18–v0.21)把这六项写成 `Injected` 的类型字段。读回时库会把它们移进 `annotations`(同名键已存在则不覆盖),一个字节不丢。

### `None` 的读法

库把"记录未说"和"已知为空"分开记。`Transformed.sources` 有三种取值:`None` 表示这份记录没说来源;`()` 表示说了,来源就是空的;非空元组表示构成关系。`origin_sources` 对前两种都不出边,所以要区分它们得看字段本身,只看有没有边分不出来。

`Remainder` 这一格的 `None` 由持有它的变体决定怎么读。在 `ToolReturned` / `Parsed` / `Recalled` 上读作"未截断";在 `LlmDerived` 上读作"没有证词",因为模型一侧通常拿得到 stop_reason,没记下来不代表没截断。写通用代码遍历各变体的 `remainder` 槽时,这两种读法要分开处理。

## 库的承诺

1. **不丢、不编造**(A9)。旧记录读回一个字节不丢。记录没说的就是 `None` 或缺键,库不补默认值。没见过的 id 归 unknown,不会算成 lost。
2. **机制不塞策略**(A0)。可以有默认值,不能有默认动作:`check_ledger` 只报告不拦截,`render` 是纯函数,空的保留策略一个块都不剪。
3. **库不调模型、不调工具**(A8)。它在调用前准备要发的内容,调用后记账;一切副作用由你执行。
4. **字段只给库要解释的信息**(A10)。库里有函数读取的字段不会退成注记;其余信息放 `annotations`,库只存储和携带,不解释。
5. **无损保底由构造保证**(A5)。解析器不认识的结构原样包成 opaque 块,不依赖解析器的识别能力。

库的 docstring 里出现的 A0 / A5 / A8 / A9 / A10,指的就是这五条。

## 三层导入

公开面分三层:

| 层 | 导入 | 名 | 给谁 |
|---|---|---|---|
| lite | `from espalier import Ledger, Block, render, …` | 175 | 日常所需:账本、块、出身、事件、渲染、清单、取回、检查 |
| expert | `from espalier.expert import Lens, Shape, chain_hash, seal, …` | 29 | 透镜扩展点;写验证器 / 取回工具的作者用的哈希与流水函数 |
| internal | `espalier.hashes.BYTES_HASH_PREFIX`、`espalier.persist.event_line`、… | 41 | 只经模块路径访问:前缀常量、行级编解码、ULID 内部工具 |

另有九个公开 API 是 `Ledger` 的方法:`served` / `returned` / `manifest_of` / `saw` / `verify` / `calls_showing` / `prepare_compact` / `commit` / `commit_with_receipt`。它们不是可导入的名字,所以不在 `__all__` 里,用法是 `ledger.served(…)`。

## 规范、许可与作者

- `spec/` 是这套方法的规范文本(规则、证据、模板);本库是它在 agent 上下文账本上的实现。
- 许可:本库(`src/`、两份 README、`pyproject.toml`)以 MIT 许可发布,见 `LICENSE-CODE`;`spec/` 下的文档以 CC BY 4.0 发布,见 `LICENSE`。
- 引用:DOI [10.5281/zenodo.22075256](https://doi.org/10.5281/zenodo.22075256)(见 `CITATION.cff`)。
- 作者:Yu-Chi TSOU (Liamour)。
