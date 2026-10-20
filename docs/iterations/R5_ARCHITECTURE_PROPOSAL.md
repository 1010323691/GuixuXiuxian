# R5图形自动战斗：架构候选与交叉审查

状态：**仅方案，不改运行代码/配表/存档/服务**。已读AGENTS、岗位与R4实际接口，核对world._battle/_start/_victory/_complete_dungeon、Store去重/事务、loot法宝与资格、app.js的pending/战斗/只读校正。以下字段、动作、上限均为候选，不能当作现有API或功能通过。

## 推荐结论

采用**服务端确定性、有限分块自动仿真，前端图形回放**。本地SVG/CSS呈现角色/NPC站位、出招、血蓝、CD与副本节点，服务器决定所有命中/技能/资源/胜负。正常播放自动请求下一小块；玩家不用点击每次普攻/强攻。客户端计时器只安排动画与何时申请下块，不计算CD、伤害、资格或奖励；停止请求时不会在后台无限打怪。

不首选整场同步结算：普通战斗虽短，但高血量/零输出/控制链可能阻塞请求，且无法表达中止/恢复。也不首选后台线程、WebSocket、数据库定时器或真实墙钟战斗：现有stdlib HTTP和SQLite事务已足够，新增并发后台结算会增加多页、停服、时钟回拨和成长经济竞态。

推荐默认每块1–3个完整玩家/NPC行动机会，快进最多约8个，最终值须按事件长度与端到端耗时确定；每场还需固定最大合法机会及僵持终态。倍速/跳过只缩短回放或选择有界批量，不能改变战斗规则或奖励。一次只自动推进当前战斗，不自动开下一副本/消耗下一份资格。图形副本地图负责选择真实下一节点；自动连战/连刷若未来需要，必须另有明确授权与总次数预算。

## 与现有代码的真实差距

目前world._battle一次手动动作内完成玩家→同行→敌意图→毒/抽灵→胜负；敌人常击/蓄势/重击按turn%3，技能无ready_at状态。现有两法宝槽仅被动修炼/攻击/气血派生，没有可主动施放的大招。world.apply_action外层每POST加一次world.tick/全局行动、跑一次AI及活动/故事观察；不能直接把现_battle循环5次却仍只做一次外层结算。

现有GET只读成长/资格预览；Store在dedup与原revision检查后同步成长、资格，执行domain，最后一次事务提交。页面以sessionStorage保存未确认请求，丢响应使用原request_id重试。以上能力继续复用，不能为了动画绕过原契约。当前battle字段与r3顶层严格校验，新状态必须有版本/兼容处理，不能任意塞字段后忽略验证。

## 仿真与时序

新增纯combat模块负责整数虚拟战斗tick、自动策略、技能就绪/资源、确定性事件；伤害/防御/毒/炉盾/抽灵/世界Boss评分尽量抽出现_battle的单机会resolver共用。编排层负责依次提交真实机会对应的world.tick、AI及领域观察，不复制两套伤害公式。

建议一tick表示该角色的一次行动机会，图示“战斗秒”只是其播放映射；不使用UTC秒扣CD。技能在t施放后记ready_at=t+CD：CD3于t0施放，t1/t2不可用、t3再就绪。以此固定边界，避免每帧减CD/刚施放即减一次的偏差。普攻CD1、常驻技能短CD、战力法宝爆发长CD；具体值/倍率由策划统一，架构不擅定数值。无资源或控制中按合法优先级退回可执行动作，不因自动AI挑了非法技能导致整个循环报错卡死。

同一机会内固定顺序：到期状态/就绪判断→玩家策略选择与资源扣除→命中/护盾/个人有效伤害→同行（单独归属）→若击杀立即终结不受反击→敌方自动意图/蓄势/技能→旧毒/刷新等既有机制顺序→败退/窗口结束→推进游标。新技能若需要不同先后，应明确版本化，不能把旧毒首次不跳、炉盾火符不穿透、镇魂跳敌、抽灵防御免耗悄悄改掉。

