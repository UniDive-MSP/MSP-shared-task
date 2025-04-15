#!/usr/bin/env python3

# Compatible with Python 2.7 and 3.2+, can be used either as a module
# or a standalone executable.
#
# Copyright 2017, 2018 Institute of Formal and Applied Linguistics (UFAL),
# Faculty of Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Authors: Milan Straka, Martin Popel <surname@ufal.mff.cuni.cz>
#
# Changelog:
# - [12 Apr 2018] Version 0.9: Initial release.
# - [19 Apr 2018] Version 1.0: Fix bug in MLAS (duplicate entries in functional_children).
#                              Add --counts option.
# - [02 May 2018] Version 1.1: When removing spaces to match gold and system characters,
#                              consider all Unicode characters of category Zs instead of
#                              just ASCII space.
# - [25 Jun 2018] Version 1.2: Use python3 in the she-bang (instead of python).
#                              In Python2, make the whole computation use `unicode` strings.
# - [10 Apr 2025] Version 1.3: Adapted for morpho-syntactic parsing by Omer Goldman

# Command line usage
# ------------------
# msp_25_eval.py gold_conllu_file system_conllu_file
#
# The official evaluation metrics of UniDive 2025 shred task will be printed, these include:
#   - LAS: how well does HEAD+DEPREL(ignoring subtypes) match between aligned system and gold words (without considering FEATS)
#   - Feats: average F1 score for the morhpo-syntactic features between aligned system and gold words (without considering HEAD and DEPREL)
#   - MSLAS: average F1 score for the morhpo-syntactic features over the nodes where the system got HEAD and DEPREL correctly

# API usage
# ---------
# - load_conllu(file)
#   - loads CoNLL-U file from given file object to an internal representation
#   - the file object should return str in both Python 2 and Python 3
#   - raises UDError exception if the given file cannot be loaded
# - evaluate(gold_ud, system_ud)
#   - evaluate the given gold and system CoNLL-U files (loaded with load_conllu)
#   - raises UDError if the concatenated tokens of gold and system file do not match
#   - returns a dictionary with the metrics described above, each metric having
#     three fields: precision, recall and f1

# Description of token matching
# -----------------------------
# For each sentence, we match content words by order of appearance. If the system
# omits abstract nodes (i.e., nodes that only have features and no form or lemma),
# the matching continues to the next content word.


from __future__ import division
from __future__ import print_function

import argparse
import io
import itertools
import sys
import unicodedata
import unittest

# CoNLL-U column names
ID, FORM, LEMMA, UPOS, XPOS, FEATS, HEAD, DEPREL, DEPS, MISC = range(10)

UNIVERSAL_FEATURES = {
    "PronType", "NumType", "Poss", "Reflex", "Foreign", "Abbr", "Gender",
    "Animacy", "Number", "Case", "Definite", "Degree", "VerbForm", "Mood",
    "Tense", "Aspect", "Voice", "Evident", "Polarity", "Person", "Polite"
}

# UD Error is used when raising exceptions in this module
class UDError(Exception):
    pass

# Conversion methods handling `str` <-> `unicode` conversions in Python2
def _decode(text):
    return text if sys.version_info[0] >= 3 or not isinstance(text, str) else text.decode("utf-8")

def _encode(text):
    return text if sys.version_info[0] >= 3 or not isinstance(text, unicode) else text.encode("utf-8")

