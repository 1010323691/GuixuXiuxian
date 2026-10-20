"""Optional milestone branches must remain attainable; full arrays cannot craft again."""
import copy
import unittest
from game import rules
from tests.support import baseline_route


class R3MilestoneTests(unittest.TestCase):
    def setUp(self):
        self.context={'now':1800000000,'day':'2027-01-15'}
        self.state=rules.new_game('小境界可达QA',mode='longline')
        baseline_route(lambda:{'state':self.state},self.act)
        self.act('world_enter')
        self.state['world']['xp']=810
        self.state['world']['arrays'].update(spirit=3,mountain=3,seal=3)

    def act(self,action,**params):
        self.state,_=rules.apply_action(self.state,action,params,context=self.context)
        return {'state':self.state}

    def test_fully_upgraded_arrays_remove_impossible_craft_branch_and_backend_rejects_it(self):
        view=rules.project(self.state,context=self.context)
        candidates=[a for p in view['world']['pages'] for a in p['actions']
                    if a['id']=='world_milestone_accept' and a['params']=={'stage':0,'tier':50}]
        self.assertEqual(len(candidates),1)
        branch=next(f for f in candidates[0]['fields'] if f['name']=='branch')
        self.assertNotIn('formations',[option['value'] for option in branch['options']])
        before=copy.deepcopy(self.state)
        with self.assertRaises(rules.GameError):
            rules.apply_action(self.state,'world_milestone_accept',
                {'stage':0,'tier':50,'branch':'formations'},context=self.context)
        self.assertEqual(self.state,before)

    def test_accepting_before_last_upgrade_still_finishes_after_crafting_to_cap(self):
        self.state['world']['arrays']['spirit']=2
        self.state['world']['inventory'].update(wood=12,ore=12)
        self.act('world_milestone_accept',stage=0,tier=50,branch='formations')
        self.act('world_craft',recipe='spirit_array',quantity=1)
        self.assertEqual(self.state['world']['arrays'],{'spirit':3,'mountain':3,'seal':3})
        before=copy.deepcopy(self.state['world'])
        self.act('world_milestone_claim',stage=0,tier=50)
        self.assertEqual(self.state['world']['arts']['formations'],before['arts']['formations']+5)
        self.assertEqual(self.state['world']['xp'],before['xp'])
        self.assertTrue(self.state['world']['r3']['milestones']['0:50']['claimed'])
