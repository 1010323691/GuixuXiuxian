# 青玄剑宗视觉参考图集

日期：2026-10-21（Asia/Tokyo）。本轮仅交付图片与资产文档；没有创建游戏页面、Three.js代码、GLB/GLTF或实际3D场景。全部图像由内置 image_gen 生成/编辑，既有图只做参考或保留，未镜像冒充新视角。

## 当前状态

60个编号项目均已有实图，共88张PNG（含修正版、普通亭台补图及草稿），约241.9 MiB。全部88张已实际解码并记录尺寸、SHA-256，见[file-inventory.json](file-inventory.json)。最终修正版已完成独立目视复查：60/60类别、66张有效参考齐全，已列阻断性可见缺陷修复通过，可作视觉参考交接。未将类别齐全写成逐构件数值一致、隐藏几何或真实三维通行性全部通过。

**最新用户裁决：南侧上山路为笔直、长、宽大的白玉石阶，宽度与构件语言参照通往主殿的阶梯；与迎仙广场、山门和北侧主殿处在同一中轴线上，不采用盘山折返路。** 最直接的视觉依据是[A04最新修正版](01-master-layout/sect-front-distant-v4-grand-stairs.png)与[A02最新总平面](01-master-layout/sect-layout-top-ortho-v4-grand-stairs.png)。

## 使用与一致性规则

- A01决定已建立的墨青琉璃瓦、白玉、玄木、少量金饰及山云美术语言；G组与A01保持同机位作光照比较。
- A02最新版本决定区域占地与道路拓扑；A03决定三级地形意图；A04最新版本补充南侧宽直阶。场景图是设计参考，不能直接视为精确地形或坐标数据。
- B组单体结构图及单独修正版优先于A组远景中的小尺寸建筑细节。结构图板按上排左/中/右为正面/右侧/背面，下排左/中/右为顶视/45度轴测/细节；洞府内部使用相应剖开视图。B04/B05原图板背面不再作为有效背面依据，使用单独back-ortho替代。B06/B07顶视以单独修正版优先。
- C组以开放接口修正版优先；C05的三维板与单独top-ortho配套使用。F组每张按左上/右上/左下/右下对应初始/运行/高能/消散，是静态关键状态参考，不是已实现的动画。
- 原提示词给出的山门36m/22m、主殿60×40×36m、藏经阁24×24×52m、试剑台直径40m保留为设计约束；其余尺寸标为本轮提案。任何图像的像素比例都没有测量验证成工程精度。
- 无法从图像确定的梁架内构、门窗逐个数量、屋面曲率、隐藏房间、洞穴厚度、栏杆锚固、基础埋深和碰撞通道都为待推定；不得当作已经得到准确三维数据。
- E组仅为材质外观参考，未交付或验证BaseColor/Normal/Roughness/Metalness/AO分通道，未验证边缘无缝。F组亦未给定时长、粒子数、Shader参数或性能结论。

## A · 空间结构

