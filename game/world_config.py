"""Versioned, JSON-compatible mortal-world content catalog; mechanics live in world.py."""
CONTENT_VERSION = 1
REALM_CAP = '渡劫'
EXPANSION = {'id': 'immortal', 'name': '仙界', 'implemented': False, 'message': '仙界属于未来大版本，本版完整体验止于凡界界门封印。'}
STAGES = [
    {'stage': s, 'id': rid, 'name': name, 'xp_cost': 100 + 60*s,
     'max_hp': 200 + 100*s, 'max_mp': 60 + 10*s, 'attack': 40 + 15*s,
     'gate': gate}
    for s, rid, name, gate in [
        (0, 'foundation', '筑基', {'type': 'consume', 'target': 'barrier_pill', 'amount': 1}),
        (1, 'core', '结丹', {'type': 'consume', 'target': 'soul_talisman', 'amount': 1}),
        (2, 'soul', '元婴', {'type': 'equipment', 'target': 'any', 'amount': 1}),
        (3, 'divinity', '化神', {'type': 'array', 'target': 'spirit_array', 'amount': 1}),
        (4, 'void', '炼虚', {'type': 'sect_contribution_total', 'target': 'any', 'amount': 40}),
        (5, 'union', '合体', {'type': 'friend_and_teaching', 'target': 'any', 'amount': 30}),
        (6, 'mahayana', '大乘', {'type': 'family_and_array', 'target': 'seal_array', 'amount': 2}),
        (7, 'tribulation', '渡劫', {'type': 'secrets_and_finale', 'target': 'all', 'amount': 3}),
    ]
]
RESOURCES = {'stone': '凡界灵石', 'herb': '药草', 'ore': '矿石', 'wood': '灵木', 'crystal': '灵晶'}
INITIAL_RESOURCES = {'stone': 60, 'herb': 6, 'ore': 6, 'wood': 6, 'crystal': 2}
LIMITS = {'resource': 999999, 'journal': 100, 'relations': 100, 'art_level': 3, 'skill_level': 3, 'orders': 3}
COMBAT = {'power_mp': 24, 'defend_mp': 6, 'defend_multiplier': 0.5,
          'boss_hp_base': 300, 'boss_hp_stage': 180, 'boss_hit_base': 30, 'boss_hit_stage': 12,
          'boss_heavy_base': 50, 'boss_heavy_stage': 20,
          'mob_hp_base': 110, 'mob_hp_stage': 60, 'mob_hit_base': 20, 'mob_hit_stage': 10,
          'mob_heavy_base': 35, 'mob_heavy_stage': 15,
          'intent_cycle': ['attack', 'charge', 'heavy'], 'defeat_hp': 1}
# 群战小怪（长线进度）：按境界 lo + min(hi-lo, stage//2) 只。首领保留原气血；每只小怪另有原气血的 minion_hp_pct；
# 每拍期望伤害中 minion_hit_pct 划给小怪（各自固定小击）——无视小怪时拍数与承伤同旧单体，见 docs/iterations/FB3_SWARM.md
SWARMS = {'minion_hp_pct': 12, 'minion_hit_pct': 30,
          'counts': {'wild': (2, 3), 'escort': (3, 4), 'secret': (2, 3), 'guard': (3, 5), 'dungeon': (2, 3), 'dungeon_boss': (4, 6), 'elite': (3, 4)},
          'names': {'wild': '荒野小妖', 'escort': '劫道山匪', 'secret': '地宫傀卫', 'guard': '劫影分身', 'dungeon': '巢穴幼兽', 'dungeon_boss': '镇守亲卫', 'elite': '精英随从'},
          'ordinals': '甲乙丙丁戊己'}
PROGRESSION = {'cultivate_base': 12, 'cultivate_stage': 4, 'rest_hp': 80, 'rest_mp': 30,
               'gather': 3, 'condense': 1, 'art_xp': 5, 'art_thresholds': [0, 20, 50],
               'root_cost': {'herb': 6, 'crystal': 1}, 'body_cost': {'ore': 4, 'crystal': 1},
               'root_cap': 3, 'body_cap': 3, 'reawaken_stone': 30}
