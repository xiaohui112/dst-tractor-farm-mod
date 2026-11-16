"""Rule parity checks, including exhaustive feasible-set equality on one tile."""
import itertools
import unittest

import benchmark as b
from ortools.sat.python import cp_model


def case(stock, tiles=((0, 0),), season='autumn'):
    return {'id': 'test', 'season': season, 'tiles': list(tiles), 'stock': stock}


class ModelTests(unittest.TestCase):
    def test_exhaustive_pair_feasible_set(self):
        c = case({'tomato': 9, 'potato': 9})
        w, slots = b.context(c)
        model, x, crops = b.model_for(w, slots)
        model.clear_objective()
        expected = set()
        # Independent enumeration: all 3^9 empty/tomato/potato assignments.
        for board in itertools.product((False, 'tomato', 'potato'), repeat=9):
            counts = {k: board.count(k) for k in ('tomato', 'potato')}
            if counts['tomato'] != counts['potato']:
                continue
            if any(0 < n < 4 for n in counts.values()):
                continue
            if counts['tomato'] == 4 and board[4]:
                continue
            # Every pair of pits on a single canonical tile is within radius 4.
            expected.add(board)

        class Collect(cp_model.CpSolverSolutionCallback):
            def __init__(self):
                super().__init__()
                self.boards = set()

            def on_solution_callback(self):
                self.boards.add(tuple(next((k for ci,k in enumerate(crops)
                                            if self.value(x[i][ci])), False) for i in range(9)))

        cb = Collect()
        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        solver.parameters.num_search_workers = 1
        self.assertEqual(solver.solve(model, cb), cp_model.OPTIMAL)
        self.assertEqual(len(expected), 71)
        self.assertEqual(cb.boards, expected)
        for board in expected:
            self.assertEqual(b.validate(c, w, slots, board)[0], [])

    def test_cross_tile_family_allowed(self):
        # Each species has only 3 per tile, but 6 across two neighboring tiles.
        c = case({'carrot': 6, 'corn': 6, 'potato': 6}, ((0, 0), (1, 0)))
        r = b.run_cp(c, 1, 5)
        self.assertTrue(r['optimal'])
        self.assertEqual(r['count'], 18)
        self.assertEqual(r['errors'], [])

    def test_empty_stock_offseason_unknown_and_under_minimum(self):
        for stock in ({}, {'randomseed': 99}, {'tomato': 99},
                      {'carrot': 3, 'asparagus': 3, 'potato': 3}, {'nonsense': 99}):
            r = b.run_cp(case(stock, season='winter'), 1, 5)
            self.assertTrue(r['optimal'])
            self.assertEqual(r['count'], 0)
            self.assertEqual(r['errors'], [])

    def test_stock_limit(self):
        r = b.run_cp(case({'tomato': 4, 'potato': 4}, ((0, 0), (1, 0))), 1, 5)
        self.assertTrue(r['optimal'])
        self.assertEqual(r['count'], 8)
        self.assertEqual(r['errors'], [])

    def test_reject_shifted_center_hole(self):
        c = case({'tomato': 4, 'potato': 4})
        w, slots = b.context(c)
        model, x, crops = b.model_for(w, slots)
        board = [False] + ['tomato']*4 + ['potato']*4
        for i, k in enumerate(board):
            for ci, crop in enumerate(crops):
                model.add(x[i][ci] == int(k == crop))
        self.assertEqual(cp_model.CpSolver().solve(model), cp_model.INFEASIBLE)
        self.assertIn('4+4-center', b.validate(c, w, slots, board)[0])

    def test_family_is_spatial_not_just_global_stock(self):
        c = case({'carrot': 6, 'corn': 6, 'potato': 6}, ((0, 0), (1, 0), (2, 0)))
        w, slots = b.context(c)
        model, x, crops = b.model_for(w, slots)
        board = ['carrot']*3 + ['corn']*3 + ['potato']*3
        board = board + [False]*9 + board
        for i, k in enumerate(board):
            for ci, crop in enumerate(crops):
                model.add(x[i][ci] == int(k == crop))
        self.assertEqual(cp_model.CpSolver().solve(model), cp_model.INFEASIBLE)
        self.assertIn('family', b.validate(c, w, slots, board)[0])

    def test_spacing_conflict_is_enforced(self):
        c = case({'tomato': 4, 'potato': 4})
        w, slots = b.context(c)
        # A synthetic geometry conflict, beyond the canonical benchmark input.
        slots[1]['x'], slots[1]['z'] = slots[0]['x'], slots[0]['z']
        w.lua.globals().slots = w.lua.table_from(slots, recursive=True)
        model, x, crops = b.model_for(w, slots)
        board = ['tomato']*4 + [False] + ['potato']*4
        for i, k in enumerate(board):
            for ci, crop in enumerate(crops):
                model.add(x[i][ci] == int(k == crop))
        self.assertEqual(cp_model.CpSolver().solve(model), cp_model.INFEASIBLE)

    def test_nutrient_balance_is_per_tile(self):
        c = case({'tomato': 9, 'potato': 9}, ((0, 0), (1, 0)))
        w, slots = b.context(c)
        model, x, crops = b.model_for(w, slots)
        board = ['tomato']*9 + ['potato']*9  # Balanced globally, not on each tile.
        for i, k in enumerate(board):
            for ci, crop in enumerate(crops):
                model.add(x[i][ci] == int(k == crop))
        self.assertEqual(cp_model.CpSolver().solve(model), cp_model.INFEASIBLE)
        self.assertIn('nutrient-balance', b.validate(c, w, slots, board)[0])


if __name__ == '__main__':
    unittest.main()