| 编号/资产 | 有效参考与配套图 | 视角/用途 | 设计尺寸或比例约束 | 对应关系/审查依据 | 待推定信息 |
| --- | --- | --- | --- | --- | --- |
| A01 宗门整体鸟瞰 | [00-art-direction/sect-overview-aerial.png](00-art-direction/sect-overview-aerial.png)（1672×941） | 南侧高空约45度透视 | 场地目标800×800m；三主要平台80/140/220m | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |
| A02 严格俯视总平面 | [01-master-layout/sect-layout-top-ortho-v4-grand-stairs.png](01-master-layout/sect-layout-top-ortho-v4-grand-stairs.png)（1672×941） | 北上南下屋顶总平面 | 同A01；仅视觉占地，不从像素直接换算米制 | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |
| A03 南北地形侧剖 | [01-master-layout/sect-terrain-section-v3.png](01-master-layout/sect-terrain-section-v3.png)（1672×941） | 南左北右地形侧剖 | 南80m、中140m、北220m，数值为设计目标 | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |
| A04 宗门正面远景与南侧宽直阶 | [01-master-layout/sect-front-distant-v4-grand-stairs.png](01-master-layout/sect-front-distant-v4-grand-stairs.png)（1672×941） | 南向北远距偏正面透视 | 南侧入口宽直长阶与主阶同轴同风格 | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |
| A05 山门向主殿地面视角 | [01-master-layout/sect-gate-to-main-hall-ground-v3.png](01-master-layout/sect-gate-to-main-hall-ground-v3.png)（1672×941） | 朝北地面人眼透视 | 人眼视点约1.7m；正北观察 | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |
| A06 主殿向山门反向视角 | [01-master-layout/sect-main-hall-to-gate-ground-v2.png](01-master-layout/sect-main-hall-to-gate-ground-v2.png)（1672×941） | 朝南地面反向透视 | 主殿平台视点约1.7m；朝南 | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |
| A07 西向东横向观察 | [01-master-layout/sect-west-to-east-cross-view-v2.png](01-master-layout/sect-west-to-east-cross-view-v2.png)（1672×940） | 西向东横向透视 | 西向东，北在画面左 | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |
| A08 东南高空御剑视角 | [01-master-layout/sect-sword-flight-aerial-v3-grand-stairs.png](01-master-layout/sect-sword-flight-aerial-v3-grand-stairs.png)（1672×941） | 东南高空朝西北透视 | 东南上空朝西北；透视 | A02/B母版；见quality-review-final.md（最新修正版已复查） | 精确坐标/标高/峰形逐点匹配 |

## B · 核心建筑

