# V2 视觉语言 ·「晨光青绿 · 游戏化界面」

> 2026-10-20：第 2–3 节（token 与组件）已由 `V4_DESIGN_SYSTEM.md` 覆盖；本文的总纲与第 7 节 V3 一屏骨架仍然有效。

适用范围：正式游戏前端 `static/`（index.html / styles.css / app.js）。`prototypes/r5-combat/`、后端、存档与接口不在本轮范围。
用户裁决（2026-10-20）：①清亮舒适、去除灰蒙；②两套亮色预览中选定「方案一 晨光宣纸·青绿山水」；③只做亮色；④设计语言去网页化，改为真正的游戏 UI 语言。

## 1. 总纲：从"网页"到"游戏"

| 旧（网页化） | V2（游戏化） | 实现位置 |
|---|---|---|
| 品牌栏 + 文字工具链接 | 朱砂印章 + 胶囊图标系统钮（存/读/新卷） | `.masthead`、`.toolbar .text-button::before` 遮罩图标 |
| 人物标题 + 资源表 | 常驻 HUD：玉璧头像、境界朱印、气血/灵力槽、修为/灵石筹码 | `.hud`（sticky）、`.resource` 两种形态 |
| 编号文字目录 | 玉牌导航：圆形玉牌图标 + 短名；移动端底部 Tab 栏 | `.world-navigation`、`.world-nav-token` |
| h2 + 段落 | 场景横幅（每页一幅分层山水 SVG）+ 深青描金匾额 | `#world-scene`/`#journey-scene`、`.world-page-heading h2` |
| 文字/描边按钮 | 立体玉质按钮：下沿厚度、按下下沉 | `.primary-button` `.secondary-button` |
| 平铺区块 | 描金画框：象牙底、双线内框、四角金线 | 第 6 节通用面板选择器 + `--corners` |
| 行动列表 | 事件卡：左侧语义色条，按事项类别着色 | `.world-action[data-kind]`、`.action-row` |
| 品质纯文本 | 品质胶囊与法宝槽框：凡灰/下绿/中青/上紫/极金 | `.quality[data-q]`、`.r3-slot[data-q]` |
| 日志 ol | 卷轴记事：上下深青轴头、虚线分隔、增减数值着色 | `.chronicle` `.world-recent` 等、`.log-gain/.log-loss` |
| 敌人标题 | 对峙横幅：朱砂框、"敌"印、血槽、意图气泡、状态胶囊 | `.world-battle-banner` `.battle` |
| 静态刷新 | 飘字、获得弹层、突破演出、面板入场、灵气微粒 | `.fx-layer` 与 app.js 的 `floatNumbers/showToasts/showBreakthrough` |

## 2. Token（唯一颜色来源：`styles.css` 的 `:root`）

| 组 | Token | 值 | 用途 |
|---|---|---|---|
| 底 | `--paper` / `--paper-deep` | #F6F3EA / #EFEADC | 宣纸页底 / 禁用底 |
| 面 | `--ivory` / `--scroll` / `--white` | #FFFDF7 / #FFFBF0 / #FFFFFF | 画框 / 卷轴 / 卡片 |
| 天 | `--sky-top` / `--sky-low` | #DCEEF0 / #F8F4E8 | 页面晨光渐变、横幅天空 |
| 墨 | `--ink` / `--ink-2` / `--ink-3` | #1F2B28 / #4D5D58 / #65726E | 正文 / 次要 / 辅助 |
| 石绿 | `--jade` / `-bright` / `-deep` / `-soft` / `-line` | #1A7A62 / #1D8469 / #13604D / #E3F3EC / #9CC7B8 | 主操作、修炼、进度 |
| 石青 | `--azure` / `-deep` / `-soft` | #2B6CB0 / #1F528A / #E5EEF8 | 链接、社交、信息、灵力 |
| 朱砂 | `--cinnabar` / `-bright` / `-deep` / `-soft` | #C8452F / #D9573F / #9C2F1C / #FBEAE6 | 印章、战斗、危险、入道按钮 |
| 金 | `--gold` / `-deep` / `-light` / `-soft` | #B5832A / #7E5A14 / #F1E3BF / #FBF1DC | 画框角、匾额字、标签、交易 |
| 匾额 | `--plaque` / `-deep` | #2E4A44 / #1C302C | 匾额、卷轴轴头、剪影 |
| 画框 | `--frame-line` / `-2` | #D9C9A3 / #E8DCC0 | 外框 / 内框线 |
| 远山 | `--mist-1..3` | #CFE4D9 / #A8D0BF / #7DB7A0 | 页面远景与横幅三层山 |
| 槽 | `--hp` `--hp-track` `--mp` `--mp-track` `--xp-track` | — | 气血/灵力/修为槽 |
| 品质 | `--q0..q4`(+`-soft`) `--q4-glow` | 灰 #7D8883 / 绿 / 青 / 紫 #7B4FC0 / 金 | 品质胶囊、槽框 |

