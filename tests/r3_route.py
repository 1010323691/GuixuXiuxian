"""Legal-action R3 route planner shared by real HTTP and browser drivers."""
import math
from tests.test_world_systems import WorldPlanner


class R3Planner(WorldPlanner):
    def execute(self, projected, **fields):
        before=self.snapshot()
        # Continuous preview is the full entitlement at this unchanged server UTC.
        allowed=int(before['view']['growth']['available_micro'])//1_000_000
        result=super().execute(projected,**fields)
        assert result['state']['world']['xp']<=allowed, ('direct XP bypass',projected['id'])
        return result

    def character_stat(self, label):
        page = next(p for p in self.snapshot()['view']['world']['pages'] if p['id']=='character')
        return next(s['value'] for s in page['stats'] if s['label']==label)

    def win(self):
        """One public auto-battle submission resolves the whole fight; defeat resets hp to 1."""
        world = self.world()
        if world['battle'] is None:
            assert world['hp'] > 1, ('unexpected defeat in public route', self.trace[-15:])
            return
        self.perform('world_auto_battle', strategy='balanced')
        world = self.world()
        assert world['battle'] is None, ('auto battle left the fight open', world['battle'])
        assert world['hp'] > 1, ('unexpected defeat in public route', self.trace[-15:])
    def prepare(self):
        self.perform('world_root', choice='fire')
        self.perform('world_constitution', choice='sturdy')
        self.three_equipment()
        for recipe in ['spirit_array','mountain_array','seal_array']:
            for _ in range(3):
                self.craft(recipe)
        for _ in range(12):
            self.craft('pill')
        self.rest()

    def three_equipment(self):
        for recipe,slot in [('blade','weapon'),('armor','armor'),('pendant','pendant')]:
            before = set(self.world()['r3']['instances'])
            self.craft(recipe)
            uid = next(iter(set(self.world()['r3']['instances'])-before))
            self.perform('world_loot_equip', uid=uid)
            for target in [1,2,3]:
                self.ensure('ore',4*target)
                while self.world()['r3']['materials']['enhance_material']<target:
                    self.cost({'ore':4,'wood':2})
                    self.perform('world_loot_exchange', item='enhance_material')
                self.ensure('ore',4*target)
                self.perform('world_loot_enhance', uid=uid)
            assert self.world()['r3']['equipped'][slot] == uid

    def dungeon(self, dungeon='den', region='qinglan', difficulty=1, chapter=0):
        self.travel(region)
        self.rest()
        self.perform('world_dungeon_enter',dungeon=dungeon,difficulty=difficulty,chapter=chapter)
        run = self.world()['dungeon']['run_id']
        for round_index in range(3):
            self.rest()
            self.perform('world_dungeon_next')
            if difficulty>=2 and round_index==2:
                expected={'den':'venom','forge':'furnace_shield','tower':'mana_seal'}[dungeon]
                assert self.world()['battle'].get('mechanic')==expected, 'high difficulty omitted its tactical rule'
                if not hasattr(self,'mechanics_seen'):
                    self.mechanics_seen=[]
                self.mechanics_seen.append([dungeon,difficulty,expected])
            self.win()
        assert self.world()['dungeon'] is None
        assert self.world()['r3']['runs'][run]['completed']
        assert f'{dungeon}:{chapter}:{difficulty}' in self.world()['dungeon_wins']
        return run

    def full_growth(self, clock, restart=None):
        self.prepare()
        self.common_social('sword','healer')
        for quest in ['first_art','alliance','lineage']:
            self.perform('world_quest_accept',quest=quest)
            self.perform('world_quest_claim',quest=quest)
        self.craft('barrier_pill')
        self.craft('soul_talisman')
        # R4 approved curve replaces the default longline progression; old release evidence remains archived.
        costs = [270,1215,3564,8640,17010,28080,43740,71280]
        milestones=[]
        for stage,cost in enumerate(costs):
            assert self.world()['stage']==stage
            if stage==2:
                self.perform('world_disciple',disciple='herbalist')
                self.perform('world_teach',disciple='herbalist')
            self.rest()
            xp_before = self.world()['xp']
            self.perform('world_boss')
            self.win()
            assert str(stage) in self.world()['guard_wins']
            assert self.world()['xp']==xp_before, 'guard victory leaked old direct XP'
            view = self.snapshot()['view']['growth']
            need = max(0,cost-view['available'])
            seconds = math.ceil(need/view['rate']['per_day']*86400)
            clock.advance(seconds)
            # A real legal action commits growth; no state/XP injection.
            self.perform('world_gather',item='ore')
            assert self.world()['xp']>=cost
            if stage<7:
                xp_before_advance = self.world()['xp']
                self.perform('world_advance')
                assert self.world()['xp']==xp_before_advance-cost
                if restart:
                    after_advance=self.world()
                    restart()
                    assert self.world()==after_advance, 'restart returned spent breakthrough XP or stage'
            milestones.append({'stage':stage,'elapsed_seconds':clock(),'xp':self.world()['xp']})
        for secret,region in [('mist','qinglan'),('desert','chisha'),('tide','xuanchao')]:
            self.secret(secret,region)
        self.perform('world_quest_accept',quest='seal_gate')
        self.perform('world_quest_claim',quest='seal_gate')
        before = self.world()['xp']
        self.perform('world_finish')
        assert self.world()['xp']==before-costs[-1]
        assert self.world()['ending'] and self.world()['stage']==7
        return milestones
