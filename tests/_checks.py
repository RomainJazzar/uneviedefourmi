"""Vérifications indépendantes des règles du sujet (n'utilisent pas _validate_solution)."""

from __future__ import annotations

from collections import Counter

SOURCE, SINK = "Sv", "Sd"


def assert_valid_solution(test, anthill, solution) -> None:
    """Contrôle toutes les règles du sujet sur une solution."""
    trajectories = solution.trajectories
    horizon = solution.turns
    edges = {frozenset(e) for e in anthill.graph.edges}

    # nombre exact de fourmis, nommées f1..fF
    test.assertEqual(len(trajectories), anthill.ant_count)
    test.assertEqual(set(trajectories), {f"f{i}" for i in range(1, anthill.ant_count + 1)})

    for ant, path in trajectories.items():
        test.assertEqual(len(path), horizon + 1, ant)
        test.assertEqual(path[0], SOURCE, f"{ant} ne part pas de Sv")
        test.assertEqual(path[-1], SINK, f"{ant} ne finit pas dans Sd")
        arrived = False
        for before, after in zip(path, path[1:]):
            if before != after:
                test.assertIn(frozenset((before, after)), edges, f"{ant} : tunnel {before}-{after} inexistant")
            if arrived:
                test.assertEqual(after, SINK, f"{ant} ressort du dortoir")
            arrived = arrived or after == SINK

    # capacité respectée à chaque instant
    for t in range(horizon + 1):
        occupancy = Counter(path[t] for path in trajectories.values())
        for room, count in occupancy.items():
            if room not in (SOURCE, SINK):
                test.assertLessEqual(count, anthill.room_capacity(room), f"{room} saturée à t={t}")

    # la dernière fourmi arrive exactement à T
    test.assertEqual(max(path.index(SINK) for path in trajectories.values()), horizon)

    # les étapes affichées correspondent aux trajectoires
    test.assertEqual(len(solution.steps), horizon)
    for t, moves in enumerate(solution.steps, start=1):
        expected = {(a, p[t - 1], p[t]) for a, p in trajectories.items() if p[t - 1] != p[t]}
        test.assertEqual(set(moves), expected)


def count_oscillations(solution) -> int:
    """Nombre de motifs A -> B -> A (aller-retour immédiat)."""
    return sum(
        1
        for path in solution.trajectories.values()
        for i in range(2, len(path))
        if path[i] == path[i - 2] != path[i - 1]
    )