排版：标题/匾额/道号用宋体栈 `--serif`，UI 用系统黑体 `--sans`；字号阶 12/13/15/17/20/26/34，最小 12px（旧版 9–11px 全部上调）；数值 `tabular-nums`。
形态：圆角 6/8/12；按钮厚度 `--bevel: 0 4px 0`；画框 `--frame-shadow`；角花 `--corners`（在 `*` 上计算，子元素改 `--corner` 即可换色）。
动效：`--ease`、120/200/600ms；`prefers-reduced-motion: reduce` 下所有动画与过渡关闭，突破演出与飘字不生成。

## 3. 组件规格要点
- 按钮：主（石绿实底白字，下沿 4px 深绿）/次（象牙底深绿字描边）/文字（石青）/禁用（宣纸深底、灰字、无位移）；全部 `min-height:44px`；`:focus-visible` 2px 石青环 + 白间隔。入道按钮为朱砂变体。
- 事件卡：`data-kind` 由 `actionKind()` 按页面与事项 id 推断，仅影响表现：cultivate 石绿 / social 石青 / combat 朱砂 / trade 金 / craft 紫 / quest 匾额深青。序章按 `.group-*` 分类着色。
- 资源：有真实上限的（气血、灵力、序章修为）显示为槽；上限为存储上限或无意义的（凡界修为/灵石、灵石、药草、丹药、功法层）显示为筹码，隐藏无意义的"/ 上限"。
- 法宝槽：五槽以字形占位（剑/甲/佩/鼎/镜），空槽虚线，装备后按品质着框，上品外圈、极品金光。
- 场景横幅：`sceneBanner(target, id)` 为 11 个世界页各生成一幅三层山 + 地标的 SVG；颜色全部由 `.sb-*` 类引用 token。序章平时用九州图、战斗时用演武图。
- 反馈：飘字比对两次完整渲染之间的资源差值；获得弹层取新增日志（至多 3 条，3.2 秒消失，`aria-hidden`，读屏仍由 `#notice` 播报）；突破演出在境界文本变化时播放 1.4 秒。三者 `pointer-events:none`，不遮挡操作。

## 4. 布局与断点
- ≥1150px：HUD sticky；世界页三栏 = 玉牌栏 92px / 主舞台 / 右侧卷轴 270px（sticky）。
- 760–1150px：玉牌栏 76px；右侧卷轴移到舞台下方两列。
- <760px（含 320px）：HUD 取消 sticky；玉牌栏变底部固定 Tab 栏（栏内横向滚动，文档不横向溢出），内容与页脚预留 96px 底部空间。
- `--hud-h` 由 `syncHudHeight()` 写入，供 `scroll-padding-top`、sticky 偏移和弹层避让使用。

## 5. 兼容约束（已遵守）
- 不删除、不改名任何 id、`data-world-page`、`data-action-key`、`data-group`、表单 name；新增 DOM 仅为装饰/包裹（`#hud`、`#hud-avatar`、`#world-scene`、`#journey-scene`、`#world-battle-meter`、`#fx-layer`、图标 sprite）。
- 所有可点击元素均为原有真实控件换皮，未新增无后端行为的按钮。
- 不新增静态文件（`server.py` 仅服务三份静态资源），图标与场景全部内联。