| 编号/资产 | 有效参考与配套图 | 视角/用途 | 设计尺寸或比例约束 | 对应关系/审查依据 | 待推定信息 |
| --- | --- | --- | --- | --- | --- |
| B01 宗门山门 | [02-architecture/sect-gate/sect-gate-structure-sheet.png](02-architecture/sect-gate/sect-gate-structure-sheet.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 宽36m、高22m；进深10m为本轮提案 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B02 宗门主殿 | [02-architecture/main-hall/main-hall-structure-sheet.png](02-architecture/main-hall/main-hall-structure-sheet.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 宽60m、深40m、高36m；三重檐 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B03 藏经阁 | [02-architecture/scripture-pavilion/scripture-pavilion-structure-sheet.png](02-architecture/scripture-pavilion/scripture-pavilion-structure-sheet.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 24×24×52m；七层、七重檐、方形平面 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B04 炼丹阁 | [02-architecture/alchemy-hall/alchemy-hall-structure-sheet.png](02-architecture/alchemy-hall/alchemy-hall-structure-sheet.png)（1536×1024）<br>[02-architecture/alchemy-hall/alchemy-hall-back-ortho.png](02-architecture/alchemy-hall/alchemy-hall-back-ortho.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 32×24×20m为提案；统一四排气管 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B05 炼器阁 | [02-architecture/forging-hall/forging-hall-structure-sheet.png](02-architecture/forging-hall/forging-hall-structure-sheet.png)（1536×1024）<br>[02-architecture/forging-hall/forging-hall-back-ortho.png](02-architecture/forging-hall/forging-hall-back-ortho.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 36×28×22m为提案；一根后烟囱 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B06 弟子居所 | [02-architecture/disciple-residence/disciple-residence-structure-sheet.png](02-architecture/disciple-residence/disciple-residence-structure-sheet.png)（1536×1024）<br>[02-architecture/disciple-residence/disciple-residence-top-ortho.png](02-architecture/disciple-residence/disciple-residence-top-ortho.png)（1312×1199） | 正/右/背/顶/45度轴测与构件细节 | 18×20m、单层、约7m高为提案 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B07 长老居所 | [02-architecture/elder-residence/elder-residence-structure-sheet.png](02-architecture/elder-residence/elder-residence-structure-sheet.png)（1536×1024）<br>[02-architecture/elder-residence/elder-residence-top-ortho-v2.png](02-architecture/elder-residence/elder-residence-top-ortho-v2.png)（1211×1299） | 正/右/背/顶/45度轴测与构件细节 | 28×30m、主楼双层约14m高为提案 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B08 修炼洞府入口 | [02-architecture/cultivation-cave/cave-entrance-structure-sheet.png](02-architecture/cultivation-cave/cave-entrance-structure-sheet.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 局部岩壁与入口尺寸仍待推定 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B09 修炼洞府内部 | [02-architecture/cultivation-cave/cave-interior-structure-sheet.png](02-architecture/cultivation-cave/cave-interior-structure-sheet.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 石室12×16×7m、入口通道6m为提案 | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |
| B10 观剑亭与普通亭台 | [02-architecture/sword-pavilion/sword-pavilion-structure-sheet.png](02-architecture/sword-pavilion/sword-pavilion-structure-sheet.png)（1536×1024）<br>[02-architecture/sword-pavilion/simple-pavilion-structure-sheet.png](02-architecture/sword-pavilion/simple-pavilion-structure-sheet.png)（1536×1024） | 正/右/背/顶/45度轴测与构件细节 | 观剑亭六角双檐约12m跨/14m高；方亭6×6×6m | A01美术；quality-review-b/revisions/final | 逐构件精确一致性、隐藏结构、内部布局 |

## C · 功能设施

| 编号/资产 | 有效参考与配套图 | 视角/用途 | 设计尺寸或比例约束 | 对应关系/审查依据 | 待推定信息 |
| --- | --- | --- | --- | --- | --- |
| C01 白玉登仙石阶 | [03-environment/ascension-stairs-structure-v2.png](03-environment/ascension-stairs-structure-v2.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 宽12m；踏高0.16/踏深0.32m为设计提案 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C02 迎仙广场 | [03-environment/welcome-plaza-structure.png](03-environment/welcome-plaza-structure.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 广场直径64m为提案；南北连接开放 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C03 圆形试剑台 | [03-environment/sword-platform-structure.png](03-environment/sword-platform-structure.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 直径40m；露天；两向入口 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C04 大型练功场 | [03-environment/training-courtyard-structure.png](03-environment/training-courtyard-structure.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 60×40m为提案；六练习纹样 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C05 山间直线石桥 | [03-environment/straight-jade-bridge-connected-approaches.png](03-environment/straight-jade-bridge-connected-approaches.png)（1536×1024）<br>[03-environment/straight-jade-bridge-top-ortho.png](03-environment/straight-jade-bridge-top-ortho.png)（2172×724） | 整体轴测、顶视、侧视或模块图 | 桥长40m、净宽6m；两端各20m引道为提案 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C06 山间弧形云桥 | [03-environment/curved-cloud-bridge-structure-v2.png](03-environment/curved-cloud-bridge-structure-v2.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 净宽6m、平面曲线半径32m为提案 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C07 悬崖栈道 | [03-environment/cliff-boardwalk-structure.png](03-environment/cliff-boardwalk-structure.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 长24m、净宽3m；锚固与三角托架 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C08 道路护栏石灯模块 | [03-environment/path-rail-lamp-modules.png](03-environment/path-rail-lamp-modules.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 路宽6m；栏板2m；栏高1.1m；灯高2.4m为提案 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C09 灵泉与水池 | [03-environment/spiritual-spring-pool-structure-v2.png](03-environment/spiritual-spring-pool-structure-v2.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 约12×8m、深1.2m为提案 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |
| C10 灵田与药圃 | [03-environment/spirit-fields-herb-garden-structure.png](03-environment/spirit-fields-herb-garden-structure.png)（1536×1024） | 整体轴测、顶视、侧视或模块图 | 约32×24m、三级台地为提案 | A02道路；quality-review-c/final | 准确踏数、锚固、承载、逐点尺寸 |

## D · 自然资产

| 编号/资产 | 有效参考与配套图 | 视角/用途 | 设计尺寸或比例约束 | 对应关系/审查依据 | 待推定信息 |
| --- | --- | --- | --- | --- | --- |
| D01 主峰山体 | [04-natural-assets/main-peak-structure.png](04-natural-assets/main-peak-structure.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 主峰目标平台220m；顶台约110×90m为提案 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D02 次峰山体 | [04-natural-assets/secondary-peak-structure.png](04-natural-assets/secondary-peak-structure.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 次峰目标140m；台地约70×55m为提案 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D03 悬崖岩壁 | [04-natural-assets/cliff-wall-modules.png](04-natural-assets/cliff-wall-modules.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 直壁/转角/凹壁模块；不按图量尺寸 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D04 大中小岩石 | [04-natural-assets/rocks-size-family.png](04-natural-assets/rocks-size-family.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 大8m、中2.5m、小0.2–0.6m为提案 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D05 古松与普通松树 | [04-natural-assets/pine-tree-structure.png](04-natural-assets/pine-tree-structure.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 古松约14m、普通松约10m为提案 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D06 竹林与普通植被 | [04-natural-assets/bamboo-common-vegetation.png](04-natural-assets/bamboo-common-vegetation.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 竹约8m；草灌0.6–1.4m为提案 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D07 灵草与发光植物 | [04-natural-assets/spirit-herbs-luminous-plants.png](04-natural-assets/spirit-herbs-luminous-plants.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 灵草0.4–0.9m、灵树约2.5m为提案 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D08 瀑布与溪流 | [04-natural-assets/waterfall-stream-structure.png](04-natural-assets/waterfall-stream-structure.png)（1536×1024） | 独立轮廓、多方向或局部结构 | 落差约24m、池12×8m为提案 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D09 山间云雾 | [04-natural-assets/mountain-mist-layers.png](04-natural-assets/mountain-mist-layers.png)（1672×941） | 云层/环境外观 | 低浓云/中薄雾/高云丝；密度待推定 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |
| D10 远景群山与天空 | [04-natural-assets/distant-mountains-sky.png](04-natural-assets/distant-mountains-sky.png)（1672×940） | 云层/环境外观 | 远中近景层次；距离待推定 | A01配色；quality-review-def.md已目视 | 背面几何、尺寸、程序化参数 |

## E · 材质外观

| 编号/资产 | 有效参考与配套图 | 视角/用途 | 设计尺寸或比例约束 | 对应关系/审查依据 | 待推定信息 |
| --- | --- | --- | --- | --- | --- |
| E01 墨青琉璃瓦 | [05-materials/ink-teal-glazed-tiles.png](05-materials/ink-teal-glazed-tiles.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |
| E02 白玉石材 | [05-materials/white-jade-stone.png](05-materials/white-jade-stone.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |
| E03 青灰石砖 | [05-materials/blue-gray-stone-bricks.png](05-materials/blue-gray-stone-bricks.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |
| E04 玄木梁柱 | [05-materials/dark-xuan-wood.png](05-materials/dark-xuan-wood.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |
| E05 金属与鎏金装饰 | [05-materials/gilded-metal-decoration.png](05-materials/gilded-metal-decoration.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |
| E06 山体岩石 | [05-materials/mountain-rock-surface.png](05-materials/mountain-rock-surface.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |
| E07 地面泥土与草地 | [05-materials/soil-grass-ground.png](05-materials/soil-grass-ground.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |
| E08 水面与灵泉 | [05-materials/spiritual-water-surface.png](05-materials/spiritual-water-surface.png)（1254×1254） | 正面/垂直表面近景；外观参考 | 取色/纹理尺度待后续校准 | A01配色；quality-review-def.md已目视 | PBR通道、无缝性、物理参数 |

## F · 特效关键状态

| 编号/资产 | 有效参考与配套图 | 视角/用途 | 设计尺寸或比例约束 | 对应关系/审查依据 | 待推定信息 |
| --- | --- | --- | --- | --- | --- |
| F01 聚灵阵 | [06-vfx/spirit-gathering-array-states.png](06-vfx/spirit-gathering-array-states.png)（1672×941） | 四状态、固定示意机位 | 阵径约12m；三维厚度与时序待推定 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |
| F02 护宗大阵 | [06-vfx/sect-protection-barrier-states.png](06-vfx/sect-protection-barrier-states.png)（1672×941） | 四状态、固定示意机位 | 示意穹顶约120m；非整宗门定尺 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |
| F03 环绕飞剑剑阵 | [06-vfx/orbiting-sword-array-states.png](06-vfx/orbiting-sword-array-states.png)（1672×941） | 四状态、固定示意机位 | 实际统一七剑环；不要沿提示词自定八剑 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |
| F04 御剑飞行拖尾 | [06-vfx/sword-flight-trail-states.png](06-vfx/sword-flight-trail-states.png)（1672×941） | 四状态、固定示意机位 | 单飞剑、青白曲线拖尾 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |
| F05 流动灵气粒子 | [06-vfx/flowing-spiritual-particles-states.png](06-vfx/flowing-spiritual-particles-states.png)（1672×940） | 四状态、固定示意机位 | 山体上升螺旋粒子；速度待推定 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |
| F06 山间体积云海 | [06-vfx/volumetric-cloud-sea-states.png](06-vfx/volumetric-cloud-sea-states.png)（1672×941） | 四状态、固定示意机位 | 三岩峰云层四状态；流速待推定 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |
| F07 灵泉发光水流 | [06-vfx/spiritual-spring-water-states.png](06-vfx/spiritual-spring-water-states.png)（1672×941） | 四状态、固定示意机位 | 约4×3m池体仅作发光示例 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |
| F08 建筑环绕灵气 | [06-vfx/architecture-spiritual-aura-states.png](06-vfx/architecture-spiritual-aura-states.png)（1672×941） | 四状态、固定示意机位 | 普通方亭周边独立灵气效果 | A01配色；quality-review-def.md已目视 | 动态时序、粒子/Shader参数 |

## G · 昼夜与天气

| 编号/资产 | 有效参考与配套图 | 视角/用途 | 设计尺寸或比例约束 | 对应关系/审查依据 | 待推定信息 |
| --- | --- | --- | --- | --- | --- |
| G01 清晨 | [07-lighting/sect-dawn.png](07-lighting/sect-dawn.png)（1672×941） | A01南侧高空同机位光照比较 | 沿用A01布局与机位；不新增尺寸 | A01/G02；quality-review-final.md | 实际灯光强度、曝光、雾参数 |
| G02 正午 | [07-lighting/sect-noon.png](07-lighting/sect-noon.png)（1672×941） | A01南侧高空同机位光照比较 | 沿用A01布局与机位；不新增尺寸 | A01/G02；quality-review-final.md | 实际灯光强度、曝光、雾参数 |
| G03 黄昏 | [07-lighting/sect-sunset.png](07-lighting/sect-sunset.png)（1672×941） | A01南侧高空同机位光照比较 | 沿用A01布局与机位；不新增尺寸 | A01/G02；quality-review-final.md | 实际灯光强度、曝光、雾参数 |
| G04 月夜 | [07-lighting/sect-moonlit-night.png](07-lighting/sect-moonlit-night.png)（1672×941） | A01南侧高空同机位光照比较 | 沿用A01布局与机位；不新增尺寸 | A01/G02；quality-review-final.md | 实际灯光强度、曝光、雾参数 |
| G05 浓雾天气 | [07-lighting/sect-dense-cloud-weather.png](07-lighting/sect-dense-cloud-weather.png)（1672×941） | A01南侧高空同机位光照比较 | 沿用A01布局与机位；不新增尺寸 | A01/G02；quality-review-final.md | 实际灯光强度、曝光、雾参数 |
| G06 护宗阵启动 | [07-lighting/sect-protection-barrier-active-v2.png](07-lighting/sect-protection-barrier-active-v2.png)（1672×941） | A01南侧高空同机位光照比较 | 沿用A01布局与机位；不新增尺寸 | A01/G02；quality-review-final.md | 实际灯光强度、曝光、雾参数 |

## 独立审查与可追溯证据

[最终交付检查摘要](delivery-review.md)列出覆盖数、有效文件数、修复结果与未验证范围。

- [A组初审](quality-review-a.md)：原稿发现的投影、重复门楼与布局漂移，不能覆盖后来的修正版。
- [B组初审](quality-review-b.md)：核心建筑五视角与细节，及需替换的背/顶视。
- [C组初审](quality-review-c.md)：设施通路与端点问题。
- [第一轮修正版复查](quality-review-revisions.md)。
- [D/E/F全组审查](quality-review-def.md)：26张实图均已目视；四状态完整；材质仅作风格参考。
- [最终修正版审查](quality-review-final.md)：按每次具体文件与哈希读结论，不把历史报告中旧版缺陷误作已修或未修。
- [全部图像尺寸与SHA-256](file-inventory.json)。
- [本轮补图与修正版生成提示词/路径记录](generation-records-final.json)；generation-prompts/下另有逐次提示词。工具模式为内置image_gen，未使用CLI/API密钥。

## 旧稿与修正版

以下文件仅保留过程与追溯，不应覆盖上表选定的当前参考：

- [01-master-layout/sect-front-distant-v2.png](01-master-layout/sect-front-distant-v2.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-front-distant-v3-access-road.png](01-master-layout/sect-front-distant-v3-access-road.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-front-distant.png](01-master-layout/sect-front-distant.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-gate-to-main-hall-ground.png](01-master-layout/sect-gate-to-main-hall-ground.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-layout-top-ortho-v2.png](01-master-layout/sect-layout-top-ortho-v2.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-layout-top-ortho-v3.png](01-master-layout/sect-layout-top-ortho-v3.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-layout-top-ortho.png](01-master-layout/sect-layout-top-ortho.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-main-hall-to-gate-ground.png](01-master-layout/sect-main-hall-to-gate-ground.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-sword-flight-aerial.png](01-master-layout/sect-sword-flight-aerial.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-terrain-section-draft.png](01-master-layout/sect-terrain-section-draft.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-terrain-section-v2.png](01-master-layout/sect-terrain-section-v2.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-terrain-section.png](01-master-layout/sect-terrain-section.png)：旧稿/补充候选，使用前查对应QA记录。
- [01-master-layout/sect-west-to-east-cross-view.png](01-master-layout/sect-west-to-east-cross-view.png)：旧稿/补充候选，使用前查对应QA记录。
- [02-architecture/elder-residence/elder-residence-top-ortho.png](02-architecture/elder-residence/elder-residence-top-ortho.png)：旧稿/补充候选，使用前查对应QA记录。
- [03-environment/ascension-stairs-structure.png](03-environment/ascension-stairs-structure.png)：旧稿/补充候选，使用前查对应QA记录。
- [03-environment/curved-cloud-bridge-structure.png](03-environment/curved-cloud-bridge-structure.png)：旧稿/补充候选，使用前查对应QA记录。
- [03-environment/spiritual-spring-pool-structure.png](03-environment/spiritual-spring-pool-structure.png)：旧稿/补充候选，使用前查对应QA记录。
- [03-environment/straight-jade-bridge-open-endpoints.png](03-environment/straight-jade-bridge-open-endpoints.png)：旧稿/补充候选，使用前查对应QA记录。
- [03-environment/straight-jade-bridge-structure.png](03-environment/straight-jade-bridge-structure.png)：旧稿/补充候选，使用前查对应QA记录。
- [07-lighting/sect-protection-barrier-active.png](07-lighting/sect-protection-barrier-active.png)：旧稿/补充候选，使用前查对应QA记录。


- [01-master-layout/sect-gate-to-main-hall-ground-v2.png](01-master-layout/sect-gate-to-main-hall-ground-v2.png)：被v3替代，主殿檐数不清。
- [01-master-layout/sect-sword-flight-aerial-v2.png](01-master-layout/sect-sword-flight-aerial-v2.png)：被v3-grand-stairs替代，南侧旧平桥不采用。

## 交付边界

文件层面的存在、可解码、命名、尺寸与哈希已检查。纯Three.js程序化建模、渲染性能、碰撞、可进入空间以及真实运行均未实施，也未以参考图推定为通过。最终独立复查若仍有可见结构冲突，应继续修图；不得把未测或待推定项写成已通过。

