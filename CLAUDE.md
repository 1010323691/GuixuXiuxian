# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` 已退役，其仍有效的约束全部并入本文件；各轮交付状态/验收证据不在此重复，以 `docs/` 下对应文档与最新实测为准。

## 项目概览

HTML/CSS/JavaScript + Python 的中文文字修仙游戏《归墟修行手札》，现为**服务化多用户在线游戏**：玩家注册/登录，各账号进度以 `user_id` 隔离，同一服务进程、同一个 `data/game.db` 承载所有账号。序章（v0.1青岚短篇）之外，当前实现完整「凡界」（势力、功法境界、宗门师徒家族、四艺、秘境、副本Boss、经济拍卖、NPC任务、成就、赛季）。仙界仅保留版本扩展，不纳入本版。

- 所有社交/竞技/拍卖都是 **NPC 模拟**，不是真人 PVP/跨服/玩家互市；多账号只互相隔离，账号间无任何互动。NPC 模拟不得伪装真人。
- 所有按钮必须有实际后端/状态；所有后端能力必须有可达 UI 入口（含注册、登录、退出、改密）。
- 历史文档中的“存档/载入”描述的是 v1.2 单机行为，不是现行行为。

## 常用命令

```sh
python server.py --host 127.0.0.1 --port 8000 --data-dir ./data   # 启动（或双击 启动游戏.bat / python scripts/launch.py）
python -m tests.parallel                 # 并行白盒全量（约30–45秒）；追加子串只跑匹配的测试
python -m tests.parallel -j 4 test_mu    # 指定并发/子串
python -m unittest discover -s tests -v  # 串行全量
python -m unittest tests.test_growth     # 单个模块（亦可 tests.test_growth.Class.test_x）
python -m tests.browser_all              # 浏览器套件并行（默认3并发，约5分钟，需 Playwright + Chromium/Edge，GUIXU_BROWSER 可指定浏览器）
python -m tests.browser_world            # 单个浏览器套件（另有 browser_smoke/r3/r4/fx3d/fx3d_real/sect3d）
npm install && npm run build             # 重建前端 bundle（npm run typecheck 做类型检查，npm run watch 监听）
python scripts/swarm_balance.py --check  # 群战平衡校验
python server.py --backup --data-dir ./data  # 整库在线备份到 data/backups/
```

运维一次性命令（执行后退出、不启动服务）：`--create-user`、`--reset-password`、`--legacy-status`、`--claim-legacy`、`--migrate-multiuser`；详见 `README.md`。

## 架构

- **后端（仅标准库 Python，不引入第三方包/外部付费 API）**：`server.py` 为 HTTP 入口与 CLI；`game/` 为领域层——`storage.py`（唯一数据访问层）、`auth.py`（账号/会话/scrypt）、`world.py` + `world_config.py`（凡界规则与内容）、`rules.py`（序章）、`growth/cadence/journey/loot/activities.py`（长线成长、节奏、故事、掉落、活动）、`legacy.py`/`admin.py`（旧库迁移与运维）。接口契约见 `docs/API.md`、`docs/iterations/WORLD_API.md`、`WORLD_DATA.md`。
- **前端（`static/`，无构建即可运行）**：`index.html` + `app.js` + `styles.css`（V4「青绿金碧」设计系统，规范见 `docs/iterations/V4_DESIGN_SYSTEM.md`）。
- **TypeScript 3D 包（仅开发者需要 Node）**：`src/battle/` → `static/arena3d.js`（斗法台「云海御空」，战报回放、群战、飞行转向），`src/sect/` → `static/sect3d.js`（三维宗门主界面；HUD 为 `static/sect_hub.js`，只读快照、不发请求）。**产物提交入库**；`scripts/build.mjs` 在产物头部记录 `src-sha256`（源目录 + `package.json`）与 `body-sha256`，`tests/test_frontend_build.py` / `tests/test_sect3d.py` 只校验哈希，不重建。**改 `src/battle/**`、`src/sect/**` 或 `package.json` 后必须 `npm run build` 并提交重建产物。**
- 第三方前端库只能同源内置固定版本（`static/vendor/three.module.min.js`，Three.js r170；three.quarks、postprocessing 打包于 arena3d），不得改用 CDN，且必须有无 WebGL 的降级路径（SVG 战报、二维「宗门图录」）。
- 战斗为自动斗法（点击式战斗已退役）；响应带不入库的 `battle_report`，前端按其精确同步回放。独立实验 `prototypes/r5-combat/` 不得改写正式 `game/static/data`。

## 多账号与数据规则（现行）

- **身份与隔离**：账号身份只来自服务端会话 Cookie，请求体/URL 无用户参数。进度表 `current`、`requests` 以 `user_id` 隔离；**所有进度 SQL 只允许出现在 `game/storage.py`，且必须带 `user_id` 谓词**，不得绕过该层。
- **自动保存**：无手动存档/载入，`/api/save`、`/api/load` 为 404。写操作在事务提交后才返回成功；提交失败整次回滚返回 503，界面提示“进度保存失败…当前操作未生效”。库使用 WAL 与 `synchronous=FULL`，写事务只做乐观版本校验+更新+登记请求，规则计算在事务外。
- **并发**：世界操作沿用 `request_id` 与 `expected_revision`，冲突 409；revision/请求账本不得回退；world 资产与序章资产隔离。
- **旧库**：旧单机格式的 `data/game.db` 会被拒绝启动，须停服后 `--migrate-multiuser`（schema1 另加 `--migrate-save`，先备份），旧进度入“待认领区”，由运维 `--claim-legacy 用户名` 认领；严禁首位注册者自动继承；损坏/未知 schema 拒绝，禁止静默清档。
- **备份/部署**：不要手拷运行中的 `game.db`（漏 WAL）；WAL 不支持网络盘。默认只监听本机；对外须 `--allowed-host`，公网开放注册必须置于 HTTPS 反向代理后并加 `--secure-cookies`。
- **术语**：玩家可见文案用“进度/进度已同步/登录后恢复进度”，不得出现“存档、读档、载入、检查点、保存位置、单机”（历史文档除外），由 `tests/test_terminology.py` 扫描兜底。

## 工作约束

1. **浏览器套件只在收尾时跑**：`python -m tests.browser_all` 及各 `tests.browser_*` 耗时长，当前轮次所有修改结束后才运行；修改过程中用 `python -m tests.parallel` 和临时脚本局部验证。
2. **不做手机端适配**：不新增或调整针对手机宽度的布局、样式与交互。
3. 使用现有检出，除用户明确要求外不创建 Git worktree；保留玩家数据与现有修改，测试/迁移不得覆盖真实玩家数据（测试用独立临时数据，不对玩家 data 注入故障）。
4. 完成状态仅按最新代码和当轮实际证据，不沿用历史通过结论；修复后按影响回归，不删除有效断言，不把未运行/跳过当通过。
5. 协作与岗位流程文档在 `docs/studio/`（`README.md`、`TASKS.md`、`DECISIONS.md`、`roles/`）；新决策/任务记入其中。
