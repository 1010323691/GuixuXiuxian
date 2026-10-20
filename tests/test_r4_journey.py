"""Independent story counters preserve ordinary participation semantics."""
import copy
import unittest
from game import rules, journey, activities


class R4JourneyTests(unittest.TestCase):
    def setUp(self):
        self.w=rules.new_game('故事计数QA',mode='longline')['world']
        self.w['active']=True
        self.context={'now':1800000000,'day':'2027-01-15'}
        if 'journey' not in self.w['r3']:self.w['r3']['journey']=journey.initial_state()

    def predecessor(self,id):
        from game.gameplay_config import STORIES
        s=next(s for s in STORIES if s['id']==id)
        self.w['r3']['journey']['stories'][id]={'progress':[o['amount'] for o in s['objectives']],'claimed':True}

    def test_sweep_counts_ordinary_dungeon_but_not_manual_story_proof(self):
        self.w['stage']=2;self.predecessor('venom_medicine')
        journey.handle(self.w,'world_story_accept',{'story':'dangerous_proof'},[])
        activities.handle(self.w,'world_activity_accept',{'project':'expedition'},[],self.context)
        before=copy.deepcopy(self.w)
        self.w['r3']['runs']['sweep']={'completed':True,'difficulty':2,'manual':False}
        journey.observe(before,self.w,'world_dungeon_sweep',{})
        activities.observe(before,self.w,'world_dungeon_sweep',{},self.context)
        self.assertEqual(self.w['r3']['journey']['stories']['dangerous_proof']['progress'][0],0)
        entry=next(iter(self.w['r3']['activities']['entries'].values()))
        self.assertEqual(entry['objectives'][1]['progress'],1)
        before=copy.deepcopy(self.w)
        self.w['r3']['runs']['manual']={'completed':True,'difficulty':2,'manual':True}
        journey.observe(before,self.w,'world_attack',{})
        self.assertEqual(self.w['r3']['journey']['stories']['dangerous_proof']['progress'][0],1)

    def test_zero_damage_boss_counts_old_activity_but_not_story_then_positive_counts(self):
        self.w['stage']=3;self.predecessor('dangerous_proof')
        journey.handle(self.w,'world_story_accept',{'story':'astral_bridge'},[])
        activities.handle(self.w,'world_activity_accept',{'project':'artisan'},[],self.context)
        before=copy.deepcopy(self.w)
        self.w['r3']['boss']['2027-01-15']={'runs':{'zero':{'settled':True,'commands':1,'damage':0}}}
        journey.observe(before,self.w,'world_flee',{})
        activities.observe(before,self.w,'world_flee',{},self.context)
        self.assertEqual(self.w['r3']['journey']['stories']['astral_bridge']['progress'][1],0)
        entry=next(iter(self.w['r3']['activities']['entries'].values()))
        self.assertEqual(entry['objectives'][1]['progress'],1)
        before=copy.deepcopy(self.w)
        self.w['r3']['boss']['2027-01-15']['runs']['positive']={'settled':True,'commands':1,'damage':1}
        journey.observe(before,self.w,'world_flee',{})
        self.assertEqual(self.w['r3']['journey']['stories']['astral_bridge']['progress'][1],1)

    def test_delayed_story_reward_stays_frozen_chapter_quality_and_unique(self):
        self.w['stage']=7
        self.w['r3']['journey']['stories']['caravan_rescue']={'progress':[1,1],'claimed':False}
        journey.handle(self.w,'world_story_claim',{'story':'caravan_rescue','item':'blade'},[])
        item=next(iter(self.w['r3']['instances'].values()))
        self.assertEqual((item['template_id'],item['chapter'],item['quality']),('blade',1,1))
        before=copy.deepcopy(self.w)
        with self.assertRaises(rules.GameError):journey.handle(self.w,'world_story_claim',{'story':'caravan_rescue','item':'armor'},[])
        self.assertEqual(self.w,before)

    def test_history_before_accept_is_not_replayed_into_first_story(self):
        self.w['r3']['crafted']['smithing']=20
        before=copy.deepcopy(self.w)
        journey.handle(self.w,'world_story_accept',{'story':'first_forge'},[])
        journey.observe(before,self.w,'world_story_accept',{})
        self.assertEqual(self.w['r3']['journey']['stories']['first_forge']['progress'],[0,0])

    def test_story_claim_accept_and_elite_goals_reference_unique_enabled_real_actions(self):
        def check(expected):
            state=rules.new_game('目标入口QA',mode='longline');state['world']=self.w
            view=rules.project(state,context=self.context)['world']
            goals=view['goals']
            self.assertIn(expected,[g['action']['id'] for g in goals])
            for g in goals:
                matches=[a for p in view['pages'] if p['id']==g['target_page'] for a in p['actions']
                         if a['id']==g['action']['id'] and a['params']==g['action']['params']]
                self.assertEqual(len(matches),1,g)
                if g['action']['id']==expected:self.assertTrue(matches[0]['enabled'],g)
        check('world_story_accept')
        self.w['r3']['journey']['stories']['first_forge']={'progress':[1,1],'claimed':False}
        check('world_story_claim')
        self.w['stage']=1;self.w['region']='chisha'
        self.w['r3']['journey']['stories']['first_forge']['claimed']=True
        self.predecessor('allied_roads')
        self.w['r3']['journey']['stories']['caravan_rescue']={'progress':[1,0],'claimed':False}
        check('world_elite_enter')
