SCHEMA_VERSION = 2
TITLE = "归墟修行手札"
REALMS = ["炼气一层", "炼气二层", "炼气三层", "筑基"]
HP = [60, 80, 100, 140]
MP = [12, 16, 20, 28]
ATTACK = [8, 11, 14, 19]
BREAKTHROUGH = [32, 64, 96]
REGIONS = {
    "village": {"name": "青岚村", "realm": 0, "stones": 3, "herbs": 1, "description": "山雨初歇，村后的旧祠传来断续钟声。你从残卷中读到《归元诀》，决定循着灵气的去向寻一条修行之路。"},
    "forest": {"name": "灵雾林", "realm": 1, "stones": 6, "herbs": 2, "description": "雾色沿着青石小径流动，草木间藏着古境逸出的灵息。守在林口的妖猿挡住前路，只有稳住呼吸，才能看清它蓄势时的破绽。"},
    "ruins": {"name": "归墟古境", "realm": 2, "stones": 9, "herbs": 3, "description": "断碑围住一道尚未闭合的裂隙，石傀仍在履行旧日的守誓。更深处，你听见与自己吐纳相合的回声。"},
}
ENEMIES = {
    "wolf": {"name": "山狼", "region": "village", "realm": 0, "hp": 36, "attack": 8, "heavy": 14, "stones": 6, "cultivation": 4},
    "ape": {"name": "雾林妖猿", "region": "forest", "realm": 1, "hp": 80, "attack": 12, "heavy": 20, "stones": 12, "cultivation": 0},
    "sentinel": {"name": "守阵石傀", "region": "ruins", "realm": 2, "hp": 140, "attack": 16, "heavy": 28, "stones": 18, "cultivation": 0},
    "shadow": {"name": "归墟之影", "region": "ruins", "realm": 3, "hp": 220, "attack": 22, "heavy": 38, "stones": 30, "cultivation": 0},
}

BREAKTHROUGH_STORIES = ["第一缕灵息终于沿经脉完成周天。你将残卷收入怀中，灵雾林的入口已不再遥远。", "妖猿的咆哮渐远，紊乱的灵息在丹田凝成细流。你看懂断碑上的路标，归墟古境向你敞开。", "石傀沉寂后，残卷的最后一页浮现出完整心法。你以归元之息筑稳道基，终于有能力直面裂隙中的影子。"]
ENDING = "归墟之影化作晨雾，古境的裂隙在你的吐纳间缓缓闭合。你已稳固筑基，而山中还有漫长岁月；归墟已平，修行未止。"
