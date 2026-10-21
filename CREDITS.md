# CREDITS

入库并随站点分发的第三方内容一览。`static/vendor/` 下的许可全文与这里的条目一一对应；新增前须先列来源、版本、许可与体积并经用户同意（D016）。

## 第三方代码（同源内置，不用 CDN）

| 组件 | 版本 | 许可 | 位置 | 许可全文 |
|------|------|------|------|----------|
| three.js | r170 | MIT | `static/vendor/three.module.min.js`（外置，页面直接加载） | `static/vendor/three.LICENSE` |
| three.quarks | 0.16.0 | MIT（Copyright 2019 Forrest Sun） | 打包进 `static/arena3d.js`（粒子/拖尾） | `static/vendor/three.quarks.LICENSE` |
| postprocessing | 6.39.5 | Zlib（Copyright 2015 Raoul van Rüschen） | 打包进 `static/arena3d.js`（后期处理） | `static/vendor/postprocessing.LICENSE` |

`static/arena3d.js` 由 `scripts/build.mjs` 生成，构建时把上面两条打包库的版权与许可声明写进分发物本身：文件头部列出组件与许可，文件末尾附 MIT 全文（用 `tail -c 2000 static/arena3d.js` 可见）。只改 `src/battle/**` 或 `package.json` 时无需改动本表；**新增**打包库必须同时补 `static/vendor/<name>.LICENSE`、在 `scripts/build.mjs` 的声明里登记、重跑 `npm run build` 并提交 bundle。

构建工具（esbuild 0.25.12 MIT、TypeScript 5.9.3 Apache-2.0）只在开发机使用，`node_modules/` 不入库、不分发，因此不在署名范围内。

## 美术素材（用户提供）

| 文件 | 内容 | 来源与授权 | 处理 |
|------|------|-----------|------|
| `assets/char_protagonist_turnaround_v001.png` | 主角三视图设定图 | 用户提供，使用权归项目所有者，可入库分发（D017） | `scripts/cutout_turnaround.py` 裁切为 `static/art/hero/*.png` |
| `assets/mon_amethyst_winged_lion_king_sheet_v001.png` | 紫晶翼狮王设定集 | 用户提供（D018） | 裁切为 `static/art/lion/*.png`，来源另见 `static/art/lion/SOURCE.md` |
| `assets/ref_qingxuan_sect_*_concept_v001.png`、`_prompt_v001/v002.md` | 青玄剑宗场景参考图与配套提示词 | 用户提供，仅作设计参考 | 不被服务、不被测试读取；命名与登记见 `assets/NAMING.md` |

本阶段未引入任何第三方模型/贴图资产（D016：检索的免费低模达不到品质基准，高品质模型需登录下载），因此没有第三方署名义务。日后若引入，先登记本文件再入库。
