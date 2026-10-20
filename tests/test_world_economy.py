"""Economic CAP/escrow boundary fixtures, distinct from legal player routes."""
import copy
import unittest

from game import rules
from tests.support import baseline_route


CAP = 999999


class WorldEconomicBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.state = rules.new_game('经济边界QA')
        baseline_route(lambda: {'state': self.state}, self.act)
        self.act('world_enter')

    def act(self, command, **params):
        self.state, _ = rules.apply_action(self.state, command, params)
        return {'state': self.state}

    def world(self):
        return self.state['world']

    def order(self, order_id):
        return next(order for order in self.world()['auctions'] if order['id'] == order_id)

    def reject(self, command, **params):
        before = copy.deepcopy(self.state)
        with self.assertRaises(rules.GameError):
            rules.apply_action(self.state, command, params)
        self.assertEqual(self.state, before)

    def cash_total(self):
        w = self.world()
        escrow = sum(order['price'] for order in w['auctions'] if not order['settled'] and not order['cancelled'])
        pending = sum(order.get('delivery', {}).get('stone', 0) for order in w['auctions'])
        tax = sum(order['price'] // 20 for order in w['auctions'] if order['settled'] and order['bidder'])
        npc_pending = sum(agent.get('pending', {}).get('stone', 0) for agent in w['npc_agents'].values())
        return w['wallet'] + sum(agent['wallet'] for agent in w['npc_agents'].values()) + escrow + pending + npc_pending + tax

    def test_cancellation_at_inventory_cap_preserves_goods_until_single_claim(self):
        self.act('world_auction_list', item='herb', quantity=2, price=1000)
        order = next(order for order in self.world()['auctions'] if order['seller'] == 'player')
        order_id = order['id']
        # Explicit boundary fixture; not evidence of a public full-growth route.
        self.world()['inventory']['herb'] = CAP
        rules.validate_state(self.state)
        self.act('world_auction_cancel', auction=order_id)
        self.assertEqual(self.world()['inventory']['herb'], CAP)
        self.assertEqual(self.order(order_id)['delivery']['herb'], 2)
        self.reject('world_delivery', auction=order_id)
        self.world()['inventory']['herb'] = CAP - 2
        self.act('world_delivery', auction=order_id)
        self.assertEqual(self.world()['inventory']['herb'], CAP)
        self.assertEqual(self.order(order_id)['delivery'], {})
        self.reject('world_delivery', auction=order_id)
        self.reject('world_auction_cancel', auction=order_id)

    def test_specific_npc_refunds_and_bid_escrow_conserve_all_cash_each_tick(self):
        total = self.cash_total()
        for _ in range(9):
            self.act('world_wait')
            self.assertEqual(self.cash_total(), total, 'NPC outbid/refund/settlement minted or burned cash')
            for order in self.world()['auctions']:
                self.assertIn(order['bidder'], [None, 'player', 'healer', 'smith', 'stargazer'])
                self.assertIn(order['seller'], ['player', 'healer', 'smith', 'stargazer'])
            self.assertTrue(all(agent['wallet'] >= 0 for agent in self.world()['npc_agents'].values()))

    def test_player_refund_at_wallet_cap_keeps_full_pending_cash(self):
        target = next(order for order in self.world()['auctions'] if order['seller'] != 'player')
        order_id, price = target['id'], target['base']
        self.act('world_auction_bid', auction=order_id, price=price)
        self.assertEqual(self.order(order_id)['bidder'], 'player', 'NPC may not outbid in same completed action')
        self.world()['wallet'] = CAP
        rules.validate_state(self.state)
        self.act('world_wait')
        self.assertNotEqual(self.order(order_id)['bidder'], 'player')
        self.assertEqual(self.world()['wallet'], CAP)
        self.assertEqual(self.order(order_id)['delivery']['stone'], price)
        self.reject('world_delivery', auction=order_id)
        self.world()['wallet'] = CAP - price
        self.act('world_delivery', auction=order_id)
        self.assertEqual(self.world()['wallet'], CAP)
        self.assertEqual(self.order(order_id)['delivery'], {})

    def test_winner_at_inventory_cap_can_recover_all_won_goods(self):
        target = next(order for order in self.world()['auctions'] if order['seller'] != 'player')
        order_id, item, amount = target['id'], target['item'], target['quantity']
        self.act('world_auction_bid', auction=order_id, price=target['base'] + 4)
        self.world()['inventory'][item] = CAP
        rules.validate_state(self.state)
        for _ in range(10):
            if self.order(order_id)['settled']:
                break
            self.act('world_wait')
        self.assertTrue(self.order(order_id)['settled'])
        self.assertEqual(self.world()['inventory'][item], CAP)
        self.assertEqual(self.order(order_id)['delivery'][item], amount)
        self.reject('world_delivery', auction=order_id)
        self.world()['inventory'][item] = CAP - amount
        self.act('world_delivery', auction=order_id)
        self.assertEqual(self.world()['inventory'][item], CAP)
        self.assertEqual(self.order(order_id)['delivery'], {})
        self.reject('world_delivery', auction=order_id)

    def test_multi_item_forms_are_enabled_when_nonfirst_option_is_legal(self):
        self.world()['inventory'].update(herb=0, ore=3)
        projection = rules.project(self.state)['world']
        market = next(page for page in projection['pages'] if page['id'] == 'market')
        for action_id in ['world_auction_list', 'world_sell']:
            actions = [action for action in market['actions'] if action['id'] == action_id]
            self.assertTrue(actions, action_id)
            self.assertTrue(any(action['enabled'] for action in actions),
                            f'{action_id} disabled despite owned ore: {actions}')
        self.act('world_auction_list', item='ore', quantity=1, price=1000)
        self.assertEqual(self.world()['inventory']['ore'], 2)
        self.assertTrue(any(order['seller'] == 'player' and order['item'] == 'ore' for order in self.world()['auctions']))

    def test_market_buy_form_does_not_disable_all_items_when_first_item_is_full(self):
        self.world()['inventory']['herb'] = CAP
        projection = rules.project(self.state)['world']
        market = next(page for page in projection['pages'] if page['id'] == 'market')
        buy = [action for action in market['actions'] if action['id'] == 'world_buy']
        self.assertTrue(any(action['enabled'] for action in buy), buy)
        before = self.world()['inventory'].get('ore', 0)
        self.act('world_buy', item='ore', quantity=1)
        self.assertEqual(self.world()['inventory']['ore'], before + 1)

    def test_dynamic_events_have_real_modifiers_expire_and_npc_assets_are_bounded(self):
        observed = set()
        while self.world()['tick'] < 60:
            self.act('world_gather', item='ore')
            if self.world()['event']:
                observed.add(self.world()['event']['id'])
            for agent in self.world()['npc_agents'].values():
                self.assertGreaterEqual(agent['wallet'], 0)
                self.assertTrue(all(0 <= amount <= 200 for amount in agent['inventory'].values()))
            if self.world()['tick'] == 20:
                self.assertEqual(self.world()['event']['id'], 'herb')
                before = self.world()['inventory']['herb']
                self.act('world_gather', item='herb')
                self.assertEqual(self.world()['inventory']['herb'] - before, 6)
            if self.world()['tick'] == 26:
                self.assertIsNone(self.world()['event'])
                before = self.world()['inventory']['herb']
                self.act('world_gather', item='herb')
                self.assertEqual(self.world()['inventory']['herb'] - before, 5)
        self.assertEqual(observed, {'herb', 'beast', 'trade'})
        self.assertTrue(all(agent['turns'] > 0 and agent['last'] for agent in self.world()['npc_agents'].values()))

    def test_all_three_encounters_resolve_real_results_and_cannot_replay(self):
        observed = set()
        for _ in range(80):
            encounter = self.world()['encounter']
            if encounter and encounter['id'] not in observed:
                kind = encounter['id']
                observed.add(kind)
                before = copy.deepcopy(self.world())
                if kind == 'traveler':
                    self.act('world_encounter', choice='heal')
                    self.assertEqual(self.world()['inventory']['herb'], before['inventory']['herb'] - 2)
                    self.assertGreater(sum(self.world()['factions'].values()), sum(before['factions'].values()))
                elif kind == 'furnace':
                    self.act('world_encounter', choice='salvage')
                    self.assertEqual(self.world()['inventory']['wood'], before['inventory']['wood'] + 2)
                else:
                    self.act('world_encounter', choice='meditate')
                    self.assertEqual(self.world()['xp'], before['xp'] + 8)
                self.assertIsNone(self.world()['encounter'])
                self.reject('world_encounter', choice='meditate')
            else:
                self.act('world_gather', item='ore')
            if len(observed) == 3:
                break
        self.assertEqual(observed, {'traveler', 'furnace', 'inscription'})

    def test_full_npc_wallet_refund_is_owned_and_pending_not_burned(self):
        self.act('world_wait')
        target = next(order for order in self.world()['auctions'] if order['bidder'] not in (None, 'player'))
        npc, refund, order_id = target['bidder'], target['price'], target['id']
        self.world()['npc_agents'][npc]['wallet'] = 200
        rules.validate_state(self.state)
        total = self.cash_total()
        self.act('world_auction_bid', auction=order_id, price=refund + 1)
        self.assertGreaterEqual(self.world()['npc_agents'][npc]['pending'].get('stone', 0), refund)
        self.assertEqual(self.cash_total(), total)
        self.assertTrue(all(agent['wallet'] <= 200 for agent in self.world()['npc_agents'].values()))

    def test_full_npc_item_inventory_keeps_won_goods_until_capacity_returns(self):
        self.act('world_wait')
        target = next(order for order in self.world()['auctions'] if order['bidder'] not in (None, 'player'))
        npc, item, amount = target['bidder'], target['item'], target['quantity']
        # Boundary fixture forces next tick settlement without producing a
        # fabricated high-level character or replacing a full-route outcome.
        target['end'] = self.world()['tick'] + 1
        self.world()['npc_agents'][npc]['inventory'][item] = 200
        rules.validate_state(self.state)
        self.act('world_wait')
        agent = self.world()['npc_agents'][npc]
        self.assertEqual(agent['inventory'][item], 200)
        self.assertGreaterEqual(agent['pending'].get(item, 0), amount)
        agent['inventory'][item] = 200 - amount
        self.act('world_wait')
        self.assertEqual(self.world()['npc_agents'][npc]['pending'].get(item, 0), 0)


if __name__ == '__main__':
    unittest.main()