REGIONS = {
    'qinglan': {'name': '青岚州', 'stage': 0, 'material': 'herb', 'faction': '青岚盟', 'specialty_bonus': 1,
                'description': '村外的青山连成药田，青岚盟正在收拢归墟余波中失散的修士。'},
    'chisha': {'name': '赤砂洲', 'stage': 1, 'material': 'ore', 'faction': '赤砂会', 'specialty_bonus': 1,
               'description': '赤砂下的古炉仍未熄灭，赤砂会以锻器与护送维系荒原商道。'},
    'xuanchao': {'name': '玄潮域', 'stage': 2, 'material': 'wood', 'faction': '玄潮阁', 'specialty_bonus': 1,
                 'description': '潮水绕过残缺星碑，玄潮阁的阵师正寻找封闭界门的旧契。'},
}
ROOTS = {
    'wood': {'name': '木灵根', 'description': '生机绵长，利于吐纳与采药。', 'cultivate': 3, 'gather_herb': 1},
    'fire': {'name': '火灵根', 'description': '灵息炽烈，直接提高凡界攻击。', 'attack': 4},
    'earth': {'name': '土灵根', 'description': '根基厚重，提高气血上限。', 'max_hp': 25},
}
CONSTITUTIONS = {
    'clear': {'name': '清灵体', 'description': '灵台澄明，提高灵力上限。', 'max_mp': 10},
    'sturdy': {'name': '坚骨体', 'description': '筋骨坚韧，先于防御减少所受伤害。', 'damage_reduction': 2},
    'renew': {'name': '回元体', 'description': '调息迅速，提高静养恢复气血。', 'rest_hp': 20},
}
SKILLS = {
    'origin': {'name': '归元诀', 'description': '强攻每级额外提高0.1倍攻击。', 'effect': 'power_multiplier', 'amount': 0.1},
    'flame': {'name': '赤霄功', 'description': '普攻每级额外造成4点伤害。', 'effect': 'attack_bonus', 'amount': 4},
    'mountain': {'name': '玄岳经', 'description': '防御时每级额外减少2点原始敌伤。', 'effect': 'defend_reduction', 'amount': 2},
}
SECTS = {
    'sword': {'name': '青岚剑宗', 'region': 'qinglan', 'task': 'battle', 'description': '以护民与试剑修心，击败妖兽可得贡献。'},
    'herb': {'name': '百草谷', 'region': 'qinglan', 'task': 'craft', 'description': '以丹济世，制造丹药可得贡献。'},
    'array': {'name': '玄阵门', 'region': 'xuanchao', 'task': 'secret', 'description': '勘察地脉，通关秘境可得贡献。'},
}
SECT_RULES = {'ranks': [20, 60, 120], 'rank_names': ['记名弟子', '外门弟子', '内门弟子', '宗门长老'],
              'tasks': {'battle': {'goal': 1, 'contribution': 10, 'stone': 12},
                        'craft': {'goal': 1, 'contribution': 8, 'stone': 10},
                        'secret': {'goal': 1, 'contribution': 15, 'stone': 20}},
              'material_task_cost': 3, 'material_task_contribution': 8, 'material_task_stone': 10,
              'exchange': {'pill': {'contribution': 10, 'output': {'pill': 1}},
                           'crystal': {'contribution': 20, 'output': {'crystal': 3}},
                           'skill_coupon': {'contribution': 40, 'output': {'skill_coupon': 1}}}}
NPCS = {
    'healer': {'name': '林药师', 'gift': 'herb', 'art': 'alchemy', 'region': 'qinglan', 'role': 'alchemist',
               'description': '她在药棚中照看归墟伤者，愿将丹术传给肯耐心救人的修士。',
               'quest': 'healer_help', 'dialogue': ['一味灵草，也能替人留住一线生机。', '你的丹药替药棚解了燃眉之急。', '有你同行，这条山路便不再冷清。']},
    'smith': {'name': '铁衣道人', 'gift': 'ore', 'art': 'smithing', 'region': 'chisha', 'role': 'smith',
              'description': '旧甲上的裂痕记着商道旧战，他重视亲手锻出的器物。',
              'quest': 'smith_help', 'dialogue': ['器物不可只看光华，要看能否护住身后的人。', '这件灵刃的锤纹已经稳了。', '归墟若再生变，老夫与你同行。']},
    'stargazer': {'name': '沈观星', 'gift': 'wood', 'art': 'formations', 'region': 'xuanchao', 'role': 'talisman',
                  'description': '他在潮边重排星阵，寻找界门封印失落的一角。',
                  'quest': 'stargazer_help', 'dialogue': ['星位并非命数，阵眼仍在人心。', '你带回的潮府拓片正是缺失的一角。', '此后观星，不必再独守一夜。']},
}
DISCIPLES = {
    'herbalist': {'name': '采药童', 'material': 'herb', 'description': '善辨草木，可派往药谷。'},
    'forger': {'name': '铸炉徒', 'material': 'ore', 'description': '熟识矿脉，可派往矿山。'},
    'scout': {'name': '听风客', 'material': 'crystal', 'description': '擅寻秘闻，可派往古迹。'},
}
SOCIAL = {'gift_cost': 2, 'gift_relation': 5, 'talk_relation': 1, 'talk_interval': 3,
          'master_relation': 10, 'friend_relation': 30, 'family_relation': 20,
          'teach_stone': 5, 'teach_art_xp': 5, 'teach_relation': 2, 'teach_interval': 3,
          'disciple_stage': 2, 'disciple_teach_xp_cost': 5, 'disciple_teach_xp': 5,
          'disciple_thresholds': [0, 20, 50], 'dispatch_ticks': 3,
          'companion_damage': 10, 'companion_interval': 3}
