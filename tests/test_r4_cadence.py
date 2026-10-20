"""Independent recoverable-credit arithmetic, including occupied capacity time."""
import copy
import unittest
from game import cadence


class R4CadenceTests(unittest.TestCase):
    def setUp(self):
        self.state={'world':{'active':True,'r3':{'cadence':cadence.initial_state(0)}}}

    def account(self,state=None):return (state or self.state)['world']['r3']['cadence']

    def spend(self,key,now=0):
        self.assertTrue(cadence.reserve(self.state['world'],key,{'now':now}))
        self.assertTrue(cadence.finish(self.state['world'],key,True,{'now':now}))

    def test_exact_eight_hour_boundary_and_preview_never_mutates_input(self):
        self.spend('one')
        before=copy.deepcopy(self.state)
        self.assertEqual(self.account(cadence.sync(self.state,28799))['available'],2)
        self.assertEqual(self.account(cadence.sync(self.state,28800))['available'],3)
        self.assertEqual(self.state,before)
        self.assertEqual(cadence.project(self.state,{'now':28799})['seconds_until_next'],1)

    def test_three_credits_can_be_spent_then_eight_and_sixteen_hours_really_restore(self):
        for key in ['one','two','three']:self.spend(key)
        self.assertFalse(cadence.reserve(self.state['world'],'practice',{'now':0}))
        self.assertNotIn('practice',self.account()['reservations'])
        self.state=cadence.sync(self.state,28800)
        self.assertEqual(self.account()['available'],1)
        self.spend('four',28800)
        self.state=cadence.sync(self.state,57600)
        self.assertEqual(self.account()['available'],1)

    def test_reserved_full_capacity_discards_wait_before_success(self):
        w=self.state['world']
        cadence.reserve(w,'long-run',{'now':0})
        self.assertEqual((self.account()['available'],sum(v=='reserved' for v in self.account()['reservations'].values())),(2,1))
        cadence.finish(w,'long-run',True,{'now':28800})
        self.assertEqual(self.account()['available'],2)
        self.assertEqual(self.account()['banked_seconds'],0)
        self.assertEqual(self.account(cadence.sync(self.state,57599))['available'],2)
        self.assertEqual(self.account(cadence.sync(self.state,57600))['available'],3)

    def test_reserved_full_capacity_refund_is_once_and_does_not_bank_hidden_time(self):
        w=self.state['world'];cadence.reserve(w,'cancel',{'now':0})
        self.assertTrue(cadence.finish(w,'cancel',False,{'now':28800}))
        self.assertFalse(cadence.finish(w,'cancel',False,{'now':28800}))
        self.assertEqual(self.account()['available'],3)
        self.spend('after-refund',28800)
        self.assertEqual(self.account(cadence.sync(self.state,57599))['available'],2)
        self.assertEqual(self.account(cadence.sync(self.state,57600))['available'],3)

    def test_seven_day_absence_only_fills_three_and_rewind_never_mints(self):
        for key in ['one','two','three']:self.spend(key)
        self.state=cadence.sync(self.state,7*86400)
        self.assertEqual(self.account()['available'],3)
        self.assertEqual(self.account()['banked_seconds'],0)
        self.spend('return',7*86400)
        before=copy.deepcopy(self.state)
        self.state=cadence.sync(self.state,0)
        self.assertEqual(self.state,before)
        self.assertTrue(cadence.project(self.state,{'now':0})['clock_rewound'])

    def test_fractional_interval_is_preserved_until_cap_then_forgotten(self):
        for key in ['one','two','three']:self.spend(key)
        self.state=cadence.sync(self.state,10000)
        self.state=cadence.sync(self.state,28801)
        self.assertEqual((self.account()['available'],self.account()['banked_seconds']),(1,1))
        self.state=cadence.sync(self.state,86401)
        self.assertEqual((self.account()['available'],self.account()['banked_seconds']),(3,0))
        self.spend('after-cap',86401)
        self.assertEqual(self.account(cadence.sync(self.state,115200))['available'],2)

    def test_once_daily_and_three_times_daily_have_distinct_half_open_week_yields(self):
        def simulate(times):
            self.state={'world':{'active':True,'r3':{'cadence':cadence.initial_state(0)}}}
            count=0
            for now in times:
                self.state=cadence.sync(self.state,now)
                while self.account()['available']:
                    self.spend('clear-'+str(count),now);count+=1
            return count
        self.assertEqual(simulate(range(0,7*86400,86400)),21)
        self.assertEqual(simulate(range(0,7*86400,28800)),23)

    def test_unentered_character_cannot_accumulate_elapsed_credits(self):
        self.state['world']['active']=False
        before=copy.deepcopy(self.state)
        self.assertEqual(cadence.sync(self.state,7*86400),before)
