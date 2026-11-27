# 页面流程图 SOP（spec 驱动）

流程图不再手工摆坐标。你只维护两类 JSON，剩下交给引擎。

```
spec/screens.json     页面登记（单一事实源：截图、清单、流程图、附录 B 都从这里来）
spec/flows/<scope>.json   流转关系，scope = 章号（3.1）或 3.0 / all（整体图）
```

格式说明见 `scripts/lib/spec.py` 文件头。

## 1. 工作流

```
0. 页面地图闸门  先登记 screens.json + 写 flows，再运行
                 python3 scripts/prdkit.py flow -p <项目> --draft   → .prdkit/draft/flow-*.png（草案，不进 images/）
                 此时不需要原型和截图，节点画成“待绘制”。把草案给用户确认章节、页面、流转，通过后再画原型。
1. 登记页面     写 screens.json：每个页面/状态/弹窗一条（id、name、kind、chapter、section、url、actions、shot）
2. 截图         python3 scripts/prdkit.py shot  -p <项目>        → images/*.png
3. 画流转关系   写 flows/3.x.json：nodes（放在哪一列哪一行）+ edges（谁到谁、标签、种类）
4. 渲染+自检    python3 scripts/prdkit.py flow  -p <项目>        → images/flow-*.png，打印 FLOWGEO 自检结果
5. 生成清单表   python3 scripts/prdkit.py flow  -p <项目> --table → 粘贴到 PRD 各章开头
   生成流转行   python3 scripts/prdkit.py flow  -p <项目> --transit → 各页面“流转”行草稿，直接贴到小节首行（不要手写页面名）
6. 校验         python3 scripts/prdkit.py lint  -p <项目>
```

改了页面或流转，从对应步骤重来；不要手改 PNG，也不要手改清单表。

## 2. 画图规则

| 项 | 规则 |
|---|---|
| 列（col） | 按用户走向从左到右，起点节点在第 0 列 |
| 行（row） | 主流程放第 0 行；分支、异常态、结果态放下一行，位置尽量在来源页正下方 |
| 节点 | 页面/状态/弹窗用 `screen` 引用 screens.json；起点用 `kind:start`；条件用 `kind:cond`；备注 `kind:note` |
| 连线种类 | `normal` 普通跳转 / `popup` 弹窗浮层 / `success` 成功完成 / `boundary` 异常边界 / `back` 返回循环 |
| 标签 | 写**用户动作**（“点‘申请借用’”），不写系统内部动作，**不要写成目标页面的名字**；≤ 14 字，超长会触发 FLOWGEO-14 折行提醒 |
| 返回线 | 返回/循环用 `kind:"back"`。目标页正下方放着结果态时，去程与回程并排走：去程 `fo:-38,to:-38`，回程 `fs:"t",ts:"b",fo:38,to:38`（贴边走线由 FLOWGEO-05 检查，仍建议肉眼看一眼图） |
| 跨章节点 | 章级图可以放他章页面（如回到 3.1 的物品列表），清单里自动标“（他章）” |
| 泳道 | 整体图可用 `lanes` 分阶段；章级图一般不用 |
| 他章页面 | 章级图里出现他章页面会自动标注“（他章）”，仅用于说明来源/去向 |

## 3. 不要手工指定的东西

引擎已经自动处理，**默认不写**：`fs / ts`（连线出入口方向）、`fo / to`（端口偏移）、`mid`（绕行距离）、`route`、`lx / ly`（标签位置）。

- 同一行被中间节点挡住的连线：引擎自动从上方绕行。
- 一个节点向外多条连线：自动错开端口和层次。
- 标签：量过真实尺寸后放在不压线、不压节点、不互相重叠的位置。

只有这几种情况才手动：

1. 想让分支从下方出口（`"fs":"b","ts":"t"`）——常见于“来源页正下方放结果态”。
2. 自检报 `FLOWGEO-12`（找不到标签位置）：先加大 `col_w`，仍不行再用 `lx/ly`。
3. 需要一条刻意从下方绕行的返回线：`"route":"under"`。

## 4. 自检码速查

`prdkit.py flow` 渲染后用真实浏览器测量几何关系，**error 必须清零**才算完成，warn 尽量清零：

| 码 | 级别 | 含义 | 处理 |
|---|---|---|---|
| FLOW-025 | warn | 边标签与目标页面同名 | 标签写用户动作（“点…”“发送…”），不写页面名；写图（spec）阶段就会提示 |
| FLOW-026 | warn | 边标签超过 14 字 | 缩短，避免渲染时折行；写图（spec）阶段就会提示 |
| FLOWGEO-00 | error | 节点截图不存在 | 先运行 `shot` |
| FLOWGEO-01 | error | 连线穿过某个节点 | 去掉手写的 fs/ts/route 让引擎自动选；或把节点挪位 |
| FLOWGEO-02 | warn | 两条连线重叠 | 通常是手写了 fo/to，删掉让引擎错开 |
| FLOWGEO-03 | warn | 连线交叉过多 | 调整节点行列顺序，减少交叉 |
| FLOWGEO-04 | error | 连线超出画布 | 减小 mid，或增加行列 |
| FLOWGEO-05 | warn | 连线沿节点边缘贴着走（距边缘 ≤ 7px 且重叠 > 12px） | 调大 `fo/to`（≥ 38）把线挪开，或改走 `route:"under"` |
| FLOWGEO-10 | error | 标签压住节点 | 加大 `col_w`，或把相关节点拆到不同行 |
| FLOWGEO-11 | error | 标签互相重叠 | 缩短标签文字；加大列间距 |
| FLOWGEO-12 | warn | 标签找不到不压线的位置 | 加大 `col_w` / 行距，或手动 lx/ly |
| FLOWGEO-13 | warn | 标签压住泳道标题 | 用 lx/ly 平移 |
| FLOWGEO-14 | warn | 标签折成多行 | 缩短标签文字 |

## 4b. 原型与流转必须一致

`prdkit check prototype` 把原型里的页面跳转与本目录的连线逐对比较（以页面文件为单位，同一 HTML 里的状态/弹窗不算跳转）：

| 码 | 级别 | 含义 | 处理 |
|---|---|---|---|
| PROTO-020 | error | 原型里有 A→B 的跳转，流转里没有对应连线 | 业务流转：补连线，重新 `flow`、`flow --table`、`flow --transit` 并同步 PRD；示意链接：删掉或加 `data-flow-ignore` |
| PROTO-021 | warn | 流转里有 A→B 的连线，原型里没有能点过去的入口 | 补入口，或删连线并重新生成 |
| PROTO-022 | error | 链接指向不存在的页面文件 | 改成正确文件名，或补页面并登记 spec |

不要求画进图的：返回键、底部 Tab、PC 侧栏/顶栏/面包屑（全局导航）。

## 5. 什么时候需要章级图 / 整体图

- 章内页面+弹窗 ≥ 3 个：必须有章级图（lint L-321）。
- 全文页面 > 2 个：必须有整体图 `flows/3.0.json`，只放主干页面，状态和异常留给章级图（lint L-310）。

## 6. 回归

改动引擎、lint、模板之后，运行 `python3 tests/regress.py`。它用虚构案例 `examples/neighbor-lend`（移动端）和 `tests/fixtures/admin`（PC 后台，1440 视口）跑完 spec → shot → flow → index → lint，4 种风格逐一应用，并检查草案模式、FLOWGEO-05 植入缺陷、固定风格预览图是否过期，要求全部通过、PRD 100 分。**不要把真实项目的页面或流程图放进 skill 目录。**
