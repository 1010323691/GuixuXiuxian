"""R3 proactive gameplay catalog. Data only; activities.py/world.py own state."""
CONTENT_VERSION = 1
DAILY_PROJECTS = {
    'expedition': {
        'name': '山海勘行', 'description': '探索一处完整秘境，再完成一次副本，材料与装备有去处。',
        'objectives': [
            {'kind': 'secret', 'target': 'any', 'amount': 1, 'label': '接取后完整通关秘境1次'},
            {'kind': 'dungeon', 'target': 'any', 'amount': 1, 'label': '接取后完整通关副本1次'},
        ], 'reward': {'dust': 1, 'enhance_material': 2},
    },
    'artisan': {
        'name': '百工试锋', 'description': '实际使用一项四艺产物，并完成一次界门Boss有效挑战；自制或交易取得均可。',
        'objectives': [
            {'kind': 'use', 'target': 'any', 'amount': 1, 'label': '接取后实际服丹/用符/装备/布阵1次'},
            {'kind': 'boss', 'target': 'any', 'amount': 1, 'label': '接取后完成Boss有效正式挑战1次'},
        ], 'reward': {'dust': 1, 'enhance_material': 2},
    },
    'social': {
        'name': '同道相济', 'description': '为宗门交付委托，再与NPC交谈、赠礼或请教，不要求真人或高境界。',
        'objectives': [
            {'kind': 'commission', 'target': 'any', 'amount': 1, 'label': '接取后交付宗门材料或正式委托1次'},
            {'kind': 'social', 'target': 'any', 'amount': 1, 'label': '接取后与NPC交谈/赠礼/请教1次'},
        ], 'reward': {'dust': 1, 'enhance_material': 2},
    },
}
WEEKLY_ACTIVITIES = [
    {'id': 'hunt', 'name': '猎妖周', 'description': '以药济战：完成两次副本，并在接取后实际用一次丹药。低难和练习通关也可计目标，但不额外获得副本掉落次数。',
     'objectives': [
         {'kind': 'dungeon', 'target': 'any', 'amount': 2, 'label': '接取后完整通关副本2次'},
         {'kind': 'use', 'target': 'alchemy', 'amount': 1, 'label': '接取后实际服丹1次'},
     ], 'reward': {'dust': 2, 'herb': 6}},
    {'id': 'forge', 'name': '匠火周', 'description': '炼器与符术协同：完成两份器物制造，并实际使用一次符箓。基础配方即可，不锁高难炉盾。',
     'objectives': [
         {'kind': 'craft', 'target': 'smithing', 'amount': 2, 'label': '接取后完成炼器制作2份'},
         {'kind': 'use', 'target': 'talismans', 'amount': 1, 'label': '接取后在战斗中实际用符1次'},
     ], 'reward': {'dust': 2, 'ore': 6}},
    {'id': 'stars', 'name': '星阵周', 'description': '先用阵，再试界门：实际启用阵法并完成一次Boss有效挑战。满级阵法可从暂停切回启用，不虚构维护产物。',
     'objectives': [
         {'kind': 'use', 'target': 'formations', 'amount': 1, 'label': '接取后实际启用阵法1次（制造即启用或暂停后重启）'},
         {'kind': 'boss', 'target': 'any', 'amount': 1, 'label': '接取后完成Boss有效正式挑战1次'},
     ], 'reward': {'dust': 2, 'wood': 6}},
]
ACTIVITY_RULES = {
    'timezone': 'UTC', 'daily_choices': 1, 'weekly_choices': 1,
    'weekly_anchor_monday': '1970-01-05', 'week_theme_modulus': 3,
    'progress_after_accept_only': True, 'freeze_period_on_accept': True,
    'completed_claim_survives_expiry': True, 'incomplete_expires': True,
    'expired_does_not_block_new_period': True, 'abandon_refunds': False,
    'reward_xp': 0, 'reward_speed_bp': 0, 'extra_loot_qualifications': 0,
    'history_claimed_limit': 60, 'never_prune_unclaimed_rights': True,
    'social_actions': ['world_chat', 'world_gift', 'world_consult'],
}
DUNGEON_MECHANICS = {
    'den': {
        'id': 'venom', 'name': '妖巢蚀毒', 'minimum_difficulty': 2, 'last_battle_only': True,
        'description': '未防御的重击附两回合毒；防御可避新毒，回元丹清毒且本回合免重挂。',
        'trigger_intent': 'heavy', 'poison_base': 6, 'poison_per_chapter': 2,
        'poison_turns': 2, 'tick_on_apply': False, 'stacking': 'refresh_not_stack',
        'defend_prevents_apply': True, 'defend_clears_old': False,
        'pill_clears': True, 'pill_prevents_apply_this_turn': True,
        'control_skip_prevents_apply': True, 'control_skip_ticks_old': True,
        'guard_talisman_prevents_apply': False, 'poison_ignores_physical_reduction': True,
        'player_kill_skips_poison': True, 'old_poison_ticks_before_refresh': True,
    },
    'forge': {
        'id': 'furnace_shield', 'name': '熔炉护盾', 'minimum_difficulty': 2, 'last_battle_only': True,
        'description': '开场一次25%气血护盾；火符对盾2倍攻击且无溢出，无盾时火符仍为1.5倍。',
        'shield_num': 1, 'shield_den': 4, 'regenerates': False,
        'physical_overflow_to_hp': True, 'fire_shield_num': 2, 'fire_shield_den': 1,
        'fire_overflow_to_hp': False, 'fire_unshielded_num': 3, 'fire_unshielded_den': 2,
    },
    'tower': {
        'id': 'mana_seal', 'name': '星塔封灵', 'minimum_difficulty': 2, 'last_battle_only': True,
        'description': '常击未防御会耗最多6灵力；防御或镇魂跳过可免耗，零蓝仍可普攻。',
        'trigger_intent': 'attack', 'mp_drain': 6,
        'defend_prevents_drain': True, 'control_skip_prevents_drain': True,
        'min_mp': 0, 'insufficient_mp_costs_hp': False,
    },
}
GUIDANCE_RULES = {
    'max_recommended_chain': 3,
    'priorities': ['active_battle', 'completed_activity_claim', 'growth_advance',
                   'next_difficulty_gap', 'treasure_choice_or_upgrade',
                   'boss_next_reward', 'free_recovery_or_material'],
    'no_action_no_fake_link': True, 'never_submits_on_navigation': True,
    'show_xp_reward': False, 'always_show_daily_growth_rate': True,
}