# Load given CoNLL-U file into internal representation
def load_conllu(file, path=None):
    # Internal representation classes
    class UDRepresentation:
        def __init__(self):
            # Characters of all the tokens in the whole file.
            # Whitespace between tokens is not included.
            self.characters = []
            # List of UDSpan instances with start&end indices into `characters`.
            self.tokens = []
            # List of UDWord instances.
            self.words = []
            # List of UDSpan instances with start&end indices into `words`.
            self.sentences = []
        def __repr__(self):
            if path:
                return "UD file: " + path
            else:
                return super.__repr__()
    class UDSpan:
        def __init__(self, start, end):
            self.start = start
            # Note that self.end marks the first position **after the end** of span,
            # so we can use either characters[start:end], words[start:end] or range(start, end).
            self.end = end
        def __repr__(self):
            return f"{self.start}--{self.end}"
    class UDWord:
        def __init__(self, span, columns):
            # Span of this word (or MWT, see below) within ud_representation.characters.
            self.span = span
            # 10 columns of the CoNLL-U file: ID, FORM, LEMMA,...
            self.columns = columns
            # Reference to the UDWord instance representing the HEAD (or None if root).
            self.parent = None
            # Only consider universal FEATS.
            if columns[FEATS]=='|':
                self.columns[FEATS] = columns[FEATS]
            else:
                self.columns[FEATS] = "|".join(sorted(feat for feat in columns[FEATS].split("|")))
            # Let's ignore language-specific deprel subtypes.
            self.columns[DEPREL] = columns[DEPREL].split(":")[0]

        def __repr__(self):
            return self.columns[FORM]

    ud = UDRepresentation()

    # Load the CoNLL-U file
    index, sentence_start = 0, None
    while True:
        line = file.readline()
        if not line:
            break
        line = _decode(line.rstrip("\r\n"))

        # Handle sentence start boundaries
        if sentence_start is None:
            # Skip comments
            if line.startswith("#"):
                continue
            # Start a new sentence
            sentence_start = len(ud.words)
            ud.sentences.append(UDSpan(sentence_start, 0))
        if not line:
            # Add parent and children UDWord links and check there are no cycles
            abstracts = list(itertools.accumulate([int('.' in word.columns[ID]) for word in ud.words[sentence_start:]]))
            def process_word(word):
                if word.parent == "remapping":
                    print(word.columns[FORM])
                    raise UDError("There is a cycle in a sentence")
                if word.parent is None:
                    head = int(word.columns[HEAD])
                    if head < 0 or head > len(ud.words) - sentence_start:
                        raise UDError("HEAD '{}' points outside of the sentence".format(_encode(word.columns[HEAD])))
                    if head:
                        parent = ud.words[sentence_start + head - 1 + abstracts[head-1]]
                        word.parent = "remapping"
                        process_word(parent)
                        word.parent = parent

            for word in ud.words[sentence_start:]:
                if word.columns[FEATS] and word.columns[FEATS] != '_':
                    process_word(word)
                else:
                    word.parent = '_'
            # func_children cannot be assigned within process_word
            # because it is called recursively and may result in adding one child twice.
            # for word in ud.words[sentence_start:]:
            #     if word.parent and word.is_functional_deprel:
            #         word.parent.functional_children.append(word)

            # Check there is a single root node
            if len([word for word in ud.words[sentence_start:] if word.parent is None]) > 1:
                raise UDError("There are multiple roots in a sentence")
            if len([word for word in ud.words[sentence_start:] if word.parent is None]) == 0 and len(ud.words[sentence_start:]) > 1:
                raise UDError("There are no roots in a sentence")

            # End the sentence
            # ud.sentences[-1].end = index
            ud.sentences[-1].end = ud.sentences[-1].start + len(ud.words[sentence_start:])
            sentence_start = None
            continue

        # Read next token/word
        columns = line.split("\t")
        if len(columns) != 10:
            raise UDError("The CoNLL-U line does not contain 10 tab-separated columns: '{}'".format(_encode(line)))

        # Skip empty nodes
        if "." in columns[ID] and columns[HEAD] == '_':
            continue

        # Skip multi-word lines
        if "-" in columns[ID]:
            continue

        # Delete spaces from FORM, so gold.characters == system.characters
        # even if one of them tokenizes the space. Use any Unicode character
        # with category Zs.
        columns[FORM] = "".join(filter(lambda c: unicodedata.category(c) != "Zs", columns[FORM]))
        if not columns[FORM]:
            raise UDError("There is an empty FORM in the CoNLL-U file")

        # Save token
        ud.characters.extend(columns[FORM])
        ud.tokens.append(UDSpan(index, index + len(columns[FORM])))
        index += len(columns[FORM])

        try:
            word_id = int(columns[ID])
        except:
            if '.' not in columns[ID]:
                raise UDError("incorrect ID format")
            word_id = columns[ID]

        try:
            head_id = int(columns[HEAD])
        except:
            # TODO
            # raise UDError("Cannot parse HEAD '{}'".format(_encode(columns[HEAD])))
            head_id = 0
        if head_id < 0:
            raise UDError("HEAD cannot be negative")

        ud.words.append(UDWord(ud.tokens[-1], columns))

    if sentence_start is not None:
        raise UDError("The CoNLL-U file does not end with empty line")

    return ud

