# 青玄剑宗 G 组与后续修正版独立复核

日期：2026-10-21。本报告名称中的 final 表示本次后续复核记录，**不代表完整图集已经全部通过**。本次只审下列13张指定文件；A05–A08后续修正版尚未列入本次结论。

实际执行：逐张 `view_image` 检查；将G组和A01比较主殿、山门、试剑台、藏经塔及前景边界位置；检查C组轴测与顶视端点；检查A03建筑侧面、A04远景机位、B07顶图立面残留；以.NET System.Drawing实际解码并记录尺寸、SHA-256。未生成或修改图片、模型或游戏代码。

## G 组：同机位昼夜与天气

| 编号及文件（相对 `07-lighting/`） | 复核结果 |
| --- | --- |
| G01 `sect-dawn.png` | 清晨暖金云海、东侧太阳及柔光清楚；主殿、山门、藏经塔、试剑台和前景大石/亭台位置与A01大体保持，主要变化来自光照和天空。未见明显整场景相机位移，可作清晨光照参考。 |
| G02 `sect-noon.png` | 蓝天、较中性的日光及清晰材质符合正午参考；主要建筑和山峰轮廓位置保持，未见明显构图漂移。可作正午对照基准。 |
| G03 `sect-sunset.png` | 西侧夕阳、橙紫天空和建筑暖边光符合黄昏；主要固定物位置保持，没有为夕阳改换宗门布局。可作黄昏光照参考。 |
| G04 `sect-moonlit-night.png` | 深蓝月夜、暖灯和少量青色泉光清楚，建筑仍可读；主要固定物位置与日景保持。可作月夜光照参考。 |
| G05 `sect-dense-cloud-weather.png` | 浓雾提高、低对比散射明显，同时主轴及重要建筑仍可辨认；主要轮廓仍在原位置，天气差异没有明显重排场景。可作浓雾天气参考。 |
| G06 `sect-protection-barrier-active.png` | 金青色护宗穹顶和覆盖关系可读，但**严格同机位比较未通过**：整座宗门明显向画面下移约100像素，主殿、藏经塔、中央山门和试剑台均下移，底部前景裁切也改变。不是单纯增加能量膜。建筑尺度变化不如整体下移明显，不能只笼统说已确认缩放；可确认的是画面构图/投影中心已改变。应以G02或A01原镜头直接增加护罩，保留所有固定建筑像素位置，允许护罩顶部超出取景而不移动场景。 |

G组未见人物、UI、水印或明显可读文字。上述通过是光照对照参考通过，不表示像素级完全相等，更不撤销A01与其他空间/建筑母版之间的既有一致性问题。

## C组连接修正版

| 文件（相对 `03-environment/`） | 复核结果 |
| --- | --- |
| `ascension-stairs-structure-v2.png` | **连接端修复通过目视复核。** 上下连接平台均能看到开放铺装面，轴向终端没有跨整条路径的栏板；两侧栏随台阶上升，顶图及整体能对应开放接口。注意仍只证明图面接口开放，未测量净宽/踏步或进行真实拼接。 |
| `curved-cloud-bridge-structure-v2.png` | **原封路缺陷已修复。** 轴测近端和远端都能看到开放石铺口，栏杆终止在两侧，不再横跨终端；顶视也保留开放终端。拱、桥墩、落岩桥台仍完整。可作为开放弧桥结构参考。 |
| `spiritual-spring-pool-structure-v2.png` | **原出口封栏及左端裁切缺陷已修复。** 东西两个连接台均完整进入画面，终端可见开放铺装断面；沿池和连接台两侧的栏杆保留，轴向无横栏。北泉/南排水及环池步道关系保持。 |
| `straight-jade-bridge-open-endpoints.png` | **仍失败，需再修复。** 两端亭顶虽已移除，但轴测左上远端和右下近端最外缘都能看到跨桥宽的连续白玉栏板；俯视两端外缘也呈封闭框边。现在仍像两头封闭的观景桥，文件名 open-endpoints 不能作为开放证明。必须保留长边侧栏、去掉短边端部横栏，使两头都有全净宽开放铺装口，并在轴测/顶/侧图一致呈现。 |

