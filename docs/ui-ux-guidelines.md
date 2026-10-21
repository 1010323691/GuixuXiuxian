# UI/UX 规范

视觉与交互规范沿用并以 **`docs/iterations/V4_DESIGN_SYSTEM.md`（青绿金碧）** 为唯一来源：两层 token、五态按钮、类别字牌事项卡、一屏不滚动、分页、减少动态效果支持、对比度≥4.5:1。

本轮增补：
1. **三维特效**只用于战报回放，由 `static/fx3d.js` 统一管理，页面其他处不得自行创建 WebGL 上下文。
2. 三维层始终是**增强**：`prefers-reduced-motion` 下不加载；无 WebGL、模块加载失败、上下文丢失都回落到原 SVG 演出，信息（数值浮字、日志、条）不依赖三维层。
3. 三维画布 `pointer-events:none`、`aria-hidden`，不影响键盘与读屏。
4. 第三方库只能同源内置于 `static/vendor/`，固定版本，不用 CDN。
5. “页面应回答：我在哪/状态/能做什么/条件/消耗/结果/下一步”——现有事项卡已含消耗、所得、锁定原因；缺口见 `implementation-roadmap.md`。

6. **三维舞台**（`mountStage`）同样是增强：不可见即停帧、≈30fps、DPR≤1.5、帧耗时过高自动降档；`body.stage3d-on` 时 2D 灵气隐藏。
7. **下一步指引**：服务端 `world.guide` 给出瓶颈与第一个可执行事项；界面只做跳转与高亮（`.world-action.guided`，仅阴影，不改布局）。
8. **破坏性操作**一律由服务端为动作下发 `confirm`，前端复用 `confirm-dialog`，不得在前端自行判断。