# Evaluate the gold and system treebanks (loaded using load_conllu).
def evaluate(gold_ud, system_ud):
    class Score:
        def __init__(self, gold_total, system_total, correct, aligned_total=None):
            self.correct = correct
            self.gold_total = gold_total
            self.system_total = system_total
            self.aligned_total = aligned_total
            self.precision = correct / system_total if system_total else 0.0
            self.recall = correct / gold_total if gold_total else 0.0
            self.f1 = 2 * correct / (system_total + gold_total) if system_total + gold_total else 0.0
            self.aligned_accuracy = correct / aligned_total if aligned_total else aligned_total
    class AlignmentWord:
        def __init__(self, gold_word, system_word):
            self.gold_word = gold_word
            self.system_word = system_word
        def __repr__(self):
            return f"g-{self.gold_word}:s-{self.system_word}"
    class Alignment:
        def __init__(self, gold_words, system_words, include_function=False):
            self.include_function = include_function
            self.gold_words = gold_words
            self.system_words = system_words
            self.matched_words = []
            self.matched_words_map = {}
            if not include_function:
                self.gold_words = [word for word in self.gold_words if word.columns[FEATS]]
                self.system_words = [word for word in self.system_words if word.columns[FEATS]]
        def append_aligned_words(self, gold_word, system_word):
            if (gold_word.columns[FEATS] and system_word.columns[FEATS]) or self.include_function:
                self.matched_words.append(AlignmentWord(gold_word, system_word))
                self.matched_words_map[system_word] = gold_word

    def spans_score(gold_spans, system_spans):
        correct, gi, si = 0, 0, 0
        while gi < len(gold_spans) and si < len(system_spans):
            if system_spans[si].start < gold_spans[gi].start:
                si += 1
            elif gold_spans[gi].start < system_spans[si].start:
                gi += 1
            else:
                correct += gold_spans[gi].end == system_spans[si].end
                si += 1
                gi += 1

        return Score(len(gold_spans), len(system_spans), correct)

    def feats_dict(feats_str: str):
        if feats_str == '|':
            return {}
        if feats_str == '':
            raise ValueError('evaluating features of a function node?!')
        feats = feats_str.split('|')
        feats = dict([feat.split('=') for feat in feats])
        return {k: v for k,v in feats.items() if k in UNIVERSAL_FEATURES}

    def f1_of_feats(gold_feats, system_feats):
        if not gold_feats and not system_feats:
            return 1
        elif not gold_feats or not system_feats:
            return 0

        all_keys = set(gold_feats.keys()) | set(system_feats.keys())
        matched_feats = [(gold_feats.get(key, None), system_feats.get(key, None)) for key in all_keys]
        correct = sum([mf[0]==mf[1] for mf in matched_feats if mf[0] and mf[1]])

        precision = correct / len(system_feats)
        recall = correct / len(gold_feats)
        f1 = 2 * correct / (len(system_feats) + len(gold_feats)) if len(system_feats) + len(gold_feats) else 0.0

        return f1

    def alignment_score(alignment, key_fn=None, filter_fn=None, LAS=False):
        if filter_fn is not None:
            gold = sum(1 for gold in alignment.gold_words if filter_fn(gold))
            system = sum(1 for system in alignment.system_words if filter_fn(system))
            aligned = sum(1 for word in alignment.matched_words if filter_fn(word.gold_word))
        else:
            gold = len(alignment.gold_words)
            system = len(alignment.system_words)
            aligned = len(alignment.matched_words)

        if key_fn is None:
            # Return score for whole aligned words
            return Score(gold, system, aligned)

        def gold_aligned_gold(word):
            return word
        def gold_aligned_system(word):
            return alignment.matched_words_map.get(word, "NotAligned") if word is not None else None
        correct = 0
        for words in alignment.matched_words:
            if filter_fn is None or filter_fn(words.gold_word):
                if key_fn(words.gold_word, gold_aligned_gold) == key_fn(words.system_word, gold_aligned_system):
                    if LAS:
                        correct += 1
                    else:
                        gold_feats = feats_dict(words.gold_word.columns[FEATS])
                        system_feats = feats_dict(words.system_word.columns[FEATS])
                        correct += f1_of_feats(gold_feats, system_feats)

        return Score(gold, system, correct, aligned)

    def compute_lcs(gold_words, system_words, gi, si, gs, ss):
        lcs = [[0] * (si - ss) for i in range(gi - gs)]
        for g in reversed(range(gi - gs)):
            for s in reversed(range(si - ss)):
                if gold_words[gs + g].columns[FORM].lower() == system_words[ss + s].columns[FORM].lower():
                    lcs[g][s] = 1 + (lcs[g+1][s+1] if g+1 < gi-gs and s+1 < si-ss else 0)
                lcs[g][s] = max(lcs[g][s], lcs[g+1][s] if g+1 < gi-gs else 0)
                lcs[g][s] = max(lcs[g][s], lcs[g][s+1] if s+1 < si-ss else 0)
        return lcs

    def align_words(gold_words, system_words, gold_sentences, system_sentences):
        alignment = Alignment(gold_words, system_words)

        gi, si = 0, 0
        sent_idx = 0
        gold_sent_end = gold_sentences[sent_idx].end
        system_sent_end = system_sentences[sent_idx].end
        while gi < len(gold_words) and si < len(system_words):

            # make sure we don't align words across sentences
            if gi == gold_sent_end or si == system_sent_end:
                if gi != gold_sent_end:
                    gi = gold_sent_end
                elif si != system_sent_end:
                    si = system_sent_end

                sent_idx += 1
                gold_sent_end = gold_sentences[sent_idx].end
                system_sent_end = system_sentences[sent_idx].end

            if gold_words[gi].columns[FEATS] and system_words[si].columns[FEATS]:
                # if the content words are abstract nodes align them only if both words are abstract. this is done to
                # not over-punish systems for missing one abstract node (which may cause a shift in the following
                # content words.
                if gold_words[gi].columns[FORM] == '_' or system_words[si].columns[FORM] == '_':
                    if gold_words[gi].columns[FORM] == system_words[si].columns[FORM]:
                        alignment.append_aligned_words(gold_words[gi], system_words[si])
                        gi += 1
                        si += 1
                    elif gold_words[gi].columns[FORM] == '_':
                        gi += 1
                    else: # system_words[si].columns[FORM] == '_':
                        si += 1
                else:
                    alignment.append_aligned_words(gold_words[gi], system_words[si])
                    gi += 1
                    si += 1
            elif not gold_words[gi].columns[FEATS]:
                gi += 1
            else: # not system_words[si].columns[FEATS]
                si += 1

        return alignment

    # Align words
    alignment = align_words(gold_ud.words, system_ud.words, gold_ud.sentences, system_ud.sentences)

    # Compute the F1-scores
    scores = {
        "MSLAS": alignment_score(alignment, lambda w, ga: (ga(w.parent), w.columns[DEPREL])),
        "Feats": alignment_score(alignment, lambda w, ga: True),
        "LAS": alignment_score(alignment, lambda w, ga: (ga(w.parent), w.columns[DEPREL]), LAS=True),
    }
    return scores


