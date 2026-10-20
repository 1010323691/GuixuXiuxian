"""Focused last-boss fixtures assert different tactical rules, not just HP multipliers."""
import copy
import unittest
from game import rules
from tests.support import baseline_route


class R3DungeonMechanicTests(unittest.TestCase):
    def setUp(self):
        self.context={'now':1800000000,'day':'2027-01-15'}
        self.state=rules.new_game('战术反例QA',mode='longline')
        baseline_route(lambda:{'state':self.state},self.act)
        self.act('world_enter')

    def act(self,action,**params):
        self.state,_=rules.apply_action(self.state,action,params,context=self.context)
        return {'state':self.state}

    def boss(self,dungeon,difficulty=2):
        w=self.state['world']
        # Controlled valid post-two-wins fixture. Full three-fight routes are separate tests.
        w['region']={'den':'qinglan','forge':'chisha','tower':'xuanchao'}[dungeon]
        if dungeon!='den':
            w['stage']=2 if dungeon=='tower' else 1
        chapter=0
        w['dungeon_wins']=[f'{dungeon}:0:1']
        for template,slot in [('blade','weapon'),('armor','armor'),('pendant','pendant')]:
            uid='fixture-'+template
            w['r3']['instances'][uid]=dict(uid=uid,template_id=template,chapter=0,quality=1,
                enhance=0,effect_type='combat',source_receipt='fixture:'+uid)
            w['r3']['equipped'][slot]=uid
        w['inventory'].update(pill=3,fire_talisman=3,soul_talisman=3,guard_talisman=3)
        self.act('world_dungeon_enter',dungeon=dungeon,difficulty=difficulty,chapter=chapter)
        self.state['world']['dungeon']['round']=2
        self.act('world_dungeon_next')
        return self.state['world']['battle']

    def test_difficulty_one_has_no_special_mechanic(self):
        b=self.boss('den',1)
        self.assertNotIn('mechanic',b)
        self.assertNotIn('poison_turns',b)

    def test_den_poison_first_applies_without_tick_then_old_poison_ticks_even_on_control(self):
        self.boss('den')
        self.act('world_defend');self.act('world_defend')
        before=self.state['world']['hp']
        self.act('world_attack')
        w=self.state['world']
        self.assertEqual(w['battle']['poison_turns'],2)
        self.assertEqual(before-w['hp'],62,'first heavy applied immediate poison tick')
        before=w['hp']
        self.act('world_defend')
        w=self.state['world']
        self.assertEqual(before-w['hp'],18+6)
        self.assertEqual(w['battle']['poison_turns'],1,'defense improperly cleared old poison')
        before=w['hp']
        self.act('world_soul')
        self.assertEqual(before-self.state['world']['hp'],6,'control wrongly stopped old poison')
        self.assertEqual(self.state['world']['battle']['poison_turns'],0)

    def test_den_defending_heavy_prevents_poison_and_pill_clears_without_reapply(self):
        self.boss('den')
        self.act('world_defend');self.act('world_defend');self.act('world_defend')
        self.assertEqual(self.state['world']['battle']['poison_turns'],0)
        # Representative existing old poison at a heavy opportunity.
        self.state['world']['battle']['turn']=5
        self.state['world']['battle']['poison_turns']=2
        self.act('world_pill')
        self.assertEqual(self.state['world']['battle']['poison_turns'],0)

    def test_forge_single_shield_physical_overflows_but_fire_does_not(self):
        b=self.boss('forge')
        hp,max_hp,shield=b['hp'],b['max_hp'],b['barrier']
        self.assertEqual(shield,max_hp//4)
        # chapter0 q1 blade adds8, stage1 base55 => attack63.
        self.act('world_attack')
        b=self.state['world']['battle']
        self.assertEqual(b['barrier'],shield-63)
        self.assertEqual(b['hp'],hp)
        self.act('world_fire')
        b=self.state['world']['battle']
        self.assertEqual(b['barrier'],0)
        self.assertEqual(b['hp'],hp,'fire damage spilled from shield into HP')
        self.act('world_fire')
        b=self.state['world']['battle']
        self.assertEqual(b['hp'],hp-94,'unshielded fire must return to floor1.5A')
        self.assertEqual(b['barrier'],0,'shield regenerated')
        # Valid weakened-shield fixture: physical damage spills the remainder to HP.
        self.state['world']['battle']['barrier']=10
        hp=self.state['world']['battle']['hp']
        self.act('world_attack')
        self.assertEqual(self.state['world']['battle']['barrier'],0)
        self.assertEqual(self.state['world']['battle']['hp'],hp-53)

    def test_tower_drain_is_preventable_and_zero_mp_does_not_turn_into_hp_damage(self):
        self.boss('tower')
        self.act('world_attack')
        self.assertEqual(self.state['world']['mp'],54)
        # Fresh attack intent, defense restores its ordinary6, seal drains nothing.
        self.state['world']['battle']['turn']=3
        self.act('world_defend')
        self.assertEqual(self.state['world']['mp'],60)
        self.state['world']['battle']['turn']=6
        self.act('world_soul')
        self.assertEqual(self.state['world']['mp'],60)
        self.state['world']['battle']['turn']=9
        self.state['world']['mp']=0
        hp=self.state['world']['hp']
        self.act('world_attack')
        self.assertEqual(self.state['world']['mp'],0)
        self.assertEqual(hp-self.state['world']['hp'],37,'insufficient MP became extra HP damage')

    def test_den_old_poison_ticks_before_repeated_heavy_refreshes_full_two_turns(self):
        self.boss('den')
        original=copy.deepcopy(self.state)
        for old in [1,2]:
            with self.subTest(old=old):
                self.state=copy.deepcopy(original)
                self.state['world']['battle']['turn']=2
                self.state['world']['battle']['poison_turns']=old
                before=self.state['world']['hp']
                self.act('world_attack')
                self.assertEqual(before-self.state['world']['hp'],62+6)
                self.assertEqual(self.state['world']['battle']['poison_turns'],2,
                                 'refresh was decremented by the old poison tick')

    def test_den_guard_talisman_is_not_defense_and_poison_death_cannot_reapply(self):
        self.boss('den')
        original=copy.deepcopy(self.state)
        self.state['world']['battle']['turn']=2
        self.act('world_guard')
        self.assertEqual(self.state['world']['battle']['poison_turns'],2)
        self.state=copy.deepcopy(original)
        self.state['world']['battle']['turn']=2
        self.state['world']['battle']['poison_turns']=1
        self.state['world']['hp']=68
        result,events=rules.apply_action(self.state,'world_attack',{},context=self.context)
        self.assertIsNone(result['world']['battle'])
        self.assertEqual(result['world']['hp'],1)
        self.assertFalse(any('重击挂毒' in event for event in events),
                         'poison killed the player but a fresh debuff still applied')