## 6. 对比度（浏览器实测，WCAG 相对亮度）
| 组合 | 比值 |
|---|---|
| ink / ivory | 14.39 |
| ink-2 / ivory | 6.83 |
| ink-3 / white | 5.02 |
| gold-deep / ivory | 6.14 |
| white / jade（主按钮） | 5.24 |
| white / jade-bright（悬停） | 4.61 |
| ivory / cinnabar（印章、入道钮） | 4.75 |
| gold-light / plaque（匾额） | 7.56 |
| azure / white（文字按钮） | 5.42 |
| cinnabar-deep / cinnabar-soft | 6.35 |
| q3 / q3-soft | 4.72 |

禁用态 ink-3 / paper-deep 为 4.17（禁用控件不计入 WCAG 要求）。

## 7. V3 一屏游戏界面（2026-10-20，覆盖第4节布局）

用户要求：任何界面都必须在一屏内显示，绝不能出现超出屏幕的滚动条。V3 在 V2 token 上重排骨架，后端、接口与存档不变。

**锁屏原则**：`html, body` 高 100dvh、`overflow: hidden`；外壳与所有分区都用 CSS Grid 划定固定区域（`min-height: 0; overflow: hidden`），任何元素都不使用 `overflow: auto/scroll`。`app.js` 另有兜底：一旦有元素被程序性滚动，立即把 scrollTop 复位为 0。

**翻页器 `createPager/paginate`**：内容超出区域时按实际渲染高度分页，不靠滚动。每个分区由若干"原子"组成（事项卡、数据行、日志条、任务卡等）；逐个加入原子，加到放不下就另起一页，分页结果按区域尺寸（ResizeObserver）、字体加载完成和每 500ms 的溢出巡检重算。支持 ‹ › 按钮、PageUp/PageDown、滚轮与左右滑动翻页。如果单个原子本身就高过整个区域，就加渐隐并在翻页栏出现"阅全文"，打开阅览弹层（弹层同样分页）。跨页的数据段在右上角标注"续前页"。

**骨架**
| 视口 | 布局 |
|---|---|
| ≥1280 | 顶栏48 · HUD（立绘头像/境界朱印/血灵槽/筹码）· 玉牌栏76 │ 舞台（场景/对峙）+ 页签 + 内容面板 │ 卷宗（任务/回执/存档）· 潜修底栏 |
| 760–1279 | 同上，玉牌栏60、卷宗栏变窄 |
| <760 | 存/读/新收为 44px 图标钮并入 HUD 行；潜修条在 HUD 下；舞台64（战斗120）；页签末尾增加"卷宗"页签（卷宗区由脚本移入）；底部 2×6 玉牌网格 |
| 矮屏 | ≤760/≤640（桌面）、≤620（手机）逐级压缩舞台、页签和翻页栏；手机极矮屏隐藏潜修条 |

**舞台页签**：每个世界页拆成「事项」「手札」以及若干长线要务页签（目标/行纪/精英/器物/首领/副本/资材/待领），没有内容的页签不显示。原来展开的表单（`details`）改为在事项区上方弹出的浮层，不再挤占布局。序章行动分组沿用 `data-group` 按钮作为页签。

**立绘（"模型"）**：`portrait(tier)` 生成主角立绘，光环颜色随九境递进，冠、簪、法宝珠、光晕随境界逐步出现，用于 HUD 头像、对峙舞台和人物页；`enemyPortrait(name)` 按敌人名称中的关键词选用 8 类剪影（猿/傀/影/兽/蛟/狐/修士/灵），首领加朱砂光环。

**字体**（均为系统字体，离线可用）：页名、匾额、页签、境界用楷体栈 `--kai`；数值和标题用宋体栈 `--serif`；正文用 `--sans`。字号阶 12/13/14/16/18/22/28，最小 12px。

**兼容**：保留全部原 id、`data-world-page`、`data-action-key`、`data-group` 与表单 name。`#world-actions-show-more/-all` 保留但始终隐藏（分页已取代"再看八项"）。测试与内部跳转统一派发 `guixu:reveal` 事件，切换到目标所在页签和页。浏览器套件新增断言 `assert_one_screen`：文档与所有元素都不可滚动。

**实测**（浏览器面板，临时存档）：1920×1080、1440×900、1366×768、1280×720、768×1024、375×667、320×740、320×560 下，遍历 11 页 × 全部页签（含凡界战斗中、序章战斗与结局），文档无纵横溢出、无可滚动元素、分区无未分页溢出；手机宽度下所有可见按钮高度 ≥44px。
