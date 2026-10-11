import numpy as np
from rocks.automaton import rule110, generations, single_seed

# Rule 110 by definition: neighbourhoods 111,110,101,100,011,010,001,000 -> 0,1,1,0,1,1,1,0
DEFINITION = {(1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0,
              (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0}


def reference(row):
    p = [0] + list(row) + [0]
    return [DEFINITION[(p[i - 1], p[i], p[i + 1])] for i in range(1, len(p) - 1)]


def test_matches_definition_on_random_rows():
    rng = np.random.default_rng(0)
    for _ in range(200):
        row = rng.integers(0, 2, rng.integers(1, 64))
        assert list(rule110(row)) == reference(row)


def test_every_consecutive_generation_pair_follows_the_rule():
    rows = generations(single_seed(80), 60)
    for a, b in zip(rows[:-1], rows[1:]):
        assert list(b) == reference(a)


def test_single_seed_grows_leftward():
    rows = generations(single_seed(40), 10)
    assert rows[0].sum() == 1
    assert rows[9, :30].sum() > 0 or rows[9].sum() > rows[0].sum()