NPC也按服务端策略/CD行动；大招须有可见蓄势/预告，不能只给NPC换个技能名仍没有不同后果。玩家自动防御/清毒/破盾应是预设策略可理解的结果，而非要求画面中临时手点反应。精英与普通副本共用机制枚举、同一个结算流水线。

世界Boss仍最多12次玩家机会，非12秒真实等待；个人分只计玩家实际削减的HP，不计同行/NPC/过量/纯护盾伤害。倍速不能多得行动机会或多发参与奖，提前败退/撤退按既有有效参与规则结算。

## 策略、技能与法宝边界

战前有限预设策略及开关优先于可编程脚本：输出/稳健/机制优先等由策划给明确优先级，服务端只接受已知preset ID。战斗开始冻结规则版本、技能目录/等级/法宝uid与属性来源、策略及允许耗材预算；同场禁止通过换装备/改策略重置CD或重复施放开场爆发。若允许中途改策略，必须独立POST并保持CD/资源不重置。

丹符默认不自动消耗；显式开启并给单场数量上限后才使用，且同时受真实库存限制。自动AI不能一次看守关就无提示耗光全部药符。演武仍只消费snapshot模拟库存，不把拍卖/材料到账覆盖回旧inventory；自动引擎需继续调用原模拟库存adapter。

修炼型法宝仍只改变未来持续修炼速率，双槽取舍及总15%不变；长CD爆发优先绑定战力型法宝，不能让修炼宝无成本兼得同等爆发。战力被动与主动技能是否替换/保留、同机会多宝是否共享施放位置、初始就绪还是预热、控制/防御是否计CD推进，必须在策划表中统一，避免每个模板各写特例。无请求提供自造倍率/技能效果/下一就绪时间。

## 候选状态与接口

推荐新场`combat_mode='auto_v1'`并单独combat_rules_version；旧场legacy。逻辑状态包括battle_id、cursor/tick、actors及其HP/MP/护盾/状态、loadout快照、known ability IDs与ready_at、preset/耗材预算与实际花费、敌意图/蓄势、终态与run关联。首版保持确定性，无需求不加随机；以后增加随机再保存服务端seed/游标，不能让前端给seed。

候选统一动作`world_battle_advance {battle_id,expected_cursor,steps}`，steps为严格整数且服务端有固定上限。继续外层request_id/expected_revision；客户端不得提交目标伤害、技能结果、时钟、HP、胜负。不同请求旧cursor返回409，原ID同内容返回duplicate最新快照，不再次扣耗材/CD或派奖。battle_id在开始/首个授权POST分配并持久，不在GET随机生成，不由当前HP等可变状态导出；新旧游标与revision是不同层面的保护。

事件建议`{id,battle_id,cursor,index,actor_id,target_id,ability_id,kind,value,before,after,status_changes}`，id由battle_id:cursor:index确定。具体before/after只投影必要血蓝/盾/机制，纯展示事件不能作为下一次执行输入或领奖凭证。客户端去重事件后按顺序播放；最终状态以服务器snapshot为准。

battle保留最近一块`{from_cursor,to_cursor,events}`即可；终结battle=null时，将最后块与摘要移入有上限的last_battle_report，刷新也能呈现胜负。优先保存最近1场，避免累计每帧/所有历史导致GET和存档无限膨胀；日志仍有原上限。客户端sessionStorage只记播放游标，不持有权威战斗状态。

## 自动推进、暂停与断线

1x/2x/跳过使用同一服务器事件，渲染器按本地时钟播放。页面隐藏/断网停止续请求；已经提交的一块保持有效，回到页面GET取得原battle_id/cursor或最终report。丢响应先按原request_id重试，不能创建新ID再“补打一次”。多标签只允许一个版本成功推进；另页显示刷新/接管，不能让多个自动循环抢写。

“暂停播放”只暂停回放和续请求，不能暗示撤销已提交的一小块。真正撤退用服务端动作处理当前状态，释放/消耗资格照既有规则；不能客户端关动画就返还丹药或重置Boss次数。若以后有真正服务端暂停状态，也只限制未来step，不能倒回已提交cursor。

