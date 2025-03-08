# MSP-shared-task

Welcome to the official repo of UniDive's 1st shared task on morpho-syntactic parsing. In this repo you will find the data for training and testing your systems. Soon we will add scripts for evalutation and data in some more languages.

To ensure being up to date, please join [our Google group](https://groups.google.com/g/msp-sharedtask-2025-participants).

There is also [a webpage](https://unidive.lisn.upsaclay.fr/doku.php?id=other-events:msp) on the UniDive website.

## Motivation

Words have long been an essential concept in the definition of treebanks in Universal Dependencies (UD), since the first stage in their construction is delimiting words in the language at hand. This is done due to the common view in theoretical linguistics of words as the dividing line between syntax, the grammatical module of word combination, and morphology, that is word construction. But the lack on an agreed cross-lingual definition for words cause dependency parsing treebanks to vary in handling different languages, mostly on the basis of word delimitation.

Morphosyntactic parsing redefines the content-function boundary to differentiate 'morphological' from 'syntactic' elements. In our morphosyntactic data structure, content words are represented as separate nodes on a dependency graph, even if they share a whitespace-separated word, and both function words and morphemes contribute morphology-style features to characterize the nodes. Systems are required to predict both arcs and features, and model syntax and morphology at the same time.

## File Format

The data resembles UD treebanks and is using the same CoNLL-U structure. The required output from systems includes the arcs with their labels between content nodes, together with their grammatical features (that may be deduced from the function words). That is to say that systems should predict the `head`, `deprel` and `feats` columns. Other columns, namely `lemma` and `upos` areprovided for reference, systen may or may not predict them and our metrics do not consider them. In addition, function words are also present in the data without any columns other than `lemma` and `upos`. This is also just for reference and systems won't take nodes of function words into account. Function nodes are distinguished by `_` in their `feats` column.

Example sentence (from the English training data):
~~~ conllu
# sent_id = weblog-typepad.com_ripples_20040407125600_ENG_20040407_125600-0020
# text = There is a lot to learn about Chernobyl.
1	There	there	PRON	_	|	2	expl	_	_
2	is	be	VERB	_	Mood=Ind|Polarity=Pos|Tense=Pres|VerbForm=Fin|Voice=Act	0	root	_	_
3	a	a	DET	_	_	_	_	_	_
4	lot	lot	NOUN	_	Definite=Ind|Number=Sing	2	nsubj	_	_
5	to	to	PART	_	_	_	_	_	_
6	learn	learn	VERB	_	Mood=Ind|Polarity=Pos|VerbForm=Inf|Voice=Act	4	acl	_	_
7	about	about	ADP	_	_	_	_	_	_
8	Chernobyl	Chernobyl	PROPN	_	Case=The|Number=Sing	6	obl	_	_
9	.	.	PUNCT	_	_	_	_	_	_
~~~~
Note that the 3rd and 7th node are function nodes and deduceable from the features `Definite=Ind` and `Case=The`, respectively.

For each langauge, a covered sev set is also provided to let participants know in what format the covered test set will be.

## Important Dates

- ~~Training and development set release: 7 Mar~~
- Test set without labels release: 15 June
- System submission deadline: 1 July
- Evaluations released to participants: 7 July
- System description deadline: 1 Aug
- Concluding event @ SyntaxFest 2025: 26 Aug