## A/B组修正版

| 文件 | 复核结果 |
| --- | --- |
| `01-master-layout/sect-terrain-section-v3.png` | **上一轮混合投影缺陷目视修复。** 最高主殿由正面长屋脊改为短向三角山墙/侧向柱廊轮廓，左侧山门也收窄为侧向结构，不再将完整南向门面正对观察者。三级台地、沿坡石阶、岩层及洞穴关系清楚；未见人物。可作地形侧向结构参考。标高80/140/220米、建筑精确比例、主殿隐藏内部及剖切位置未通过三维数据验证，不能宣称精确建模参数已得到。 |
| `01-master-layout/sect-front-distant-v2.png` | **旧重复高空鸟瞰机位缺陷已修复。** 当前镜头退远并降低俯角，可完整看到前侧山体、南门、逐级主轴及主峰正面轮廓，区别于A01高空近距鸟瞰。主殿为B母版类似的三重檐、藏经塔在西、试剑和训练区在东，布局更接近A02。可作宗门正面远景参考；跨A01全部建筑外观逐构件一致性未在这一张单图中验证。 |
| `02-architecture/elder-residence/elder-residence-top-ortho-v2.png` | **原大面积正立面残留缺陷已修复。** 主要呈屋顶、院落铺装、圆形柱顶/基座平面，旧主屋柱身/正面廊栏/南门门面被消除；北主屋、两翼、南门、左后泉池和右后古松关系保留。可作顶向占地参考。楼梯被屋面遮挡的部分仍不能由此确认，不能凭顶图补全隐藏结构。 |

## 本次证据版本

| 文件简名 | 尺寸 | SHA-256 |
| --- | --- | --- |
| sect-dawn.png | 1672×941 | `E93A88683F28ACC174427DC20B84B2D62307B295AC8A02E3A228821342F29EA3` |
| sect-noon.png | 1672×941 | `BFEA1543D7522C991F5A499F97A16B2CDB6AD0B73E563EDFF131D9043B7BB811` |
| sect-sunset.png | 1672×941 | `27C7F5A914C1431CDB7D89DBC0799446E972147C6AFA9E67FD5CD31AF49420A3` |
| sect-moonlit-night.png | 1672×941 | `B25C93D5D972F53C53D70E673846FA08EED8334C16CAC6368970A44AE7F9B062` |
| sect-dense-cloud-weather.png | 1672×941 | `8698F70424A2EF9CB02020AB25766043520A92744804E7CB27A336AC83A3FD06` |
| sect-protection-barrier-active.png | 1672×941 | `641DF37BBCA10BAF25F26F8AC11D0F9F9C2D0C84F08D6815E08CBA01511A2C38` |
| ascension-stairs-structure-v2.png | 1536×1024 | `82DFD8997902E482A530FFB380DF23B2247A6797FFED1C32C76AAF82850B2AE5` |
| curved-cloud-bridge-structure-v2.png | 1536×1024 | `25A26B7665957904635D763ECB8373CD341B4018B2F7A31BE0F231F0DF3617A9` |
| spiritual-spring-pool-structure-v2.png | 1536×1024 | `19718829879D9ACEDABBE2C9BBD542E44906E354F3ED17514D129E89A8D2E601` |
| straight-jade-bridge-open-endpoints.png | 1536×1024 | `F0E709850A44CE44D13C962A620F3AC771637C81A401C0DB3CCFC70D0AFEB806` |
| sect-terrain-section-v3.png | 1672×941 | `88D09BDA962698A9E57432FEB4B38F969553D1D138B5C4FAA05220014412BD74` |
| sect-front-distant-v2.png | 1672×941 | `9D29E44A266BC34771A43970ADE88D5FC38C584589B99D1187FFC90F8E70D249` |
| elder-residence-top-ortho-v2.png | 1211×1299 | `5D9A224F38FBDB631EF4DDC384C9AB937C4FFA4F076A19530C677D9B4F01B260` |