离线期间仍只有原持续修炼与恢复资格增加，不自动战斗、跑拍卖或自动消耗下一run。小批量逻辑时间不当成额外UTC时间发修为；一次POST用同一权威now同步成长，不能每个模拟秒再领一份离线XP。当前行动制AI按真实逻辑机会推进，不按动画帧或前端观看时长推进；完整终战不得由外层重复加tick/观察两次。

## 副本图与领域结算

路线图从当前dungeon.round/exploration.node和已提交战果投影节点：locked/current/cleared，配真实action引用、禁用原因、敌方概况和资格状态。前端不靠动画播完私自开下一节点，合法下一节点须服务器current cursor/run仍匹配。地图不是独立产奖系统，不复制掉落/保底/手战证明。

每次自动块执行结束仍走原guard/secret/dungeon/elite/arena/世界Boss的唯一结算adapter；新auto真实战斗完成才写manual clear证明（字段若改名actual_combat应兼容旧manual），已有sweep不伪造成真实战斗。故事、日周目标观察实际使用与战果增量，不能每块都重复读历史胜利或把回放算使用一次。

恢复资格仍按reservation账，开始同一run预约一次，成功消耗，失败/撤退释放；动画快慢、刷新、重连不占新run。单机长线load继续保current完整成长/资产/资格/当前战斗，只有安全位置检查点；旧free的完整回档语义必须明确保留，不用auto模式偷偷改掉。

## 旧进行中战斗与数据升级

旧battle继续legacy规则直到结算；保留turn、HP/MP、毒/盾/蓄势、已用药符、演武snapshot、Boss commands/player_damage/period与副本reservation。可提供“一键委托完成旧战斗”，由服务端旧resolver选择合法动作分块推进，让用户不用继续逐次攻击，但本场不追加新CD/法宝主动技。下一场才生成auto_v1。不得为了新图形把旧战斗取消、重新入场或重新扣资格。

新形状采用显式模式/规则版本；兼容升级复用先唯一备份current/slot/requests再事务校验的既有机制。没有新战斗的旧档仅新增必要可选元数据，free规则不能被静默转长线。精确迁移字段待实现冻结，不在方案阶段声称schema已经改变。

旧Boss本UTC周期已有best/paid/attempts必须保留，不能为了CD重建周期。推荐该期冻结legacy评分/战斗版本至结束，新期再auto_v1；若PM选择同一期允许新技能提高个人best，也须明确仅F(newbest)-paid补差，不重发次数/参与币，不拿NPC名次重算。本地无真人公平排名，但账本仍不能重复。

## 已完成交叉质疑与必须验证的风险

- 开发认同抽单机会resolver、有限分块与last_battle_report，反对复制第二伤害引擎；强调外层tick/AI/观察不能漏跑或重复。我采纳其终块持久化与游标409建议。
- 策划认同CD为行动机会、ready_at=t+CD及12玩家机会；同意丹符默认off/显式单场预算，旧场可委托但不重置，修炼宝与战力宝须守取舍。
- 视觉同意SVG/CSS双站位/事件轴/CD格/节点图，要求稳定battle_id/event_seq、actors/abilities、HP/MP变化与机制反馈、真实action引用；暂停/倍速为回放，未提出让前端扣CD。
- 关键风险：AI无合法输出造成永动或无限经济tick；需每场机会硬上限、僵持终态及禁止自动开新run。CD/自动药符改变战斗平衡需重新核普通根骨、低难补救、三机制反制、精英和Boss档位，不能引用R4通过。
- 事件块过大造成HTTP锁太久、视图提前显示最终态而舞台仍在播、旧ID重试把旧事件播两遍、多标签自动写冲突、终战report丢失、迁移回滚与存档增长均需专测；默认小块降低已提交与画面差距。

