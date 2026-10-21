# 主角立绘与法宝贴图来源

- 来源：`assets/protagonist_xianxia_character_concept_turnaround_v001.png.png`（修仙主角三视图设定图），由项目所有者提供，使用权归项目所有者（2026-10-21 确认可入库并随游戏分发）。
- 生成：`python scripts/cutout_turnaround.py`（裁切 + 拟合背景去底 + 半透明反混合），输出本目录 7 张 PNG：`front`/`side`/`back` 三视图，`sword` 飞剑、`talisman` 符箓、`circle` 法阵、`jade` 玉佩。
- 修改设定图后重跑脚本即可再生成；不要手工编辑这些 PNG。
