# V2 美术资源台账

全部资源由视觉岗位在本轮手工编写为矢量代码，无第三方素材、字体或图标库，无许可限制；不新增静态文件。

| 资源 id | 类型 | 用途 | 位置 | 来源 / 许可 | 状态 |
|---|---|---|---|---|---|
| `i-world` `i-character` `i-sects` `i-social` `i-craft` `i-exploration` `i-estate` `i-market` `i-quests` `i-achievements` `i-arena` | 24px SVG symbol | 11 个世界页玉牌导航图标 | `static/index.html` 顶部 `.icon-sprite` | 自制 / 项目自有 | 正式 |
| `i-battle` `i-scroll` | 24px SVG symbol | 预留：战斗、卷轴类图标 | 同上 | 自制 / 项目自有 | 正式（暂未引用） |
| 系统钮遮罩图标（存档/载入/新卷） | data URI SVG mask | 顶栏胶囊按钮 | `static/styles.css` `#save-button` 等的 `--glyph` | 自制 / 项目自有 | 正式 |
| 场景横幅 ×11 + 公共底景 | 运行时内联 SVG | 世界页与序章场景横幅 | `static/app.js` `sceneMarks` / `sceneBanner()` | 自制 / 项目自有 | 正式 |
| 页面远山与灵气微粒 | CSS clip-path + box-shadow | 全局背景 | `static/styles.css` `.landscape*` `.motes` | 自制 / 项目自有 | 正式 |
| 画框角花、匾额描金、卷轴轴头、印章 | CSS 渐变 / 阴影 | 面板与标题装饰 | `static/styles.css` `--corners` 等 | 自制 / 项目自有 | 正式 |
| 主角立绘（九境递进：光环色、冠、簪、法宝珠、光晕） | 运行时内联 SVG | HUD 头像、对峙舞台、人物页舞台 | `static/app.js` `portrait()`；色阶 `--tier-0..8` | 自制 / 项目自有 | 正式（V3） |
| 敌人剪影 ×8（猿/傀/影/兽/蛟/狐/修士/灵）+ 首领光环 | 运行时内联 SVG | 凡界与序章对峙舞台 | `static/app.js` `enemyPortrait()`；色 `--enemy-*` | 自制 / 项目自有 | 正式（V3） |
| `i-save` `i-load` `i-new` `i-prev` `i-next` `i-lock` `i-close` | 24px SVG symbol | 翻页钮、阅览关闭等 | `static/index.html` `.icon-sprite` | 自制 / 项目自有 | 正式（V3） |
| 手机端存/读/新图标钮 | data URI SVG mask | <760px 时并入 HUD 行 | `static/styles.css` `--tool-icon` | 自制 / 项目自有 | 正式（V3） |
| favicon | data URI SVG | 朱砂底"归"字 | `static/index.html` `<link rel="icon">` | 自制 / 项目自有 | 正式 |

占位与替换：无占位资源。法宝槽以汉字字形（剑/甲/佩/鼎/镜）代替插画，属于正式的文字化风格选择，后续如增加物品插画需另行登记。