FAMILIES = {
    'orchard': {'name': '族中药园', 'description': '每级采药额外增加1药草。', 'cost': {'wood': 3, 'ore': 3}, 'effect': 'gather_herb', 'amount': 1, 'cap': 3},
    'guard': {'name': '护院堂', 'description': '每级气血上限增加10。', 'cost': {'wood': 3, 'ore': 3}, 'effect': 'max_hp', 'amount': 10, 'cap': 3},
    'school': {'name': '家族学堂', 'description': '每级弟子授业经验额外增加1。', 'cost': {'wood': 3, 'ore': 3}, 'effect': 'disciple_xp', 'amount': 1, 'cap': 3},
}
HOMES = {
    'garden': {'name': '洞府药圃', 'description': '每级采药额外增加1。', 'cost': {'wood': 4, 'ore': 2}, 'effect': 'gather_herb', 'amount': 1, 'cap': 3},
    'workshop': {'name': '百工坊', 'description': '每级制造熟练额外增加1。', 'cost': {'ore': 4, 'crystal': 1}, 'effect': 'art_xp', 'amount': 1, 'cap': 3},
    'chamber': {'name': '静修室', 'description': '每级静养灵力额外增加5。', 'cost': {'wood': 4, 'crystal': 1}, 'effect': 'rest_mp', 'amount': 5, 'cap': 3},
}
ITEMS = {
    'pill': {'name': '回元丹', 'kind': 'consumable', 'hp': 80, 'mp': 20, 'buy': 12, 'sell': 6},
    'barrier_pill': {'name': '破障丹', 'kind': 'gate', 'description': '筑基突破结丹时消耗。'},
    'root_dew': {'name': '养根露', 'kind': 'growth', 'root_points': 1},
    'blade': {'name': '灵刃', 'kind': 'equipment', 'slot': 'weapon', 'attack': 8},
    'armor': {'name': '玄甲', 'kind': 'equipment', 'slot': 'armor', 'max_hp': 30},
    'pendant': {'name': '灵佩', 'kind': 'equipment', 'slot': 'pendant', 'max_mp': 10},
    'fire_talisman': {'name': '焚火符', 'kind': 'talisman', 'damage_multiplier': 1.5, 'buy': 10, 'sell': 5},
    'guard_talisman': {'name': '护身符', 'kind': 'talisman', 'duration': 2, 'damage_multiplier': 0.75},
    'soul_talisman': {'name': '镇魂符', 'kind': 'talisman', 'skip_enemy': 1, 'description': '可供突破使用，或使敌人跳过当前一回合。'},
    'spirit_array': {'name': '聚灵阵', 'kind': 'array', 'effect': 'cultivate', 'amount': 4, 'cap': 3},
    'mountain_array': {'name': '护山阵', 'kind': 'array', 'effect': 'damage_reduction', 'amount': 2, 'cap': 3},
    'seal_array': {'name': '封界阵', 'kind': 'array', 'effect': 'boss_attack', 'amount': 6, 'cap': 3},
    'skill_coupon': {'name': '功法进益券', 'kind': 'coupon', 'description': '抵一次功法升级的灵石成本，仍需灵晶。'},
}
RECIPES = {
    'pill': {'name': '回元丹', 'art': 'alchemy', 'cost': {'herb': 3}, 'output': {'pill': 1}},
    'barrier_pill': {'name': '破障丹', 'art': 'alchemy', 'cost': {'herb': 6, 'crystal': 2}, 'output': {'barrier_pill': 1}},
    'root_dew': {'name': '养根露', 'art': 'alchemy', 'cost': {'herb': 8, 'wood': 3}, 'output': {'root_dew': 1}},
    'blade': {'name': '灵刃', 'art': 'smithing', 'cost': {'ore': 6, 'wood': 2}, 'output': {'blade': 1}},
    'armor': {'name': '玄甲', 'art': 'smithing', 'cost': {'ore': 8, 'wood': 3}, 'output': {'armor': 1}},
    'pendant': {'name': '灵佩', 'art': 'smithing', 'cost': {'ore': 4, 'crystal': 2}, 'output': {'pendant': 1}},
    'fire_talisman': {'name': '焚火符', 'art': 'talismans', 'cost': {'wood': 4, 'crystal': 1}, 'output': {'fire_talisman': 1}},
    'guard_talisman': {'name': '护身符', 'art': 'talismans', 'cost': {'wood': 3, 'crystal': 1}, 'output': {'guard_talisman': 1}},
    'soul_talisman': {'name': '镇魂符', 'art': 'talismans', 'cost': {'wood': 5, 'crystal': 2}, 'output': {'soul_talisman': 1}},
    'spirit_array': {'name': '聚灵阵', 'art': 'formations', 'cost': {'wood': 4, 'ore': 4}, 'output': {'spirit_array': 1}},
    'mountain_array': {'name': '护山阵', 'art': 'formations', 'cost': {'ore': 6, 'crystal': 2}, 'output': {'mountain_array': 1}},
    'seal_array': {'name': '封界阵', 'art': 'formations', 'cost': {'wood': 6, 'crystal': 3}, 'output': {'seal_array': 1}},
}
ARTS = {'alchemy': '炼丹', 'smithing': '炼器', 'talismans': '制符', 'formations': '阵法'}
SECRETS = {
    'mist': {'name': '雾林遗径', 'region': 'qinglan', 'material': 'herb', 'description': '先寻雾中石标，再决定采集或修整，最后击退守林妖兽。'},
    'desert': {'name': '赤砂地宫', 'region': 'chisha', 'material': 'ore', 'description': '辨识炉壁旧刻，在矿脉与休息间选择，击败地宫守卫。'},
    'tide': {'name': '玄潮水府', 'region': 'xuanchao', 'material': 'wood', 'description': '勘探退潮水道，寻找灵木或休息，击败水府守卫。'},
}
DUNGEONS = {
    'den': {'name': '妖兽巢', 'region': 'qinglan', 'material': 'herb', 'boss': '噬雾妖王', 'description': '两轮兽群之后面对噬雾妖王，丹药与护身符可保留容错。'},
    'forge': {'name': '熔炉遗城', 'region': 'chisha', 'material': 'ore', 'boss': '赤炉魔像', 'description': '清理两队炉卫后面对魔像，玄甲与封界阵提供稳定优势。'},
    'tower': {'name': '沉星塔', 'region': 'xuanchao', 'material': 'wood', 'boss': '沉星阵灵', 'description': '穿过两层守卫后面对阵灵，镇魂符可以打断重击。'},
}
DIFFICULTIES = {1: {'name': '初探', 'multiplier': 1.0}, 2: {'name': '险境', 'multiplier': 1.25}, 3: {'name': '绝境', 'multiplier': 1.5}}
EVENTS = {
    'traveler': {'name': '受伤旅人', 'kind': 'encounter', 'description': '商道旁一位旅人正扶树喘息。',
                 'choices': {'heal': {'name': '赠草救治', 'cost': {'herb': 2}, 'reward': {'reputation': 5, 'relation': 2}},
                             'escort': {'name': '护送归途', 'battle': 'mob', 'reward': {'stone': 15}}}},
    'furnace': {'name': '废弃药炉', 'kind': 'encounter', 'description': '一尊旧药炉仍留着温热的余火。',
                'choices': {'repair': {'name': '修炉成丹', 'cost': {'ore': 2}, 'reward': {'pill': 1}},
                            'salvage': {'name': '拆解炉架', 'cost': {}, 'reward': {'wood': 2}}}},
    'inscription': {'name': '碑文回响', 'kind': 'encounter', 'description': '残碑上的文字与你的灵息相合。',
                    'choices': {'offer': {'name': '以晶共鸣', 'cost': {'crystal': 1}, 'reward': {'xp': 20}},
                                'meditate': {'name': '静悟碑意', 'cost': {}, 'reward': {'xp': 8}}}},
    'herb_tide': {'name': '药潮', 'kind': 'dynamic', 'description': '山野灵草繁茂，药草采集增加，市价回落。', 'gather_herb': 1, 'price_materials': ['herb'], 'price_multiplier': 0.8},
    'beast_tide': {'name': '兽潮', 'kind': 'dynamic', 'description': '商道急需清剿妖兽，普通战斗灵石奖励增加。', 'mob_stone': 4},
    'trade_tide': {'name': '商潮', 'kind': 'dynamic', 'description': '异地商队带来矿木灵晶，相关市价回落。', 'price_materials': ['ore', 'wood', 'crystal'], 'price_multiplier': 0.8},
}
EVENT_RULES = {'encounter_interval': 12, 'dynamic_interval': 20, 'duration': 6, 'npc_interval': 3, 'npc_wallet': 50}
QUESTS = {
    'first_art': {'name': '青岚余波·百工初试', 'chapter': 1, 'kind': 'counter', 'target': 'craft_total', 'amount': 1, 'reward': {'stone': 20, 'crystal': 1}, 'description': '亲手完成任一四艺制作，理解修行不止于战斗。'},
    'alliance': {'name': '三宗会盟', 'chapter': 2, 'kind': 'counter', 'target': 'sect_contribution_total', 'amount': 40, 'reward': {'stone': 20, 'crystal': 1}, 'description': '为任一宗门积累四十历史贡献。'},
    'lineage': {'name': '人间守望', 'chapter': 3, 'kind': 'counter', 'target': 'family_build_total', 'amount': 2, 'reward': {'stone': 20, 'crystal': 1}, 'description': '完成两次家族建设，为后来者留一盏灯。'},
    'seal_gate': {'name': '合拢裂隙', 'chapter': 4, 'kind': 'finale', 'target': 'world_finale', 'amount': 1, 'reward': {'stone': 100, 'crystal': 5}, 'description': '渡劫守关胜利并完成三秘境后封印凡界界门，不进入仙界。'},
    'healer_help': {'name': '药棚之急', 'npc': 'healer', 'kind': 'deliver', 'target': 'pill', 'amount': 1, 'reward': {'stone': 15, 'relation': 10}, 'description': '交付一枚回元丹帮助伤者。'},
    'smith_help': {'name': '护路之刃', 'npc': 'smith', 'kind': 'deliver', 'target': 'blade', 'amount': 1, 'reward': {'stone': 15, 'relation': 10}, 'description': '交付一件未装备的灵刃护卫商道。'},
    'stargazer_help': {'name': '水府星图', 'npc': 'stargazer', 'kind': 'secret', 'target': 'tide', 'amount': 1, 'reward': {'stone': 15, 'relation': 10}, 'description': '完成玄潮水府勘探，带回星阵线索。'},
}
ACHIEVEMENTS = {
    'battle': {'name': '百战', 'counter': 'mob_wins', 'tiers': [3, 10, 30], 'rewards': [{'stone': 10}, {'stone': 20}, {'stone': 30}]},
    'craft': {'name': '百工', 'counter': 'craft_total', 'tiers': [3, 12, 30], 'rewards': [{'crystal': 1}, {'crystal': 2}, {'crystal': 3}]},
    'friends': {'name': '同道', 'counter': 'friends_total', 'tiers': [1, 2, 3], 'rewards': [{'herb': 3}, {'herb': 6}, {'herb': 9}]},
}
TITLES = {
    'veteran': {'name': '百战归来', 'achievement': 'battle', 'threshold': 10, 'effect': 'attack', 'amount': 3},
    'artisan': {'name': '百工通明', 'achievement': 'craft', 'threshold': 12, 'effect': 'cultivate', 'amount': 2},
    'companion': {'name': '山海同道', 'achievement': 'friends', 'threshold': 2, 'effect': 'rest_hp', 'amount': 10},
}
ECONOMY = {'material_buy': 2, 'material_sell_batch': 2, 'material_sell_stone': 4,
           'auction_interval': 20, 'auction_duration': 6, 'auction_fee': 0.05,
           'npc_bid_margin': 4, 'npc_initial_wallet': 50,
           'lots': [{'item': 'herb', 'amount': 6, 'price': 8}, {'item': 'crystal', 'amount': 3, 'price': 12}, {'item': 'pill', 'amount': 2, 'price': 16}]}
