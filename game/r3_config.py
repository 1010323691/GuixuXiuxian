"""R3 long-profile catalog. Integer data only; engine/storage own all transitions.

Old world_config is intentionally untouched. R3 new materials live in
world.r3.materials; ordinary herbs/ore/wood/crystal remain in world.inventory.
Quality IDs are integers 0..4; all percentage values are basis points (1%=100).
"""
CONTENT_VERSION = 1
PROFILE_ID = 'r3'
BASE_DAILY_XP = 540
SECONDS_PER_DAY = 86400
MICROS_PER_XP = 1_000_000
# Growth uses arbitrary-precision Python integers; no gameplay XP cap.
CURVE_VERSION = 2
LEGACY_BASE_DAYS = [3, 4, 5, 5, 6, 7, 7, 8]
LEGACY_COSTS = [1620, 3240, 5940, 8640, 14580, 24570, 34020, 51840]
# Half-days use an exact integer numerator/denominator in CURVES.
BASE_DAYS = [0.5, 1.5, 3, 5, 7, 8, 9, 11]
COEFFICIENTS = [(1, 1), (3, 2), (11, 5), (16, 5), (9, 2), (13, 2), (9, 1), (12, 1)]
COSTS = [270, 1215, 3564, 8640, 17010, 28080, 43740, 71280]
CURVES = {
    1: {'costs': LEGACY_COSTS, 'day_halves': [6, 8, 10, 10, 12, 14, 14, 16]},
    2: {'costs': COSTS, 'day_halves': [1, 3, 6, 10, 14, 16, 18, 22]},
}
STAGES = [
    {'stage': s, 'name': name, 'factor_num': num, 'factor_den': den,
     'days': BASE_DAYS[s], 'cost': COSTS[s], 'final': s == 7}
    for s, (name, (num, den)) in enumerate(zip(
        ['筑基', '结丹', '元婴', '化神', '炼虚', '合体', '大乘', '渡劫'], COEFFICIENTS))
]
TOTAL_SPEED_CAP_BP = 1500
TREASURE_CAP_BP = 1000
OTHER_CAP_BP = 500
QUALITIES = [
    {'id': q, 'name': name, 'combat_bonus_bp': bonus,
     'treasure_speed_bp': 100*(q+1), 'main_attack_bp': 200*(q+1),
     'guard_hp_bp': 300*(q+1)}
    for q, (name, bonus) in enumerate(zip(
        ['凡品', '下品', '中品', '上品', '极品'], [0, 1000, 2500, 4000, 6000]))
]
OTHER_BONUSES = {
    'wood_root': {'name': '木灵根', 'levels_bp': [0, 25, 50, 100]},
    'skill': {'name': '当前功法进修', 'levels_bp': [0, 0, 50, 100]},
    'chamber': {'name': '洞府静室', 'levels_bp': [0, 25, 50, 100]},
    'spirit_array': {'name': '聚灵阵', 'levels_bp': [0, 25, 50, 100]},
    'sect': {'name': '当前宗门职位', 'ranks_bp': [0, 10, 25, 50], 'thresholds': [20, 60, 120]},
    'title': {'name': '已佩戴成就称号', 'equipped_bp': 50},
}
QUALITY_NAMES = [q['name'] for q in QUALITIES]
ENHANCE_BONUS_BP = [0, 500, 1000, 1500]
EQUIPMENT = {
    'blade': {'name': '灵刃', 'kind': 'equipment', 'slot': 'weapon',
              'stat': 'attack', 'base': 8, 'per_chapter': 2,
              'cost': {'ore': 6, 'wood': 2}, 'max_enhance': 3},
    'armor': {'name': '玄甲', 'kind': 'equipment', 'slot': 'armor',
              'stat': 'max_hp', 'base': 30, 'per_chapter': 10,
              'cost': {'ore': 8, 'wood': 3}, 'max_enhance': 3},
    'pendant': {'name': '灵佩', 'kind': 'equipment', 'slot': 'pendant',
                'stat': 'max_mp', 'base': 10, 'per_chapter': 2,
                'cost': {'ore': 4, 'crystal': 2}, 'max_enhance': 3},
}
TREASURES = {
    'main_treasure': {'name': '本命法宝', 'kind': 'treasure', 'slot': 'main',
                      'cultivation_stat': 'speed_bp', 'combat_stat': 'attack_bp',
                      'cost': {'dust': 4, 'herb': 4, 'ore': 4, 'wood': 4},
                      'max_enhance': 0},
    'guard_treasure': {'name': '护持法宝', 'kind': 'treasure', 'slot': 'guard',
                       'cultivation_stat': 'speed_bp', 'combat_stat': 'max_hp_bp',
                       'cost': {'dust': 4, 'herb': 4, 'ore': 4, 'wood': 4},
                       'max_enhance': 0},
}
# 战力型法宝在自动斗法中独立出手/回护；按品质（凡/下/中/上/极）取值。
TREASURE_COMBAT = {
    'main': {'cd': 2, 'attack_pct': [30, 34, 38, 42, 46]},
    'guard': {'cd': 3, 'absorb_hp_pct': [6, 8, 10, 12, 14]},
}
TREASURE_PATHS = {
    'unselected': '尚未定向（不可装备）',
    'cultivation': '修炼型：只提高未来持续修炼速率',
    'combat': '战力型：只提高实际战斗能力',
}
FORGE_COSTS = {
    1: {'ore': 4, 'enhance_material': 1},
    2: {'ore': 8, 'enhance_material': 2},
    3: {'ore': 12, 'enhance_material': 3},
}
QUALITY_UPGRADE_COSTS = {
    1: {'dust': 8, 'crystal': 1},
    2: {'dust': 12, 'crystal': 2},
    3: {'dust': 16, 'crystal': 3},
    4: {'dust': 20, 'crystal': 4},
}
DECOMPOSE = {
    q: {'enhance_material': 1+q, 'dust': 1+q//2} for q in range(5)
}
MATERIALS = {
    'dust': {'name': '宝尘', 'description': '保底制作与逐级提升法宝品质。'},
    'enhance_material': {'name': '通用强化材', 'description': '三器强化共用，低难副本也稳定取得。'},
    'boss_coin': {'name': '界门战功币', 'description': '世界Boss按个人最高有效伤害补差取得，2枚兑换宝尘1。'},
}
RESOURCE_STORAGE = {**{k: 'world.inventory' for k in ['herb', 'ore', 'wood', 'crystal']},
                    **{k: 'world.r3.materials' for k in MATERIALS}, 'stone': 'world.wallet'}
INITIAL_MATERIALS = {'dust': 0, 'enhance_material': 0, 'boss_coin': 0}
LIMITS = {'owned_instances': 200, 'pending_instances': 200, 'material': 999999}
INSTANCE_FIELDS = ['uid', 'template_id', 'chapter', 'quality', 'enhance', 'effect_type', 'source_receipt']
EQUIPMENT_SLOTS = ['weapon', 'armor', 'pendant']
TREASURE_SLOTS = ['main', 'guard']
DROP_CYCLE = ['blade', 'armor', 'pendant', 'main_treasure', 'guard_treasure']
DUNGEON_RULES = {
    'daily_rewarded_clears': 3, 'timezone': 'UTC', 'battles_per_run': 3,
    'max_chapter': 7, 'chapter_requires_stage': True,
    'score_chapter_weight': 2, 'score_quality_offset': 1,
    'no_reward_practice': True, 'difficulty_snapshot': True,
    'deterministic_rewards': True, 'failed_runs_advance_pity': False,
}
DIFFICULTIES = {
    1: {'name': '历练', 'multiplier_num': 1, 'multiplier_den': 1,
        'required_clear': 0, 'score_base': 0, 'score_per_chapter': 0,
        'quality_base': 0, 'materials': {'dust': 2, 'enhance_material': 2}},
    2: {'name': '险境', 'multiplier_num': 5, 'multiplier_den': 4,
        'required_clear': 1, 'score_base': 6, 'score_per_chapter': 6,
        'quality_base': 1, 'materials': {'dust': 3, 'enhance_material': 4}},
    3: {'name': '绝境', 'multiplier_num': 3, 'multiplier_den': 2,
        'required_clear': 2, 'score_base': 12, 'score_per_chapter': 6,
        'quality_base': 2, 'materials': {'dust': 4, 'enhance_material': 6}},
}
# Evaluate entries in listed order: largest quality guarantee takes priority.
# Count only completed rewarded runs for this difficulty, starting at 1.
PITY = {
    1: [{'every': 10, 'quality': 2}, {'every': 5, 'quality': 1}],
    2: [{'every': 12, 'quality': 3}, {'every': 4, 'quality': 2}],
    3: [{'every': 12, 'quality': 4}, {'every': 3, 'quality': 3}],
}
ENEMIES = {
    'mob': {'hp_base': 110, 'hp_chapter': 60, 'attack_base': 20, 'attack_chapter': 10,
            'heavy_base': 35, 'heavy_chapter': 15},
    'boss': {'hp_base': 300, 'hp_chapter': 180, 'attack_base': 30, 'attack_chapter': 12,
             'heavy_base': 50, 'heavy_chapter': 20},
}
# Only real dust exchange is implemented; no placeholder quality-blueprint shop.
BOSS = {
    'name': '界门裂隙·NPC模拟世界Boss', 'simulation': True,
    'rounds': 12, 'daily_attempts': 3, 'timezone': 'UTC', 'hp': 10**12,
    'reference_base': 450, 'reference_stage': 180,
    'score_cap_num': 2, 'score_cap_den': 1,
    'coin_participation': 2, 'coin_scale': 60, 'coin_max': 62,
    'attack_base': 30, 'attack_stage': 12, 'heavy_base': 50, 'heavy_stage': 20,
    'intent_cycle': ['attack', 'charge', 'heavy'],
    'player_only_damage': True, 'count_companion_damage': False,
    'require_kill': False, 'best_only': True, 'minimum_valid_commands': 1,
    'bands': [
        {'num': 1, 'den': 4, 'name': '初试', 'dust_total': 1},
        {'num': 1, 'den': 2, 'name': '入门', 'dust_total': 2},
        {'num': 1, 'den': 1, 'name': '精通', 'dust_total': 4},
        {'num': 3, 'den': 2, 'name': '大成', 'dust_total': 6},
        {'num': 2, 'den': 1, 'name': '极境', 'dust_total': 8},
    ],
    'exchanges': {'dust': {'name': '兑换宝尘', 'cost': {'boss_coin': 2}, 'reward': {'dust': 1}}},
}
# Milestones never grant XP, speed bonuses, or battle stats and never gate advance.
MILESTONES = {
    25: {'name': '中期·灵息渐稳', 'optional': True,
         'objectives': [{'kind': 'deliver', 'item': 'herb', 'amount': 2},
                        {'kind': 'craft', 'item': 'pill', 'amount': 1}],
         'reward': {'ore': 2}, 'xp': 0},
    50: {'name': '后期·心法融通', 'optional': True,
         'objectives': [{'kind': 'craft_then_use', 'amount': 1}],
         'reward': {'art_xp': 5}, 'xp': 0},
    75: {'name': '圆满·蓄势待破', 'optional': True,
         'objectives': [{'kind': 'secret_clear', 'amount': 1},
                        {'kind': 'map_commission', 'amount': 1}],
         'reward': {'wood': 2}, 'xp': 0},
}
PHASES = [{'percent': 0, 'name': '初期'}, {'percent': 25, 'name': '中期'},
          {'percent': 50, 'name': '后期'}, {'percent': 75, 'name': '圆满蓄势'},
          {'percent': 100, 'name': '可突破'}]
TEACH_COST = {'stone': 5}
FINAL_REWARD = {'stone': 100, 'crystal': 5}
FINAL_TITLE = {'id': 'mortal_sealer', 'name': '凡界封界者', 'combat_bonus': 0, 'speed_bp': 0}

EXCHANGES = {
    'dust': {'name': '战功币兑换宝尘', 'cost': {'boss_coin': 2}, 'reward': {'dust': 1}},
    'enhance_material': {'name': '四艺材料课业', 'cost': {'ore': 4, 'wood': 2}, 'reward': {'enhance_material': 1}},
}

# Longline inscription cannot charge crystal for a suppressed XP reward.
# Overrides affect R3 only; original free-profile story and XP remain unchanged.
ENCOUNTER_OVERRIDES = {
    'inscription': {
        'offer': {'name': '以晶辨矿', 'cost': {'crystal': 1}, 'reward': {'ore': 4},
                  'description': '灵晶照亮碑底矿纹，取回矿石4；无直接修为。'},
        'meditate': {'name': '循纹取木', 'cost': {}, 'reward': {'wood': 2},
                     'description': '循着碑文找到可用灵木2；持续修炼仍照常。'},
    },
}
