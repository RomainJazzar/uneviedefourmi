import unittest

from ants import AnthillFormatError, parse_anthill_text, parse_room_token


class RoomTokenTests(unittest.TestCase):
    def test_room_variants(self):
        for token in ["S1", "S1{5}", "S1 {5}", "S1{ 5}", "S1 { 5 }", "S1   {   5   }", "S1\t{\t5\t}", "  S1  "]:
            with self.subTest(token=token):
                expected = ("S1", None) if "{" not in token else ("S1", 5)
                self.assertEqual(parse_room_token(token), expected)

    def test_bad_room_tokens(self):
        for token in ["S1{", "S1{}", "S1{a}", "{5}", "1S", "S1{5}{6}", "S1 5"]:
            with self.subTest(token=token), self.assertRaises(ValueError):
                parse_room_token(token)


class AntCountTests(unittest.TestCase):
    def test_count_variants(self):
        for header, expected in [("3", 3), ("f=50", 50), ("F=100", 100), ("F = 100", 100), ("fourmis: 50", 50), ("FOURMIS : 7", 7), ("ants=4", 4)]:
            with self.subTest(header=header):
                self.assertEqual(parse_anthill_text(f"{header}\nSv - Sd\n").ant_count, expected)

    def test_zero_ants_rejected(self):
        with self.assertRaises(AnthillFormatError):
            parse_anthill_text("f=0\nSv-Sd\n")

    def test_missing_count(self):
        with self.assertRaises(AnthillFormatError) as ctx:
            parse_anthill_text("Sv - S1\nS1 - Sd\n")
        self.assertEqual(ctx.exception.line_number, 1)

    def test_count_twice(self):
        with self.assertRaises(AnthillFormatError) as ctx:
            parse_anthill_text("f=2\nSv-Sd\nf=3\n")
        self.assertEqual(ctx.exception.line_number, 3)

    def test_empty_file(self):
        with self.assertRaises(AnthillFormatError):
            parse_anthill_text("\n  \n# rien\n")


class FileFormatTests(unittest.TestCase):
    def test_official_style_with_spaces_crlf_bom_tabs_comments(self):
        text = (
            "﻿# fourmilière de test\r\n"
            "f=50\r\n"
            "S1 { 5 }\r\n"
            "S8 { 4 }   \r\n"
            "\tS9\t\r\n"
            "S10\r\n"
            "\r\n"
            "Sv - S1   # tunnel d'entrée\r\n"
            "S1-S8\r\n"
            "S8 - S9\r\n"
            "S9 -S10\r\n"
            "S10 - Sd\r\n"
        )
        anthill = parse_anthill_text(text)
        self.assertEqual(anthill.ant_count, 50)
        self.assertEqual(anthill.room_capacity("S1"), 5)
        self.assertEqual(anthill.room_capacity("S8"), 4)
        self.assertEqual(anthill.room_capacity("S9"), 1)
        self.assertEqual(anthill.room_capacity("S10"), 1)
        self.assertEqual(anthill.room_capacity("Sv"), 50)
        self.assertEqual(anthill.room_capacity("Sd"), 50)
        self.assertEqual(len(anthill.tunnels), 5)
        self.assertTrue(anthill.graph.has_edge("S9", "S10"))

    def test_tunnel_variants(self):
        for line in ["Sv - S1", "Sv-S1", "Sv  -  S1", "Sv\t-\tS1", "Sv – S1", "S1 - Sv"]:
            with self.subTest(line=line):
                anthill = parse_anthill_text(f"2\n{line}\nS1 - Sd\n")
                self.assertTrue(anthill.graph.has_edge("Sv", "S1"))

    def test_capacity_inside_tunnel(self):
        anthill = parse_anthill_text("3\nSv - S1 { 2 }\nS1{2} - Sd\n")
        self.assertEqual(anthill.room_capacity("S1"), 2)

    def test_rooms_declared_before_tunnels_in_any_order(self):
        anthill = parse_anthill_text("f=10\nS1 { 2 }\nS2\nS2 - Sd\nS1 - S2\nSv - S1\n")
        self.assertEqual(anthill.room_capacity("S1"), 2)
        self.assertEqual(anthill.shortest_distance(), 3)

    def test_contradictory_capacities_are_reported(self):
        with self.assertRaises(AnthillFormatError) as ctx:
            parse_anthill_text("f=3\nS1 { 2 }\nSv - S1\nS1 { 3 } - Sd\n")
        self.assertEqual(ctx.exception.line_number, 4)
        self.assertIn("contradictoires", str(ctx.exception))
        self.assertIn("ligne 2", str(ctx.exception))

    def test_same_capacity_twice_is_fine(self):
        anthill = parse_anthill_text("f=3\nS1{2}\nSv - S1 {2}\nS1 - Sd\n")
        self.assertEqual(anthill.room_capacity("S1"), 2)

    def test_invalid_lines_report_line_number(self):
        cases = {
            "f=3\nSv - S1\nS1 -> Sd\n": 3,
            "f=3\nSv - S1 - Sd\n": 2,
            "f=3\nSv - S1\nS1 { 0 }\nS1 - Sd\n": 3,
            "f=3\nSv - S1\nS1 - S1\nS1 - Sd\n": 3,
            "f=3\nSv - S1\nS1 {-2}\nS1 - Sd\n": 3,
            "f=3\nSv - \nS1 - Sd\n": 2,
        }
        for text, line_number in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(AnthillFormatError) as ctx:
                    parse_anthill_text(text)
                self.assertEqual(ctx.exception.line_number, line_number)

    def test_no_path_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_anthill_text("2\nSv-S1\nS2-Sd\n")

    def test_missing_sink_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_anthill_text("2\nSv-S1\nS1-S2\n")

    def test_capacity_on_source_is_ignored_with_warning(self):
        anthill = parse_anthill_text("4\nSv{2} - Sd\n")
        self.assertEqual(anthill.room_capacity("Sv"), 4)
        self.assertEqual(len(anthill.warnings), 1)

    def test_adjacency_matrix_is_symmetric(self):
        anthill = parse_anthill_text("3\nSv-S1\nSv-S2\nS1-Sd\nS2-Sd\n")
        nodes, matrix = anthill.adjacency_matrix()
        self.assertEqual(nodes, ["Sv", "S1", "S2", "Sd"])
        self.assertEqual(matrix, [[0, 1, 1, 0], [1, 0, 0, 1], [1, 0, 0, 1], [0, 1, 1, 0]])


if __name__ == "__main__":
    unittest.main()
