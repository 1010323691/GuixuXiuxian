"""World-system QA and legal-action planner; no save or internal-state injection.

Planner reads only public snapshots and consumes projected actions/fields. The
same planner can drive an HTTP callback or actual browser button clicks.
"""
import copy
import unittest
import uuid

from tests.support import Server, baseline_route


class WorldPlanner:
    def __init__(self, snapshot, action):
        self.snapshot = snapshot
        self.action = action
        self.trace = []

    def world(self):
        return self.snapshot()['state']['world']

    def actions(self, page=None):
        return [action for entry in self.snapshot()['view']['world']['pages']
                if page is None or entry['id'] == page for action in entry['actions']]

    def choose(self, action_id=None, *, page=None, label=None, params=None):
        candidates = [action for action in self.actions(page)
                      if (action_id is None or action['id'] == action_id)
                      and (label is None or label in action['label'])
                      and (params is None or all(action['params'].get(key) == value for key, value in params.items()))]
        if len(candidates) != 1:
            raise AssertionError(('expected one public action', action_id, page, label, params,
                                  [(item['id'], item['params'], item['label']) for item in candidates]))
        return candidates[0]

    def execute(self, projected, **fields):
        assert projected['enabled'], (projected['label'], projected['reason'])
        declared = {field['name']: field for field in projected.get('fields', [])}
        assert not set(fields) - set(declared), ('undeclared UI field', fields, declared)
        params = copy.deepcopy(projected['params'])
        for name, field in declared.items():
            if name in fields:
                value = fields[name]
            elif 'default' in field:
                value = field['default']
            elif field['required']:
                raise AssertionError(('required field needs explicit route value', projected['id'], field))
            else:
                continue
            assert name not in params, ('cannot overwrite fixed target', name)
            params[name] = value
        self.trace.append({'id': projected['id'], 'params': params})
        return self.action(projected['id'], **params)

    def do(self, action_id=None, *, page=None, label=None, params=None, **fields):
        return self.execute(self.choose(action_id, page=page, label=label, params=params), **fields)

    def repeat_until(self, predicate, step, *, budget=500, description='route progress'):
        for _ in range(budget):
            if predicate():
                return
            before = self.snapshot()
            step()
            after = self.snapshot()
            assert after['revision'] > before['revision'], ('no write progress', description)
        raise AssertionError(('public route exceeded budget', description, self.trace[-12:]))

    def perform(self, action_id, **params):
        """Submit only an operation actually exposed in the public projection."""
        candidates = [item for item in self.actions() if item['id'] == action_id
                      and all(params.get(key) == value for key, value in item['params'].items())
                      and set(params) == set(item['params']) | {field['name'] for field in item.get('fields', []) if field['required']}]
        if len(candidates) != 1:
            raise AssertionError(('operation not uniquely reachable in UI', action_id, params, candidates))
        projected = candidates[0]
        return self.execute(projected, **{key: value for key, value in params.items() if key not in projected['params']})

    def inventory(self, item):
        return self.world()['inventory'].get(item, 0)

    def ensure(self, item, amount):
        assert item in {'herb', 'ore', 'wood', 'crystal'}
        self.repeat_until(lambda: self.inventory(item) >= amount,
                          lambda: self.perform('world_gather', item=item),
                          description=f'free acquisition {item} >= {amount}')

    def cost(self, resources):
        for item, amount in resources.items():
            self.ensure(item, amount)

    def money(self, amount):
        def sell_safe_materials():
            self.ensure('ore', 20)
            self.perform('world_sell', item='ore', quantity=20)
        self.repeat_until(lambda: self.world()['wallet'] >= amount, sell_safe_materials,
                          description='renewable material sale funds')

    def craft(self, recipe):
        # Independent GDD literal costs, not production config imports.
        costs = {'pill': {'herb': 3}, 'barrier_pill': {'herb': 6, 'crystal': 2},
                 'root_dew': {'herb': 8, 'wood': 3}, 'blade': {'ore': 6, 'wood': 2},
                 'armor': {'ore': 8, 'wood': 3}, 'pendant': {'ore': 4, 'crystal': 2},
                 'fire_talisman': {'wood': 4, 'crystal': 1}, 'guard_talisman': {'wood': 3, 'crystal': 1},
                 'soul_talisman': {'wood': 5, 'crystal': 2}, 'spirit_array': {'wood': 4, 'ore': 4},
                 'mountain_array': {'ore': 6, 'crystal': 2}, 'seal_array': {'wood': 6, 'crystal': 3}}
        cost = costs[recipe]
        if recipe.endswith('_array'):
            key = recipe.removesuffix('_array')
            cost = {item: amount * (self.world()['arrays'][key] + 1) for item, amount in cost.items()}
        self.cost(cost)
        before = self.world()
        result = self.perform('world_craft', recipe=recipe, quantity=1)
        assert result['state']['world']['counters']['crafts'] == before['counters']['crafts'] + 1
        return result

    def rest(self):
        for _ in range(30):
            match = [item for item in self.actions() if item['id'] == 'world_rest']
            assert len(match) == 1
            if not match[0]['enabled']:
                return
            self.perform('world_rest')
        raise AssertionError('free rest never reached full hp/mp')

    def win(self):
        for _ in range(120):
            world = self.world()
            if world['battle'] is None:
                assert world['hp'] > 1, ('unexpected defeat in public route', self.trace[-15:])
                return
            battle = world['battle']
            base = 40 + 15 * world['stage']
            if world['root']['id'] == 'fire':
                base += 4 * (world['root']['level'] + 1)
            if world['equipment']['weapon'] == 'blade':
                base += 8 * world['gear']['blade']
            if world['title'] == 'veteran':
                base += 3
            if (battle['kind'] == 'guard' or battle['kind'] == 'dungeon' and world['dungeon']['round'] == 2) and world.get('arrays_enabled', {}).get('seal', True):
                base += 6 * world['arrays']['seal']
            ordinary_damage = base + (4 * world['skills'][world['skill']] if world['skill'] == 'flame' else 0)
            # A free lethal basic attack takes priority over recovery. Repeated
            # defense against an almost-dead foe is a planner error, not a bug.
            if battle['hp'] <= ordinary_damage:
                self.perform('world_attack')
            elif world['hp'] < 100 and self.inventory('pill') and battle['turn'] % 3 != 2:
                self.perform('world_pill')
            elif world['mp'] >= 24:
                self.perform('world_power')
            elif battle['turn'] % 3 != 2:
                self.perform('world_attack')
            else:
                self.perform('world_defend')
        raise AssertionError(('battle did not terminate', self.world()['battle']))

    def prepare(self):
        self.perform('world_root', choice='fire')
        self.perform('world_constitution', choice='sturdy')
        for recipe in ['blade', 'armor', 'pendant']:
            self.craft(recipe)
            self.perform('world_equip', item=recipe)
            for target in [2, 3]:
                self.cost({'ore': 4 * target, 'crystal': target})
                self.perform('world_forge', item=recipe)
        for recipe in ['spirit_array', 'mountain_array', 'seal_array']:
            self.craft(recipe)
        for _ in range(8):
            self.craft('pill')
        self.rest()

    def common_social(self, sect, npc):
        self.perform('world_sect_join', sect=sect)
        for _ in range(5):
            self.ensure('herb', 3)
            self.perform('world_sect_daily', item='herb')
        for _ in range(6):
            self.ensure('herb', 2)
            self.perform('world_gift', npc=npc)
        self.perform('world_friend', npc=npc)
        self.perform('world_companion', npc=npc)
        self.perform('world_master', npc=npc)
        self.perform('world_family_create', name='回归山庄')
        self.perform('world_family_invite', npc=npc)
        for facility in ['orchard', 'school']:
            self.cost({'wood': 3, 'ore': 3})
            self.perform('world_family_build', facility=facility)

    def travel(self, region):
        if self.world()['region'] != region:
            before = self.world()['tick']
            self.perform('world_travel', region=region)
            assert self.world()['tick'] == before, 'travel must not advance AI clock'

    def secret(self, secret, region):
        self.travel(region)
        self.rest()
        self.perform('world_secret_enter', secret=secret)
        for choice in ['survey', 'gather', 'fight']:
            self.perform('world_secret_step', choice=choice)
        self.win()
        assert secret in self.world()['secret_wins']

    def dungeon(self, dungeon, region, difficulty):
        self.travel(region)
        self.perform('world_dungeon_enter', dungeon=dungeon, difficulty=difficulty)
        for _ in range(3):
            self.rest()
            self.perform('world_dungeon_next')
            self.win()
        assert self.world()['dungeon'] is None
        assert dungeon + ':' + str(difficulty) in self.world()['dungeon_wins']

    def full_progress(self):
        """Public acquisition/preparation→eight stage bosses→mortal finale.

        No state fixtures. This is intentionally not the only system test: all
        non-required recipes, permissions, and economic failures have own cases.
        """
        self.prepare()
        self.common_social('sword', 'healer')
        for quest in ['first_art', 'alliance', 'lineage']:
            self.perform('world_quest_accept', quest=quest)
            self.perform('world_quest_claim', quest=quest)
        self.craft('barrier_pill')
        self.craft('soul_talisman')
        for stage in range(8):
            assert self.world()['stage'] == stage
            if stage == 2:
                self.perform('world_disciple', disciple='herbalist')
                if self.world()['xp'] < 5:
                    self.perform('world_cultivate')
                self.perform('world_teach', disciple='herbalist')
            self.rest()
            before = self.world()
            self.perform('world_boss')
            self.win()
            assert str(stage) in self.world()['guard_wins']
            assert self.world()['xp'] == before['xp'] + 20 + 6 * stage, 'first stage-boss XP mismatch'
            if stage < 7:
                self.repeat_until(lambda: self.world()['xp'] >= 100 + 60 * stage,
                                  lambda: self.perform('world_cultivate'), description='next realm XP')
                self.perform('world_advance')
        for secret, region in [('mist', 'qinglan'), ('desert', 'chisha'), ('tide', 'xuanchao')]:
            self.secret(secret, region)
        self.perform('world_quest_accept', quest='seal_gate')
        self.perform('world_quest_claim', quest='seal_gate')
        self.perform('world_finish')
        assert self.world()['ending'] and self.world()['stage'] == 7


