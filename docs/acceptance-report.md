# 验收报告（云海御空 v2 阶段四：自由飞行、避障与性能 · 2026-10-21，分支 feat/flight-battle-v2）

**结论：用户视觉验收通过（2026-10-21）。**

## 已完成且已验证（本轮实际运行）
| 项 | 证据 |
|---|---|
| 白盒全量 | `python -m tests.parallel`：413 项、0 跳过，其中 6 项并发/SQLite 类失败（`503 SAVE_FAILED`、`attempt to write a readonly database`）。同一失败集合在 `origin/main` 上同样出现且逐次漂移，属本机抖动，与本分支改动无关；稳定复现的确定性失败 4 项，另有 1–3 项随机抖动。bundle 头部 `src-sha256` 与 `body-sha256` 均由测试校验一致 |
| 浏览器套件（本机 Edge，Playwright） | `browser_smoke`、`browser_world`、`browser_r3`、`browser_r4`、`browser_fx3d`、`browser_fx3d_real` **全部 passed** |
| 12 单位避障 | `browser_fx3d_real` 新增压力回放（首领 + 10 小怪 + 主角，6 拍，含群攻收 3 只、首领败亡溃散）：`agents=12`，全程最小石柱间隙 `clearance=2.47`（≥0 即从未触柱），避障介入 `avoids=47` 个 tick，AI 频率 `aiHz=30`，终局小怪全部倒下/溃散 |
| 性能（无头 Edge，`--use-angle=d3d11`） | 12 单位回放 `fps≈240`、`frameMs 4.2`、`drawCalls 46`、`triangles 131434`、`geometries 62`、`textures 31`，质量档 `level 0`（未触发降档） |
| 真实战报回放 | 序章/野外/副本/精英/世界Boss 在转向群驱动下终局状态与战报一致、小怪数与 HUD 一致 |
| 构建 | `npm run typecheck` 无错误，`npm run build` 后源码哈希测试通过 |

## 未验证 / 限制
- 真实 GPU 帧率（低端独显/核显、移动端真机）与长时内存**未测**；无头 Edge 数字非受控测量。性能阶梯（像素比 0.75 → 关远景细节 → 0.6）只做了代码路径，未在真实低端机上观察触发。
- 避障只针对近场三根石柱（`ARENA_PILLARS`）；远景石柱与浮岛不参与。冲撞是叠加在 AI 位置上的短脚本位移，未做探针（时长不足 1 秒，测得间隙仍 ≥0）。
- 「几何实例化」未做：小怪各自一套立绘网格，12 单位绘制调用 46，暂无必要；更大群体再议。
- 飞行观感（各敌形飞行程序、个性幅度）待用户视觉验收；目前所有敌形外观仍为紫晶翼狮王（D018）。

---

# 验收报告（云海御空 v2 阶段三：规则层真实小怪与群战 · 2026-10-21，分支 feat/flight-battle-v2）

**结论：用户视觉验收通过（2026-10-21）。**

## 已完成且已验证（本轮实际运行）
| 项 | 证据 |
|---|---|
| 白盒全量 | `python -m tests.parallel`：413 项、0 跳过，其中 6 项并发/SQLite 类失败（同一失败集合在 `origin/main` 上同样出现且逐次漂移，属本机抖动，与本分支改动无关；确定性失败 4 项，另有 1–3 项随机抖动。新增 `test_swarm_battle` 13 项，其后补群战×机制与存档校验用例，现 20 项；R3/R4 合法路线测试未改且通过；11 项首领机制测试用 `solo_battles` 固定为单体，断言不变） |
| 平衡 | `python scripts/swarm_balance.py`：7 类战斗 × 境界 0/2/4/6 × 4 策略 = **112/112 组在目标内**（拍数 ±15%（另容 1 拍）、剩余气血 ±10%、胜负一致）；白盒以 `--check` 纳入 |
| 浏览器套件（本机 Edge，Playwright） | `browser_smoke`、`browser_world`、`browser_r3`、`browser_r4`、`browser_fx3d`、`browser_fx3d_real` **全部 passed** |
| 三维群战 | `browser_fx3d`：合成群战战报建出 2 只小怪，跳到结果后小怪全倒/溃散；`browser_fx3d_real`：真实战报野外 2 只、副本镇守 4 只、精英 3 只，斗法台小怪数与 HUD 小格与战报一致，终局全部倒下或溃散；序章/世界Boss 无小怪 |
| SVG 降级 | 禁用 WebGL：SVG 舞台画出小怪，拖到小怪伏诛一拍其变淡，跳到结果后全部变淡 |
| 构建 | `npm run typecheck` 无错误，`npm run build` 后源码哈希测试通过 |

