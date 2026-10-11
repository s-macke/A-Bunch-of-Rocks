"""Rule 110 elementary cellular automaton: the rock computer (D-18, AC-7)."""
import numpy as np

RULE = 110
# lookup: neighbourhood (left, centre, right) as a 3-bit number -> next state
TABLE = np.array([(RULE >> k) & 1 for k in range(8)], dtype=np.uint8)


def rule110(row):
    """Next generation; cells outside the row count as empty (no wrap-around)."""
    row = np.asarray(row, dtype=np.uint8)
    padded = np.pad(row, 1)
    idx = (padded[:-2] << 2) | (padded[1:-1] << 1) | padded[2:]
    return TABLE[idx]


def generations(first, n):
    """First row plus n-1 successors, as an (n, width) array."""
    rows = [np.asarray(first, dtype=np.uint8)]
    for _ in range(n - 1):
        rows.append(rule110(rows[-1]))
    return np.stack(rows)


def single_seed(width):
    """Classic start: one rock at the right edge; Rule 110 grows leftward from it."""
    row = np.zeros(width, dtype=np.uint8)
    row[-1] = 1
    return row
