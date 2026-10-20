"""Independent item-effect and ownership boundaries; no progression cheats in route tests.

Controlled domain fixtures isolate ownership and arithmetic. End-to-end acquisition
is covered separately through public actions, not inferred from these fixtures.
"""
import copy
import unittest
from game import rules
from tests.support import baseline_route


class R3ItemTests(unittest.TestCase):
    def setUp(self):
        self.state = rules.new_game('器物边界QA', mode='longline')
        def legacy(action, **params):
            self.state, _ = rules.apply_action(self.state, action, params, context={'now':1800000000,'day':'2027-01-15'})
            return {'state': self.state}
        baseline_route(lambda: {'state': self.state}, legacy)
        self.state, _ = rules.apply_action(self.state, 'world_enter', {}, context={'now': 1800000000, 'day': '2027-01-15'})
        self.context = {'now': 1800000000, 'day': '2027-01-15'}

    def act(self, action, **params):
        self.state, _ = rules.apply_action(self.state, action, params, context=self.context)
        return self.state['world']

    def instance(self, uid, template='blade', quality=0, chapter=0, enhance=0, path='combat'):
        item = dict(uid=uid, template_id=template, chapter=chapter, quality=quality,
                    enhance=enhance, effect_type=path, source_receipt='fixture:'+uid)
        self.state['world']['r3']['instances'][uid] = item
        return item

    def reject(self, action, **params):
        before = copy.deepcopy(self.state)
        with self.assertRaises(rules.GameError):
            rules.apply_action(self.state, action, params, context=self.context)
        self.assertEqual(self.state, before, 'rejected domain call mutated caller state')

    def test_equipment_quality_and_enhancement_are_additive_with_floor(self):
        from game import world
        w = self.state['world']
        base = world.attributes(w)['attack']
        self.instance('blade-a', quality=2, chapter=3, enhance=3)
        self.act('world_loot_equip', uid='blade-a')
        # chapter3 blade14, quality25% + enhancement15% => floor19.6 =19.
        self.assertEqual(world.attributes(self.state['world'])['attack'], base + 19)
        self.assertEqual(self.state['world']['inventory'].get('blade', 0), 0,
                         'equipping an instance also minted a legacy template copy')

    def test_enhancing_one_same_template_instance_does_not_change_another(self):
        self.instance('blade-a')
        self.instance('blade-b', quality=3)
        w = self.state['world']
        w['inventory']['ore'] = 24
        w['r3']['materials']['enhance_material'] = 6
        before_b = copy.deepcopy(w['r3']['instances']['blade-b'])
        self.act('world_loot_enhance', uid='blade-a')
        r = self.state['world']['r3']
        self.assertEqual(r['instances']['blade-a']['enhance'], 1)
        self.assertEqual(r['instances']['blade-b'], before_b)
        self.assertEqual(self.state['world']['inventory']['ore'], 20)
        self.assertEqual(r['materials']['enhance_material'], 5)

    def test_unselected_treasure_must_choose_once_and_cannot_have_both_effects(self):
        self.instance('main-a', 'main_treasure', quality=4, path='unselected')
        self.reject('world_loot_equip', uid='main-a')
        self.act('world_loot_choose', uid='main-a', effect_type='cultivation')
        self.reject('world_loot_choose', uid='main-a', effect_type='combat')
        self.act('world_loot_equip', uid='main-a')
        from game import loot, world
        self.assertEqual(loot.growth_bonus_bps(self.state), 500)
        # Repair fixture to isolate actual combat-type path on a distinct instance.
        baseline_attack = world.attributes(self.state['world'])['attack']
        self.instance('main-b', 'main_treasure', quality=4, path='combat')
        self.act('world_loot_equip', uid='main-b')
        self.assertEqual(loot.growth_bonus_bps(self.state), 0)
        self.assertEqual(world.attributes(self.state['world'])['attack'], baseline_attack * 110 // 100)

    def test_two_max_treasures_plus_other_bonuses_cap_at_fifteen_percent(self):
        from game import loot
        self.instance('main-a', 'main_treasure', quality=4, path='cultivation')
        self.instance('guard-a', 'guard_treasure', quality=4, path='cultivation')
        self.act('world_loot_equip', uid='main-a')
        self.act('world_loot_equip', uid='guard-a')
        w = self.state['world']
        self.assertEqual(loot.growth_bonus_bps(self.state), 1000)
        w['root']['level'] = 3
        w['skills']['origin'] = 3
        w['home']['chamber'] = 3
        w['arrays']['spirit'] = 3
        w['sect'] = 'sword'
        w['sect_earned']['sword'] = 120
        w['title'] = 'artisan'
        self.assertEqual(loot.growth_bonus_bps(self.state), 1500)
        for i in range(20):
            self.instance('spare-'+str(i), 'main_treasure', quality=4, path='cultivation')
        self.assertEqual(loot.growth_bonus_bps(self.state), 1500, 'unequipped inventory multiplied cultivation')

    def test_dismantle_is_single_consumption_and_equipped_item_is_protected(self):
        self.instance('blade-a', quality=4)
        self.act('world_loot_equip', uid='blade-a')
        self.reject('world_loot_dismantle', uid='blade-a')
        self.act('world_loot_unequip', slot='weapon')
        before = copy.deepcopy(self.state['world']['r3']['materials'])
        self.act('world_loot_dismantle', uid='blade-a')
        r = self.state['world']['r3']
        self.assertNotIn('blade-a', r['instances'])
        self.assertEqual(r['materials']['enhance_material'] - before['enhance_material'], 5)
        self.assertEqual(r['materials']['dust'] - before['dust'], 3)
        self.reject('world_loot_dismantle', uid='blade-a')
        self.reject('world_loot_equip', uid='blade-a')

    def test_full_instance_bag_retains_original_uid_pending_and_claims_exactly_once(self):
        for i in range(200):
            self.instance('full-'+str(i))
        w=self.state['world']
        w['inventory']['ore']=20
        w['inventory']['wood']=20
        self.act('world_craft',recipe='blade',quantity=1)
        r=self.state['world']['r3']
        self.assertEqual(len(r['instances']),200)
        self.assertEqual(len(r['pending']),1)
        receipt,delivery=next(iter(r['pending'].items()))
        original_uid=delivery['item']['uid']
        self.reject('world_loot_claim',receipt=receipt)
        self.act('world_loot_dismantle',uid='full-0')
        self.act('world_loot_claim',receipt=receipt)
        r=self.state['world']['r3']
        self.assertIn(original_uid,r['instances'])
        self.assertNotIn(receipt,r['pending'])
        self.assertEqual(len(r['instances']),200)
        self.reject('world_loot_claim',receipt=receipt)

    def test_crafting_instance_cannot_also_sell_or_list_a_legacy_template_copy(self):
        self.act('world_craft',recipe='blade',quantity=1)
        r=self.state['world']['r3']
        uid=next(iter(r['instances']))
        self.assertEqual(self.state['world']['inventory'].get('blade',0),0)
        self.reject('world_sell',item='blade',quantity=1)
        self.reject('world_auction_list',item='blade',quantity=1,price=10)
        self.assertIn(uid,self.state['world']['r3']['instances'])

    def test_leaving_unfinished_run_releases_only_its_pending_slot_reservation(self):
        for i in range(200):
            self.instance('owned-'+str(i))
        r=self.state['world']['r3']
        for i in range(199):
            uid='pending-'+str(i)
            item=dict(uid=uid,template_id='blade',chapter=0,quality=0,enhance=0,
                      effect_type='combat',source_receipt='receipt:'+uid)
            r['pending']['receipt:'+uid]={'source':'fixture','item':item,'materials':{}}
        self.act('world_dungeon_enter',dungeon='den',chapter=0,difficulty=1)
        run=self.state['world']['dungeon']['run_id']
        self.reject('world_craft',recipe='blade',quantity=1)
        self.act('world_dungeon_leave')
        self.assertFalse(self.state['world']['r3']['runs'][run]['completed'])
        self.act('world_craft',recipe='blade',quantity=1)
        self.assertEqual(len(self.state['world']['r3']['pending']),200,
                         'an abandoned historical run permanently reserved the last delivery slot')

    def test_final_dungeon_hit_retains_item_and_both_full_material_rewards_at_pending_boundary(self):
        for i in range(200):
            self.instance('capacity-owned-'+str(i))
        r=self.state['world']['r3']
        for i in range(199):
            uid='capacity-pending-'+str(i)
            item=dict(uid=uid,template_id='blade',chapter=0,quality=0,enhance=0,
                      effect_type='combat',source_receipt='receipt:'+uid)
            r['pending']['receipt:'+uid]={'source':'fixture','item':item,'materials':{}}
        r['materials']['dust']=999999
        r['materials']['enhance_material']=999999
        self.act('world_dungeon_enter',dungeon='den',chapter=0,difficulty=1)
        run=self.state['world']['dungeon']['run_id']
        self.state['world']['dungeon']['round']=2
        self.act('world_dungeon_next')
        self.state['world']['battle']['hp']=1  # Valid last-hit boundary, not a route shortcut claim.
        self.act('world_attack')
        w=self.state['world'];r=w['r3']
        self.assertIsNone(w['battle'])
        self.assertIsNone(w['dungeon'])
        self.assertTrue(r['runs'][run]['completed'])
        deliveries={key:value for key,value in r['pending'].items() if value['source']==run}
        self.assertEqual(sum(v['item'] is not None for v in deliveries.values()),1)
        self.assertEqual(sum(v['materials'].get('dust',0) for v in deliveries.values()),2)
        self.assertEqual(sum(v['materials'].get('enhance_material',0) for v in deliveries.values()),2)
        self.assertEqual(sum(v['item'] is not None for v in r['pending'].values()),200)
        rules.validate_state(self.state)
        material_key=next(k for k,v in deliveries.items() if v['materials'])
        self.reject('world_loot_claim',receipt=material_key)
        self.state['world']['r3']['materials']['dust']=999997
        self.state['world']['r3']['materials']['enhance_material']=999997
        self.act('world_loot_claim',receipt=material_key)
        self.assertEqual(self.state['world']['r3']['materials']['dust'],999999)
        self.assertEqual(self.state['world']['r3']['materials']['enhance_material'],999999)
        self.reject('world_loot_claim',receipt=material_key)
