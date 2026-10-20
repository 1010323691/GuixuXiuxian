"""R4 legal public-action route: accepted stories, elites, then mortal finale."""
import math
from fractions import Fraction
from tests.r3_route import R3Planner

COSTS=[270,1215,3564,8640,17010,28080,43740,71280]


class R4Planner(R3Planner):
    def story(self,id):return self.world()['r3']['journey']['stories'][id]

    def accept(self,id):self.perform('world_story_accept',story=id)

    def claim(self,id,item=None):
        before=set(self.world()['r3']['instances'])
        self.perform('world_story_claim',story=id,**({'item':item} if item else {}))
        assert self.story(id)['claimed']
        if item:
            uid=next(iter(set(self.world()['r3']['instances'])-before))
            self.perform('world_loot_equip',uid=uid)
            return uid

    def stage_gate(self):
        s=self.world()['stage']
        if str(s) not in self.world()['guard_wins']:
            self.rest();self.perform('world_boss');self.win()
            assert str(s) in self.world()['guard_wins']

    def wait_for(self,clock,amount):
        g=self.snapshot()['view']['growth']
        missing=max(0,amount*1_000_000-int(g['available_micro']))
        rate=Fraction(int(g['rate']['numerator']),g['rate']['denominator'])
        seconds=math.ceil(Fraction(missing,1)/rate)
        clock.advance(seconds)
        self.perform('world_gather',item='ore')
        assert self.world()['xp']>=amount

    def advance(self,clock,elapsed_target=None,start=None):
        s=self.world()['stage'];self.stage_gate()
        if elapsed_target is not None:
            target=start+elapsed_target
            assert target>=clock()
            clock.advance(target-clock())
            self.perform('world_gather',item='ore')
        else:self.wait_for(clock,COSTS[s])
        before=self.world()['xp'];self.perform('world_advance')
        assert self.world()['stage']==s+1 and self.world()['xp']==before-COSTS[s]

    def elite(self,id,region):
        self.travel(region);self.rest()
        self.perform('world_elite_enter',elite=id)
        self.win()
        assert id in self.world()['r3']['journey']['elite_wins']

    def first_week(self,clock):
        start=clock();checkpoints=[]
        self.accept('first_forge');self.prepare();self.dungeon(difficulty=1)
        self.claim('first_forge')
        self.accept('allied_roads');self.perform('world_sect_join',sect='sword')
        for _ in range(2):
            self.cost({'herb':2});self.perform('world_gift',npc='healer')
        self.cost({'herb':3});self.perform('world_sect_daily',item='herb')
        self.claim('allied_roads')
        self.craft('barrier_pill');self.craft('soul_talisman')
        self.advance(clock,12*3600,start)
        self.accept('caravan_rescue');self.secret('desert','chisha')
        self.elite('caravan_guard','chisha');self.claim('caravan_rescue','blade')
        self.accept('arts_in_concert')
        self.craft('fire_talisman');self.craft('guard_talisman')
        self.perform('world_array_toggle',array='spirit');self.perform('world_array_toggle',array='spirit')
        self.claim('arts_in_concert')
        checkpoints.append({'hours':(clock()-start)/3600,'stage':self.world()['stage'],'claimed':4})
        self.advance(clock,48*3600,start)
        self.accept('venom_medicine');self.travel('xuanchao');self.rest()
        self.perform('world_elite_enter',elite='venom_keeper')
        self.perform('world_defend');self.perform('world_pill');self.win()
        assert 'venom_keeper' in self.world()['r3']['journey']['elite_wins']
        self.claim('venom_medicine','armor')
        self.accept('dangerous_proof');self.craft('pendant');self.dungeon(difficulty=2)
        self.claim('dangerous_proof')
        checkpoints.append({'hours':(clock()-start)/3600,'stage':self.world()['stage'],'claimed':6})
        self.advance(clock,120*3600,start)
        self.accept('astral_bridge');self.elite('astral_warden','xuanchao')
        self.rest();self.perform('world_boss_enter');self.perform('world_attack');self.perform('world_flee')
        self.claim('astral_bridge','pendant')
        checkpoints.append({'hours':(clock()-start)/3600,'stage':self.world()['stage'],'claimed':7})
        assert len(self.world()['r3']['journey']['elite_wins'])==3
        return checkpoints

    def finish_month(self,clock,checkpoint=None):
        while self.world()['sect_earned'].get('sword',0)<40:
            self.cost({'herb':3});self.perform('world_sect_daily',item='herb')
        while self.world()['relations'].get('healer',0)<30:
            self.cost({'herb':2});self.perform('world_gift',npc='healer')
        for action in ['world_friend','world_companion','world_master']:
            self.perform(action,npc='healer')
        self.perform('world_disciple',disciple='herbalist');self.perform('world_teach',disciple='herbalist')
        self.perform('world_family_create',name='首周实证山庄')
        for facility in ['orchard','school']:
            self.cost({'wood':3,'ore':3});self.perform('world_family_build',facility=facility)
        for quest in ['first_art','alliance','lineage']:
            self.perform('world_quest_accept',quest=quest);self.perform('world_quest_claim',quest=quest)
        for s in range(self.world()['stage'],7):
            self.stage_gate();self.wait_for(clock,COSTS[s])
            if checkpoint:checkpoint('save')
            before=self.world()['xp'];self.perform('world_advance')
            assert self.world()['xp']==before-COSTS[s]
            if checkpoint:
                after=self.world();checkpoint('load');assert self.world()==after,'checkpoint refunded breakthrough cost'
        self.stage_gate();self.wait_for(clock,COSTS[7])
        for secret,region in [('mist','qinglan'),('desert','chisha'),('tide','xuanchao')]:
            if secret not in self.world()['secret_wins']:self.secret(secret,region)
        self.perform('world_quest_accept',quest='seal_gate');self.perform('world_quest_claim',quest='seal_gate')
        before=self.world()['xp'];self.perform('world_finish')
        assert self.world()['xp']==before-71280 and self.world()['ending']