ARENA_OPPONENTS = {
    'swordsman': {'name': 'NPC·青岚剑客', 'kind': 'attack', 'attack': 10, 'max_hp': -30, 'description': '迅疾凌厉，气血较低。'},
    'bodyguard': {'name': 'NPC·赤砂体修', 'kind': 'defense', 'attack': -5, 'max_hp': 80, 'description': '根基深厚，攻击稍缓。'},
    'alchemist': {'name': 'NPC·玄潮丹师', 'kind': 'healer', 'heal': 30, 'heal_interval': 3, 'heal_limit': 2, 'description': '每三回合恢复三十气血，每场最多两次。'},
}
ARENA_RULES = {'cycle_ticks': 20, 'first_win_score': 10, 'first_win_stone': 10,
               'season_rounds': 3, 'season_win_stone': 30, 'season_champion_crystal': 3,
               'description': 'NPC模拟演武与跨域赛；没有真人、无跨账号互动、真实服务器或在线玩家。'}
STORIES = {
    'enter': '筑基之后，你才察觉自己的灵根与体质。青岚不再是修行的终点，三洲的来信带来界门将开的消息。',
    'breakthrough': '灵息越过旧日关隘，你的道基更加稳固；但凡界的裂隙仍需众人共同守望。',
    'ending': '三洲阵眼依次亮起，界门在你的守护下重归沉寂。你已走至凡界渡劫之境，却选择留下一条可供后来者前行的道路。仙界仍是下一卷尚未开启的故事。',
}