未来验收至少覆盖：同初态/策略分块1与分块N最终状态/资源/世界tick完全相同；1x/2x/跳过成绩相同；CD边界/资源不足/控制/毒盾抽灵及同行归属；多次请求与丢响应仅一次实际消费/派奖；断线/重启恢复同cursor；GET/隐藏页不推进；旧进行中各kind不重置；run四退出路径预约守恒；实际图形出招/冷却/副本图可读与窄屏/减少动效可用。UI回放成功不等于伤害已验证，规则测试也不等于画面已经做好。

上文正式集成机制尚未实现，也没有生产改动或新增通过声明；本轮独立实验范围及已冻结合同见下一节。实验不引入网络账号、付费资源或外部依赖。

## 本轮独立实验：最终最小合同（覆盖此前聊天草案）

PM本轮选择先用`prototypes/r5-combat/`验证自动出招、CD与图形可读性；开发拥有engine/server，视觉拥有static，QA拥有实验tests。**不改正式v1.2生产game/static/storage/data**，不把实验胜利/物品/副本节点写回正式档。上文分块/持久游标是未来正式集成推荐，本实验有意采用有限整场同步仿真，不能声称已实现正式断线续战/经济幂等。

实验stdlib HTTP默认127.0.0.1:8001，静态资源本地SVG/CSS；GET /api/health、/api/config和静态文件纯读、不推进。POST /api/simulate仅允许以下JSON白名单，不接受旧草案talisman_budget/companion别名或version、玩家攻击/HP/MP/秒数/伤害/路径/状态注入：

| 字段 | 最终范围 |
| --- | --- |
| scenario（必需） | den / forge / tower / boss / dungeon |
| build（必需） | sustain / burst / guard |
| strategy（必需） | balanced / aggressive |
| pill_budget（可选） | 精确int0..3，默认0 |
| fire_budget / guard_budget / soul_budget（可选） | 各精确int0..2，各默认0 |
| npc（可选） | 严格bool，默认false；同行支援10伤，单独归属 |

bool不当int、浮点1.0不当整数、未知键/非法枚举/负预算/超额拒绝；HTTP body最大16KiB，拒绝非有限数/溢出1e999、重复JSON键与不支持的分块请求。/api/config给defaults、options、limits和experimental/persistent/rewards说明，UI不复制另一套预算常量。高级补给默认折叠，明确**实验虚拟单run预算**；同run冻结不可中改，没有无限药/复活。

普通实验固定玩家攻击100、HP600、MP60；受控0MP等只可通过engine-only fixture测，不开放HTTP钩子。全部模拟至多120个玩家机会，Boss窗口至多12，副本路线固定3节点；预算/技能CD跨该run三个节点连续，不每节点重领药符或无条件重置大招。当前sustain/burst/guard均为**战斗实验构筑**；sustain是战斗持续触发，不代表正式修炼法宝可无成本兼得战力。

相同规范化input与配置版本生成同simulation_id、frames/events/metrics；随机数、正式request_id/revision、DB、资格扣费、奖励写入不在实验中。重复POST只是重新计算同一无副作用实验，不是正式经济层幂等验收。初态`frames[0].tick=0`，第N帧tick=N为第t=N−1个行动机会结算后；CD使用t机会索引，帧显示remaining相对下一机会，不按动画帧减CD。

实际响应为`{ok,experimental,simulation_id,config_version,input,result:{outcome,ticks},frames,events,metrics,nodes,notice}`：

- frame包括tick/node/player/enemy/before/after/decision/cooldowns/statuses/events/nodes；cooldowns为`{id,name,remaining,total}`；player含HP/MP与上限，enemy含HP/意图/护盾等。before/after与画面帧终态应一致。
- event包括稳定id、tick/node/type/source/target/label与可选amount，source区分玩家/NPC/法宝；metrics独立分player_damage/direct_damage/treasure_damage/npc_damage及预算实际用量，Boss评分只用玩家真实伤害，NPC不计。
- nodes为当前实验三节点locked/active/complete状态，只有前节点实际胜利才进下节点；败退后后续不模拟。它是实验演算/回放进度，不能标成正式存档权威进度或领奖入口。