全部13张实际可解码为PNG。

## 交接结论

当前明确仍需修复：**C05直桥两个终端横栏、G06构图下移**。A05–A08新版本等待主Agent完成并指定后另行复审。本次报告未检查最终manifest覆盖性，没有创建或运行模型/场景，不能据此宣布全部参考图通过，也不能进入未经用户另行授权的Three.js开发阶段。

## 追加复核：开放直桥、固定镜头护阵与南侧直线长阶

本节为上述13张之后的三个新版本复核，以本节结果取代对应旧缺陷的“尚未修复”状态；旧版本审查记录保留。三张均已实际使用 `view_image` 查看、解码和计算哈希。A05–A08的后续修正版仍等待另行指定。

### C05 连续进路修正版

文件：`03-environment/straight-jade-bridge-connected-approaches.png`。

**两端通路修复通过目视复核。** 石铺桥面沿轴线连续延伸至两侧岩体进路，栏杆沿左右长边设置并在桥台附近终止；没有跨越两端轴向出口的栏板、端亭或门槛封堵。桥拱、桥台与岩体接合仍可见，可用于理解进路—桥台—跨中—桥台—进路的连续关系。旧 `straight-jade-bridge-open-endpoints.png` 的两个封口问题在新图中已解决。

剩余界限：中间横向视图仍能看见桥拱和桥侧立面，不是严格90°顶视，不能把该面板直接标注为严格顶向工程图。此次通过仅针对连续通路和两端开放；米制净宽、铺装与相邻设施精确拼接均未实测。

### G06 原镜头护宗大阵修正版

文件：`07-lighting/sect-protection-barrier-active-v2.png`。

**原构图下移缺陷已修复。** 与A01/G02对照，主殿、南侧门楼、藏经塔、东侧圆台及前景大石/亭台均回到原来的大致图面位置；没有再为容纳护罩整体下移宗门。金青色能量膜、经纬光纹与光点覆盖场景，穹顶顶部延展出取景边缘，没有以移动建筑构图换取穹顶完整入画。可用作固定镜头下的护宗大阵光照/特效氛围参考。

此结论是可见固定地标的对照，未进行像素级图像配准，不应声称每个纹理像素完全一致。

### A04 南侧笔直宽大白玉长阶修订

文件：`01-master-layout/sect-front-distant-v4-grand-stairs.png`。

**最新南侧路网修订目视通过。** 南侧前景现为宽大白玉直阶，所有梯段沿同一笔直轴线爬升，以同轴休息平台衔接，没有蛇形折返或侧向绕山。下段长阶的中心、山门中央通道、门后登仙主阶和最高主殿中心基本对齐，构成清楚连续的南北入宗中轴。

可见踏步与平台之间没有横向栏板、人物、雕像或不连通裂缝；主入口净空开放。东西支路在山门/门前台地附近向两侧分流，未横断中央直阶。主轴较两侧支路显著宽大、白玉材质统一，符合本次“南侧上山路必须是笔直宽大白玉长阶”的追加要求。

画面底部的阶梯继续延伸出取景，不据此推断下山路的完整长度、起点标高或底部建筑；同样没有验证真实踏步米制尺寸。此修订已改变旧A01/G组未展现的南侧前景，应在最终索引说明采用的最新南入口设计，并在其余视角中保持一致。

