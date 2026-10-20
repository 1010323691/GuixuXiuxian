"""Architect-owned activity period/progress/receipt invariants."""
import copy
import unittest
from game import activities as A
from game.rules import GameError

C={'day':'2027-01-15','now':1800000000}


def state():
    return {'active':True,'battle':None,'wallet':0,'inventory':{},'r3':{
        'activities':A.initial_state(),'profile_id':'activity-tests','materials':{'dust':0,'enhance_material':0},
        'crafted':dict.fromkeys(['alchemy','smithing','talismans','formations'],0),
        'used':dict.fromkeys(['alchemy','smithing','talismans','formations'],0),
        'secret_count':0,'daily_count':0,'runs':{},'boss':{},'pending':{},'seq':0}}


class ActivityTests(unittest.TestCase):
    def perform(self,w,action,params,mutate=lambda w:None,context=C):
        before=copy.deepcopy(w);mutate(w);A.observe(before,w,action,params,context)
        A.validate({'world':w})

    def test_daily_two_targets_no_retroactive_progress(self):
        w=state();w['r3']['secret_count']=100
        A.handle(w,'world_activity_accept',{'project':'expedition'},[],C)
        key='d:'+C['day'];entry=w['r3']['activities']['entries'][key]
        self.assertFalse(entry['completed'])
        self.perform(w,'world_attack',{},lambda w:w['r3'].__setitem__('secret_count',101))
        self.assertEqual(entry['objectives'][0]['progress'],1)
        self.perform(w,'world_attack',{},lambda w:w['r3']['runs'].__setitem__('run',{'completed':True}))
        self.assertTrue(entry['completed'])
        A.handle(w,'world_activity_claim',{'key':key},[],C)
        self.assertEqual(w['r3']['materials'],{'dust':1,'enhance_material':2})
        with self.assertRaises(GameError):A.handle(w,'world_activity_claim',{'key':key},[],C)
        self.assertEqual(w['r3']['materials']['dust'],1)
        A.validate({'world':w})

    def test_expired_unfinished_does_not_lock_new_day_or_gain_progress(self):
        w=state();A.handle(w,'world_activity_accept',{'project':'social'},[],C)
        tomorrow={'day':'2027-01-16','now':1800086400}
        A.handle(w,'world_activity_accept',{'project':'social'},[],tomorrow)
        self.perform(w,'world_chat',{},context=tomorrow)
        self.assertEqual(w['r3']['activities']['entries']['d:2027-01-15']['objectives'][1]['progress'],0)
        self.assertEqual(w['r3']['activities']['entries']['d:2027-01-16']['objectives'][1]['progress'],1)
        with self.assertRaises(GameError):A.handle(w,'world_activity_accept',{'project':'artisan'},[],tomorrow)

    def test_completed_old_day_claim_survives_new_period_and_no_reroll(self):
        w=state();A.handle(w,'world_activity_accept',{'project':'social'},[],C)
        self.perform(w,'world_chat',{})
        self.perform(w,'world_sect_quest',{},lambda w:w['r3'].__setitem__('daily_count',1))
        late={'day':'2027-03-16','now':1805184000}
        before=copy.deepcopy(w);project=A.project({'world':w},late)
        self.assertEqual(before,w)
        self.assertTrue(any(a['id']=='world_activity_claim' and a['enabled'] for a in project['actions']))
        A.handle(w,'world_activity_claim',{'key':'d:2027-01-15'},[],late)
        self.assertEqual(w['r3']['materials']['dust'],1)

    def test_week_is_monday_anchored_and_only_once(self):
        w=state();A.handle(w,'world_activity_week_accept',{},[],C)
        self.assertEqual(len(w['r3']['activities']['entries']),1)
        weekend={'day':'2027-01-17','now':1800172800}
        with self.assertRaises(GameError):A.handle(w,'world_activity_week_accept',{},[],weekend)
        monday={'day':'2027-01-18','now':1800259200}
        A.handle(w,'world_activity_week_accept',{},[],monday)
        self.assertEqual(len(w['r3']['activities']['entries']),2)
        self.assertNotEqual(A._weekly(__import__('datetime').date(2027,1,15))['id'],A._weekly(__import__('datetime').date(2027,1,18))['id'])

    def test_nested_corruption_rejected_and_not_mutated(self):
        w=state();A.handle(w,'world_activity_accept',{'project':'social'},[],C)
        for field,value in [('claimed',1),('receipt','forged'),('reward',{'dust':True,'enhance_material':2}),('objectives',[]),('kind',[])]:
            broken=copy.deepcopy(w);entry=next(iter(broken['r3']['activities']['entries'].values()));entry[field]=value
            original=copy.deepcopy(broken)
            with self.assertRaises(ValueError):A.validate({'world':broken})
            self.assertEqual(broken,original)

    def test_social_and_any_use_count_only_valid_successful_events(self):
        w=state();A.handle(w,'world_activity_accept',{'project':'artisan'},[],C)
        self.perform(w,'world_pill',{},lambda w:w['r3']['used'].__setitem__('alchemy',1))
        entry=next(iter(w['r3']['activities']['entries'].values()))
        self.assertEqual(entry['objectives'][0]['progress'],1)
        self.perform(w,'world_attack',{},lambda w:w['r3']['boss'].__setitem__('p',{'runs':{'b':{'settled':True,'commands':1}}}))
        self.assertTrue(entry['completed'])


if __name__=='__main__':unittest.main()