## 未验证 / 限制
- 前瞻几乎总是专注首领（首领败亡即胜、小怪伤害占比 30% 且分散），小怪主要由群攻收掉或在首领败亡时溃散；「先清小怪」的打法目前极少出现。
- 小怪暂为缩小的紫晶翼狮王立绘（D018 唯一怪物）；不同敌形的专属小怪待设定图。
- 小怪多的拍次回放会按错峰总长顺延（最长约 3 秒一拍），未做用户体感测试。
- 真实 GPU 帧率（低端/移动端）、长时内存未测；无头 Edge GPU 回放约 220–240fps，非受控测量。

---

# 验收报告（云海御空 v2 阶段二：战报精确同步 · 2026-10-21，分支 feat/flight-battle-v2）

**结论：用户视觉验收通过（2026-10-21）。**

## 已完成且已验证（本轮实际运行）
| 项 | 证据 |
|---|---|
| 白盒全量 | `python -m tests.parallel`：**400 项通过，0 跳过**（`test_fx3d` 改为校验新斗法台源码/bundle、旧 `battle3d.js` 与 `vendor/addons` 返回 404） |
| 构建 | `npm run typecheck` 无错误；`npm run build` 生成 `static/arena3d.js`，`test_frontend_build` 校验源码哈希一致 |
| 浏览器套件（本机 Edge，Playwright） | `browser_smoke`、`browser_world`、`browser_r3`、`browser_r4`、`browser_fx3d` **全部 passed**（D020 改动后重跑） |
| 真实战报回放 | 新增 `tests.browser_fx3d_real`：沿 R4 合法路线打出 序章（守阵石傀，8 拍胜）/野外（1 拍胜）/秘境副本镇守 Boss（3 拍胜）/支线精英商路炉甲（3 拍，含破盾）/世界 Boss（12 拍时限 defeat）真实战报，在 GPU 浏览器回放：三维启用、终局状态与战报一致（胜局敌方消散、时限 defeat 不倒下）、无页面异常；截图 `artifacts/fx3d-qa/real/`（不入库）；**passed** |
| 同步 | 命中时刻与飘字一致（D019 表）；慢帧分步追赶（SwiftShader 4fps 下不脱拍）；第 0 拍三维就绪后按 2.3 s 入场重排第一拍 |
| 文字战报退役（D020） | 回放卡只保留舞台/HUD/控制条/终局铭牌；五套浏览器套件在此改动后通过 |
| 降级 | 禁用 WebGL：无三维画布、SVG 版式可用；`reduced-motion` 不加载三维（`browser_fx3d`） |

## 未验证 / 限制
- GPU 浏览器（本机无头 Edge，`--use-angle=d3d11`）回放约 218–240fps，非受控测量；低端 GPU、移动端真机与长时内存**未测**。
- 所有敌形暂用紫晶翼狮王（D018），体型按首领区分；敌形专属外观待更多设定图。
- 冲击瞬间色差/泛光偏强（截图中可见），属观感调参，待用户视觉验收意见。
- 境界（tier）目前只影响主角灵气粒子与飞剑数，未像旧斗法台那样切换天时。

---

# 验收报告（三维斗法台「云海御空」· 2026-10-21，分支 feat/3d-battle-arena）

## 已完成且已验证（本轮实际运行）
| 项 | 证据 |
|---|---|
| 白盒全量 | `python -m tests.parallel`：**394 项通过，0 跳过**（新增 2 项：斗法台/后期扩展同源内置、GPU 资源释放且不发请求；终端词扫描纳入 `battle3d.js`） |
| 浏览器套件（本机 Edge，Playwright） | `browser_fx3d`、`browser_smoke`、`browser_world`、`browser_r3`、`browser_r4` **全部 passed** |
| 斗法台播放 | `browser_fx3d`：兽(首领·夜)/蛟(昼)/傀(暮)/影(晨) 四套外观 × 合成战报（覆盖 damage/shield/shield_absorb/heal/control/defend、法宝、同行、胜局）完整播放、跳到结果、合上后无残留画布；截图 `artifacts/fx3d-qa/`（不入库） |
| 单上下文/释放 | 战报开合 30 次：渲染器恒为 1，舞台几何/纹理不增长 |
| 窄屏 | 375×812：斗法台可见（≥150px 高，竖屏改斜对站位），无横向溢出 |
| 降级 | 禁用 WebGL：无三维画布、`data-fx3d` 不设置、SVG 可见、跳到结果可用；`reduced-motion` 不加载三维 |
| 控制台 | 套件内无页面异常/控制台错误；开发时内置浏览器无错误 |

