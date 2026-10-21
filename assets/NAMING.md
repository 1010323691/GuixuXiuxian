# assets 目录命名规则

`assets/` 存放项目所有者提供的**原始美术素材**（设定图、参考图、配套提示词），不被游戏直接服务；入库资源由脚本/构建处理后放到 `static/art/`。

## 格式

```
<类别>_<主题>_<类型>_v<三位版本>.<扩展名>
```

- 全部小写英文 + 数字 + 下划线（snake_case），**不使用中文、空格、大写、连字符**；
- 只有一个扩展名（避免 `.png.png`），扩展名小写；
- 版本号 `v001` 起，同一素材重绘/修订时递增，**不覆盖旧版本**；
- 主题用能区分对象的英文名（角色用其英文名，魔物同理）；
- 参考图与配套提示词同样适用本规则，提示词的扩展名为 `.md`（`ref_*` 前缀），不另建中文名或 `prompt.md` 之类的通用名。

## 类别前缀

| 前缀 | 含义 |
|------|------|
| `char_` | 人物/主角设定 |
| `mon_`  | 魔物/Boss 设定 |
| `env_`  | 场景/环境 |
| `prop_` | 道具/法宝/特效元素 |
| `ui_`   | 界面元素 |
| `ref_`  | 风格/品质参考图（仅参考，不入游戏） |

## 类型后缀

`turnaround`（三视图）、`sheet`（设定集）、`concept`（概念图/参考图）、`sample`（示例）、`icon`、`texture`、`prompt`（配套提示词文本）等，按实际内容选用。

## 当前文件

| 文件 | 说明 |
|------|------|
| `char_protagonist_turnaround_v001.png` | 修仙主角三视图设定图（`scripts/cutout_turnaround.py` 的输入） |
| `mon_amethyst_winged_lion_king_sheet_v001.png` | 紫晶翼狮王设定集 |
| `ref_qingxuan_sect_aerial_concept_v001.png` | 青玄剑宗总览鸟瞰参考图 |
| `ref_qingxuan_sect_layout_oblique_concept_v001.png` | 青玄剑宗布局斜视图（草稿） |
| `ref_qingxuan_sect_layout_orthographic_concept_v001.png` | 青玄剑宗布局正交视图 |
| `ref_qingxuan_sect_terrain_concept_v001.png` | 青玄剑宗地形剖面参考图 |
| `ref_qingxuan_sect_player_view_concept_v001.png` | 青玄剑宗玩家地面视角参考图 |
| `ref_qingxuan_sect_gate_concept_v001.png` | 青玄剑宗山门四视图 |
| `ref_qingxuan_sect_prompt_v001.md` | 青玄剑宗场景搭建提示词（第一版） |
| `ref_qingxuan_sect_prompt_v002.md` | 青玄剑宗场景搭建提示词（第二版，含参考图清单与目录约定） |

### 尚未入库

| 文件 | 说明 |
|------|------|
| `ref_battle_scene_sample_v001.png` | 斗法场景品质基准图（用户提供的参考，**尚未入库**）。D016 用它作为「免费低模达不到品质要求」的判断依据；入库时按本规则放在 `assets/` 下。 |

## 改名注意

被引用的素材改名时需同步引用处：`scripts/cutout_turnaround.py`、`static/art/hero/SOURCE.md`、`src/battle/art.ts` 注释、`tests/test_frontend_build.py`、`docs/studio/DECISIONS.md`；改 `src/` 后须 `npm run build` 重新生成 `static/arena3d.js`。

`ref_*` 参考图与提示词不被服务、不被测试读取，改名只需更新本文件的「当前文件」表与引用它们的文档；`prompt2.md` 正文里提到的 `assets/references/qingxuan-sect/` 是提示词写作时的**建议目录**，不是本仓库的实际路径。
