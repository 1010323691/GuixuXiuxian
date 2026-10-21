# 紫晶翼狮王立绘来源

- 来源：`assets/mon_amethyst_winged_lion_king_sheet_v001.png`（紫晶翼狮王设定集），由项目所有者提供，使用权归项目所有者（2026-10-21 提供并要求替换斗法台魔物）。
- 生成：`python scripts/cutout_turnaround.py lion`（三视图用二维多项式拟合雾状背景去底；`sigil` 为「灵气凝聚」阵印，按加色发光处理）。输出 `front`/`side`/`back`/`sigil` 四张 PNG。
- 比例：设定集标注含翼展约 6~8 米、修士约 1.8 米；斗法台中狮王正面高 7.6 单位（主角 3.0 单位），各视图共用同一像素比例尺。
- 修改设定图后重跑脚本即可再生成；不要手工编辑这些 PNG。
