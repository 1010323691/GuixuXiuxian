"""Real HTTP full R4 accepted journey and month progression. Clock is injected, not XP."""
import json
import unittest
from tests.r3_support import ClockHTTP
from tests.support import ROOT,baseline_route
from tests.r4_route import R4Planner


class R4ProgressionTests(unittest.TestCase):
    def test_real_seven_story_three_elite_early_gates_then_month_finale(self):
        server=ClockHTTP().start();self.addCleanup(server.close)
        server.create();baseline_route(server.snapshot,server.action);server.action('world_enter')
        p=R4Planner(server.snapshot,server.action);start=server.clock()
        early=p.first_week(server.clock)
        self.assertEqual([c['claimed'] for c in early],[4,6,7])
        self.assertEqual([c['hours'] for c in early],[12,48,120])
        p.finish_month(server.clock,checkpoint=lambda op:server.write('/api/'+op))
        w=p.world();self.assertTrue(w['ending']);self.assertEqual(w['stage'],7)
        self.assertTrue(all(r['claimed'] for r in w['r3']['journey']['stories'].values()))
        report={'passed':True,'kind':'legal real HTTP with injected UTC, not human month observation',
            'early_checkpoints':early,'elapsed_seconds':server.clock()-start,'world_actions':len(p.trace),
            'stage':w['stage'],'remaining_xp':w['xp'],'ending':w['ending'],
            'manual_clears':w['r3']['journey']['manual_clears'],'elite_wins':w['r3']['journey']['elite_wins']}
        folder=ROOT/'artifacts'/'r4-qa';folder.mkdir(parents=True,exist_ok=True)
        (folder/'full-progression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
