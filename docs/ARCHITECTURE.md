> 序章历史文档：本文件保留原v0.1.0范围与证据；完整凡界的当前契约和验收见 `docs/iterations/`，不能用本文件代替W1结论。多用户在线化之后的存储与并发架构见文末“多用户在线化增量”一节及 `docs/iterations/MU_DESIGN.md`，正文中关于单文件单角色、手动 slot 与“不支持公网多用户部署”的描述属升级前行为。

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

---

# 多用户在线化增量（现行）

权威设计：`docs/iterations/MU_DESIGN.md`（v2，方案B）；序列图与类图 `MU_sequence.mermaid`、`MU_class.mermaid`；接口 `docs/API.md`。以下概括现行架构，实现完成度与测试结果以 QA 记录为准。

**单库布局**：所有账号共用一个 `data/game.db`（运行期含 `game.db-wal`、`-shm`），表：`meta`、`accounts`、`sessions`、`login_attempts`、`current(user_id 主键)`、`requests(主键 (user_id, request_id))`、待认领区 `legacy_progress`/`legacy_requests`。库布局版本用 `PRAGMA user_version`（首版1），进度 JSON 版本仍为 `config.SCHEMA_VERSION=2`，二者独立。启动检查 `integrity_check`、`journal_mode=wal`（网络盘不支持，拒绝启动）、`foreign_keys=ON`；旧格式库、未知版本或损坏文件拒绝启动并保留原件。

**数据访问层**：`game/storage.py` 的 `Database`（连接、布局、备份）、`ProgressRepo`（进度表 SQL 的唯一所在，每条带 `user_id` 谓词，并有运行时断言、AST 静态扫描与全量 SQL 采集三重兜底）、`Store(db, user_id, clock)`（面向业务的用户作用域门面，方法签名里没有 user_id，业务代码无法传错用户）。身份只来自会话 Cookie → `Principal.account_id` → `App.store_for()`，请求中的任何用户参数一律拒绝。

**写事务协议**：事务外读状态与账本并完成规则/成长/冷却计算（`now` 取在读取之后）；事务内 `BEGIN IMMEDIATE` 只做三步——复核请求账本、`UPDATE current … WHERE user_id=? AND revision=?` 乐观比较并交换、`INSERT INTO requests`——然后 COMMIT，`synchronous=FULL`。COMMIT 成功后才返回成功；失败回滚并返回 503，同 `request_id` 重试幂等。同账号并发不同请求由版本比较裁决，后到者 409 `STALE_STATE`，不丢更新、不自动重放；正确性来自 SQLite 的 CAS 与复合主键，不依赖进程内锁，多进程共享同一数据目录同样成立。`database is locked` 在 5 秒忙等耗尽后至多重试 2 次，仍失败则 503。

**认证**：`game/auth.py`（scrypt 加盐哈希在任何数据库事务之外计算、会话 Cookie、登录/注册/改密限流）、`game/settings.py`（允许主机、Secure Cookie、注册开关、反代信任等部署参数）、`game/admin.py`（`--create-user`、`--reset-password`、`--legacy-status`、`--backup` 等一次性运维命令）。

**迁移**：`game/legacy.py`。`--migrate-multiuser` 先 `sqlite3.backup` 校验备份旧库，再建新布局库、把旧进度导入待认领区并原子换位；`--claim-legacy` 在单个事务内认领给已存在的账号，并在此时才套用内容升级。严禁自动继承，任何网络路径都读不到待认领区。

**备份与容量**：`--backup` 对单个库做 WAL 在线备份，是整库快照而非按用户；`requests` 账本随操作线性增长，本版不裁剪。规模假设为单机单库、数十到数百活跃账号；写吞吐上限约为一次 WAL 同步的速率，`synchronous=FULL` 的目标机 P99 须由 QA 实测，不得为性能私自降级。

**已知风险**：漏写 `user_id` 串号（三重兜底）、单写锁与磁盘延迟、单文件损坏影响全站（在线备份+启动检查）、并发写重构引入的竞态（并发测试最高优先级）、开放注册公网部署需 HTTPS 反代与限流、scrypt 在目标机耗时待实测。
