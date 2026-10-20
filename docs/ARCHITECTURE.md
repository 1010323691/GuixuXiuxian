> 序章历史文档：本文件保留原v0.1.0范围与证据；完整凡界的当前契约和验收见 `docs/iterations/`，不能用本文件代替W1结论。

# 首版架构实施契约

状态：按项目经理裁决冻结；数值与玩法服从 GDD。使用 Python 3.11+ 标准库、原生 HTML/CSS/JavaScript。无安装依赖、外部账号、CDN 或联网运行要求，默认 `127.0.0.1:8000`。

## 模块与所有权
- 开发：`server.py`（路由、静态服务、参数）、`game/config.py`（内容和数值）、`game/rules.py`（纯确定性行动及展示投影）、`game/storage.py`（原子存储和幂等）。文件可合理合并，但规则不得依赖 HTTP 或磁盘。
- 视觉交互：`static/index.html`、`static/styles.css`、`static/app.js`；同源 fetch，所有成本、禁止原因与行动由服务端返回，不复制公式。
- QA：`tests/`，临时数据目录运行标准库 unittest/HTTP 与 Playwright 验证；真实玩家数据不得作为测试输入目录。
- 项目经理：GDD、任务、决策及交付说明。接口固定见 API.md，修改需协调前后端及 QA。

建议启动：`python server.py --host 127.0.0.1 --port 8000 --data-dir ./data`，数据目录忽略进 Git；此命令是待实现约定，尚未验证。不使用后台时间推进、随机数、离线收益或前端权威状态。

## SQLite事务与生命周期
按项目经理裁决使用标准库sqlite3，单一数据库保存 current（schema_version、revision、state JSON）、manual checkpoint（slot JSON）和requests（request_id、规范化载荷）。revision初始0、state/slot初始null；每个成功写操作加1，包括新局、save、load；GET、拒绝、幂等重试不加。载入只替换state，绝不恢复旧revision或requests。新局清空slot以防跨角色误载。无需game_id，单调全局revision防止旧页覆盖。

每请求独立连接，有限busy_timeout，使用默认DELETE journal及synchronous=FULL，无WAL/备份轮转。所有修改 `BEGIN IMMEDIATE`：查请求ID → 比较载荷 → 校验revision → 纯函数产生候选 → 校验不变量 → 同事务写state/slot/revision及请求账本 → commit。只有提交后返回成功。异常rollback，不发布候选内存状态。以数据库为唯一权威，不保留可与持久化分离的可变全局缓存。

同ID同载荷重试不执行旧行动，读取最新快照并返回 `duplicate:true`，其events为空；新成功及GET为duplicate:false。冲突检查在幂等查询之后。首版保留完整请求账本，适用于短篇单人游戏。SQLite写锁协调跨请求；不额外引入进程文件锁。

启动检查完整性、schema与state/slot合法性；损坏、不支持版本拒绝启动并保留原件，不自动覆盖或重置。README提供停服后复制完整数据库的备份/恢复步骤；恢复前先备份当前文件。手动slot是游戏检查点，不是独立灾备，不引入自动备份轮转。存储故障返回503且不得向用户报告行动成功。

## 行动与存档
rules 返回新状态和本次事件，不读磁盘/真实时间。投影函数根据状态/GDD产生中文可用行动、成本、效果和不可用原因。所有资源与战斗结果在后端结算，非法行动不消耗、不推进回合。

工作快照每个成功写操作自动保存。`save` 将当前游戏 state 深拷贝至单 slot，保留工作状态；`load` 将 slot 深拷贝至当前 state，全局revision继续增加且请求历史保留；允许战斗中保存/载入，只要完整敌人状态和行动位置也序列化。新局替换当前state，清空手动档、保留请求历史。仅新局覆盖已有进度、载入覆盖工作快照要求前端明确确认，常规行动和存档不弹确认。创建参数、动作与数值由 GDD 定义。

## HTTP 与错误边界
固定静态文件白名单；限制JSON体（建议16KiB）、校验字段/整数（拒绝bool）、动作白名单，统一JSON错误。默认回环绑定，不启用 CORS；写操作必须同源自定义 `X-Game-Client: guixu-web` 头并校验存在的Origin与Host匹配，拒绝非预期Host，降低外站驱动本地写入风险。不支持公网多用户部署。

健康检查必须反映存储可用；保存异常返回503，未知异常返回500及中文说明，日志记录诊断、不向客户端暴露回溯。前端网络未知结果保留pending payload与ID供重试；不把超时当失败重做。

## 必须验证
纯规则完整通关及防卡死、确定性战斗/奖励一次性；SQLite事务失败回滚、重启续玩、损坏拒绝覆盖；同ID重试/异载荷冲突、并发revision冲突、载入后旧页冲突、重复新局不丢进度；真实浏览器主流程、中文窄屏、键盘与错误恢复。尚无实现或测试通过声明。