倍速、暂停播放、重播、跳结尾只读取同一响应，均不再次POST或施放；重新模拟按钮才POST，须取消旧请求/定时器，用generation token防旧响应、旧帧污染新实验。后端已经算完实验时“暂停”明确只是回放暂停，不宣称服务端尚未结算。当前实验HTTP无正式API接入、SQLite或磁盘存档；退出页面不影响正式角色，缺少持久恢复是刻意隔离边界。

### 实现读审反馈（不是完整验收）

架构已只读检查实验server/engine：纯simulate、严格输入、确定性hash与有界循环符合该实验边界。初读发现frame.after先于next intent更新会不一致、balanced重击用25%护符替代免费50%防御可能反优化，两项已直接反馈开发；开发已修为同一终态快照及策划明确优先级（击杀优先、丹/火/魂条件、重击防御、蓄势低血护符）。预算冲突已由PM最终统一为上表，所有角色已同步。尚须QA独立确认实际画面/HTTP/纯引擎、正式运行源SHA不变；不能把上述读审当通过报告。

## 最终只读复核：神识灵印与独立双宝空战实验

本轮视觉冻结方向为御空神识灵印与独立主副法宝，规则仍是服务端离散机会模拟；御空位移/飞行光轨是表现，不是客户端碰撞或额外命中判定。正式版未来采用有界step与持久轨迹；战前可一次授权当前固定run自动推进，无选择价值的战间无需重复点继续，真实分支/失败/条件变化则停，绝不自动开启新run或重复扣信用。正式营地免费整备与run内CD连续须单独冻结；实验无营地，不拿其高压连战直接宣称正式平衡已通过。

最新engine/server读审与额外只读诊断（非新增正式QA用例）：

- `shield_absorb`仅在真实吸收量>0时发出，source=secondary、target=player、amount=min(当时屏障,已过防御/护符的敌伤)。它不是护盾生成90的重复动画，不增加玩家伤害/Boss个人评分；毒伤不经过该物理屏障。damage_prevented包含防御/护符/屏障等总减免，不能把它全部显示为法宝吸收。
- frame.decision_reason与最终选择的decision一起记录，理由来自实际可用资源/CD/预估终结/反制优先级。它解释本次策略，并非“全局最优”保证；药符占主行动、改变相位，给更多预算仍可能更慢或更险，界面不应承诺自动一定更强。
- 针对5场景×3构筑×2策略×NPC开关×零/最高预算共120组作纯函数诊断：重复计算结构完全相同、帧数=ticks+1、所有decision_reason非空、frame.player/enemy等于after对应终态、事件ID唯一、Boss≤12/其他≤120、个人伤害等于非NPC实际命中事件总和。共检查134条真实shield_absorb，均为正确归属的正整数且不超过90。此为架构补充诊断，不与QA用例数量相加。
- server只调用实验engine，GET仅health/config/本地静态，POST唯一simulate；严格白名单/预算类型、重复JSON键/非有限数/16KiB上限和静态目录限制保留。未导入生产game、SQLite、玩家目录或奖励接口；`initial`仅纯engine fixture，HTTP不能提交。
- 按QA记录的17份正式runtime基线逐一SHA256复核，**0份变更**。本轮架构没有修改开发/视觉文件或正式代码；只更新本提案。实际空战浏览器与最终发包以QA当轮结果为准。

最新读审源码SHA256：engine `43aa7cdc1b9663f8b8a44bea4a41e05dcae01bbd849dc0a5136d116c5533f2ca`；server `0cddbb0c57bd36c1cfbfdc1bc0f25db06ecea5cbfb1aa6f41b63678c976fe61e`。当前没有发现阻断本地隔离实验交付的架构缺陷；真实剩余风险是策略非最优、纯表现不等于物理空战、整场预计算不提供正式存档/中途服务端暂停，以及实验构筑/无营地难度不可直接迁入正式月余经济。正式集成/旧档迁移/持久重试与全战斗兼容仍未实现，必须独立验收。