def load_conllu_file(path):
    _file = open(path, mode="r", **({"encoding": "utf-8"} if sys.version_info >= (3, 0) else {}))
    return load_conllu(_file, path)

def evaluate_wrapper(args):
    # Load CoNLL-U files
    gold_ud = load_conllu_file(args.gold_file)
    system_ud = load_conllu_file(args.system_file)
    return evaluate(gold_ud, system_ud)

def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("gold_file", type=str,
                        help="Name of the CoNLL-U file with the gold data.")
    parser.add_argument("system_file", type=str,
                        help="Name of the CoNLL-U file with the predicted data.")
    args = parser.parse_args()

    # Evaluate
    evaluation = evaluate_wrapper(args)

    # Print the evaluation
    print("MSLAS <F1> Score: {:.2f}".format(100 * evaluation["MSLAS"].f1))
    print("LAS F1 Score: {:.2f}".format(100 * evaluation["LAS"].f1))
    print("Feats F1 Score: {:.2f}".format(100 * evaluation["Feats"].f1))

if __name__ == "__main__":
    main()

# Tests, which can be executed with `python -m unittest conll18_ud_eval`.
class TestAlignment(unittest.TestCase):
    @staticmethod
    def _load_words(words):
        """Prepare fake CoNLL-U files with fake HEAD to prevent multiple roots errors."""
        lines, num_words = [], 0
        for w in words:
            parts = w.split(" ")
            if len(parts) == 1:
                num_words += 1
                lines.append("{}\t{}\t_\t_\t_\tFeat=Val\t{}\t_\t_\t_".format(num_words, parts[0], int(num_words>1)))
            else:
                lines.append("{}-{}\t{}\t_\t_\t_\t_\t_\t_\t_\t_".format(num_words + 1, num_words + len(parts) - 1, parts[0]))
                for part in parts[1:]:
                    num_words += 1
                    lines.append("{}\t{}\t_\t_\t_\tFeat=Val\t{}\t_\t_\t_".format(num_words, part, int(num_words>1)))
        return load_conllu((io.StringIO if sys.version_info >= (3, 0) else io.BytesIO)("\n".join(lines+["\n"])))

    def _test_exception(self, gold, system):
        self.assertRaises(UDError, evaluate, self._load_words(gold), self._load_words(system))

    def _test_ok(self, gold, system, correct):
        metrics = evaluate(self._load_words(gold), self._load_words(system))

    def test_equal(self):
        self._test_ok(["a"], ["a"], 1)
        self._test_ok(["a", "b", "c"], ["a", "b", "c"], 3)

    def test_equal_with_abstracts(self):
        self._test_ok(["a", "b", "c"], ["a", "_", "b", "c"], 3)

    def test_equal_with_multiword(self):
        self._test_ok(["abc a b c"], ["a", "b", "c"], 3)
        self._test_ok(["a", "bc b c", "d"], ["a", "b", "c", "d"], 4)
        self._test_ok(["abcd a b c d"], ["ab a b", "cd c d"], 4)
        self._test_ok(["abc a b c", "de d e"], ["a", "bcd b c d", "e"], 5)

    def test_alignment(self):
        self._test_ok(["abcd"], ["a", "b", "c", "d"], 0)
        self._test_ok(["abc", "d"], ["a", "b", "c", "d"], 1)
        self._test_ok(["a", "bc", "d"], ["a", "b", "c", "d"], 2)
        self._test_ok(["a", "bc b c", "d"], ["a", "b", "cd"], 2)
        self._test_ok(["abc a BX c", "def d EX f"], ["ab a b", "cd c d", "ef e f"], 4)
        self._test_ok(["ab a b", "cd bc d"], ["a", "bc", "d"], 2)
        self._test_ok(["a", "bc b c", "d"], ["ab AX BX", "cd CX a"], 1)
