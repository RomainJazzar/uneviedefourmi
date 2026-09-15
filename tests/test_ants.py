import unittest

from ants import parse_anthill_text


class AnthillTests(unittest.TestCase):
    def test_subject_simple_case(self):
        anthill = parse_anthill_text(
            """3
            Sv-S1
            Sv-S2
            S1-Sd
            S2-Sd
            """
        )
        solution = anthill.solve()
        self.assertEqual(solution.turns, 3)

    def test_direct_tunnel_is_one_step(self):
        anthill = parse_anthill_text("10\nSv-Sd\n")
        self.assertEqual(anthill.solve().turns, 1)

    def test_single_capacity_pipeline(self):
        anthill = parse_anthill_text("3\nSv-S1\nS1-Sd\n")
        self.assertEqual(anthill.solve().turns, 4)

    def test_capacity_two(self):
        anthill = parse_anthill_text("3\nSv-S1{2}\nS1-Sd\n")
        self.assertEqual(anthill.solve().turns, 3)

    def test_no_path_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_anthill_text("2\nSv-S1\nS2-Sd\n")

    def test_all_ants_finish_and_capacities_are_respected(self):
        anthill = parse_anthill_text(
            """8
            Sv-S1{2}
            Sv-S2
            S1-S3
            S2-S3
            S1-S4
            S4-Sd
            S3-Sd
            """
        )
        solution = anthill.solve()
        self.assertEqual(len(solution.trajectories), 8)
        for path in solution.trajectories.values():
            self.assertEqual(path[0], "Sv")
            self.assertEqual(path[-1], "Sd")


if __name__ == "__main__":
    unittest.main()