## 未验证 / 限制
- 真实 GPU 帧率与长时内存**未测**：SwiftShader 下斗法台约 8fps（截图时序因此滞后于真实节奏）；开发时内置浏览器硬件渲染观察约 84fps，非受控测量。
- 服务端真实生成的凡界战报 + WebGL 的组合未在自动化中单独跑（合成战报已覆盖全部事件类型；`browser_world/r3/r4` 无 GPU 参数，走降级路径）。
- 美术为几何体拼装的低多边形风格，无外部模型/贴图；外观线索只取前端快照，后端与战报结构未改。
- 变更**尚未提交**。

---

# 验收报告（体验重构 · 2026-10-21，分支 feat/three-battle-fx）

## 已完成且已验证（均有本轮实际运行证据）
| 项 | 证据 |
|---|---|
| 白盒全量 | `python -m tests.parallel`：**392 项通过，0 跳过**（改前基线 385） |
| 浏览器套件（本机 Edge，Playwright） | `browser_smoke`、`browser_world`、`browser_r3`、`browser_r4`、`browser_fx3d` **全部 passed**；四个旧套件原先因多账号登录、自动同步、自动斗法而失效，已按现行行为修复（见下） |
| 凡界逐页审计 | `scripts/audit_pages.py`：11 卷目 × 4 视口 = 44 组，一屏/横向溢出问题 **0**，控制台错误 **0**，页面异常 **0**；手机视口按钮均≥44px |
| Three.js 战报特效 | 序章与凡界战报事件驱动；序章每拍按气血实际变化追加 `fx_only` 事件（`test_prelude_battle_frames_carry_fx_events_matching_hp_changes`）；真实服务端序章战斗出现浮字与尾迹 |
| Three.js 舞台氛围 | 透视云雾视差 + 境界色灵气；洞府页灯笼数=设施等级之和（`browser_fx3d` 断言 6→0） |
| 单上下文/释放 | 战报让出并恢复舞台；开合 30 次后渲染器恒为 1、几何 3/纹理 2 不增长、无残留战报画布 |
| 降级 | 禁用 WebGL：无 3D 画布，战报与页面照常；`reduced-motion` 不加载三维层 |
| 下一步引导 | 服务端 `guide`（契约测试）+ 前端“去办理”按钮，真实浏览器点击后切页并高亮目标卡 |
| 破坏性确认 | 新增封界、撤离副本、辞别师父确认（联动 `tests.browser_*` 的确认流程通过） |
| 任务簿 | 无名称的“状态/奖励”行已带任务名 |
| 规则修订 | AGENTS.md、README、V4 规范按你的裁决允许同源内置第三方库 |

## 旧浏览器套件的修复内容（如实说明）
- 浏览器启动：不再硬编码 `/usr/bin/chromium`，新增 `tests.support.launch_browser`（`GUIXU_BROWSER` 环境变量 → 自动探测 Chromium/Chrome/Edge）。
- 登录：新增 `attach_session`，把默认账号会话 Cookie 注入浏览器。
- 已退役的手动保存/载入断言改为“刷新后从服务端恢复且一致”；响应丢失场景改为现行的“断线→原操作编号自动重放，只记一次”；r3 的“只读刷新不写库”改为比较 `current/requests` 表；r3 中点击式战斗时代的“毒状态可见”断言因战斗已自动化而移除（由副本通关断言覆盖）。

## 未完成 / 未验证
- **真实 GPU 帧率与小时级内存**：只有 SwiftShader 软件渲染数据（舞台约 13–22fps，触发自动降档，证明降级链路有效，不代表真实硬件）。
- **凡界战报的 3D 特效**：`browser_world/r3/r4` 在无 GPU 参数下运行，走降级路径；凡界真实战报 + WebGL 的组合未单独验证（序章真实战斗和合成战报已验证）。
- 命中爆发/冲击环未单独截图；仅核对了弹道对齐与舞台/灯笼截图。
- `guide` 只细分到 `_advance_reason` 的各条件；更深目标（师友好感等）未细分。
- 事件 toast 约 3 秒内遮挡右栏页签（P3，未改）。
- 变更**尚未提交**。

## 已知风险
- 增加约 690KB 静态库，仅在需要三维时按需加载。
- 舞台氛围替换了该宿主上的 Canvas2D 灵气；WebGL 失败/丢失时自动回到 2D。
- 帧率数据环境相关，不外推到低端设备。