class WorldSystemInvariantTests(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.addCleanup(self.server.close)
        self.server.start()
        self.server.write('/api/new-game', name='凡界系统QA')
        baseline_route(self.server.snapshot, self.server.action)
        self.server.action('world_enter')
        self.planner = WorldPlanner(self.server.snapshot, self.server.action)

    def test_all_projected_actions_reject_extra_state_overrides_without_mutation(self):
        # Inspect each distinct exposed operation/target, not just page 1's first.
        actions = self.planner.actions()
        self.assertTrue(actions)
        for index, action in enumerate(actions):
            with self.subTest(id=action['id'], params=action['params']):
                before = self.server.snapshot()
                params = {**action['params'], 'qa_override_wallet': 999999}
                status, body = self.server.request('POST', '/api/action', {
                    'request_id': f'extra-parameter-{index}-{uuid.uuid4()}',
                    'expected_revision': before['revision'], 'action': action['id'], 'params': params})
                self.assertEqual(status, 400, body)
                self.assertEqual(body['error']['code'], 'BAD_REQUEST')
                self.assertEqual(self.server.snapshot(), before)

    def test_world_read_only_navigation_projection_never_advances_ai(self):
        before = self.server.snapshot()
        self.assertEqual(len(before['view']['world']['pages']), 11)
        for _ in before['view']['world']['pages']:
            self.assertEqual(self.server.snapshot(), before)
        status, health = self.server.request('GET', '/api/health')
        self.assertEqual((status, health['schema_version']), (200, 2))
        self.assertEqual(self.server.snapshot(), before)

    def test_full_mortal_world_progress_with_legal_free_resources(self):
        self.planner.full_progress()
        finished = self.planner.world()
        self.assertEqual(len(finished['guard_wins']), 8)
        self.assertEqual(set(finished['secret_wins']), {'mist', 'desert', 'tide'})
        self.assertGreaterEqual(finished['contribution_total'], 40)
        self.assertGreaterEqual(finished['family_builds'], 2)
        self.assertGreaterEqual(finished['counters']['teaching'], 1)
        self.assertEqual(finished['quests']['seal_gate'], 'claimed')
        self.assertTrue(finished['ending'])
        # Continued play after the real mortal finale must remain possible.
        self.server.action('world_gather', item='ore')
        self.assertTrue(self.planner.world()['ending'])

    def test_all_twelve_recipes_outputs_are_consumed_equipped_or_affect_rules(self):
        p = self.planner
        if p.world()['root']['id'] != 'wood':
            p.perform('world_root', choice='wood')
        p.perform('world_constitution', choice='clear')
        recipes = ['pill', 'barrier_pill', 'root_dew', 'blade', 'armor', 'pendant',
                   'fire_talisman', 'guard_talisman', 'soul_talisman',
                   'spirit_array', 'mountain_array', 'seal_array']
        for recipe in recipes:
            p.craft(recipe)
        self.assertEqual(p.world()['counters']['crafts'], 12)
        for item in ['blade', 'armor', 'pendant']:
            p.perform('world_equip', item=item)
        self.assertEqual(set(value for value in p.world()['equipment'].values() if value), {'blade', 'armor', 'pendant'})
        p.perform('world_dew')
        self.assertEqual((p.inventory('root_dew'), p.world()['root']['points']), (0, 1))
        before_xp = p.world()['xp']
        p.perform('world_cultivate')
        self.assertEqual(p.world()['xp'] - before_xp, 19, '12 base + wood3 + spirit4')
        p.rest()
        p.perform('world_hunt')
        p.perform('world_guard')
        self.assertEqual(p.inventory('guard_talisman'), 0)
        hp = p.world()['hp']
        p.perform('world_soul')
        self.assertEqual(p.inventory('soul_talisman'), 0)
        self.assertEqual(p.world()['hp'], hp, 'soul talisman must suppress the enemy turn')
        p.perform('world_pill')
        self.assertEqual(p.inventory('pill'), 0)
        before_hp = p.world()['battle']['hp']
        p.perform('world_fire')
        self.assertEqual(p.inventory('fire_talisman'), 0)
        self.assertEqual(p.world()['battle']['hp'], before_hp - 72, 'floor((base40+blade8)*1.5)')
        p.win()
        p.rest()
        p.perform('world_boss')
        # Seal array adds 6 boss-only attack; blade adds8: floor54*2.1=113.
        enemy_hp = p.world()['battle']['hp']
        p.perform('world_power')
        self.assertEqual(p.world()['battle']['hp'], enemy_hp - 113)
        p.win()
        p.repeat_until(lambda: p.world()['xp'] >= 100, lambda: p.perform('world_cultivate'))
        p.perform('world_advance')
        self.assertEqual(p.inventory('barrier_pill'), 0)
        self.assertEqual(p.world()['stage'], 1)

    def test_repeated_rewards_social_permissions_and_dispatched_progress(self):
        p = self.planner
        p.prepare()
        p.common_social('sword', 'healer')
        before = p.world()
        p.perform('world_sect_leave')
        self.assertEqual(p.world()['contributions']['sword'], before['contributions']['sword'])
        p.perform('world_sect_join', sect='herb')
        self.assertEqual(p.world()['contributions']['herb'], 0)
        self.assertEqual(p.world()['contribution_total'], before['contribution_total'])
        p.perform('world_master_leave')
        self.assertIsNone(p.world()['master'])
        # Returning to the same master must not clear art/relationship progress.
        arts = p.world()['arts']
        p.perform('world_master', npc='healer')
        self.assertEqual(p.world()['arts'], arts)
        p.craft('barrier_pill')
        p.craft('soul_talisman')
        for stage in [0, 1]:
            p.rest()
            p.perform('world_boss')
            p.win()
            p.repeat_until(lambda: p.world()['xp'] >= 100 + 60 * stage, lambda: p.perform('world_cultivate'))
            p.perform('world_advance')
        p.perform('world_disciple', disciple='herbalist')
        p.perform('world_dispatch', disciple='herbalist', destination='herb')
        mission = p.world()['disciples']['herbalist']['mission']
        p.repeat_until(lambda: p.world()['tick'] >= mission['end'], lambda: p.perform('world_gather', item='ore'))
        before_herb = p.inventory('herb')
        p.perform('world_collect_disciple', disciple='herbalist')
        self.assertEqual(p.inventory('herb'), before_herb + 4)
        self.assertIsNone(p.world()['disciples']['herbalist']['mission'])
        before = self.server.snapshot()
        status, body = self.server.request('POST', '/api/action', {
            'request_id': str(uuid.uuid4()), 'expected_revision': before['revision'],
            'action': 'world_collect_disciple', 'params': {'disciple': 'herbalist'}})
        self.assertEqual(status, 422, body)
        self.assertEqual(self.server.snapshot(), before)

    def test_all_three_secrets_and_three_dungeons_have_real_completion(self):
        p = self.planner
        p.full_progress()
        for dungeon, region in [('den', 'qinglan'), ('forge', 'chisha'), ('tower', 'xuanchao')]:
            for difficulty in [1, 2, 3]:
                p.dungeon(dungeon, region, difficulty)
        self.assertEqual(len(p.world()['dungeon_wins']), 9)
        # Repeating an already-cleared dungeon is allowed but not a second first-clear.
        before = list(p.world()['dungeon_wins'])
        xp = p.world()['xp']
        p.dungeon('den', 'qinglan', 1)
        self.assertEqual(p.world()['dungeon_wins'], before)
        self.assertEqual(p.world()['xp'] - xp, 24 + 6 * 7)

    def test_home_production_collect_and_array_effect_can_be_toggled(self):
        p = self.planner
        for facility, costs, item in [('garden', {'wood': 4, 'ore': 2}, 'herb'),
                                      ('workshop', {'ore': 4, 'crystal': 1}, 'ore'),
                                      ('chamber', {'wood': 4, 'crystal': 1}, 'crystal')]:
            p.cost(costs)
            p.perform('world_home', facility=facility)
            p.repeat_until(lambda: p.world()['home_storage'][facility] >= 1,
                           lambda: p.perform('world_gather', item='wood'), budget=5)
            amount = p.world()['home_storage'][facility]
            before = p.inventory(item)
            p.perform('world_home_collect', facility=facility)
            self.assertEqual(p.inventory(item), before + amount)
        p.craft('spirit_array')
        xp = p.world()['xp']
        p.perform('world_cultivate')
        active_gain = p.world()['xp'] - xp
        p.perform('world_array_toggle', array='spirit')
        xp = p.world()['xp']
        p.perform('world_cultivate')
        self.assertEqual(active_gain - (p.world()['xp'] - xp), 4)
        p.perform('world_array_toggle', array='spirit')
        self.assertEqual(p.world()['arrays']['spirit'], 1)

    def test_market_fields_reject_bad_quantity_and_buy_sell_are_real(self):
        p = self.planner
        before = p.world()
        p.perform('world_buy', item='ore', quantity=3)
        after = p.world()
        self.assertEqual(after['inventory']['ore'], before['inventory']['ore'] + 3)
        self.assertEqual(after['wallet'], before['wallet'] - 6)
        p.perform('world_sell', item='ore', quantity=3)
        self.assertEqual(p.world()['wallet'], before['wallet'])
        for quantity in [0, -1, 21, True, 1.5, '2']:
            before = self.server.snapshot()
            status, body = self.server.request('POST', '/api/action', {
                'request_id': str(uuid.uuid4()), 'expected_revision': before['revision'],
                'action': 'world_buy', 'params': {'item': 'ore', 'quantity': quantity}})
            self.assertEqual(status, 400, body)
            self.assertEqual(self.server.snapshot(), before)

    def test_player_auction_return_is_once_and_bid_inventory_is_escrowed(self):
        p = self.planner
        before = p.inventory('herb')
        p.perform('world_auction_list', item='herb', quantity=2, price=1000)
        order = next(order for order in p.world()['auctions'] if order['seller'] == 'player' and not order['settled'] and not order['cancelled'])
        self.assertEqual(p.inventory('herb'), before - 2)
        p.perform('world_auction_cancel', auction=order['id'])
        # R2 permits direct delivery or an explicit pending right, never loss.
        order = next(item for item in p.world()['auctions'] if item['id'] == order['id'])
        if p.inventory('herb') != before:
            self.assertTrue(order.get('delivery'), order)
            p.perform('world_delivery', auction=order['id'])
        self.assertEqual(p.inventory('herb'), before)
        snap = self.server.snapshot()
        status, body = self.server.request('POST', '/api/action', {
            'request_id': str(uuid.uuid4()), 'expected_revision': snap['revision'],
            'action': 'world_auction_cancel', 'params': {'auction': order['id']}})
        self.assertEqual(status, 422, body)
        self.assertEqual(self.server.snapshot(), snap)

    def test_three_domain_npc_season_and_claim_once(self):
        p = self.planner
        p.prepare()
        p.perform('world_season_join')
        season_id = p.world()['arena']['current']['id']
        for round_number in range(3):
            p.rest()
            hp_mp = (p.world()['hp'], p.world()['mp'])
            inventory = copy.deepcopy(p.world()['inventory'])
            p.perform('world_season_fight')
            p.win()
            self.assertEqual(p.world()['arena']['current']['round'], round_number + 1)
            self.assertEqual((p.world()['hp'], p.world()['mp']), hp_mp)
            self.assertEqual(p.world()['inventory'], inventory, 'simulated combat must not consume real items')
        before = p.world()
        p.perform('world_season_claim')
        self.assertEqual(p.world()['wallet'], before['wallet'] + 30)
        self.assertEqual(p.inventory('crystal'), before['inventory'].get('crystal', 0) + 3)
        self.assertTrue(p.world()['arena']['current']['claimed'])
        snap = self.server.snapshot()
        status, body = self.server.request('POST', '/api/action', {
            'request_id': str(uuid.uuid4()), 'expected_revision': snap['revision'],
            'action': 'world_season_claim', 'params': {}})
        self.assertEqual(status, 422, body)
        self.assertEqual(self.server.snapshot(), snap)
        p.perform('world_season_join')
        self.assertEqual(p.world()['arena']['current']['id'], season_id + 1)
        self.assertEqual(p.world()['arena']['current']['round'], 0)

    def test_craft_achievement_title_changes_growth_and_cannot_duplicate(self):
        p = self.planner
        for _ in range(12):
            p.craft('pill')
        p.perform('world_achievement', kind='craft', tier=1)
        p.perform('world_title', title='artisan')
        xp = p.world()['xp']
        p.perform('world_cultivate')
        # Initial default wood level0 adds3, title adds2, no array.
        self.assertEqual(p.world()['xp'] - xp, 17)
        before = self.server.snapshot()
        status, body = self.server.request('POST', '/api/action', {
            'request_id': str(uuid.uuid4()), 'expected_revision': before['revision'],
            'action': 'world_achievement', 'params': {'kind': 'craft', 'tier': 1}})
        self.assertEqual(status, 422, body)
        self.assertEqual(self.server.snapshot(), before)

    def test_three_roots_bodies_and_skills_have_actual_effect_and_caps(self):
        p = self.planner
        for choice in ['fire', 'earth', 'wood']:
            if p.world()['root']['id'] != choice:
                p.money(30)
                p.perform('world_root', choice=choice)
            before = p.world()['xp']
            p.perform('world_cultivate')
            self.assertEqual(p.world()['xp'] - before, 15 if choice == 'wood' else 12)
        for _ in range(3):
            p.cost({'herb': 6, 'crystal': 1})
            p.perform('world_root_train')
        self.assertEqual(p.world()['root']['level'], 3)
        before = self.server.snapshot()
        status, _ = self.server.request('POST', '/api/action', {'request_id': str(uuid.uuid4()),
            'expected_revision': before['revision'], 'action': 'world_root_train', 'params': {}})
        self.assertEqual(status, 422)
        self.assertEqual(self.server.snapshot(), before)
        for choice in ['clear', 'sturdy', 'renew']:
            if p.world()['constitution']['id'] != choice:
                p.money(30)
                p.perform('world_constitution', choice=choice)
            self.assertEqual(p.world()['constitution']['id'], choice)
        for _ in range(3):
            p.cost({'ore': 4, 'crystal': 1})
            p.perform('world_constitution_train')
        for skill in ['flame', 'mountain']:
            p.money(20)
            p.perform('world_skill_learn', skill=skill)
        for skill in ['flame', 'mountain', 'origin']:
            if p.world()['skill'] != skill:
                p.perform('world_skill_equip', skill=skill)
            for target in [2, 3]:
                p.money(20 * target)
                p.ensure('crystal', target)
                p.perform('world_skill_upgrade', skill=skill)
            self.assertEqual(p.world()['skills'][skill], 3)

    def test_three_npc_relationships_teacher_and_family_variants(self):
        p = self.planner
        p.perform('world_family_create', name='三洲同道庄')
        for npc, material in [('healer', 'herb'), ('smith', 'ore'), ('stargazer', 'wood')]:
            for _ in range(6):
                p.ensure(material, 2)
                p.perform('world_gift', npc=npc)
            xp = p.world()['xp']
            p.perform('world_friend', npc=npc)
            self.assertEqual(p.world()['xp'] - xp, 20)
            p.perform('world_family_invite', npc=npc)
            p.perform('world_master', npc=npc)
            p.money(5)
            before = p.world()
            p.perform('world_consult', npc=npc)
            self.assertEqual(p.world()['xp'] - before['xp'], 6)
            self.assertGreater(sum(p.world()['arts'].values()), sum(before['arts'].values()))
            p.perform('world_master_leave')
        self.assertEqual(set(p.world()['friends']), {'healer', 'smith', 'stargazer'})
        self.assertEqual(set(p.world()['family_members']), {'healer', 'smith', 'stargazer'})
        p.perform('world_achievement', kind='friends', tier=2)
        p.perform('world_title', title='companion')
        p.perform('world_family_remove', npc='smith')
        self.assertEqual(p.world()['relations']['smith'], 32)
        p.perform('world_family_dissolve')
        self.assertIsNone(p.world()['family'])
        self.assertEqual(p.world()['friends'], ['healer', 'smith', 'stargazer'])

    def test_three_npc_side_quests_require_real_delivery_and_claim_once(self):
        p = self.planner
        for quest, recipe in [('healer_help', 'pill'), ('smith_help', 'blade')]:
            p.perform('world_quest_accept', quest=quest)
            p.craft(recipe)
            before = p.world()
            p.perform('world_quest_claim', quest=quest)
            self.assertEqual(p.world()['quests'][quest], 'claimed')
            self.assertEqual(p.inventory(recipe), before['inventory'].get(recipe, 0) - 1)
            self.assertEqual(p.world()['xp'] - before['xp'], 15)
            snap = self.server.snapshot()
            status, body = self.server.request('POST', '/api/action', {
                'request_id': str(uuid.uuid4()), 'expected_revision': snap['revision'],
                'action': 'world_quest_claim', 'params': {'quest': quest}})
            self.assertEqual(status, 422, body)
            self.assertEqual(self.server.snapshot(), snap)
        p.perform('world_quest_accept', quest='stargazer_help')
        # Build useful equipment after the delivered blade leaves inventory.
        p.prepare()
        p.craft('barrier_pill')
        p.craft('soul_talisman')
        for stage in [0, 1]:
            p.rest()
            p.perform('world_boss')
            p.win()
            p.repeat_until(lambda: p.world()['xp'] >= 100 + 60 * stage,
                           lambda: p.perform('world_cultivate'))
            p.perform('world_advance')
        p.secret('tide', 'xuanchao')
        before = p.world()
        p.perform('world_quest_claim', quest='stargazer_help')
        self.assertEqual(p.world()['xp'] - before['xp'], 15)
        self.assertEqual(p.world()['quests']['stargazer_help'], 'claimed')


if __name__ == '__main__':
    unittest.main()
