# W1 完整修仙界界面契约与评审

状态：两轮交叉评审后进入前端实施；系统完成与否以实际规则及独立QA为准。接口以WORLD_API.md为准。早期真人联机、公共账本、复杂组件DSL、integer字段类型、对象confirmation与preview端点提议均已否决，不作为实施要求。

## 范围、缺口与评审
首版三地和四组动作不足以承载完整世界的实体、关系、资产和表单。保留序章及53动作回归，但不以原20项测试代表新版通过。

第一轮审查指出：全部动作平铺会重现长页面；任意数量若前端计算会复制经济公式；未投影active则不能判断序章与世界边界。第二轮已读冻结WORLD_API、WORLD_ARCHITECTURE、WORLD_DEV_REVIEW，采用PM精简形状；世界投影新增必需active布尔，fields仅text/number/select，confirm为中文字符串，所有写入仍走原/api/action。

用户确定全部单机NPC模拟。明确显示NPC竞技、模拟跨域赛、NPC拍卖，师徒宗门家族朋友也为NPC。无账号、真人社交或外部服务。世界关系、市场、赛程、榜单都随手动档整体回溯，不维护公共账本。仙界只留版本接口，无可进入页或假内容。

## 导航与视觉
深墨青、古纸、旧金、细线、手札叙事延续；顶部身份/凡界境界/资产，下方左卷目、中工作台、右任务簿与近期回执。段落、账表、紧凑动作行各司其职，不堆卡片。

world.active=false保留序章；完成序章后后端提供world_enter，显式进入后显示独立工作台，不混合两套动作。世界active后不显示旧归墟结局作为整个游戏完成，当前境界来自world.stage/summary或人物页投影。提供只读序章历史入口，不能由其触发旧操作或重开。

导航使用普通button及aria-pressed，严格按pages顺序；切页不写库、不推回合，状态更新保留选择。窄屏为可滚动卷目行与单列工作台，任务簿下移；320px无文档横向溢出。正文、账表自然换行，触达至少44px。

| page id | 信息与真实流程 | 必须可见状态 |
| --- | --- | --- |
| world | 地图/势力→地点条件→旅行探索 | 位置、势力、声望、解锁理由 |
| character | 灵根体质/境界/功法装备→培养学习装备突破 | 已有、槽位、门槛、替换影响 |
| sects | 宗门师徒→加入申请指导贡献兑换 | NPC、身份、职位、申请中、奖励 |
| social | 家族朋友→创建加入交往消息 | NPC对象、关系、权限、拒绝原因 |
| craft | 四艺→配方材料→制作→使用装备 | 专业、门槛、余量、产物用途 |
| exploration | 秘境奇遇/副本Boss→节点战斗→结算 | 风险、阶段、意图、退出损失 |
| estate | 洞府→建造升级→行动推进→领取 | 等级、资源、上限、领取状态 |
| market | NPC商城交易拍卖→买卖上架竞价→结算领取 | 单价/费用、托管、竞价、结算、已领取 |
| quests | NPC任务剧情/AI事件→对话选择→完成领取 | 节点、影响、目标计数、规则AI来源 |
| achievements | 成就称号/排行/长线历程→领取装备 | 条件、已领、槽、本地NPC榜口径 |
| arena | NPC竞技/模拟跨域赛→赛程挑战→排名奖励 | 对手成长、轮次、积分、奖励一次性 |

未解锁页提供说明与中文条件，不是死链接。任务追踪从quests投影取信息，跳转只导航、不接任务或领奖。资产只用后端投影，不另造余额。

## 固定协议与表单
view.world为version:2、active:boolean、pages数组；stage/summary可选。每页id/label/title/description、stats(label/value)、sections(title/body?/rows(label/value))、actions。value为字符串，所有正文使用textContent。

标准action仍含id/label/detail/cost/effect/enabled/reason/params/primary，可附fields与中文字符串confirm。普通动作紧凑展示；fields动作展开为表单，默认不把所有输入常驻。label应包括具体目标，params含机器ID，不让多名NPC只对应含糊的互动按钮。