| 新版本 | 尺寸 | SHA-256 |
| --- | --- | --- |
| straight-jade-bridge-connected-approaches.png | 1536×1024 | `0FE5D42744C875465178CAC0189BD9A4461FB3FA5117FC495F1476BAC1416B25` |
| sect-protection-barrier-active-v2.png | 1672×941 | `E7E6C2870EDB3EB64D61FE7E5538BFFBEBF98E228FB10E3D67784771F6AC9E66` |
| sect-front-distant-v4-grand-stairs.png | 1672×941 | `7E95041853C67A08DBFCAB378711C5FEA12AEE9BA534CD06B7D629B48196DF2C` |

本节三个新版本均实际可解码为PNG。本节不等同于全套图集终验，也不批准启动三维建模或游戏开发。

## 追加复核：A05–A08 v2、A02南侧直阶与直桥顶视

本节实际查看六张新图，以本节结论取代对应旧版本相关缺陷状态；未以文件名或生成记录代替图片检查。

| 文件 | 结果与可见证据 |
| --- | --- |
| `01-master-layout/sect-gate-to-main-hall-ground-v2.png` | 地面仰看方向保留，西侧已恢复为单座七层藏经塔，旧多层宫殿替塔的问题已改善。**主殿三重檐仍未充分通过**：图中仅能清楚辨出两道中央青瓦主檐，最低局部檐只在左右翼露出，和B02明确三道贯通主屋面的三重檐并不清楚一致。应重做或补充使第三层主檐明确可辨，不能因为提示词写三层就视为已交付三层。 |
| `01-master-layout/sect-main-hall-to-gate-ground-v2.png` | 朝南方向正确，试剑区在左、西侧藏经区在右；旧近远两座完整山门已消除，现主轴只出现一座完整三通道门楼，门外为广场与向南延伸的同轴长路。门楼数量缺陷修复通过。主殿在身后，不能从这一视角验证其屋檐层数。 |
| `01-master-layout/sect-west-to-east-cross-view-v2.png` | 西向东横向机位、桥梁两端和东侧试剑训练区关系保留；旧主峰左后重复高塔已移除。远处主殿有三层屋檐轮廓，和B02的三重檐层数相容。主要方向与重复高塔缺陷修复通过；视线遮住近处藏经塔整体，不能由此逐层确认它的七层结构。 |
| `01-master-layout/sect-sword-flight-aerial-v2.png` | 东南朝西北的空中视角合理，单座藏经塔在西、单座三通道山门在南、试剑台在东。原主轴一根超长直阶已恢复分段休息平台，南北主轴层次改善；主殿上檐紧密，未宣称逐檐完全精确一致。**最新南侧直阶要求仍有冲突**：左下进入迎仙广场的长进路仍为大片剑纹铺砖的水平桥面，带桥墩，没有沿整段连续可见的踏步，不能作为与A04 v4/A02 v4相同的笔直白玉上山长阶。应保留相机和场景，重做这一段南侧进路。 |
| `01-master-layout/sect-layout-top-ortho-v4-grand-stairs.png` | 南侧现有宽大直线阶梯及同轴平台，朝北依次连接迎仙圆广场、山门中央开口、登仙主轴与主殿；没有蛇形绕行或横栏封住阶口。东侧试剑台仍为露天圆台，东北灵泉和东西功能区保持。可作最新南入口布局参考。米制800×800范围与标高没有由图像精确验证。 |
| `03-environment/straight-jade-bridge-top-ortho.png` | 真正仅呈铺装、两侧栏杆顶部与两端岩台平面，没有再显示桥拱侧面。两端铺装向外连续开放，与connected-approaches整体图相容。补顶图的目的已达成，可作为直桥顶向轮廓参考；不得将其误称桥拱几何或承载数据。 |

