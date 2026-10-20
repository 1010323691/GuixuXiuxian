# v1.1.0 R3 界面实施与验证

状态：前端功能已完成，正提交独立QA最终验收。仅维护static三文件与本文，不修改后端、数据、测试或既有设计；本轮视口证据存入artifacts/r3-qa/ui。依据MONTH_BALANCE_DESIGN R3、LOOT_GROWTH_UI及PM最终裁决；无HTTP改钟入口，无外部账号或费用。

## 模式、存档与兼容
新角色默认longline，提供显式free选项；新局确认说明仅影响新角色、不自动转换旧档。HTTP请求提交mode，旧自由行动/原序章与11页DOM、导航、busy、sessionStorage pending及同ID重试保留。

长线入世后界面标记持续修行，保存入口为位置检查点。load仅恢复安全位置；成长、境界/修为消费、物品/经济/掉落权益、当前剧情与战斗不回退，进行中的战斗探索不被重置。完整进度依靠自动保存与重启恢复。序章/free继续完整快照，以后端profile.load_policy显示准确规则。

## 潜修显示
消费view.growth：active、available/settled、server_now、last_settled、rate.per_hour/per_day、offline_gain及clock_rewound。显示三位修为小数、每小时速率、从上次结算至本次校正的持续增长摘要；不提供离线领取按钮。progress由world.loot提供required/stage_label/next_label/milestone_label/conditions/ready，预计修为足够时刻只按当前境界/装备速率计算，不承诺自动突破或固定毕业日期。

250ms显示更新基于服务端余额与performance单调经过时长；15秒只读GET校正，不产生写入、不推进世界。clock_rewound时停止外推，保留已有修为并说明等待时钟恢复。未知写请求时保留最后校正值与原payload，不假定新速率生效。

周期GET同revision更新growth、snapshot全部只读page.stats/sections/summary、既有action可用状态及Boss/难度指标；现存正文、账表和目标文字同步patch，不重建表单、选项、输入节点或焦点。人物重复整数修为统计省略，由顶部唯一小数潜修显示代替。跨revision保留输入，提示显式同步，不偷偷用另一页新数据覆盖正在编辑的对象。正式写入仍由服务端结算，不提交客户端估算收益。

回拨保护明确为已结算余额保留；GET尚未持久化的预估权益会按服务端当前时间校正，不能承诺所有曾显示的available已永久锁定。clock_rewound时不继续本地外推，不以浏览器缓存高值冒充权威可花余额。

## 装备与挑战
人物页专用面板呈现weapon/armor/pendant/main/guard五槽、品质/方向/来源和同槽比较，before/after/delta全部服务端字符串；不自算属性、战力或修炼公式。选择物品可按uid定位其真实装备/强化/提质/分解actions，参数来自pages，不造操作。

秘境页提供章节/三难度选择、条件风险、固定敌强、共享日资格、奖励与确定保底预览；物品、待领来源与材料列表来自world.loot。独立世界Boss呈现本期ID、3次尝试、本次伤害、个人单次best、参考伤害、paid、下档差值与封顶状态；12回合不累计多场，只补权益差额，NPC模拟明确。操作仍统一真实actions/fields/confirm，当前战斗继续置顶不分页。

## 验证记录
首次隔离真HTTP联调遇到后端loot.project尚在实现的500，未修改数据或掩盖错误；后端checkpoint完整后已恢复并继续。以下为本岗位真实生产Handler/Store+Chromium自测，使用临时存档、可注入服务端时钟，无浏览器HTTP改钟接口或存档注入，不代替QA全套结论：

- 真实长线默认入世、5槽、每小时22.500、15秒只读GET校正；表单输入值/原DOM/焦点保留且revision不变。
- 真实公开操作取得材料→保底制作修炼法宝→同槽比较→装备，速率22.500变22.725；注入24小时后GET显示545.400，无额外领取；回拨时显示停止外推与校正说明。
- 真实世界Boss摘要、三难度条件/资格/保底预览、位置checkpoint确认取消、11页320px无横向溢出。
- PM发现“顶部已增长但人物stats/旧目标仍未同步”，已补全snapshot及现存只读文本patch，重跑真实15秒验证右侧summary与服务端一致，切页后的成长目标为最新数据；原输入DOM/焦点仍保留。
- 目标链点击只导航并定位现存真实action，revision不变；真实日常三选一接取→宗门交付/NPC互动两步→领取，周活动周期/奖励/进度均可达，0直接XP。
- 公开材料/制作/强化路线→难一完整副本→难二前两战→终Boss，浏览器实际观察蚀毒反制及2次残留毒，服丹后0次；320px交锋面板无横向溢出。其余盾/耗蓝状态按同一权威statuses渲染，三机制全规则结果由独立QA覆盖，不冒称本岗位都已逐场试玩。
- 上述浏览器流程未见JS异常。真实API/浏览器证据与独立QA数值/规则结果分开，不以v1.0证据代表R3通过。

## 主动玩法增强的界面闭环
世界总览最多3条实际缺口目标，按钮仅定位真实action，不自动提交；无合理推荐时由后端给免费恢复/采集。日/周活动使用r3_daily/r3_weekly/r3_activity:*稳定section ID置顶展开，accept/claim控件单独置顶、避免默认分页藏掉奖励；不因完成弹窗抢焦点。周期、双目标进度、奖励、已领/待领/过期说明均消费服务端文本。

副本选难预览显示mechanic，入场行动effect有同一规则；交锋横条展示battle.counterplay与statuses中的毒余次数、护盾、耗蓝反制或Boss12回合个人评分；结果使用真实events/记录。战斗8指令始终置顶、不受检索分页影响，不从动画或客户端HP变化计算伤害。

最终视口证据目录：artifacts/r3-qa/ui，desktop为1440×1000、mobile为320×900；fullpage仅补充，不以缩小长图代替可读审查。ui-integration-report.json记录目标/活动/只读校正/11页窄屏的实际通过项。最终完整测试与三套浏览器统一由QA执行；后续仅按明确缺陷修复，不主动扩展范围。

冻结前最后视觉调整仅收紧桌面页顶纵向留白和卷目介绍，保留小数速率/目标/全部内容；普通无notice的1440×900实际视口中，导航首项y≈597、首个真实目标按钮y≈855（高44），首屏可见并可操作。证据ordinary-no-notice-1440x900.png、ordinary-no-notice-desktop.png、ordinary-no-notice-mobile.png；有操作回执时允许页面自然增长，不删除错误或奖励反馈。当前static冻结，等待QA统一最终验收。