fields.name不能覆盖静态params。text按maxLength；number使用step=1及投影min/max，转换有限整数，拒绝小数、NaN与Infinity；select只提交options的字符串value，不能用中文label作ID。required为布尔，可选空字段不提交。字段有唯一label/id，错误可键盘读取，拒绝时保留草稿。按page+action.id+静态params保留草稿，成功才清理。

成本收益只显示后端cost/effect，不实现preview接口，不复制经济公式；数量动态成本必须由后端清楚描述单价语义或展开固定数量动作，不能将单价误称总价。

## 关键流程、权限与异常
四艺：配方材料产物→投影字段→制作→消耗/产出/熟练度回执→保存。宗门师徒家族：对象身份→允许操作→申请/同意/贡献等→关系回执，发申请不可伪称已加入。职位权限与禁用原因可见，后端重新检查。

NPC拍卖：选物品/数量/价格→成本与托管说明→confirm则确认→订单→成交/流拍/退款/领取。页面须区分托管、竞价、结算、已领取；库存/价格变化返回中文拒绝，不悄悄接纳新价格。

NPC竞技跨域：对手成长/赛程/奖励→挑战→权威战斗→排行与一次性奖励，不用静态榜单代替真实闭环。NPC剧情：说话人正文/选项/节点清晰；规则AI动态事件以行动时钟推进，不假装外部模型或真人。

所有页区分加载、空态、锁定、失败。写入时新增表单和原存档一同busy禁用；不清空草稿。未知结果冻结原载荷，sessionStorage刷新后同ID重试；409刷新不重放。确认只按后端confirm，取消不发请求且返回焦点。失败展示明确原因，不仅写操作失败。

## 验收
通用工作台不是系统完成。每页须入口→真实操作→回执→资产/关系变化→刷新/重启保持，并有拒绝分支。QA独立验收全部11页、三字段类型、可取消确认、权限/枚举/整数错误、NPC赛程和拍卖终态、世界手动档、旧档迁移、丢响应重试、多页冲突、原序章53动作。桌面/320px/键盘/长中文留证据，截图不只拍总览；跨系统成长链由策划冻结。仙界不在实现范围。

当前新版前端实施中，尚未独立验收。

## 前端协议自测（不代表新系统通过）
系统Chromium+Playwright拦截API fixture验证11页导航、text/number/select、取消确认零写入、确认后类型及静态目标准确、只读旧卷、全11页320px无横向溢出，未见JS异常。截图位于临时目录 `guixu-world-ui-fixture-desktop.png` / `guixu-world-ui-fixture-mobile.png`；数据是协议fixture，不能作为真实NPC经济/战斗证据。后端完整投影后仍需实际联调与QA独立回归。

## 冻结前真实后端联调
已用独立临时存档、隔离Python服务及系统Chromium真实验证（不拦截API、不修改存档）：公开HTTP合法53动作准备序章，浏览器点击入世→全部11页只读导航→select鉴定灵根→text建立家族→number非法0被拒且不写入→NPC拍卖确认取消不写入/确认上架成功→Boss进入、8条战斗指令置顶→跨页交锋横条返回→普攻→撤退；全部11页320px无横向溢出，零JS异常。初测发现入世被旧游历分组隐藏，已改独立置顶后重跑通过。

实际投影174动作，同道49动作。最终展示加入检索、默认8项、再看8项/展开全部，全部动作DOM保留；筛选/切页不推进状态。多于3节信息默认前2展开，可逐节展开。新增战斗时自动进入world.battle.page，战斗8指令始终置顶、不受分页影响；其他页持续显示交锋摘要和返回入口。detail不重复标准成本收益，保留title/aria-description。

真实截图在临时目录 `guixu-world-real-character.png`、`guixu-world-real-craft.png`、`guixu-world-real-market.png`、`guixu-world-real-battle.png`、`guixu-world-real-auction-confirm.png`、`guixu-world-real-mobile-social.png`、`guixu-world-real-mobile-market.png`。这些为前端代表性联调，不代替QA完整凡界路线、经济边界及最终回归报告。静态实现已冻结，后续仅按QA阻断缺陷修复。
