# 视觉与 Three.js 方案

## 三维化候选清单
| 内容 | 现状 | 三维方案 | 数据绑定 | 成本 | 优先级 | 状态 |
|---|---|---|---|---|---|---|
| 斗法战报特效 | SVG 圆点弹道 | 正交相机叠加层：粒子池+冲击环，阶段=蓄力/飞行/命中/收尾 | `battle_report.frames[].events`（type/source/target/amount） | 1 个上下文、≤520粒子、≤8环 | 高 | **已实现** |
| 境界灵气舞台 | Canvas2D 粒子 | 透视相机：6 层云雾视差 + 境界色灵气粒子 | 境界 tier（`--aura-N`） | 1 个上下文、≤160粒子 | 中 | **已实现**（`mountStage`） |
| 洞府场景 | 静态 SVG 横幅 | 灯笼光点数 = 三项设施等级之和（0–9） | 世界视图 `estate` | 低 | 中 | **已实现** |
| 秘境场景 | 静态 SVG 横幅 | 沿用舞台氛围；独立 3D 场景不做 | — | 高 | 低 | 未做（收益低） |
| 数据管理页（背包、市场等） | HTML/CSS | 不三维化 | — | — | — | 保持 |

## 实现（`static/fx3d.js`）
- 每次打开战报创建 1 个 `WebGLRenderer`（低功耗、无抗锯齿、像素比≤1.5），合上即 `dispose()`+`forceContextLoss()`；几何/材质/纹理均释放。
- 阶段配置表 `PHASES`（毫秒，倍速统一折算）；强度 = 伤害/敌方气血上限×3（夹在0.25–1），粒子数与冲击环半径随之变化。
- 时间线以内部时钟推进，暂停/倍速/跳转天然生效；`clear()` 在每拍切换时清空残留；标签页隐藏时停帧。
- 降级：`webglAvailable()` 探测 → `create()` 返回 null；`webglcontextlost` 隐藏画布，SVG 继续；`reduced-motion` 不加载。
- 坐标：相机按 SVG `viewBox` 的 meet 适配对齐（已在真实浏览器中核对弹道与 SVG 轨迹重合）。

## 统一管理器（`static/fx3d.js`）
- **单上下文**：`liveRenderers` 记录存活渲染器；战报 `create()` 先 `suspendStage()` 销毁舞台，合上 `dispose()` 后 `resumeStage()` 重建。
- **舞台**：`mountStage({host,tier,color,page,estate})`，宿主/参数变化走 `update`；`app.js` 的 `stage3d` 按需 `import("/fx3d.js")`，失败/`reduced-motion`/无 WebGL 保留 Canvas2D（`body.stage3d-on` 时 2D 画布隐藏）。
- **降级与性能**：≈30fps 上限；宿主不可见/页面隐藏即停帧；DPR≤1.5；按 `hardwareConcurrency` 选初始质量档，连续 90 帧均值>45ms 自动降一档；`stats()` 暴露 fps/帧耗时/质量/几何与纹理数/绘制调用。
- **验证**：`tests.browser_fx3d`（SwiftShader）：单渲染器、灯笼随洞府等级、战报开合30次几何3/纹理2不增长、无 WebGL 降级。

## 未覆盖
真实 GPU/低端 GPU 帧率、小时级内存曲线**未测**。SwiftShader 软件渲染下实测约 13–22fps（舞台）并触发自动降档，仅说明降级链路有效，不代表真实硬件表现。