| 本节文件简名 | 尺寸 | SHA-256 |
| --- | --- | --- |
| sect-gate-to-main-hall-ground-v2.png | 1672×941 | `DDE6BF1FCFB876CF4BB282683B7F3A9D28E3A305BF0F9FFFAB3271F5CC534291` |
| sect-main-hall-to-gate-ground-v2.png | 1672×941 | `F0D9711A5A01392767B16A85A9C4D036B365E83349A7B1C6E7D29F5031388318` |
| sect-west-to-east-cross-view-v2.png | 1672×940 | `A88096BF6769F4447B87D5AA7A57AB33FD41DF1E2D051FF84EAF635BC28DE52F` |
| sect-sword-flight-aerial-v2.png | 1672×941 | `3BCF5966B2017B1329E707E486D22EB2C80CFAFDD3A9FAB5B1B8EDF29176464F` |
| sect-layout-top-ortho-v4-grand-stairs.png | 1672×941 | `E7BF4903EB92414B0EAF3E134BAE5296805C9FF0180D7B432783210A84D15CE3` |
| straight-jade-bridge-top-ortho.png | 2172×724 | `91BEDAADFCB49A46152D7C8ED88B87DA331F7DD84DC9606FD1C5CEFC0AFF4661` |

六张均实际可解码为PNG；最后一张是3:1结构长图，其比例不构成缺陷。

## 按用户类别核对：60/60类有真实图片

这是按 `prompt2.md` 的A08+B10+C10+D10+E08+F08+G06逐类映射的覆盖检查，**不是把草稿和修订文件数加起来凑60**。每类选一个现有非空代表图，实查60个唯一代表路径无缺失；每个类别的实际图面已在本次或前几轮独立报告查看。以下仅代表“有图”，不自动等于“质量全部通过”。

| 组 | 要求类别 | 有真实图的类别 | 说明 |
| --- | --- | --- | --- |
| A | 8 | 8 | A05三重檐、A08最新南侧长阶仍需上述修复。 |
| B | 10 | 10 | 每类有五总体视角与细节图板；B04/B05背面及B06/B07顶面应以单独修正版替代旧错误面板，不能同时认定旧面板也有效。B10普通亭补图属于同一类别，不另加类别数。 |
| C | 10 | 10 | 采用开放连接修正版；C05还附独立严格顶图，补图不另加类别数。 |
| D | 10 | 10 | 包括云雾与远景天空，不把多视角单独计类。 |
| E | 8 | 8 | 材质表面参考，未冒称真实PBR分通道交付。 |
| F | 8 | 8 | 每类一张含四关键状态的真实图板，四格不算四类别。 |
| G | 6 | 6 | 护宗大阵采用固定构图v2；日夜/天气其余五类齐全。 |
| 合计 | 60 | 60 | 全部代表图存在且非空；质量结论须结合缺陷及适用边界。 |

### 逐类代表路径

所有路径相对 `assets/references/qingxuan-sect/`。旧草稿、旧版本、质量报告和生成提示词都没有充当缺失图片。