# R4 story progression is stage/action-driven, never a seven-day login lock.
# objective shape extends activities.py with elite and dungeon_difficulty kinds.
JOURNEY_VERSION = 1
STORY_VERSION = JOURNEY_VERSION
STORY_RULES = {
    'recommended_day_is_gate': False, 'after_accept_only': True,
    'claim_previous_required': True, 'expires': False,
    'reward_xp': 0, 'reward_speed_bp': 0,
    'equipment_choices': ['blade', 'armor', 'pendant'],
    'equipment_enhance': 0, 'consume_drop_credit': False,
    'advance_dungeon_pity': False, 'unique_reward_receipt': True,
    'elite_requires_active_story': True, 'elite_repeat_reward': False,
}
FIRST_WEEK_STORIES = [
    {'id': 'first_forge', 'name': '初入山海·百工护身', 'recommended_day': 0,
     'min_stage': 0, 'previous': None,
     'description': '打造一件真正可用的器物，再到妖巢检验。炼器满级仍可正常制造新实例。',
     'objectives': [
         {'kind': 'craft', 'target': 'smithing', 'amount': 1, 'label': '接取后制造器物1件'},
         {'kind': 'dungeon', 'target': 'any', 'amount': 1, 'label': '接取后完整通关副本1次'},
     ], 'reward': {'enhance_material': 3, 'herb': 6}},
    {'id': 'allied_roads', 'name': '同道来信·商路将开', 'recommended_day': 0,
     'min_stage': 0, 'previous': 'first_forge',
     'description': '和同道商议护路，完成一份有实际材料交付的宗门委托。',
     'objectives': [
         {'kind': 'social', 'target': 'any', 'amount': 2, 'label': '接取后交流/赠礼/请教2次'},
         {'kind': 'commission', 'target': 'any', 'amount': 1, 'label': '接取后交付宗门或正式材料委托1次'},
     ], 'reward': {'ore': 6, 'wood': 6, 'crystal': 2}},
    {'id': 'caravan_rescue', 'name': '赤砂护送·炉甲拦路', 'recommended_day': 1,
     'min_stage': 1, 'previous': 'allied_roads',
     'description': '探明商道，再击破一次性炉盾精英。火符破盾省蓝，残盾可普攻收尾。',
     'objectives': [
         {'kind': 'secret', 'target': 'any', 'amount': 1, 'label': '接取后完整勘探秘境1次'},
         {'kind': 'elite', 'target': 'caravan_guard', 'amount': 1, 'label': '击败商路炉甲'},
     ], 'reward': {}, 'equipment_reward': {'chapter': 1, 'quality': 1, 'choice': True}},
    {'id': 'arts_in_concert', 'name': '四艺合流·符阵同行', 'recommended_day': 2,
     'min_stage': 1, 'previous': 'caravan_rescue',
     'description': '准备两张实物符箓并启用阵法；满级阵法可暂停后重启，不要求再升级。',
     'objectives': [
         {'kind': 'craft', 'target': 'talismans', 'amount': 2, 'label': '接取后制成符箓2张'},
         {'kind': 'use', 'target': 'formations', 'amount': 1, 'label': '接取后真实启用阵法1次'},
     ], 'reward': {'enhance_material': 4, 'crystal': 3}},
    {'id': 'venom_medicine', 'name': '玄潮药试·毒潭守卫', 'recommended_day': 3,
     'min_stage': 2, 'previous': 'arts_in_concert',
     'description': '在毒潭战斗中运用防重击或清毒，并真正使用丹药；提前击杀同样有效，不强迫中毒。',
     'objectives': [
         {'kind': 'elite', 'target': 'venom_keeper', 'amount': 1, 'label': '击败毒潭守卫'},
         {'kind': 'use', 'target': 'alchemy', 'amount': 1, 'label': '接取后实际服用丹药1次'},
     ], 'reward': {}, 'equipment_reward': {'chapter': 2, 'quality': 2, 'choice': True}},
    {'id': 'dangerous_proof', 'name': '险境试锋·再铸新器', 'recommended_day': 4,
     'min_stage': 2, 'previous': 'venom_medicine',
     'description': '真正战胜一次险境或绝境并再制器物，材料皆可采集；练习胜利可证明能力但不额外发副本掉落。',
     'objectives': [
         {'kind': 'dungeon_difficulty', 'target': 'at_least_2', 'amount': 1, 'label': '接取后手动完整通关难2或难3副本1次'},
         {'kind': 'craft', 'target': 'smithing', 'amount': 1, 'label': '接取后制造器物1件'},
     ], 'reward': {'enhance_material': 6, 'herb': 9}},
    {'id': 'astral_bridge', 'name': '七章归线·星桥试阵', 'recommended_day': 6,
     'min_stage': 3, 'previous': 'dangerous_proof',
     'description': '击败星桥执阵者，再完成一次有效正式世界Boss挑战。当日三次已用尽可次日补做，故事不失效。',
     'objectives': [
         {'kind': 'elite', 'target': 'astral_warden', 'amount': 1, 'label': '击败星桥执阵者'},
         {'kind': 'boss', 'target': 'any', 'amount': 1, 'require_positive_damage': True, 'label': '接取后正式Boss挑战实际造成伤害并结算1次'},
     ], 'reward': {}, 'equipment_reward': {'chapter': 3, 'quality': 3, 'choice': True}},
]
ELITES = {
    'caravan_guard': {'name': '支线精英·商路炉甲', 'story': 'caravan_rescue',
        'region': 'chisha', 'min_stage': 1, 'chapter': 1,
        'hp': 420, 'attack': 30, 'heavy': 50, 'mechanic': 'furnace_shield',
        'barrier': 105, 'poison_damage': 0,
        'description': '一次性炉盾105；有盾火符2倍攻击且无溢出，盾破后普通火符1.5倍。'},
    'venom_keeper': {'name': '支线精英·毒潭守卫', 'story': 'venom_medicine',
        'region': 'xuanchao', 'min_stage': 2, 'chapter': 2,
        'hp': 650, 'attack': 38, 'heavy': 62, 'mechanic': 'venom',
        'barrier': 0, 'poison_damage': 10,
        'description': '未防重击附两次毒伤10；防御免新毒，丹先清且本回合免重挂，旧毒先跳再刷新。'},
    'astral_warden': {'name': '支线精英·星桥执阵者', 'story': 'astral_bridge',
        'region': 'xuanchao', 'min_stage': 3, 'chapter': 3,
        'hp': 1000, 'attack': 46, 'heavy': 76, 'mechanic': 'mana_seal',
        'barrier': 0, 'poison_damage': 0,
        'description': '真实常击抽灵力6；防常击或镇魂保蓝，零蓝仍可普攻、丹药补给。'},
}
ELITE_RULES = {'intent_cycle': ['attack', 'charge', 'heavy'],
               'entry_cost': {}, 'uses_drop_credit': False,
               'failed_attempt_reward': {}, 'standalone_victory_reward': {},
               'free_flee': True, 'same_story_retry': True,
               'first_win_only': True, 'player_kill_skips_enemy': True}

# Public aliases for the journey engine; no duplicate catalogs.
STORIES = FIRST_WEEK_STORIES
