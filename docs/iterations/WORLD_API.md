# W1 世界 API 实施契约

状态：已实施并与冻结代码对齐；数值/ID以WORLD_DESIGN和world_config为准。本轮仅单机NPC模拟，无真实联网，不创建peer端点或net.py。

## 兼容入口与生命周期
保留docs/API.md全部端点、写信封与错误形状。state新增world，旧realm保持0–3；world.active默认false，原legacy动作不推进世界动态。玩家通过world_enter显式开启完整世界（要求序章completed=true且world.active=false），world_advance控制结丹至渡劫，不能修改旧breakthrough语义。

所有新增操作仍POST /api/action，action为world_*，params由服务端动作及fields构造。信封request_id/expected_revision不变；失败不改任何资源或日志，成功同事务写state/revision/requests。save/load包括整个world，global revision和requests不回退；NPC排名/市场均在state内可回档。

## 共享Python函数（开发维护game/world.py）
```python
initial_state()
migrate_v1(state)
validate(state)
apply_action(state, action, params)
project(state)
```
以上为实际Python签名，无运行时类型注解。initial_state返回61字段world子树；migrate_v1返回完整深拷贝state（传None时仍为None），不会改旧字段；validate接收非空完整state并返回None，坏嵌套统一ValueError；apply_action返回完整新state和字符串events列表；project接受已有角色的完整state并返回下述投影。None开局状态由rules入口处理。
world接收完整state，但世界资源只修改嵌套world，不改变顶层序章stones/herbs/cultivation/hp/mp等资产；必须深拷贝，不修改输入。顶层actions_taken与logs是全游戏历史：world实质成功动作也计数+1并追加日志，世界免费旅行/切页及save/load不计；world_enter计全局+1但不推进world.tick。world.tick仅实际消耗世界行动推进（world_enter、world_travel不推进），AI仅据此结算。rules负责new_game接入、world_委派、完整校验与投影。规则纯函数不得加全局revision/写盘；storage唯一处理事务。world_config由主策划维护，world/rules由开发维护，storage/server由架构岗位维护。

## view.world固定形状
已有角色的成功快照保留原view字段并增加view.world。state=null的未开局快照不含view.world，客户端以原creation流程展示；不能直接对None调用world.project。世界投影核心结构为：
```json
{
  "version": 2,
  "active": false,
  "pages": [
    {
      "id": "world",
      "label": "九州",
      "title": "九州修仙界",
      "description": "…",
      "stats": [{"label":"…","value":"…"}],
      "sections": [{"title":"…","body":"…","rows":[{"label":"…","value":"…"}]}],
      "actions": []
    }
  ]
}
```
version恒2，active为必需布尔且与state.world.active一致；当前实现另固定返回stage（中文境界字符串）、summary（中文目标/结局字符串）、resources（下述数组）和battle（下述对象或null）。页面ID固定按顺序为world/character/sects/social/craft/exploration/estate/market/quests/achievements/arena，共11页；UI按pages动态导航，切页不写库、不推世界时间。active=false时可展示锁定信息，但UI不得自动切世界模式或读rawstate自行判断。title/description/label/body/row value全部中文可显示文本，value统一字符串。body可省，其余列表为空时[]。未实现系统不能伪造已可玩内容，NPC竞技/跨域赛/榜单/市场描述必须明确“本地NPC模拟”。仙界不提供可进入页。

page.actions沿用标准 `{id,label,detail,cost,effect,enabled,reason,params,primary,group?}`，禁用必须给中文reason，primary每页至多1。可附confirm（中文字符串；仅确有不可逆/高代价时使用）和fields：
```json
[{"name":"quantity","label":"数量","type":"number","min":1,"max":10,"required":true}]
```
field.type仅text|number|select；name是params键且每动作唯一。text可有maxLength，number必须整数min/max，select必须options=[{value,label}]，value为稳定字符串。required为bool；未填可选项不提交，不发送undefined/null冒充合法值。fields初版不支持动态联动或任意对象。

UI将base action.params与fields用户值合并提交，field.name不得与静态params键重叠，不允许用户覆盖静态目标：number转换整数（不能NaN/Infinity/bool），text/select为字符串；服务端重新校验完整params精确键集合、类型、枚举和范围。禁止提交整个action对象，禁止客户端提供资源/随机结果/胜负。禁用/展示仅作引导，不代替后端权威校验。目标较少时优先后端展开为多条无fields动作，避免不必要表单。

## 错误、幂等与迁移
沿用400 BAD_REQUEST（格式/字段/类型）、422 ACTION_UNAVAILABLE（合法动作条件不符）、409 STALE_STATE/REQUEST_ID_REUSED、503 SAVE_FAILED；同ID同载荷返回最新快照duplicate:true且events=[]。任何阶段UI保留pending原信封供安全重试。

schema1启动不得隐式改库；--migrate-save明确迁移current与slot并先验证独立备份，旧revision/requests保持。空state/slot保持null；health迁移后schema_version=2。未知高版本/损坏拒绝启动，不能用空档200假装ready。具体备份回滚步骤见WORLD_ARCHITECTURE。

## 已实施世界资源与战斗投影
`view.world.resources`为4项数组，每项`{id,label,value,max}`，value/max为整数：world_hp、world_mp、world_xp、world_stone分别显示世界生命、灵力、道行与钱包；hp/mp上限由当前属性派生，xp/stone上限999999。旧序章rawstate不充当世界UI资源来源。

`view.world.battle`非战斗为null，战斗时精确：
```json
{"name":"敌人中文名","hp":120,"max_hp":200,"intent":"常规攻击30","page":"exploration"}
```
name/intent为中文字符串，hp/max_hp为整数；page为exploration（普通世界战斗）或arena（本地NPC演武/三域赛），用于提示回到已有页面。具体战斗指令仍来自该page.actions，不由前端按kind构造。原`view.battle`继续只描述序章战斗；进入世界后应使用view.world.battle。敌方原始强度、模拟耗材快照等内部字段不直接作为战斗展示API，见WORLD_DATA.md。

## 已实施动作目录与内容
世界共有79种SCHEMAS动作ID，精确params与页面入口逐项见WORLD_DATA.md；可执行目录源为game/world.py:SCHEMAS，内容ID源为world_config，前端只按返回actions/fields提交。数组常量并非网络协议：条件性入口会随当前状态出现/消失。world_enter仅在序章全局动作中呈现；已入世view.actions为空，交互取view.world.pages。世界只读投影不生产、不结算，不以按钮存在代替行为验证。