| 类别 | 代表图 |
| --- | --- |
| A01 | `00-art-direction/sect-overview-aerial.png` |
| A02 | `01-master-layout/sect-layout-top-ortho-v4-grand-stairs.png` |
| A03 | `01-master-layout/sect-terrain-section-v3.png` |
| A04 | `01-master-layout/sect-front-distant-v4-grand-stairs.png` |
| A05 | `01-master-layout/sect-gate-to-main-hall-ground-v3.png` |
| A06 | `01-master-layout/sect-main-hall-to-gate-ground-v2.png` |
| A07 | `01-master-layout/sect-west-to-east-cross-view-v2.png` |
| A08 | `01-master-layout/sect-sword-flight-aerial-v3-grand-stairs.png` |
| B01 | `02-architecture/sect-gate/sect-gate-structure-sheet.png` |
| B02 | `02-architecture/main-hall/main-hall-structure-sheet.png` |
| B03 | `02-architecture/scripture-pavilion/scripture-pavilion-structure-sheet.png` |
| B04 | `02-architecture/alchemy-hall/alchemy-hall-structure-sheet.png` |
| B05 | `02-architecture/forging-hall/forging-hall-structure-sheet.png` |
| B06 | `02-architecture/disciple-residence/disciple-residence-structure-sheet.png` |
| B07 | `02-architecture/elder-residence/elder-residence-structure-sheet.png` |
| B08 | `02-architecture/cultivation-cave/cave-entrance-structure-sheet.png` |
| B09 | `02-architecture/cultivation-cave/cave-interior-structure-sheet.png` |
| B10 | `02-architecture/sword-pavilion/sword-pavilion-structure-sheet.png` |
| C01 | `03-environment/ascension-stairs-structure-v2.png` |
| C02 | `03-environment/welcome-plaza-structure.png` |
| C03 | `03-environment/sword-platform-structure.png` |
| C04 | `03-environment/training-courtyard-structure.png` |
| C05 | `03-environment/straight-jade-bridge-connected-approaches.png` |
| C06 | `03-environment/curved-cloud-bridge-structure-v2.png` |
| C07 | `03-environment/cliff-boardwalk-structure.png` |
| C08 | `03-environment/path-rail-lamp-modules.png` |
| C09 | `03-environment/spiritual-spring-pool-structure-v2.png` |
| C10 | `03-environment/spirit-fields-herb-garden-structure.png` |
| D01 | `04-natural-assets/main-peak-structure.png` |
| D02 | `04-natural-assets/secondary-peak-structure.png` |
| D03 | `04-natural-assets/cliff-wall-modules.png` |
| D04 | `04-natural-assets/rocks-size-family.png` |
| D05 | `04-natural-assets/pine-tree-structure.png` |
| D06 | `04-natural-assets/bamboo-common-vegetation.png` |
| D07 | `04-natural-assets/spirit-herbs-luminous-plants.png` |
| D08 | `04-natural-assets/waterfall-stream-structure.png` |
| D09 | `04-natural-assets/mountain-mist-layers.png` |
| D10 | `04-natural-assets/distant-mountains-sky.png` |
| E01 | `05-materials/ink-teal-glazed-tiles.png` |
| E02 | `05-materials/white-jade-stone.png` |
| E03 | `05-materials/blue-gray-stone-bricks.png` |
| E04 | `05-materials/dark-xuan-wood.png` |
| E05 | `05-materials/gilded-metal-decoration.png` |
| E06 | `05-materials/mountain-rock-surface.png` |
| E07 | `05-materials/soil-grass-ground.png` |
| E08 | `05-materials/spiritual-water-surface.png` |
| F01 | `06-vfx/spirit-gathering-array-states.png` |
| F02 | `06-vfx/sect-protection-barrier-states.png` |
| F03 | `06-vfx/orbiting-sword-array-states.png` |
| F04 | `06-vfx/sword-flight-trail-states.png` |
| F05 | `06-vfx/flowing-spiritual-particles-states.png` |
| F06 | `06-vfx/volumetric-cloud-sea-states.png` |
| F07 | `06-vfx/spiritual-spring-water-states.png` |
| F08 | `06-vfx/architecture-spiritual-aura-states.png` |
| G01 | `07-lighting/sect-dawn.png` |
| G02 | `07-lighting/sect-noon.png` |
| G03 | `07-lighting/sect-sunset.png` |
| G04 | `07-lighting/sect-moonlit-night.png` |
| G05 | `07-lighting/sect-dense-cloud-weather.png` |
| G06 | `07-lighting/sect-protection-barrier-active-v2.png` |

B04补充有效背面：`02-architecture/alchemy-hall/alchemy-hall-back-ortho.png`；B05：`02-architecture/forging-hall/forging-hall-back-ortho.png`；B06补顶面：`02-architecture/disciple-residence/disciple-residence-top-ortho.png`；B07：`02-architecture/elder-residence/elder-residence-top-ortho-v2.png`；B10普通亭：`02-architecture/sword-pavilion/simple-pavilion-structure-sheet.png`；C05补顶面：`03-environment/straight-jade-bridge-top-ortho.png`。这些补图已在独立报告实际检查，不计为额外类别。

