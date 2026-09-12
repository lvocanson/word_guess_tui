#!/usr/bin/env bash
# Refreshes the source word lists in res/ from the ESDB word-list generator, the one place the
# game's vocabulary comes from. Run it when the vocabulary should change; the build only ever
# reads what it leaves behind.
#
#   bash tools/fetch_words.sh
#
# Both lists come from the same generator (https://app.aspell.net/create) and differ only in how
# much of the database they let through:
#   answers — size 35, US spelling, variant level 1: the common words a target is drawn from.
#   valid   — size 95, US/GB/CA/AU spellings, variant level 6: everything a guess may be.
# Size is ESDB's own ranking by usefulness, so it is what keeps obscure words out of the answers
# while the valid list stays as permissive as the database allows (level 8 exists and adds ~30
# five-letter words — not worth the oddities it brings in).
#
# Each download is a licence preamble, a `---` line, then one word per line. The preamble is kept
# next to its list, as res/<list>.LICENSE.txt — ESDB asks that its notice travel with any list
# derived from it, and the preamble also records the exact parameters that list was generated
# from, which differ between the two (hence one file each, licence text duplicated and all).
# The body is filtered to /^[a-z]+$/, which drops proper nouns (they are capitalised),
# possessives (`'s`), hyphenated forms and anything still carrying a diacritic. Sorting is
# LC_ALL=C, the byte order the build's encoder front-codes against.
#
# Words of every length are kept: the files hold the whole vocabulary and build/main.rs takes the
# length it was asked for (WGT_WORD_LEN) out of them.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RES="$REPO/res"

BASE='https://app.aspell.net/create?download=wordlist&encoding=utf-8&format=inline&diacritic=strip&special=hacker'
ANSWERS_URL="$BASE&max_size=35&spelling=US&variant_level=1"
VALID_URL="$BASE&max_size=95&spelling=US&spelling=GBs&spelling=GBz&spelling=CA&spelling=AU&variant_level=6"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

fetch() { # fetch <url> <destination>
  local url="$1" dest="$2"
  if ! curl --fail --location --silent --show-error --max-time 300 --output "$TMP" "$url"; then
    echo "!! download failed: $dest" >&2
    exit 1
  fi
  # The preamble ends at the first `---` line; everything before it is the licence and the
  # parameters this very list was generated from.
  if ! grep -q '^---$' "$TMP"; then
    echo "!! no '---' separator in the response — the generator's format changed" >&2
    exit 1
  fi
  sed '/^---$/,$d' "$TMP" >"${dest%.txt}.LICENSE.txt"
  sed '1,/^---$/d' "$TMP" | grep -E '^[a-z]+$' | LC_ALL=C sort -u >"$dest"
  echo "  $(wc -l <"$dest" | tr -d ' ') words -> ${dest#"$REPO/"}"
}

# Inflected forms are dropped from the answers: guessing a word only to be told the target was
# its plural is the least interesting way to lose. A word goes when it is the plural, past or
# -ing form of a word the vocabulary already holds — a morphology test, not a suffix test, so
# `chess`, `gross` and `atlas` stay (they are the plural of nothing) while `abets` and `baked`
# go. Roots are looked up in the valid list, the widest one, so a root too rare to be an answer
# itself still counts. Only the answers are filtered; the valid list is left as downloaded.
drop_inflected() { # drop_inflected <roots-file> <list-file>
  awk '
    function known(s) { return (s in root) }
    function ends(w, suf,   n) { n = length(suf); return substr(w, length(w) - n + 1) == suf }
    # A root whose last letter is doubled before the suffix (up -> upped).
    function undoubled(b,   n) {
      n = length(b)
      return (n > 1 && substr(b, n, 1) == substr(b, n - 1, 1)) ? substr(b, 1, n - 1) : ""
    }
    function inflected(w,   n, b, u) {
      n = length(w)
      # Plural / third person. Never on -ss, and never off a root that is itself a plural:
      # that is what keeps brass (bras) and gross (gros) out of the rule.
      if (ends(w, "s") && !ends(w, "ss")) {
        b = substr(w, 1, n - 1)
        if (known(b) && !ends(b, "s")) return 1
        b = substr(w, 1, n - 2)
        if (ends(w, "es") && known(b) &&
            (index("sxz", substr(b, length(b), 1)) || ends(b, "ch") || ends(b, "sh"))) return 1
        if (ends(w, "ies") && known(substr(w, 1, n - 3) "y")) return 1
      }
      # Past tense: acted < act, baked < bake, upped < up, cried < cry.
      if (ends(w, "ed")) {
        b = substr(w, 1, n - 2)
        if (known(b) || known(b "e")) return 1
        u = undoubled(b)
        if (u != "" && known(u)) return 1
        if (ends(w, "ied") && known(substr(w, 1, n - 3) "y")) return 1
      }
      # Present participle: doing < do, aping < ape, potting < pot.
      if (ends(w, "ing")) {
        b = substr(w, 1, n - 3)
        if (known(b) || known(b "e")) return 1
        u = undoubled(b)
        if (u != "" && known(u)) return 1
      }
      return 0
    }
    NR == FNR { root[$0]; next }
    !inflected($0)
  ' "$1" "$2" >"$TMP" && cat "$TMP" >"$2"
}

echo "answers (size 35, US, variant level 1)"
fetch "$ANSWERS_URL" "$RES/answer_words.txt"
echo "valid (size 95, US/GB/CA/AU, variant level 6)"
fetch "$VALID_URL" "$RES/valid_words.txt"

echo "dropping inflected forms from the answers"
before="$(wc -l <"$RES/answer_words.txt" | tr -d ' ')"
drop_inflected "$RES/valid_words.txt" "$RES/answer_words.txt"
after="$(wc -l <"$RES/answer_words.txt" | tr -d ' ')"
echo "  $before -> $after words ($((before - after)) dropped)"

# Per-length breakdown: what a build would get for each WGT_WORD_LEN the game is playable at.
echo
printf '  %-6s %8s %8s\n' length answers valid
for n in 3 4 5 6 7; do
  printf '  %-6s %8s %8s\n' "$n" \
    "$(grep -cE "^[a-z]{$n}$" "$RES/answer_words.txt")" \
    "$(grep -cE "^[a-z]{$n}$" "$RES/valid_words.txt")"
done
