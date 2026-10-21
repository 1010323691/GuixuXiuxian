# assets 目录命名规则

`assets/` 存放项目所有者提供的**原始美术素材**（设定图、参考图），不被游戏直接服务；入库资源由脚本/构建处理后放到 `static/art/`。

## 格式

```
<类别>_<主题>_<类型>_v<三位版本>.<扩展名>
```

- 全部小写英文 + 数字 + 下划线（snake_case），**不使用中文、空格、大写、连字符**；
- 只有一个扩展名（避免 `.png.png`），扩展名小写；
- 版本号 `v001` 起，同一素材重绘/修订时递增，**不覆盖旧版本**；
- 主题用能区分对象的英文名（角色用其英文名，魔物同理）。

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

`turnaround`（三视图）、`sheet`（设定集）、`concept`（概念图）、`sample`（示例）、`icon`、`texture` 等，按实际内容选用。

## 当前文件

| 文件 | 说明 |
|------|------|
| `char_protagonist_turnaround_v001.png` | 修仙主角三视图设定图（`scripts/cutout_turnaround.py` 的输入） |
| `mon_amethyst_winged_lion_king_sheet_v001.png` | 紫晶翼狮王设定集 |
| `ref_battle_scene_sample_v001.png` | 斗法场景品质参考图 |

## 改名注意

被引用的素材改名时需同步引用处：`scripts/cutout_turnaround.py`、`static/art/hero/SOURCE.md`、`src/battle/art.ts` 注释、`tests/test_frontend_build.py`、`docs/studio/DECISIONS.md`；改 `src/` 后须 `npm run build` 重新生成 `static/arena3d.js`。