# Canonical IDs: world currency=stone (legacy top-level stones is unrelated);
# active skill=origin|flame|mountain; equipment slots=weapon|armor|pendant.
# Content tables never carry live stock/coins; engine keeps those in world state.
HOME_PRODUCTION = {'interval': 3, 'capacity_per_level': 20,
                   'garden': {'item': 'herb', 'amount_per_level': 1},
                   'workshop': {'item': 'ore', 'amount_per_level': 1},
                   'chamber': {'item': 'crystal', 'amount_per_level': 1}}
CROSS_DOMAIN = {
    'simulation': True, 'name': '三域NPC模拟跨域赛', 'rounds': [
        {'id': 'qinglan_round', 'name': '青岚剑会·NPC赛区', 'region': 'qinglan', 'opponent': 'swordsman'},
        {'id': 'chisha_round', 'name': '赤砂武会·NPC赛区', 'region': 'chisha', 'opponent': 'bodyguard'},
        {'id': 'xuanchao_round', 'name': '玄潮丹会·NPC赛区', 'region': 'xuanchao', 'opponent': 'alchemist'},
    ], 'round_score': 10, 'round_reward': {'stone': 10},
    'final_reward': {'stone': 30, 'crystal': 3, 'family_renown': 5},
    'npc_growth_cap': 10, 'npc_growth_hp': 15, 'npc_growth_attack': 2,
    'npc_loss_score': 5, 'npc_round_score_cap': 10,
}
ECONOMY.update({'npc_active_orders': 2, 'world_active_orders': 12,
                'closed_history_limit': 60, 'retained_order_limit': 120,
                'npc_inventory_cap': 200, 'npc_initial_materials': {'herb': 6, 'ore': 6, 'wood': 6, 'crystal': 2, 'pill': 2},
                'auction_first_tick_npc_reply': False})
CRAFT_RULES = {'quantity_default': 1, 'quantity_max': 20,
               'bonus_items': ['pill', 'fire_talisman', 'guard_talisman'], 'bonus_level': 3,
               'bonus_per_unit': 1, 'overflow': 'reject_entire_action', 'array_quantity_max': 1}
XP_REWARDS = {
    'boss_first_base': 20, 'boss_first_stage': 6,
    'boss_repeat_base': 8, 'boss_repeat_stage': 2,
    'secret_clear_base': 18, 'secret_clear_stage': 6,
    'dungeon_clear_base': 24, 'dungeon_clear_stage': 6,
    'sect_task': 12, 'sect_material_task': 4,
    'side_quest': 15, 'main_quest': 30,
    'first_friend': 20, 'consult': 6,
}
