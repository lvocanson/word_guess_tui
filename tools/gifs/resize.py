import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

# TODO: the target comes from FAKE_TIME through the word lists; editing res/ changes it, and GUESSES must be re-picked.
FAKE_TIME = '2026-10-10 12:00:04'
GUESSES = ['crane', 'pious', 'final', 'vital', 'medal', 'tidal']
COLS, ROWS = 44, 34
STEP_MS, APEX_MS = 200, 900


def main():
    args = common.parse_args('docs/resize.gif')
    term = common.Term(common.binary(args.bin), COLS, ROWS, FAKE_TIME)
    for word in GUESSES:
        term.send(word.encode() + b'\r')
    term.expect(f'Found in {len(GUESSES)} guesses')

    grids = [term.snap()]
    for rows in range(ROWS - 1, 0, -1):
        term.resize(rows)
        grid = term.snap()
        if common.visible(grid) == common.visible(grids[-1]):
            break
        grids.append(grid)
    low = ROWS - len(grids) + 1
    for rows in range(low + 1, ROWS):
        term.resize(rows)
        grids.append(term.snap())
    term.close()

    holds = [APEX_MS if i in (0, ROWS - low) else STEP_MS for i in range(len(grids))]
    common.encode(grids, holds, COLS, ROWS, args.out)


main()