### 此刻的交接判断

完整性已达到60/60类别有图，主要美术风格、功能设施、自然资产、材质和四阶段特效参考已可阅读和组织交接。但**不得宣布全套一致性最终通过**：A05 v2主殿第三重檐不够明确，A08 v2南侧进路仍与最新直阶设计冲突，需真实修图后复查。图像不能提供精确隐藏几何、标高、碰撞或实时性能数据，这些仍应清楚标记为待确定；本轮没有提前建模或开发。

## 最后两项修复复核与视觉参考交接结论

本节为后续新增A05 v3与A08 v3的实际独立复核，取代上节针对旧v2文件的剩余缺陷状态。逐类代表路径表已更新为这两张最新图；历史缺陷描述保留，以便追溯修复过程。

### A05 v3：主殿三重檐

文件：`01-master-layout/sect-gate-to-main-hall-ground-v3.png`，SHA-256：`8CC5BA50310DCE91122C8F5EF79DE08FBB2251A266CF7A6E9B96E287E9A2FB25`。

已实际查看：最高、中间、最低三道完整青瓦主檐均能清楚分辨，下层主檐贯通主屋宽度，不再仅在左右翼露出。三重檐的层数与B02主殿母版相容，主殿仍位于直阶上方，入口开放；西侧保留单座七层藏经塔，没有再次变成多层宫殿。**此前A05 v2檐层不清的可见缺陷已修复。** 柱窗精确开间、屋顶曲率和尺寸并未因此变成已验证数据。

### A08 v3：南侧白玉长阶

文件：`01-master-layout/sect-sword-flight-aerial-v3-grand-stairs.png`，SHA-256：`60FCBA8BBAE313442A672277A339D48DCB32B4A15564F6928733CCA3976DCD0D`。

已实际查看：左下南侧进路已从长段平铺桥面改为宽大的连续白玉踏步，梯段之间有同轴休息平台；下方有可见山体/岩台承托，两侧护栏沿坡延伸，没有以悬空薄阶代替地形。阶梯沿同一直线进入迎仙圆广场，再经单座主山门接上登仙主轴，未见横向栏板或装饰阻挡入口。主轴上方分段休息平台、西侧单座藏经塔与东侧试剑区保留。**此前A08 v2与最新南入口直阶要求的冲突已修复。**

### 逐类与配套补图最终实查

再次以独立类别映射检查A8、B10、C10、D10、E8、F8、G6，共**60/60类别**各有真实代表图。另有六张必要的结构补图：B04背面、B05背面、B06顶面、B07顶面、B10普通亭、C05严格顶面，合计**66张有效参考文件**；它们没有被重复计成额外类别。

对这66个最终代表/补图路径执行实际PNG解码：66个唯一路径，**0个缺失或解码失败**。资源目录本次共有**88张PNG**，含旧稿和被替代版本；88不是最终有效交付数量。旧错误背面/旧封路图/旧场景v2不能与修正版并列当成同一资产的有效结构规范。

### 当前验收判断

**本轮已列出的阻断性可见缺陷经过真实重生成和独立复核，最新版本未再发现这些阻断问题。图集可作为60类别、66张文件的视觉设计参考交接。** 交接时须通过索引指定最新代表图及补图、明确旧面板退役，并区分美术基准、总平面、侧剖、资产图板与特效示例的用途。

这不是“所有图片在像素级或全部隐藏结构上完全一致”的证明，也不是生产三维资产、实际可走地图、碰撞或实时性能验收。图像无法确定的标高、柱距、屋顶内部、洞府连接、力学支撑、碰撞和精确米制比例仍应标记为待确定。E组仍是材质表面参考，F组仍是静态关键状态参考，不能冒称已交付真实PBR通道或运行中的动态特效。本轮没有创建三维模型、编写游戏代码或提前进入开发阶段。

