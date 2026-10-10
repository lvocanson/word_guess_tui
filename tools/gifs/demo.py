import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

# TODO: the target comes from FAKE_TIME through the word lists; editing res/ changes it, and GUESSES must be re-picked.
FAKE_TIME = '2026-10-10 12:00:03'
GUESSES = ['crane', 'spoil', 'aloud', 'loved', 'lodge']
COLS, ROWS = 45, 34
KEY_MS, SUBMIT_MS, END_MS = 200, 800, 1500


def main():
    args = common.parse_args('docs/demo.gif')
    term = common.Term(common.binary(args.bin), COLS, ROWS, FAKE_TIME)
    grids, holds = [term.snap()], [KEY_MS]
    for i, word in enumerate(GUESSES):
        for letter in word:
            term.send(letter.encode())
            grids.append(term.snap())
            holds.append(KEY_MS)
        term.send(b'\r')
        grids.append(term.snap())
        holds.append(END_MS if i == len(GUESSES) - 1 else SUBMIT_MS)
    term.expect(f'Found in {len(GUESSES)} guesses')
    term.close()
    common.encode(grids, holds, COLS, ROWS, args.out)


main()
