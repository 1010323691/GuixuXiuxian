> 序章历史文档：本文件保留原v0.1.0范围与证据；完整凡界的当前契约和验收见 `docs/iterations/`，不能用本文件代替W1结论。

# 架构审查记录

## 审查范围与状态
ARCH-02：只读审查规则、存储、HTTP 和前后端契约，不修改实现。已阅读最终决策、GDD和API，并实际审查config/rules/storage/server及static/app.js。下文区分静态结论、快速诊断与未执行的QA验收。

## 契约预审
1. 已同步：GDD最终修炼6+2×realm、强攻耗灵力6，并改为53动作路线；早期旧数值冲突已消除。
2. 已同步：GDD明确单手动slot、新局清slot、全局revision与请求账本不回退；不需要game_id。
3. 实现检查项：所有JSON/params须严格类型校验；bool不可当整数，params不得为数组/null。普通动作应只接受空params，travel仅region字符串、challenge仅enemy字符串；未知字段/错误类型400，合法类型但未知目标或条件不满足422。此项为边界建议，若偏离需明确记录。
4. 实现检查项：幂等比较含路径及完整规范化载荷；应先查ID后查revision；同ID同载荷读取最新快照duplicate:true/events:[]。load仅state回退，save也加revision，新局清slot但保留账本。
5. 实现检查项：每个成功提交必须写state/revision/slot/requests同一SQLite事务；拒绝或提交前故障不得改变任何字段。启动校验损坏及schema时不得初始化覆盖已有文件。
6. 实现检查项：view.actions须包含当前情境的禁用原因和实际确定性成本/收益，不以UI禁用替代规则校验；所有权威状态在后端，客户端不传资源或敌人生命。
7. 实现检查项：静态白名单、JSON体上限、自定义请求头、Origin/Host校验、统一中文错误、无CORS与回溯泄漏。

## 实际代码审查
已读 `game/config.py`、`game/rules.py`、`game/storage.py`、`server.py`，并用临时目录与临时HTTP端口做快速诊断。

- R01（中，已修复并复查）：`validate_state` 的region未先校验字符串，list/dict造成TypeError；姓名无效会抛GameError，非同一存档校验异常。现已先判region类型并将姓名GameError转ValueError，临时坏数据检查均按ValueError拒绝。
- R02（中，已修复并复查）：project的恢复/收益/攻击显示名义数值，在上限或敌人低血时与实际到账不同。现已明确“最多”和上限截断，攻击显示min(伤害,敌hp)，静态复查通过。
- R03（中，已修复并复查）：shadow胜利标记未要求realm=3，低境界completed档可通过校验；现已逐个验证首胜敌人解锁境界；低境界shadow首胜实测拒绝。
- 已核对：最终修炼收益6+2r、强攻消耗6；params必须是字典且键集合精确；布尔数值被拒绝；battle流程胜利先于敌方反击，败退留1血；travel不加actions_taken；投影复用check给出禁用原因。


## 存储与HTTP实际审查/快速诊断
- 存储使用每请求独立连接、BEGIN IMMEDIATE、状态/slot/revision/requests同事务；无可变内存权威缓存。异常rollback/finally close；幂等先于revision检查，规范化载荷包括端点。save/load均递增，new-game清slot且不清账本，与契约一致。
- 临时目录顺序执行new-game→cultivate→save→cultivate→load，载入修为回退至6而revision递增至5；重试旧cultivate ID得到最新revision5、duplicate=true、events=[]，通过。
- 临时DB创建拒绝requests INSERT的SQL trigger注入事务后半段失败，行动状态、revision、账本整体未变，通过。未模拟真实磁盘满/断电，不能将此等同断电耐久性实测。
- 将临时数据库替换为损坏字节后重新初始化，DatabaseError拒绝且原字节未变，通过。静态检查未知schema与state/slot校验不自动清档。
- 临时HTTP端口实际请求health 200，错误params数组/bool revision/额外params均400，异源Origin 403，revision保持1，通过；静态文件白名单与无CORS、响应CSP存在。未在本审查执行浏览器主流程，交由独立QA。
- R04（低，已修复并复查）：JSON `1e999`先前会解析为inf并错误映射503；server现用parse_float拒绝非有限数。真实临时HTTP复测400 BAD_REQUEST，revision保持0，通过。

## 前端一致性只读审查
已阅读static/app.js。UI使用textContent、服务端actions与完整快照；拒绝低revision覆盖；请求期间busy锁；未知结果保留原ID和载荷，明确重试；新局/载入确认符合契约。

- R05（中，已修复并复查）：共享localStorage键会使标签页互相覆盖待确认请求。现已全部切换sessionStorage，写入/移除/恢复均按标签隔离且刷新保留，旧共享storage监听已移除。静态复查通过；浏览器多标签刷新恢复场景由QA独立执行。

前端最终展示分组只改变显示，不改变提交动作、params或后端可用性；可选group字段已写入API。新增加的分类不引入客户端结算规则。

## 当前结论
未发现行动事务、去重、revision与新局/载入路径的数据一致性阻断问题。R01–R05均已修复复查，无开放审查项；完整通关、浏览器与并发负载结果以QA报告为准。本审查只改文档，不改实现。


## 最终交接与验证边界
架构审查完成，未修改实现；仅维护API、ARCHITECTURE与本报告。项目经理另报告最终unittest共20项全部通过（6.375秒），此为PM运行结果，非本岗位重复执行。本人实际执行的快速诊断已列于上文，不替代QA的完整通关与独立浏览器验收。未做真实断电、磁盘满、长时间负载或公网部署验证；应用定位仍是本地单人游戏。
