"""Cognitively-hard benchmark tasks with OBJECTIVE ground truth (auto-generated + verified).

Generated across reasoning categories and independently verified (each answer re-derived from
scratch, code executed) before inclusion. Scoring: a solver's final answer is CORRECT if it
matches any `signatures` variant (AND-list of lowercased keywords). Built by build_cog_bank.py.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class CogTask:
    id: str
    category: str
    prompt: str
    answer: str
    difficulty: str
    signatures: List[List[str]]


def by_category():
    out = {}
    for t in COGNITIVE_TASKS:
        out.setdefault(t.category, []).append(t)
    return out


COGNITIVE_TASKS: List[CogTask] = [

    CogTask(
        id='deductive_logic__knights-knaves-spies-five', category='deductive_logic', difficulty='very-hard',
        prompt='On an island, every inhabitant is exactly one of three types: a Knight (every statement they make is true), a Knave (every statement they make is false), or a Spy (each statement may be either true or false). Five inhabitants — A, B, C, D, E — are known to consist of exactly 2 Knights, 2 Knaves, and 1 Spy. Each makes one statement:\n- A says: "E is a Knave."\n- B says: "A is a Spy."\n- C says: "B is a Spy."\n- D says: "B and E are the same type as each other."\n- E says: "B and D are different types from each other."\nGiven these statements and the type counts, exactly one assignment is consistent. Which inhabitant is the Spy?',
        answer='B is the Spy. (Full assignment: A=Knave, B=Spy, C=Knight, D=Knave, E=Knight.)',
        signatures=[['spy', 'b'], ['b is the spy']],
    ),
    CogTask(
        id='deductive_logic__zebra-four-house-fish', category='deductive_logic', difficulty='hard',
        prompt="Four houses stand in a row, numbered 1 to 4 from left to right. Each house has a distinct Color (Red, Blue, Green, White), a distinct Drink (Tea, Coffee, Milk, Water), and a distinct Pet (Cat, Dog, Fish, Bird). The following are all true:\n1. The Green house is immediately to the right of the White house.\n2. The person in the Green house drinks Coffee.\n3. The Red house's owner has a Dog.\n4. The person in house 2 drinks Milk.\n5. The Blue house is at one of the two ends of the row.\n6. The Cat owner drinks Tea.\n7. The Bird owner's house is immediately to the right of the Fish owner's house.\n8. The White house's owner drinks Water.\nIn which house (1–4) is the Fish, and what color is that house?",
        answer='The Fish is in house 3, which is the White house.',
        signatures=[['fish', 'house 3', 'white'], ['fish', '3', 'white'], ['white', 'house 3']],
    ),
    CogTask(
        id='deductive_logic__knights-knaves-count-knaves', category='deductive_logic', difficulty='hard',
        prompt='Five people — A, B, C, D, E — are each either a Knight (always tells the truth) or a Knave (always lies). They make the following statements:\n- A: "Exactly two of us five are Knaves."\n- B: "D is a Knave."\n- C: "B and D are both Knaves."\n- D: "A and C are the same type as each other."\n- E: "C is a Knight."\nExactly one assignment of Knight/Knave to the five people is consistent. List exactly which people are the Knaves.',
        answer='The Knaves are A, B, C, and E (only D is a Knight).',
        signatures=[['knaves', 'a', 'b', 'c', 'e'], ['a, b, c, e'], ['only d', 'knight']],
    ),
    CogTask(
        id='deductive_logic__forehead-sum-epistemic', category='deductive_logic', difficulty='very-hard',
        prompt='Three perfect logicians — Alice, Bob, and Carol — each have a distinct positive integer written on their forehead. They are told (and all know) that the three numbers are distinct positive integers and that one of the three numbers equals the sum of the other two. Each can see the other two foreheads but not her own. In turn they announce:\n- Alice: "I cannot determine my own number."\n- Bob: "I cannot determine my own number."\n- Carol: "Now I can determine my own number."\nIt is a fact that Alice\'s number is 20 and Bob\'s number is 30. Assuming all three reason perfectly and everyone hears every announcement, what number is on Carol\'s forehead?',
        answer='50',
        signatures=[['50'], ['carol', '50'], ['fifty']],
    ),
    CogTask(
        id='deductive_logic__race-ordering-third', category='deductive_logic', difficulty='hard',
        prompt="Five runners — P, Q, R, S, T — finished a race in distinct positions 1st through 5th, with no ties. All of the following are true:\n1. P finished before Q, and Q finished before R.\n2. Exactly one runner finished in a position between P's and T's.\n3. S finished neither first nor last.\n4. R finished in a position immediately adjacent to S's (either directly ahead of or directly behind S).\n5. T did NOT finish in the position immediately after P.\nExactly one finishing order satisfies all five conditions. Who finished in 3rd place?",
        answer='T finished 3rd. (The full order, 1st to 5th, is P, Q, T, S, R.)',
        signatures=[['p, q, t, s, r'], ['p,q,t,s,r'], ['t finished 3rd'], ['t finished third'], ['t finished in 3rd'], ['t finished in third'], ['t came in 3rd'], ['t came in third'], ['t came 3rd'], ['t came third'], ['t in 3rd place'], ['t in third place'], ['3rd place is t'], ['third place is t'], ['3rd place: t'], ['third place: t'], ['3rd place was t'], ['third place was t'], ['answer is t'], ['it is t'], ["it's t"]],
    ),
    CogTask(
        id='deductive_logic__guilty-innocent-truth-lie', category='deductive_logic', difficulty='hard',
        prompt='A window was broken by exactly one of four children: Alex, Bo, Cy, or Dee. It is known that every innocent child tells the truth, and the guilty child lies. Each child makes exactly one statement:\n- Alex: "Bo is innocent."\n- Bo: "Cy is guilty."\n- Cy: "Bo\'s statement is false."\n- Dee: "I am innocent."\nExactly one child is guilty and the above rules hold consistently. Who broke the window?',
        answer='Cy broke the window.',
        signatures=[['cy'], ['cy broke'], ['cy is guilty']],
    ),
    CogTask(
        id='deductive_logic__einstein-five-house-fish', category='deductive_logic', difficulty='very-hard',
        prompt="Five houses stand in a row, numbered 1 to 5 from left to right. Each house has an owner of a distinct Nationality (Norwegian, Brit, Swede, Dane, German), a distinct Color (Red, Green, White, Yellow, Blue), a distinct Drink (Tea, Coffee, Milk, Beer, Water), and a distinct Pet (Dog, Bird, Cat, Horse, Fish). All of the following hold:\n1. The Norwegian lives in house 1.\n2. The Brit lives in the Red house.\n3. The Green house is immediately to the left of the White house.\n4. The Norwegian lives next to the Blue house.\n5. The Green house's owner drinks Coffee.\n6. The person in the middle house (house 3) drinks Milk.\n7. The Dane drinks Tea.\n8. The German drinks Beer.\n9. The Swede keeps a Dog.\n10. The owner of the Yellow house keeps a Horse.\n11. The Bird owner lives directly next to the Cat owner.\n12. The Bird owner drinks Tea.\nExactly one full arrangement is consistent. Which nationality keeps the Fish?",
        answer='The German keeps the Fish. (Arrangement: H1 Norwegian/Yellow/Water/Horse, H2 Dane/Blue/Tea/Bird, H3 Brit/Red/Milk/Cat, H4 Swede/Green/Coffee/Dog, H5 German/White/Beer/Fish.)',
        signatures=[['german']],
    ),
    CogTask(
        id='deductive_logic__cheryl-style-date', category='deductive_logic', difficulty='very-hard',
        prompt='Albert and Bernard want to know Cheryl\'s birthday. Cheryl gives them a list of 10 possible dates:\nMay 15, May 16, May 19, June 17, June 18, July 14, July 16, August 14, August 15, August 17.\nCheryl then privately tells Albert only the MONTH of her birthday and tells Bernard only the DAY. The following exchange happens, and everything said is truthful:\n- Albert: "I don\'t know Cheryl\'s birthday, and I also know that Bernard does not know it either."\n- Bernard: "At first I didn\'t know Cheryl\'s birthday, but now I do."\n- Albert: "Then I also know Cheryl\'s birthday now."\nWhat is Cheryl\'s birthday?',
        answer='July 16.',
        signatures=[['july 16'], ['july', '16'], ['16 july']],
    ),
    CogTask(
        id='deductive_logic__send-more-money', category='deductive_logic', difficulty='hard',
        prompt='In the cryptarithm SEND + MORE = MONEY, each letter stands for a single decimal digit (0–9). Different letters represent different digits, the same letter always represents the same digit, and no number may have a leading zero (so S ≠ 0 and M ≠ 0). There is exactly one valid digit assignment. What is the numeric value of the word MONEY?',
        answer='MONEY = 10652 (S=9, E=5, N=6, D=7, M=1, O=0, R=8, Y=2; 9567 + 1085 = 10652).',
        signatures=[['10652'], ['money', '10652']],
    ),
    CogTask(
        id='deductive_logic__profession-city-grid', category='deductive_logic', difficulty='hard',
        prompt="Four friends — Ann, Ben, Cara, Dan — each have a distinct Job (Doctor, Engineer, Lawyer, Teacher) and live in a distinct City (NYC, LA, Chicago, Miami). All of the following are true:\n1. Ann is not the Doctor, and Ann does not live in NYC.\n2. The Engineer lives in LA.\n3. Ben lives in Chicago.\n4. Cara is the Lawyer.\n5. The Teacher does not live in Miami.\n6. Dan is not the Engineer.\n7. The person who lives in NYC is the Doctor.\nExactly one assignment is consistent. What is Dan's job and which city does he live in?",
        answer='Dan is the Doctor and lives in NYC. (Full: Ann=Engineer/LA, Ben=Teacher/Chicago, Cara=Lawyer/Miami, Dan=Doctor/NYC.)',
        signatures=[['dan', 'doctor', 'nyc'], ['doctor', 'new york'], ['dan', 'doctor', 'new york']],
    ),
    CogTask(
        id='deductive_logic__self-referential-five-statements', category='deductive_logic', difficulty='very-hard',
        prompt='Consider these five numbered statements, each of which is either true or false:\n(1) Exactly one of these five statements is false.\n(2) Exactly two of these five statements are false.\n(3) Exactly three of these five statements are false.\n(4) Exactly four of these five statements are false.\n(5) Exactly five of these five statements are false.\nThere is exactly one consistent assignment of true/false to the five statements. Which statement number is the TRUE one?',
        answer='Statement (4) is the only true one (and the other four are false).',
        signatures=[['statement 4'], ['statement (4)'], ['only', '4', 'true'], ['fourth', 'true']],
    ),
    CogTask(
        id='deductive_logic__nested-knights-knaves-six', category='deductive_logic', difficulty='brutal',
        prompt='Six islanders — A, B, C, D, E, F — are each either a Knight (every statement true) or a Knave (every statement false). They state:\n- A: "At least three of us six are Knaves."\n- B: "A and F are both Knights."\n- C: "If B is a Knight, then D is a Knave." (an ordinary if-then: this statement is false only when B is a Knight and D is not a Knave)\n- D: "C is a Knave, or E is a Knight, or both."\n- E: "At least two of D, E, F are Knights."\n- F: "B is a Knave and C is a Knight."\nExactly one assignment is consistent. How many of the six are Knights?',
        answer='Four are Knights (C, D, E, F are Knights; A and B are Knaves).',
        signatures=[['four', 'knights'], ['4 knights'], ['four are knights'], ['c, d, e, f', 'knights']],
    ),
    CogTask(
        id='quantitative_reasoning__delayed-bird', category='quantitative_reasoning', difficulty='hard',
        prompt='A passenger train leaves station A heading toward station B at a constant 60 mph. At the same instant, a freight train leaves station B heading toward station A at a constant 40 mph. The stations are 250 miles apart on a straight track. Exactly 30 minutes after both trains depart, a bird takes off from the front of the passenger train and flies back and forth between the two oncoming trains at a constant 80 mph, instantly reversing direction each time it touches a train, until the trains meet. What is the total distance, in miles, that the bird flies? Give a single number.',
        answer='160',
        signatures=[['160']],
    ),
    CogTask(
        id='quantitative_reasoning__four-dice-sum-13', category='quantitative_reasoning', difficulty='hard',
        prompt='Four fair six-sided dice, each a different color (so the dice are distinguishable), are rolled simultaneously. What is the probability that the four numbers showing sum to exactly 13? Express the answer as a reduced fraction a/b.',
        answer='35/324',
        signatures=[['35/324'], ['35', '324']],
    ),
    CogTask(
        id='quantitative_reasoning__twelve-divisors-div-by-12', category='quantitative_reasoning', difficulty='hard',
        prompt='Find the smallest positive integer n that is divisible by 12 and has exactly 12 positive divisors. Give the single number n.',
        answer='60',
        signatures=[['60']],
    ),
    CogTask(
        id='quantitative_reasoning__half-tank-drain', category='quantitative_reasoning', difficulty='very-hard',
        prompt='A tank starts empty. Pipe A alone fills it in 6 hours; pipe B alone fills it in 8 hours; drain C alone empties a full tank in 12 hours. Pipes A and B are both opened at time zero. The drain C is kept closed until the moment the tank first becomes exactly half full, at which instant C is opened and remains open. All flow rates are constant. How many hours, in total from time zero, does it take to fill the tank completely? Express the answer as a reduced fraction of hours.',
        answer='144/35',
        signatures=[['144/35'], ['144', '35']],
    ),
    CogTask(
        id='quantitative_reasoning__round-table-not-adjacent', category='quantitative_reasoning', difficulty='hard',
        prompt='Eight distinct people are to be seated around a circular table. Seatings that differ only by a rotation of everyone around the table are considered identical (reflections are considered DIFFERENT). Two particular people, Alice and Bob, refuse to sit in adjacent seats. How many distinct seatings are possible? Give a single number.',
        answer='3600',
        signatures=[['3600']],
    ),
    CogTask(
        id='quantitative_reasoning__loaded-die-bayes', category='quantitative_reasoning', difficulty='hard',
        prompt='A drawer contains four dice that look identical: three of them are fair six-sided dice, and one is a loaded die that always shows a 6. You reach in, pick one die uniformly at random, roll it once, and observe a 6. Given this observation, what is the probability that the die you picked is the loaded one? Express the answer as a reduced fraction.',
        answer='2/3',
        signatures=[['2/3']],
    ),
    CogTask(
        id='quantitative_reasoning__power-tower-mod-100', category='quantitative_reasoning', difficulty='very-hard',
        prompt='Compute the last two digits of 7^(7^7), i.e. 7 raised to the power (7^7). Equivalently, find 7^(7^7) mod 100. Give the two-digit number (write it as a number from 0 to 99).',
        answer='43',
        signatures=[['43']],
    ),
    CogTask(
        id='quantitative_reasoning__acid-replacement-3x', category='quantitative_reasoning', difficulty='hard',
        prompt='A vessel contains 20 liters of pure acid. The following operation is performed three times in total: remove 4 liters of the current (well-mixed) liquid from the vessel and replace it with 4 liters of water, then stir thoroughly. After the third replacement, what is the concentration of acid in the vessel, expressed as a percentage? Give the number (the percent value).',
        answer='51.2',
        signatures=[['51.2']],
    ),
    CogTask(
        id='quantitative_reasoning__grid-avoid-center', category='quantitative_reasoning', difficulty='very-hard',
        prompt='On a 6-by-6 grid of lattice points, a path goes from corner (0,0) to corner (6,6) using only unit steps Right (+1 in x) and Up (+1 in y). How many such monotone lattice paths do NOT pass through the center point (3,3)? Give a single number.',
        answer='524',
        signatures=[['524']],
    ),
    CogTask(
        id='quantitative_reasoning__family-ages-product', category='quantitative_reasoning', difficulty='hard',
        prompt="A man is currently four times as old as his son. In 20 years, the man will be exactly twice as old as his son will be then. The man also has a daughter who was born on the day the son turned 6 years old. Using everyone's CURRENT ages in whole years, compute the product of the man's age, the son's age, and the daughter's age. Give a single number.",
        answer='1600',
        signatures=[['1600']],
    ),
    CogTask(
        id='quantitative_reasoning__five-picks-collision', category='quantitative_reasoning', difficulty='very-hard',
        prompt='Five people each independently and uniformly pick an integer from 1 to 10 (repeats allowed, picks are independent). What is the probability that at least two of the five people pick the same number? Express the answer as a reduced fraction a/b.',
        answer='436/625',
        signatures=[['436/625'], ['436', '625']],
    ),
    CogTask(
        id='quantitative_reasoning__coprime-30-nonsquare', category='quantitative_reasoning', difficulty='brutal',
        prompt='How many integers n with 1 <= n <= 1000 satisfy BOTH of the following: n is divisible by none of 2, 3, or 5; AND n is not a perfect square? Give a single number.',
        answer='257',
        signatures=[['257']],
    ),
    CogTask(
        id='code_output_trace__late-binding-closure', category='code_output_trace', difficulty='hard',
        prompt='What does this Python program print (the exact single line of output)?\n\n```python\nfuncs = []\nfor i in range(3):\n    funcs.append(lambda x: x + i)\nprint([f(10) for f in funcs])\n```',
        answer='[12, 12, 12]',
        signatures=[['[12, 12, 12]'], ['12, 12, 12']],
    ),
    CogTask(
        id='code_output_trace__mutable-default-shared', category='code_output_trace', difficulty='hard',
        prompt='What does this Python program print? Give the exact output line.\n\n```python\ndef acc(x, store=[]):\n    store.append(x)\n    return store\n\na = acc(1)\nb = acc(2, [])\nc = acc(3)\nprint(a, b, c)\n```',
        answer='[1, 3] [2] [1, 3]',
        signatures=[['[1, 3] [2] [1, 3]'], ['[1, 3]', '[2]', '[1, 3]']],
    ),
    CogTask(
        id='code_output_trace__generator-mutates-list', category='code_output_trace', difficulty='very-hard',
        prompt='What does this Python program print?\n\n```python\nimport itertools\n\ndef gen():\n    lst = [1, 2, 3]\n    for x in lst:\n        yield x\n        lst.append(x * 10)\n\nprint(list(itertools.islice(gen(), 7)))\n```',
        answer='[1, 2, 3, 10, 20, 30, 100]',
        signatures=[['[1, 2, 3, 10, 20, 30, 100]'], ['1, 2, 3, 10, 20, 30, 100']],
    ),
    CogTask(
        id='code_output_trace__js-default-sort', category='code_output_trace', difficulty='hard',
        prompt='What does this JavaScript print to the console?\n\n```javascript\nconsole.log([10, 1, 2, 9, 20, 3].sort());\n```',
        answer='[ 1, 10, 2, 20, 3, 9 ]',
        signatures=[['1, 10, 2, 20, 3, 9'], ['[ 1, 10, 2, 20, 3, 9 ]'], ['[1, 10, 2, 20, 3, 9]']],
    ),
    CogTask(
        id='code_output_trace__python-precedence-trio', category='code_output_trace', difficulty='very-hard',
        prompt='What are the three values printed by this Python line, in order?\n\n```python\nprint(2 ** 3 ** 2, -2 ** 2, True + True * 2)\n```',
        answer='512 -4 3',
        signatures=[['512', '-4', '3'], ['512 -4 3']],
    ),
    CogTask(
        id='code_output_trace__js-coercion-chain', category='code_output_trace', difficulty='very-hard',
        prompt='What three lines does this JavaScript print, in order?\n\n```javascript\nconsole.log([] + {});\nconsole.log([1,2,3] + [4,5,6]);\nconsole.log(1 + - + + + - + 1);\n```',
        answer='[object Object]\n1,2,34,5,6\n2',
        signatures=[['[object Object]', '1,2,34,5,6', '2'], ['[object Object]\n1,2,34,5,6\n2']],
    ),
    CogTask(
        id='code_output_trace__chained-equality-in', category='code_output_trace', difficulty='very-hard',
        prompt='What does this Python expression print?\n\n```python\nprint(False == False in [False])\n```',
        answer='True',
        signatures=[['true']],
    ),
    CogTask(
        id='code_output_trace__python-banker-rounding', category='code_output_trace', difficulty='hard',
        prompt='What does this Python line print (four values in order)?\n\n```python\nprint(round(2.5), round(3.5), round(0.5), round(-0.5))\n```',
        answer='2 4 0 0',
        signatures=[['2 4 0 0']],
    ),
    CogTask(
        id='code_output_trace__js-var-let-loop-closures', category='code_output_trace', difficulty='hard',
        prompt='What does this JavaScript print?\n\n```javascript\nvar fns = [];\nfor (var i = 0; i < 3; i++) fns.push(() => i);\nlet g = [];\nfor (let j = 0; j < 3; j++) g.push(() => j);\nconsole.log(fns.map(f => f()), g.map(f => f()));\n```',
        answer='[ 3, 3, 3 ] [ 0, 1, 2 ]',
        signatures=[['[ 3, 3, 3 ] [ 0, 1, 2 ]'], ['3, 3, 3', '0, 1, 2'], ['[3, 3, 3] [0, 1, 2]']],
    ),
    CogTask(
        id='code_output_trace__dict-comp-key-collision', category='code_output_trace', difficulty='very-hard',
        prompt='What does this Python program print?\n\n```python\nprint({i % 3: i for i in range(7)})\n```',
        answer='{0: 6, 1: 4, 2: 5}',
        signatures=[['{0: 6, 1: 4, 2: 5}'], ['0: 6', '1: 4', '2: 5']],
    ),
    CogTask(
        id='code_output_trace__unpack-target-eval-order', category='code_output_trace', difficulty='brutal',
        prompt='What does this Python program print?\n\n```python\na = [1, 2, 3]\ni = 0\ni, a[i] = 1, 5\nprint(a, i)\n```',
        answer='[1, 5, 3] 1',
        signatures=[['[1, 5, 3] 1'], ['[1, 5, 3]', '1']],
    ),
    CogTask(
        id='code_output_trace__js-microtask-macrotask-order', category='code_output_trace', difficulty='brutal',
        prompt='What does this Node.js / browser JavaScript print, line by line in order?\n\n```javascript\nconsole.log("1");\nsetTimeout(() => console.log("2"), 0);\nPromise.resolve().then(() => console.log("3"));\n(async () => { console.log("4"); await null; console.log("5"); })();\nconsole.log("6");\n```',
        answer='1\n4\n6\n3\n5\n2',
        signatures=[['1\n4\n6\n3\n5\n2'], ['1', '4', '6', '3', '5', '2', '146352'], ['146352']],
    ),
    CogTask(
        id='subtle_bug_hunt__rotated-search-dup-boundary', category='subtle_bug_hunt', difficulty='hard',
        prompt='This function does binary search on a rotated, strictly-ascending array of distinct ints and returns the index of `target`, or -1. It has ONE bug that makes it return -1 for certain valid inputs even though `target` is present. Identify the exact condition that is wrong, say what it should be, and give a concrete input where it fails.\n\n```python\ndef search_rotated(a, target):\n    lo, hi = 0, len(a) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if a[mid] == target:\n            return mid\n        if a[lo] <= a[mid]:                 # left half is sorted\n            if a[lo] <= target and target < a[mid]:\n                hi = mid - 1\n            else:\n                lo = mid + 1\n        else:                              # right half is sorted\n            if a[mid] < target and target < a[hi]:\n                lo = mid + 1\n            else:\n                hi = mid - 1\n    return -1\n```',
        answer='In the right-half-sorted branch, `target < a[hi]` must be `target <= a[hi]`. The endpoint a[hi] was never tested for equality, so it must be included; with strict `<`, when target equals the largest element of the sorted right half the code shrinks toward the wrong half and returns -1. Failing input: a=[6,7,0,1,2,3,4], target=4. The right half [0,1,2,3,4] is sorted and target==a[hi]==4, but `target < a[hi]` is false, so it discards the correct half and returns -1 instead of index 6.',
        signatures=[['target <= a[hi]'], ['target < a[hi]', 'should', '<='], ['a[hi]', 'inclusive'], ['right', 'branch', '<=', 'a[hi]']],
    ),
    CogTask(
        id='subtle_bug_hunt__lru-touch-on-get', category='subtle_bug_hunt', difficulty='hard',
        prompt='A fixed-capacity LRU cache built on an insertion-ordered dict. `get` returns the value or None; `put` inserts/updates and evicts the least-recently-used entry when over capacity. There is ONE bug that evicts a recently-used entry under a specific access pattern. Find it and give the triggering sequence.\n\n```python\nclass LRU:\n    def __init__(self, cap):\n        self.cap = cap\n        self.d = {}\n    def get(self, k):\n        if k not in self.d:\n            return None\n        return self.d[k]\n    def put(self, k, v):\n        if k in self.d:\n            del self.d[k]\n        self.d[k] = v\n        if len(self.d) > self.cap:\n            oldest = next(iter(self.d))\n            del self.d[oldest]\n```',
        answer="`get` is a cache hit but never refreshes recency — it reads the value without moving the key to the most-recent position (it should delete and reinsert, e.g. `self.d.move_to_end(k)` or `del; reinsert`). Since recency is encoded solely by dict insertion order, a key accessed only through `get` keeps its old position and becomes a false eviction victim. Sequence (cap=2): put('A',1); put('B',2); get('A') (logically makes A most-recent, but its dict position stays oldest); put('C',3) -> over capacity, `next(iter(self.d))` is A, so A is evicted even though it was just used; B should have been evicted instead.",
        signatures=[['get', 'does not', 'recently'], ['get', 'move_to_end'], ['get', 'no', 'reorder'], ['read', 'does not', 'refresh', 'order']],
    ),
    CogTask(
        id='subtle_bug_hunt__interval-merge-sort-key', category='subtle_bug_hunt', difficulty='very-hard',
        prompt='`merge_intervals` should merge overlapping closed intervals (touching merges: [1,3]&[3,5]->[1,5]) and return them. There is ONE bug producing an incorrect merge for some inputs. Identify it precisely and give a failing input with the wrong vs. correct output.\n\n```python\ndef merge_intervals(intervals):\n    if not intervals:\n        return []\n    intervals = sorted(intervals, key=lambda iv: iv[1])\n    merged = [list(intervals[0])]\n    for s, e in intervals[1:]:\n        last = merged[-1]\n        if s <= last[1]:\n            last[1] = max(last[1], e)\n        else:\n            merged.append([s, e])\n    return merged\n```',
        answer="The sort key is wrong: it sorts by END (`iv[1]`) instead of by START (`iv[0]`). The linear merge assumes intervals arrive in start order so that the running interval's start is the minimum seen; sorting by end breaks that, so the merged interval can take its start from a later-but-larger-start interval, losing the true minimum start (and potentially missing overlaps). Failing input: [[1,10],[2,3],[4,12]]. Sorted by end -> [[2,3],[1,10],[4,12]], and the code outputs [[2,12]]; the correct answer is [[1,12]] (start 1 is lost). Fix: sort by `iv[0]`.",
        signatures=[['sort', 'by start', 'iv[0]'], ['sorted by end', 'should', 'start'], ['sort key', 'iv[1]', 'iv[0]'], ['wrong sort key', 'start']],
    ),
    CogTask(
        id='subtle_bug_hunt__retry-backoff-jitter-cap', category='subtle_bug_hunt', difficulty='hard',
        prompt='This computes the sleep delay (seconds) before retry attempt `n` (n starts at 1) using exponential backoff with full jitter and a max cap. `rand01` is uniform in [0,1). There is ONE bug that breaks the intended behavior. Find it and explain the consequence.\n\n```python\ndef backoff_delay(n, base=0.5, cap=30.0, rand01=0.5):\n    exp = base * (2 ** (n - 1))\n    capped = min(cap, exp)\n    delay = rand01 * cap\n    return delay\n```',
        answer='The jitter line uses `cap` instead of `capped`: `delay = rand01 * cap`. So `capped` (the exponentially growing, cap-limited value) is computed but never used, and the returned delay is uniform on [0, cap) for EVERY attempt regardless of `n`. Early retries that should be tiny (e.g. ~[0,0.5) for n=1) can instead be up to the full 30s, eliminating exponential backoff entirely. Fix: `delay = rand01 * capped`.',
        signatures=[['rand01 * capped'], ['uses', 'cap', 'not', 'capped'], ['capped', 'unused'], ['delay', 'should', 'capped']],
    ),
    CogTask(
        id='subtle_bug_hunt__toctou-lockfile', category='subtle_bug_hunt', difficulty='very-hard',
        prompt='This helper is meant to atomically create a brand-new lock file and fail if the lock already exists, so only one process runs at a time. There is ONE concurrency defect that lets two processes BOTH believe they acquired the lock. Identify it and explain the race precisely.\n\n```python\nimport os\n\ndef acquire_lock(path):\n    if os.path.exists(path):\n        return False\n    fd = os.open(path, os.O_WRONLY | os.O_CREAT)\n    os.write(fd, str(os.getpid()).encode())\n    os.close(fd)\n    return True\n```',
        answer="Classic TOCTOU plus a missing O_EXCL. The existence check (`os.path.exists`) and the create (`os.open` with O_CREAT but NOT O_EXCL) are two separate, non-atomic steps. Two processes can both pass the `exists` check before either creates the file, then both call os.open; without O_EXCL, os.open succeeds for both (creating or opening the existing file), so both write their pid and both return True — two simultaneous lock holders. Fix: remove the check and open atomically with `os.O_CREAT | os.O_EXCL`, catching FileExistsError as 'lock already held'.",
        signatures=[['toctou', 'o_excl'], ['missing', 'o_excl'], ['check', 'create', 'not atomic'], ['o_creat', 'without', 'o_excl', 'race']],
    ),
    CogTask(
        id='subtle_bug_hunt__kth-smallest-partition-bounds', category='subtle_bug_hunt', difficulty='brutal',
        prompt="`kth_smallest` returns the k-th smallest (1-indexed) element across two sorted ascending arrays `a`, `b` of distinct ints in O(log(min)), by binary searching the split of `a`. There is ONE bug that yields a wrong answer or crash for some valid (a, b, k). Pinpoint the exact lines that are wrong and what they must be.\n\n```python\ndef kth_smallest(a, b, k):\n    if len(a) > len(b):\n        a, b = b, a\n    n, m = len(a), len(b)\n    lo, hi = 0, n\n    while lo <= hi:\n        i = (lo + hi) // 2           # take i from a\n        j = k - i                    # take j from b\n        a_left  = a[i-1] if i > 0 else float('-inf')\n        a_right = a[i]   if i < n else float('inf')\n        b_left  = b[j-1] if j > 0 else float('-inf')\n        b_right = b[j]   if j < m else float('inf')\n        if a_left <= b_right and b_left <= a_right:\n            return max(a_left, b_left)\n        elif a_left > b_right:\n            hi = i - 1\n        else:\n            lo = i + 1\n    return -1\n```",
        answer='The search bounds on `i` are wrong. Since `j = k - i` must satisfy `0 <= j <= m`, the valid range for i is `max(0, k - m) <= i <= min(k, n)`, not `0 .. n`. With `lo=0, hi=n`, when k is large relative to m the code chooses `i` making `j = k - i` exceed m, so `b[j-1]` (i.e. `b_left`) indexes out of bounds (crash) or reasons over an impossible split. Fix: `lo = max(0, k - m)` and `hi = min(k, n)`. Concrete crash: a=[1,2,3], b=[4,5], k=5 (after the swap a=[4,5] len 2, b=[1,2,3] len 3); i can be 0 giving j=5 and b[4] is out of range — IndexError.',
        signatures=[['lo = max(0, k - m)', 'hi = min(k, n)'], ['bounds', 'max(0, k - m)', 'min(k, n)'], ['i', 'range', 'k - m', 'min(k,n)'], ['j', 'out of range', 'k - m', 'min(k']],
    ),
    CogTask(
        id='subtle_bug_hunt__ring-buffer-count-decrement', category='subtle_bug_hunt', difficulty='hard',
        prompt="A fixed-capacity ring buffer that distinguishes full vs empty with a `count`. `push` drops the write and returns False when full; `pop` returns None when empty. There is ONE bug that corrupts the buffer's state under a specific sequence. Find it and give the triggering sequence.\n\n```python\nclass Ring:\n    def __init__(self, cap):\n        self.buf = [None] * cap\n        self.cap = cap\n        self.head = 0   # next read\n        self.tail = 0   # next write\n        self.count = 0\n    def push(self, x):\n        if self.count == self.cap:\n            return False\n        self.buf[self.tail] = x\n        self.tail = (self.tail + 1) % self.cap\n        self.count += 1\n        return True\n    def pop(self):\n        if self.count == 0:\n            return None\n        x = self.buf[self.head]\n        self.head = (self.head + 1) % self.cap\n        return x\n```",
        answer='`pop` advances `head` but never decrements `count` (it is missing `self.count -= 1`). So `count` is monotonically non-decreasing: once it reaches `cap` it stays there, and `push` permanently returns False even though slots have been freed; conversely the buffer never reports empty after draining. Sequence (cap=2): push(1); push(2) -> count==2 (full); pop() returns 1 and moves head but count stays 2; push(3) sees count==cap -> returns False even though a slot is free. Fix: add `self.count -= 1` in pop.',
        signatures=[['pop', 'count -= 1', 'missing'], ['pop', 'does not decrement', 'count'], ['count', 'never decremented'], ['missing', 'decrement', 'pop']],
    ),
    CogTask(
        id='subtle_bug_hunt__sliding-window-max-evict', category='subtle_bug_hunt', difficulty='very-hard',
        prompt="`max_sliding_window(nums, k)` returns the list of maximums of each contiguous window of size k, using a monotonic deque of indices (front holds the current max's index). There is ONE off-by-one bug that returns a wrong max for some windows. Identify the exact condition that is wrong and what it should be, with a failing input.\n\n```python\nfrom collections import deque\n\ndef max_sliding_window(nums, k):\n    dq = deque()        # indices, values decreasing front->back\n    out = []\n    for i, x in enumerate(nums):\n        while dq and nums[dq[-1]] < x:\n            dq.pop()\n        dq.append(i)\n        if dq[0] < i - k:           # evict index that left the window\n            dq.popleft()\n        if i >= k - 1:\n            out.append(nums[dq[0]])\n    return out\n```",
        answer='The eviction condition `dq[0] < i - k` is off by one; it should be `dq[0] <= i - k` (equivalently `dq[0] < i - k + 1`). The window currently ending at index i spans indices `i-k+1 .. i`, so the smallest valid index is `i-k+1`; an index equal to `i-k` is already OUT of the window but `dq[0] < i-k` fails to evict it, leaving a stale (now-out-of-window) maximum at the front for one window too long. Failing input: nums=[5,1,1,1,1,1], k=3. Buggy output is [5,5,1,1] but the correct answer is [5,1,1,1]; the 5 at index 0 is reported for the window starting at index 1 even though it has slid out. Fix: `dq[0] <= i - k`.',
        signatures=[['dq[0] <= i - k'], ['<', 'should', '<=', 'i - k'], ['off-by-one', 'evict', 'window'], ['i - k + 1', 'boundary']],
    ),
    CogTask(
        id='subtle_bug_hunt__pagination-total-pages', category='subtle_bug_hunt', difficulty='hard',
        prompt='`total_pages` should return how many pages are needed to display `total_items` at `per_page` items per page (per_page > 0). Empty -> 0 pages. There is ONE bug. Identify it, state the two distinct wrong outputs it produces, and give the correct formula.\n\n```python\ndef total_pages(total_items, per_page):\n    return total_items // per_page + 1\n```',
        answer='It computes `floor(total_items/per_page) + 1`, which is wrong whenever `total_items` is an exact multiple of `per_page` (it adds a spurious empty page) and wrong for the empty case. Specifically: total_items=0 returns 1 (should be 0), and total_items=10, per_page=10 returns 2 (should be 1) — any exact multiple over-counts by one. The correct ceiling-division formula is `(total_items + per_page - 1) // per_page` (equivalently `-(-total_items // per_page)`), which gives 0 for 0 items and 1 for a single full page.',
        signatures=[['(total_items + per_page - 1) // per_page'], ['ceil', 'division', 'multiple', 'off by one'], ['-(-total_items // per_page)'], ['exact multiple', 'extra page', '0 returns 1']],
    ),
    CogTask(
        id='subtle_bug_hunt__dedup-seen-unhashable-order', category='subtle_bug_hunt', difficulty='very-hard',
        prompt="`dedup_keep_order` should return the elements of `items` with duplicates removed, preserving first-occurrence order, where two elements are 'duplicate' iff `key(x)` is equal. There is ONE bug that makes it drop a NON-duplicate element (or keep a duplicate) for certain inputs. Identify the precise defect and give a failing input with key().\n\n```python\ndef dedup_keep_order(items, key=lambda x: x):\n    seen = []\n    out = []\n    for x in items:\n        k = key(x)\n        if k not in seen:\n            seen.append(k)\n        out.append(x)\n    return out\n```",
        answer="The `out.append(x)` is unconditional — it sits outside the `if k not in seen` block, so every element is appended regardless of whether its key was already seen. The `seen` list is maintained correctly but never used to gate the output, so NO deduplication happens at all: the function returns the input unchanged. The fix is to move `out.append(x)` inside the `if k not in seen:` branch (right after `seen.append(k)`). Failing input: any with a duplicate key, e.g. items=[{'id':1},{'id':1},{'id':2}], key=lambda d: d['id'] — returns all three rows instead of two.",
        signatures=[['out.append', 'outside', 'if'], ['append', 'unconditional', 'no dedup'], ['out.append', 'inside', 'if k not in seen'], ['never used', 'seen', 'gate', 'output']],
    ),
    CogTask(
        id='algorithm_reasoning__dynamic-array-shrink-thrash', category='algorithm_reasoning', difficulty='hard',
        prompt="A dynamic array supports push and pop. Its policy: when push is attempted on a full array of capacity C, it reallocates to capacity 2C (cost C); when pop leaves the array exactly half full (size = C/2), it reallocates to capacity C/2 (cost C/2). All other push/pop cost O(1). Claim: 'these doubling/halving rules give O(1) amortized cost per operation.' This claim is FALSE for some operation sequences. Describe the specific adversarial sequence that forces Theta(n) amortized cost per operation, and state the resulting total cost for m operations starting from a full array of size n. Give the worst-case total cost in Big-Theta of m and n, and name the one-line fix to the policy.",
        answer='Adversarial sequence: alternate push, pop, push, pop, ... at the boundary where size = capacity. A push triggers grow to 2C; the immediately following pop drops size to C (= half of 2C) and triggers shrink back to C; the next push grows again, etc. Each of the m operations then costs Theta(n), so the total is Theta(m·n) (i.e., Theta(n) per op, not O(1)). Fix: shrink only when the array is one-QUARTER full (size = C/4), reallocating to C/2 — this separates the grow and shrink thresholds so no single boundary triggers reallocation on every alternating op.',
        signatures=[['alternate', 'push', 'pop', 'quarter'], ['thrash', 'half full', 'theta(m', 'quarter'], ['m*n', 'alternating', 'shrink at 1/4'], ['theta(mn)', 'boundary', 'one-quarter']],
    ),
    CogTask(
        id='algorithm_reasoning__coin-greedy-fail', category='algorithm_reasoning', difficulty='hard',
        prompt='A cashier algorithm makes change with the fewest coins by repeatedly taking the largest coin that does not exceed the remaining amount (the greedy method). For the coin system {1, 7, 10} (unlimited supply of each), what is the SMALLEST positive amount for which the greedy method uses strictly more coins than the true optimum, and what are the two coin counts (greedy vs optimal) at that amount? Give the amount and both counts.',
        answer='The smallest amount is 14: greedy gives 10 + 1 + 1 + 1 + 1 = 5 coins, while the optimum is 7 + 7 = 2 coins. (Answer: amount = 14, greedy = 5 coins, optimal = 2 coins.)',
        signatures=[['14', 'greedy', '5', 'optimal', '2'], ['14', 'five coins', 'two coins'], ['amount 14', '7+7', '10+1+1+1+1']],
    ),
    CogTask(
        id='algorithm_reasoning__median-of-medians-group-size', category='algorithm_reasoning', difficulty='very-hard',
        prompt='Deterministic selection (the BFPRT / median-of-medians algorithm) splits the n input elements into groups, sorts each group to find its median, recursively finds the median of those medians as the pivot, partitions, and recurses on one side. With groups of size 5 the algorithm runs in worst-case linear time. A student proposes using groups of size 3 to save sorting work. Explain precisely why groups of 3 destroy the linear-time guarantee: derive the recurrence for group size 3 and state its asymptotic solution, contrasting it with group size 5.',
        answer='With groups of 3, the median-of-medians pivot is guaranteed to exceed only about n/3 elements and be exceeded by only about n/3, so the partition can leave up to about 2n/3 elements on the recursive side. The recurrence becomes T(n) = T(n/3) + T(2n/3) + Θ(n). Because n/3 + 2n/3 = n (the subproblem sizes sum to exactly n, with constant fraction 1), this solves to T(n) = Θ(n log n), NOT linear. With groups of 5 the recurrence is T(n) = T(n/5) + T(7n/10) + Θ(n), and 1/5 + 7/10 = 9/10 < 1, which solves to Θ(n). The key insight: group size 5 is the smallest that makes the two recursive fractions sum to less than 1.',
        signatures=[['t(n/3)', 't(2n/3)', 'n log n', 'sum to 1'], ['2n/3', 'theta(n log n)', '9/10'], ['groups of 3', 'n log n', 'fractions sum to 1', '7n/10'], ['1/3 + 2/3', 'nlogn', 'linear fails']],
    ),
    CogTask(
        id='algorithm_reasoning__recurrence-loglog', category='algorithm_reasoning', difficulty='very-hard',
        prompt='A divide-and-conquer algorithm has running time given exactly by T(n) = 2·T(n/2) + n/log₂n for n ≥ 2, with T(1) = Θ(1). The Master Theorem does NOT apply here. Determine the tight asymptotic bound Θ(·) for T(n), and explain in one sentence why the standard Master Theorem fails for this recurrence.',
        answer="T(n) = Θ(n·log log n). The Master Theorem fails because the driving term f(n) = n/log n is not polynomially smaller than, polynomially larger than, or within a polylog factor of n^(log_b a) = n in the form required — specifically it is n divided by a logarithm, which falls into the 'gap' between cases 2 and 3 (the regularity/polynomial-separation conditions are not met), so the extended (Case-2 with log powers) analysis or Akra–Bazzi must be used instead.",
        signatures=[['n log log n', 'master theorem', 'gap'], ['theta(n log log n)', 'does not apply'], ['n loglog n', 'between case 2 and 3'], ['nloglogn', 'akra']],
    ),
    CogTask(
        id='algorithm_reasoning__union-find-rank-only-height', category='algorithm_reasoning', difficulty='hard',
        prompt="A disjoint-set (union-find) structure uses union by rank but deliberately OMITS path compression. Starting from n singleton elements, an adversary performs a sequence of unions to make some find() operation as slow as possible. (a) What is the maximum possible height of any tree the adversary can build, as a function of n? (b) Give the exact maximum height when n = 64. (c) Why does adding path compression alone (without union by rank) NOT match this bound's role, i.e., what is the worst-case single-operation time for path-compression-only on n elements?",
        answer='(a) With union by rank alone, a tree of rank r contains at least 2^r nodes, so rank (= height here) ≤ ⌊log₂ n⌋. Maximum tree height is ⌊log₂ n⌋. (b) For n = 64, max height = log₂ 64 = 6. (c) With path compression alone (no rank/size balancing), a single find can still be Θ(n) in the worst case (the adversary builds a single long chain via unions that always attach the larger tree under the smaller root), though it is amortized efficient; so worst-case single-operation time is Θ(n).',
        signatures=[['log2 n', '6', 'theta(n)'], ['floor log n', 'height 6', 'linear worst case'], ['⌊log₂ n⌋', '6', 'theta(n) single find'], ['log n', '64 -> 6', 'path compression alone', 'n']],
    ),
    CogTask(
        id='algorithm_reasoning__binary-search-rotated-duplicates', category='algorithm_reasoning', difficulty='hard',
        prompt="You have a sorted array that was rotated at an unknown pivot, and it MAY contain duplicate values. You want to decide whether a target key is present. A candidate claims: 'Binary search still works in O(log n) worst case — at each step compare the midpoint to the endpoints to decide which half is sorted, then recurse into the correct half.' State the precise worst-case time complexity of ANY comparison-based search on a rotated sorted array WITH duplicates, give the concrete adversarial input family that forces this bound, and identify the exact step in the candidate's logic that breaks.",
        answer="The worst-case time is Θ(n) (linear) — no comparison-based algorithm can beat it when duplicates are allowed. Adversarial family: an array of all equal values except one differing element, e.g. [2,2,2,...,2, X, 2,...,2] (or searching for a value in an array like [1,1,1,1,1] vs [1,1,0,1,1]); when arr[lo] == arr[mid] == arr[hi], the algorithm cannot determine which half is the sorted/rotated one and must examine both, degenerating to scanning all n elements. The breaking step: 'decide which half is sorted by comparing midpoint to the endpoints' fails when arr[mid] equals both endpoints, because that comparison gives no information about where the pivot lies, so the O(log n) halving argument collapses.",
        signatures=[['theta(n)', 'duplicates', 'arr[lo]==arr[mid]==arr[hi]'], ['o(n)', 'all equal', "can't tell which half"], ['linear', 'duplicate', 'midpoint equals endpoints'], ['n worst case', '[2,2,...,x,...]', 'ambiguous half']],
    ),
    CogTask(
        id='algorithm_reasoning__factorial-trailing-zeros', category='algorithm_reasoning', difficulty='very-hard',
        prompt='Define z(n) as the number of trailing zeros in n! (in base 10). It is known that z(n) = Σ_{i≥1} ⌊n/5^i⌋. (a) Find the SMALLEST n with z(n) ≥ 100, and state z at that n. (b) The function z is non-decreasing but its image SKIPS certain values: explain exactly which target counts are unattainable (no n gives that many trailing zeros) and why. (c) Is 100 itself attainable? Answer the exact n for (a) and yes/no for (c).',
        answer="(a) The smallest n with z(n) ≥ 100 is n = 405, and z(405) = 100 exactly. (b) z jumps by more than 1 precisely at multiples of higher powers of 5: when n crosses a multiple of 25 (which adds 2), 125 (adds 3), 625 (adds 4), etc., z increases by the number of factors of 5 in n at once, so the values strictly between the old and new z are skipped — i.e., any target ≡ 'just above a multiple-of-5^k boundary' that would require z to land in the skipped gap is unattainable. Concretely, counts that are skipped are exactly those values v for which no n satisfies z(n)=v, which happens at every multiple of 25/125/... boundary. (c) YES — 100 is attainable; n = 405 achieves z = 100 exactly.",
        signatures=[['405', '100', 'yes'], ['n = 405', 'z(405) = 100', 'attainable'], ['405', 'z = 100', 'yes'], ['smallest', '405', '100 is attainable']],
    ),
    CogTask(
        id='algorithm_reasoning__longest-path-dag-vs-general', category='algorithm_reasoning', difficulty='very-hard',
        prompt='A scheduling tool computes the longest path (by edge count) between two nodes. On a directed ACYCLIC graph (DAG) with V nodes and E edges this runs in O(V+E) via topological order + DP. An engineer reuses the SAME relaxation-style DP on a general directed graph that may contain cycles, and observes it sometimes returns wrong (too-small) answers and sometimes never terminates. (a) State the exact complexity class of LONGEST SIMPLE PATH in a general directed graph. (b) Explain why the DAG DP is correct for DAGs but fundamentally cannot be patched into a polynomial algorithm for general graphs (assuming P≠NP). (c) What graph property exactly is the DAG DP secretly relying on?',
        answer="(a) Longest simple path in a general (directed or undirected) graph is NP-hard (the decision version is NP-complete) — it contains Hamiltonian path as the special case asking for a simple path of length V−1. (b) The DAG DP works because a topological order lets each node be finalized after all predecessors, with no node revisited; in a graph with cycles there is no topological order, and forbidding revisits (the 'simple' constraint) makes the subproblem state depend on the set of already-visited vertices, which has exponential size — so it cannot be a polynomial DP. Allowing revisits instead makes 'longest path' unbounded/infinite around any positive cycle (hence non-termination or wrong results). Under P≠NP no polynomial algorithm exists. (c) The DAG DP secretly relies on the existence of a topological ordering (acyclicity), which guarantees optimal substructure without needing to track the visited set.",
        signatures=[['np-hard', 'hamiltonian', 'topological order'], ['np-complete', 'exponential', 'acyclicity'], ['longest simple path', 'np', 'visited set', 'topological'], ['np-hard', 'no topological order', 'hamiltonian path']],
    ),
    CogTask(
        id='algorithm_reasoning__quickselect-vs-medianmedians-randomized', category='algorithm_reasoning', difficulty='brutal',
        prompt="Three selection algorithms for the k-th smallest of n distinct numbers: (A) randomized quickselect with a uniformly random pivot, (B) quickselect with the pivot fixed as the FIRST element, (C) median-of-medians (BFPRT). For each, state the WORST-CASE time and the EXPECTED time (over the algorithm's own randomness, with the input adversarial/fixed). Then answer: an adversary who can SEE the random bits of algorithm (A) before choosing the input — what worst-case time can they force, and does this contradict (A)'s standard expected O(n) guarantee? Explain the resolution.",
        answer="(A) randomized quickselect: worst-case Θ(n²) (e.g., every pivot lands at an extreme), expected Θ(n) over its own coin flips for ANY fixed input. (B) first-element-pivot quickselect: worst-case Θ(n²) on an already-sorted (or reverse-sorted) adversarial input; expected is not meaningfully randomized (deterministic given input) so it's Θ(n²) worst case. (C) median-of-medians: worst-case Θ(n) deterministic, expected Θ(n). For the adaptive adversary who sees (A)'s random bits in advance: they CAN force Θ(n²), because knowing each pivot choice they arrange the input so every pivot is the current min or max. This does NOT contradict the expected-O(n) guarantee: that guarantee is over the random bits for a FIXED input chosen BEFORE the bits are drawn (an oblivious adversary). The randomized bound assumes the adversary cannot adapt to the coin flips; a bit-seeing adversary is strictly more powerful, so the Θ(n²) worst case is consistent — randomization only defeats inputs chosen independently of the randomness.",
        signatures=[['n^2', 'theta(n) expected', 'oblivious', 'adaptive adversary'], ['quadratic', 'expected linear', 'sees random bits', 'no contradiction'], ['theta(n^2)', 'fixed before bits', 'median of medians theta(n)'], ['n squared worst', 'expected o(n)', 'adversary adapts', 'not a contradiction']],
    ),
    CogTask(
        id='algorithm_reasoning__hash-table-resize-amortized-trap', category='algorithm_reasoning', difficulty='brutal',
        prompt='A hash table uses open addressing with linear probing and resizes (rehashes all elements into a table of double the size) whenever the load factor reaches 0.75. Insertions are claimed O(1) amortized. An adversary controls (i) the sequence of keys and (ii) knowledge of the hash function. They claim they can force a SINGLE insertion plus its triggered work to take Θ(n), AND force the amortized cost over n insertions to be Θ(n) per operation — i.e., Θ(n²) total. Exactly which of these two claims is true, which is false, and why? Be precise about what the standard amortized argument does and does NOT protect against.',
        answer="The 'single insertion takes Θ(n)' claim is TRUE — the insertion that triggers a rehash must move all ~n elements, costing Θ(n). The 'amortized Θ(n) per op / Θ(n²) total' claim is FALSE for the RESIZE cost alone: rehash work is geometric (sizes 1,2,4,...,n) summing to Θ(n), so resize is O(1) amortized regardless of key choice. HOWEVER, the standard amortized argument protects ONLY against resize frequency; it does NOT protect against PROBE-LENGTH attacks. If the adversary knows the (non-randomized) hash function, they can choose keys that all collide into one probe cluster, making each individual insert's probing Θ(n) and the total Θ(n²) — defeating the O(1) amortized claim, not via resizing but via clustering. Resolution: amortized analysis of resizing assumes uniform hashing; an adversary breaking that assumption forces Θ(n²) through probe sequences, which is why production tables need randomized/universal hashing (a secret seed) to restore expected O(1).",
        signatures=[['single insertion theta(n) true', 'resize geometric o(1)', 'clustering', 'universal hashing'], ['resize amortized o(1)', 'probe attack', 'theta(n^2)', 'randomized hash'], ['rehash sums to theta(n)', 'collision cluster', 'known hash function', 'n squared'], ['single rehash linear', 'amortized resize constant', 'adversary collisions', 'secret seed']],
    ),
    CogTask(
        id='causal_counterfactual__gear-train-direction-speed', category='causal_counterfactual', difficulty='hard',
        prompt='Five spur gears are mounted on fixed parallel axles in a single straight line, each meshing only with the next: Gear 1 (12 teeth) meshes with Gear 2 (24 teeth), which meshes with Gear 3 (8 teeth), which meshes with Gear 4 (36 teeth), which meshes with Gear 5 (16 teeth). Gear 1 is the driver and is turned clockwise at exactly 120 rpm (when viewed from the front). Determine BOTH (a) the rotational speed of Gear 5 in rpm, and (b) whether Gear 5 turns clockwise or counterclockwise as viewed from the same side. Give the speed and the direction.',
        answer='Gear 5 turns at 90 rpm, clockwise.',
        signatures=[['90', 'clockwise'], ['90 rpm', 'clockwise']],
    ),
    CogTask(
        id='causal_counterfactual__water-jug-4-4', category='causal_counterfactual', difficulty='hard',
        prompt='You have three jugs with no measurement markings: jug A holds exactly 8 liters and starts full; jug B holds exactly 5 liters and starts empty; jug C holds exactly 3 liters and starts empty. The only allowed operation is to pour from one jug into another until either the source is empty or the destination is full (you may pour between any ordered pair). You may not estimate partial amounts. Goal: reach a state where jug A contains exactly 4 liters and jug B contains exactly 4 liters (and C is empty). What is the minimum number of pour operations required to reach that goal state?',
        answer='7 pours.',
        signatures=[['7', 'pour'], ['seven', 'pour'], ['minimum', '7']],
    ),
    CogTask(
        id='causal_counterfactual__elevator-look-last-stop', category='causal_counterfactual', difficulty='hard',
        prompt='A single elevator serves floors 1 through 10. It uses the LOOK disk-scheduling discipline: it keeps moving in its current direction, stopping at every floor that has a pending request consistent with that direction, until there are no further requests in that direction, then it reverses. At time zero the elevator is idle at floor 1 about to move UP, and the following requests already exist: an up-hall-call at floor 3, an up-hall-call at floor 6, a down-hall-call at floor 9, and a down-hall-call at floor 4. Additionally, when the elevator stops at floor 6, the passenger who boards there presses the in-car button for floor 8. No new requests appear after that. Assuming a down-hall-call is serviced only while the elevator is traveling downward (and the topmost pending request is always reached before reversing), at which floor does the elevator make its FINAL stop before becoming idle?',
        answer='Floor 4.',
        signatures=[['floor 4'], ['4th floor'], ['final stop', '4']],
    ),
    CogTask(
        id='causal_counterfactual__nim-normal-winning-move', category='causal_counterfactual', difficulty='hard',
        prompt="Two players play a single game of Nim with three piles containing 5, 8, and 9 stones. Players alternate turns; on a turn a player must remove at least one stone, all from a single pile of their choice. Under NORMAL play convention, the player who takes the very last stone WINS. Assume both players play optimally. Answer two things: (1) Does the FIRST player or the SECOND player win? (2) State a winning first move as 'reduce the pile of size X to size Y'. Give both.",
        answer='The first player wins; a winning first move is to reduce the pile of size 5 to size 1.',
        signatures=[['first player', '5', '1'], ['first', 'reduce', '5', 'to 1'], ['first player wins', 'pile of 5', '1']],
    ),
    CogTask(
        id='causal_counterfactual__misere-nim-123', category='causal_counterfactual', difficulty='very-hard',
        prompt="Two players play Nim with three piles of sizes 1, 2, and 3. Players alternate; each turn remove one or more stones from a single pile. This game uses the MISERE convention: the player forced to take the LAST stone LOSES (equivalently, the player who takes the last stone loses). Both players play optimally. Does the FIRST player or the SECOND player win? Answer 'first' or 'second' and nothing more is required beyond justification.",
        answer='The second player wins.',
        signatures=[['second'], ['wins']],
    ),
    CogTask(
        id='causal_counterfactual__bridge-torch-crossing', category='causal_counterfactual', difficulty='very-hard',
        prompt="Four people must cross a rickety bridge at night. They have exactly one torch, and the bridge can hold at most two people at a time; anyone crossing must carry the torch, so the torch must be walked back for the next group. When two people cross together they move at the slower person's pace. Their individual one-way crossing times are 1, 2, 5, and 10 minutes. What is the minimum total time, in minutes, for all four people to get across?",
        answer='17 minutes.',
        signatures=[['17'], ['17 minutes'], ['seventeen']],
    ),
    CogTask(
        id='causal_counterfactual__cyclic-xor-automaton-step100', category='causal_counterfactual', difficulty='very-hard',
        prompt="Five cells are arranged in a circle (positions 0..4), each holding a bit. At every time step, simultaneously, each cell's new value becomes the XOR of its two immediate neighbors' CURRENT values (position 0's neighbors are positions 4 and 1, and so on cyclically). The configuration at step 0 is (1,0,0,0,0) for positions (0,1,2,3,4). Give the configuration at step 100, and state how many cells are equal to 1 at step 100.",
        answer='At step 100 the configuration is (0,1,0,0,1) and exactly 2 cells equal 1.',
        signatures=[['0,1,0,0,1', '2'], ['(0, 1, 0, 0, 1)', '2'], ['01001', 'two'], ['step 100', '2 cells']],
    ),
    CogTask(
        id='causal_counterfactual__pirates-100-coins', category='causal_counterfactual', difficulty='very-hard',
        prompt="Five rational, perfectly logical pirates (call them A, B, C, D, E in strict order of decreasing seniority, A most senior) must divide 100 indivisible gold coins. The most senior surviving pirate proposes an allocation; then ALL surviving pirates (including the proposer) vote. If at least half vote in favor, the proposal passes and is executed. Otherwise the proposer is thrown overboard and the next most senior pirate proposes, and so on. Each pirate's priorities are, in order: (1) stay alive, (2) maximize their own coins, (3) all else equal, prefer to see other pirates thrown overboard. Pirates cannot make binding side deals. Under the unique optimal outcome, how many coins does EACH of A, B, C, D, E receive?",
        answer='A=98, B=0, C=1, D=0, E=1.',
        signatures=[['98', '0', '1', '0', '1'], ['a=98', 'c=1', 'e=1'], ['98', 'c', '1', 'e', '1']],
    ),
    CogTask(
        id='causal_counterfactual__knights-knaves-unique', category='causal_counterfactual', difficulty='hard',
        prompt="On an island every inhabitant is either a knight (every statement they make is true) or a knave (every statement they make is false). Three inhabitants A, B, and C make the following statements. A says: 'A and C are of the same type.' B says: 'C is a knave.' C says: 'Exactly one of the three of us is a knight.' Each of A, B, C is exactly one type, and there is a unique assignment consistent with all the statements. Determine the type (knight or knave) of each of A, B, and C.",
        answer='A is a knave, B is a knave, and C is a knight.',
        signatures=[['a', 'knave', 'b', 'knave', 'c', 'knight'], ['a is a knave', 'b is a knave', 'c is a knight'], ['a=knave', 'b=knave', 'c=knight']],
    ),
    CogTask(
        id='causal_counterfactual__collatz-27-steps', category='causal_counterfactual', difficulty='very-hard',
        prompt='Define a process on a positive integer n: if n is even, replace it with n/2; if n is odd, replace it with 3n+1. Repeat until n becomes 1. Starting from n = 27, answer BOTH: (a) exactly how many replacement steps does it take to reach 1 (the final step that produces 1 counts), and (b) what is the largest value attained at any point during the trajectory?',
        answer='It takes 111 steps, and the maximum value reached is 9232.',
        signatures=[['111', '9232'], ['111 steps', '9232'], ['111', 'maximum', '9232']],
    ),
    CogTask(
        id='causal_counterfactual__logic-circuit-sensitive-input', category='causal_counterfactual', difficulty='hard',
        prompt="A combinational logic circuit has four 1-bit inputs a, b, c, d and computes its output through these gates (1=true, 0=false): g1 = a AND b; g2 = a XOR c; g3 = g1 OR d; g4 = g2 AND g3; g5 = g4 XOR b; out = g5 OR (d AND (NOT c)). The current inputs are a=0, b=0, c=0, d=1. Considering each single-input flip independently (flip exactly one of a, b, c, d and leave the others at their current values), exactly ONE input flip changes the value of 'out'. Which input is it?",
        answer='Input d.',
        signatures=[['input is d'], ['input d'], ['flipping d'], ['answer is d'], ['flip d'], ['it is d'], ["it's d"]],
    ),
    CogTask(
        id='causal_counterfactual__bayes-coin-three-flips', category='causal_counterfactual', difficulty='brutal',
        prompt='A bag contains three coins that are indistinguishable by touch. Coin A is fair (P(Heads)=1/2). Coin B is biased with P(Heads)=1/3. Coin C is two-headed (P(Heads)=1). You draw one coin uniformly at random and flip that SAME coin repeatedly. The first two flips both come up Heads. Conditioned on observing exactly those two Heads, what is the probability that the THIRD flip of the same coin also comes up Heads? Give the answer as an exact reduced fraction.',
        answer='251/294.',
        signatures=[['251/294'], ['251 / 294']],
    ),
    CogTask(
        id='proof_flaw_detection__all-horses-same-color', category='proof_flaw_detection', difficulty='hard',
        prompt='Consider this proof by induction that all horses are the same color.\n\nClaim: In any set of n horses (n >= 1), all horses have the same color.\n\nBase case (n=1): A set of one horse trivially has all horses the same color. True.\n\nInductive step: Assume the claim holds for all sets of n horses. Consider a set S of n+1 horses, labeled h_1, h_2, ..., h_{n+1}. Remove h_1 to get the set A = {h_2, ..., h_{n+1}}, which has n horses, so by the inductive hypothesis all horses in A are the same color. Now remove h_{n+1} instead to get B = {h_1, ..., h_n}, also n horses, so all horses in B are the same color. The horse h_2 belongs to both A and B. Therefore the common color of A equals the common color of B, so all n+1 horses have the same color. By induction, the claim holds for all n.\n\nEXACTLY which step fails, and why? Be precise about the value of n where the reasoning breaks.',
        answer='The inductive step fails specifically when going from n=1 to n=2 (i.e., for the set of n+1 = 2 horses). The overlap argument requires sets A and B to share a common horse (h_2), but when n+1 = 2, A = {h_2} and B = {h_1} are disjoint, so there is no shared horse to chain the equal-color relation. The induction is broken at the n=1 -> n=2 link, so it never gets off the ground.',
        signatures=[['n=2', 'overlap', 'disjoint'], ['two horses', 'no', 'common', 'horse'], ['n+1=2', 'a and b', 'disjoint'], ['1 to 2', 'overlap', 'fails']],
    ),
    CogTask(
        id='proof_flaw_detection__convergent-rearrangement', category='proof_flaw_detection', difficulty='very-hard',
        prompt='Let S = 1 - 1/2 + 1/3 - 1/4 + 1/5 - 1/6 + ... (the alternating harmonic series), which is known to converge to ln 2. Here is an argument that S = (1/2) ln 2.\n\nStep 1: S = (1 - 1/2) - 1/4 + (1/3 - 1/6) - 1/8 + (1/5 - 1/10) - 1/12 + ...\n  We have grouped/rearranged the terms so that each odd reciprocal 1/(2k-1) is followed by subtracting 1/(2(2k-1)) and then subtracting the next available 1/(4k).\n\nStep 2: Simplify each odd-pair: 1 - 1/2 = 1/2, 1/3 - 1/6 = 1/6, 1/5 - 1/10 = 1/10, etc. So\n  S = 1/2 - 1/4 + 1/6 - 1/8 + 1/10 - 1/12 + ...\n\nStep 3: Factor out 1/2: S = (1/2)(1 - 1/2 + 1/3 - 1/4 + 1/5 - ...) = (1/2) S = (1/2) ln 2.\n\nStep 4: Therefore ln 2 = (1/2) ln 2, and S = (1/2) ln 2.\n\nThis contradicts S = ln 2. Identify the exact step that is invalid and state the precise theorem or property whose absence makes it invalid.',
        answer='Step 1 is invalid. It rearranges the order of terms of the series. The alternating harmonic series is conditionally (not absolutely) convergent, so by the Riemann rearrangement theorem its sum is NOT invariant under reordering — rearranging can change the sum. The manipulation in Step 1 secretly reorders terms (it is the classic rearrangement that yields (1/2)ln 2), so the equality S = (the rearranged series) does not hold.',
        signatures=[['step 1', 'rearrange', 'conditionally convergent'], ['step 1', 'riemann rearrangement', 'conditional'], ['reorder', 'not absolutely convergent', 'step 1'], ['rearrangement theorem', 'conditional', 'step 1']],
    ),
    CogTask(
        id='proof_flaw_detection__limit-derivative-swap', category='proof_flaw_detection', difficulty='hard',
        prompt="Define f_n(x) = (sin(n x)) / sqrt(n) for x in [0, pi] and n a positive integer. Argument:\n\nStep 1: For each fixed x, |f_n(x)| <= 1/sqrt(n) -> 0, so f_n -> 0 uniformly on [0, pi]. Call the limit f(x) = 0.\n\nStep 2: Since f_n -> f uniformly and each f_n is differentiable, the limit f is differentiable and f'(x) = lim_{n->inf} f_n'(x).\n\nStep 3: f_n'(x) = sqrt(n) cos(n x). At x = 0, f_n'(0) = sqrt(n) -> infinity.\n\nStep 4: But f(x) = 0 so f'(0) = 0. Hence 0 = lim f_n'(0) = infinity, a contradiction; therefore uniform convergence does not preserve any derivative information and the standard theorem is false.\n\nWhich single step contains the logical error, and what is the correct statement of the theorem being misapplied?",
        answer="Step 2 is the error. The theorem that lets you differentiate a limit term-by-term does NOT follow from uniform convergence of f_n alone; it additionally requires that the sequence of DERIVATIVES f_n' converges uniformly (and that f_n converges at one point). Here f_n' = sqrt(n) cos(nx) does not converge at all, so the hypothesis fails and the conclusion 'f' = lim f_n'' is unjustified. The 'contradiction' in Step 4 just shows the missing hypothesis was essential; it does not refute the correct theorem.",
        signatures=[['step 2', 'derivatives', 'uniform'], ['step 2', "f_n'", 'converge uniformly'], ['step 2', 'sequence of derivatives', 'hypothesis'], ['step 2', 'differentiation', 'requires', 'derivatives converge']],
    ),
    CogTask(
        id='proof_flaw_detection__complex-sqrt-product', category='proof_flaw_detection', difficulty='hard',
        prompt='Argument that 1 = -1.\n\nStep 1: 1 = sqrt(1) = sqrt((-1)(-1)).\nStep 2: sqrt((-1)(-1)) = sqrt(-1) * sqrt(-1), using the identity sqrt(ab) = sqrt(a) sqrt(b).\nStep 3: sqrt(-1) * sqrt(-1) = i * i = i^2 = -1.\nStep 4: Therefore 1 = -1.\n\nState the exact step that is wrong, and give the precise condition under which the identity it uses is actually valid.',
        answer='Step 2 is wrong. The identity sqrt(ab) = sqrt(a)·sqrt(b) holds for real numbers only when at least one of a, b is nonnegative (more generally it can fail for the principal branch of the complex square root when both arguments are negative). Here a = b = -1 are both negative, so the identity does not apply, and the chain breaks at this step.',
        signatures=[['step 2', 'sqrt(ab)', 'both negative'], ['step 2', 'identity', 'nonnegative'], ['step 2', 'square root', 'both', 'negative'], ['step 2', 'branch', 'negative']],
    ),
    CogTask(
        id='proof_flaw_detection__probability-two-envelopes', category='proof_flaw_detection', difficulty='very-hard',
        prompt='Two-envelope argument. Two indistinguishable envelopes each contain money; one contains exactly twice the other. You pick one and see it contains amount X (you do not open the other). Reasoning to always switch:\n\nStep 1: The other envelope contains either 2X or X/2, each with probability 1/2 (by symmetry, since you had no information).\nStep 2: The expected amount in the other envelope is therefore (1/2)(2X) + (1/2)(X/2) = (5/4)X.\nStep 3: Since (5/4)X > X, you should always switch.\nStep 4: But after switching, the same argument applies again, so you should switch back — an absurdity, proving probability theory yields contradictions here.\n\nIdentify the exact step that contains the flawed assumption, and explain precisely why the assumption is unjustified.',
        answer="Step 1 (and its use in Step 2) is the flaw. It treats X as a fixed constant while assigning 'the other is 2X or X/2 with probability 1/2 each.' This conflates the two distinct underlying states. Conditioning on the observed value X, the probabilities of {smaller pair, larger pair} are generally NOT 1/2-1/2; they depend on the prior distribution of the smaller amount. The two X's in '2X' and 'X/2' refer to different total pair values, so the expectation in Step 2 illegitimately uses one symbol X for two different conditional scenarios. No proper prior makes the unconditional 'switch is always better' hold.",
        signatures=[['step 1', 'x', 'two different', 'amounts'], ['step 1', 'probability 1/2', 'prior', 'conditional'], ['step 1', 'fixed', 'x', 'conflate'], ['step 2', 'x', 'different values', 'expectation'], ['step 1', 'not', '1/2', 'conditional']],
    ),
    CogTask(
        id='proof_flaw_detection__graph-coloring-greedy', category='proof_flaw_detection', difficulty='very-hard',
        prompt="Claim: Every planar graph is 4-colorable, and here is a 'simple' inductive proof (the real Four Color Theorem is true, but this proof is wrong).\n\nProof: Induct on the number of vertices v. A planar graph has a vertex of degree at most 5 (standard, from Euler's formula). Let G be planar with v vertices; pick a vertex w of degree <= 5. Remove w to get G', planar with v-1 vertices, which by induction is 4-colorable. Color G'. Now restore w. If deg(w) <= 3, w has at most 3 differently colored neighbors, so a 4th color is free — done. If deg(w) = 4 or 5, w's neighbors might use all 4 colors. But by Kempe's chain argument we can always recolor to free a color for w; specifically, consider two neighbors colored 1 and 3; if they lie in different (1,3)-Kempe components, swap colors in one component to free color 1 for w. This handles degree 4. For degree 5, pick neighbor pairs (1,3) and (2,4) and perform two simultaneous Kempe swaps to free a color. Hence by induction every planar graph is 4-colorable. QED.\n\nThe Four Color Theorem is true, but THIS proof is the famous flawed one. State exactly which part of the argument fails and why.",
        answer="The degree-5 case fails: the claim that two SIMULTANEOUS Kempe-chain swaps (the (1,3) and (2,4) swaps) can always be performed independently is false. This is precisely the gap in Kempe's 1879 'proof' found by Heawood (1890): the two Kempe chains can interlink/cross so that performing one swap disrupts the color configuration assumed by the other, so you cannot in general free a color for a degree-5 vertex. The degree-4 single-swap argument is valid; the error is the simultaneous-double-swap step for degree 5.",
        signatures=[['degree 5', 'two', 'kempe', 'interlink'], ['degree-5', 'simultaneous', 'kempe chains', 'cross'], ['heawood', 'degree 5', 'two chains'], ['double', 'kempe swap', 'degree 5', 'not independent'], ['five', 'kempe', 'chains', 'interfere']],
    ),
    CogTask(
        id='proof_flaw_detection__matrix-rank-argument', category='proof_flaw_detection', difficulty='brutal',
        prompt="Let A and B be n x n real matrices. Argument that rank(AB) = rank(BA) always:\n\nStep 1: rank(AB) = rank(A) - dim(ker(A) ∩ im(B)) ... (call this formula F1)\nStep 2: By symmetry of the roles of A and B in the product, rank(BA) = rank(B) - dim(ker(B) ∩ im(A)).\nStep 3: For square matrices, rank(A) = rank(B) is not assumed, but we use the trace-like identity that rank(AB) and rank(BA) have the same nonzero eigenvalue structure, since AB and BA have the same characteristic polynomial.\nStep 4: Since AB and BA have the same characteristic polynomial, they have the same eigenvalues with multiplicity, hence the same number of zero eigenvalues, hence the same rank. Therefore rank(AB) = rank(BA).\n\nThe CONCLUSION 'rank(AB) = rank(BA)' happens to fail for some matrices. Identify the exact step whose reasoning is invalid, and explain the precise gap.",
        answer="Step 4 is invalid. AB and BA do have the same characteristic polynomial (true), hence the same eigenvalues with the same ALGEBRAIC multiplicities — but rank is determined by GEOMETRIC multiplicity of the eigenvalue 0 (= dim of the kernel), not algebraic multiplicity. Equal algebraic multiplicity of the zero eigenvalue does NOT imply equal geometric multiplicity, because AB and BA can have different Jordan structure for the eigenvalue 0. So 'same number of zero eigenvalues (algebraic) => same rank' is the false inference. (Indeed rank(AB) can differ from rank(BA): e.g. A=[[0,1],[0,0]], B=[[0,0],[0,1]] give AB=[[0,1],[0,0]] rank 1, BA=0 rank 0.)",
        signatures=[['step 4', 'algebraic', 'geometric multiplicity'], ['step 4', 'geometric multiplicity', 'rank'], ['step 4', 'zero eigenvalue', 'jordan', 'geometric'], ['step 4', 'algebraic multiplicity', 'does not', 'rank'], ['step 4', 'nilpotent', 'geometric', 'algebraic']],
    ),
    CogTask(
        id='proof_flaw_detection__epsilon-delta-uniform', category='proof_flaw_detection', difficulty='hard',
        prompt="Claim and 'proof': Every continuous function f: R -> R is uniformly continuous.\n\nProof: Fix epsilon > 0. Since f is continuous, for every point x there is delta_x > 0 such that |y - x| < delta_x implies |f(y) - f(x)| < epsilon. Define delta = inf over all x in R of delta_x. We claim delta > 0: indeed each delta_x is a positive real number, and the infimum of a set of positive reals is >= 0, and since the function x -> delta_x is itself continuous (small moves in x require only small changes in the local delta), its infimum over R is attained or approached but stays positive. With this single delta > 0 working for all x simultaneously, |y - x| < delta implies |f(y) - f(x)| < epsilon, which is exactly uniform continuity. QED.\n\nThe claim is FALSE (e.g. f(x) = x^2). Pinpoint the exact step in the proof that is unjustified, and explain precisely why it fails.",
        answer="The unjustified step is the claim that delta = inf_x delta_x > 0. The infimum of an infinite set of strictly positive numbers can be 0 (positivity of each element does not imply a positive infimum). The supporting sub-claim that x -> delta_x is continuous and that the infimum 'stays positive' is also false/unjustified — delta_x can be chosen and typically must shrink to 0 as x -> infinity (e.g. for x^2 the required delta_x ~ epsilon/(2|x|) -> 0). So delta = inf delta_x = 0, and there is no single positive delta, which is exactly why uniform continuity fails.",
        signatures=[['infimum', 'positive', 'can be', '0'], ['inf', 'delta_x', 'zero'], ['delta', 'inf', 'not positive'], ['infimum of positive', 'need not be positive'], ['delta_x', 'shrink', 'to 0']],
    ),
    CogTask(
        id='proof_flaw_detection__cantor-diagonal-rationals', category='proof_flaw_detection', difficulty='hard',
        prompt='Argument that the rationals in [0,1] are uncountable (which is FALSE — they are countable).\n\nStep 1: Suppose for contradiction the rationals in [0,1] could be listed as q_1, q_2, q_3, ... with decimal expansions q_i = 0.d_{i1} d_{i2} d_{i3} ...\nStep 2: Define a new number r = 0.e_1 e_2 e_3 ... by the diagonal rule: e_k = 5 if d_{kk} ≠ 5, and e_k = 6 if d_{kk} = 5.\nStep 3: Then r differs from every q_i in the i-th decimal place, so r is not in the list.\nStep 4: But r is a decimal in [0,1], and being built from digits it is a rational number in [0,1] not on the list — contradiction. Hence the rationals in [0,1] are uncountable.\n\nThe conclusion is false. Identify the exact step that is wrong and explain precisely why the SAME construction works for reals but not for rationals.',
        answer="Step 4 is wrong: the diagonal number r is constructed to be a real number in [0,1], but there is no guarantee whatsoever that r is RATIONAL. Cantor's diagonal argument produces a real differing from every listed number; for the reals that is a contradiction (the list was supposed to contain all reals), but for the rationals it is not — r being an arbitrary infinite decimal need not be rational (it generally has a non-eventually-periodic expansion), so 'r is a rational not on the list' is unjustified. The construction shows reals are uncountable precisely because there the produced object IS required to be in the set; for rationals it escapes the set, so no contradiction arises.",
        signatures=[['step 4', 'r', 'need not be rational'], ['step 4', 'diagonal', 'not rational'], ['step 4', 'real', 'not periodic', 'rational'], ['r', 'not guaranteed', 'rational', 'step 4'], ['step 4', 'no contradiction', 'r irrational']],
    ),
    CogTask(
        id='proof_flaw_detection__compactness-continuity-image', category='proof_flaw_detection', difficulty='brutal',
        prompt="Claim: If f: R -> R is a continuous bijection, then f^{-1} is continuous. 'Proof':\n\nStep 1: f is a continuous bijection from R to R. Let K ⊂ R be any closed set. We show (f^{-1})^{-1}(K) = f(K) is closed, which proves f^{-1} continuous.\nStep 2: Take any closed and bounded interval [a,b]. It is compact. Since f is continuous, f([a,b]) is compact, hence closed and bounded.\nStep 3: An arbitrary closed set K ⊂ R is a countable union of closed bounded intervals (write K as union of K ∩ [n, n+1] over integers n). Each K ∩ [n,n+1] is closed and bounded, hence compact, so its image is compact, hence closed.\nStep 4: f(K) = union over n of f(K ∩ [n,n+1]) is a countable union of closed sets, hence closed.\nStep 5: Therefore f maps closed sets to closed sets, so f^{-1} is continuous. QED.\n\nThe claim is actually TRUE for f: R -> R continuous bijections (such f are strictly monotone, forcing continuous inverse), but THIS proof is logically flawed. Identify the exact step whose reasoning is invalid, independent of whether the conclusion holds.",
        answer="Step 4 is the flawed step: a COUNTABLE union of closed sets need not be closed. Even though each f(K ∩ [n,n+1]) is closed (Step 3 is fine), the infinite union over all integers n can fail to be closed — its limit points coming from different pieces (or accumulation at infinity) need not be included. (A finite union of closed sets is closed, and a union of compact sets that is locally finite is closed, but 'countable union of closed sets' is not in general closed — e.g. ∪{1/n} type accumulation.) So the inference 'countable union of closed sets is closed' in Step 4 is invalid.",
        signatures=[['step 4', 'countable union', 'closed', 'not closed'], ['step 4', 'infinite union', 'closed sets', 'fails'], ['countable union of closed', 'need not be closed', 'step 4'], ['step 4', 'union', 'not necessarily closed']],
    ),
    CogTask(
        id='constraint_planning__row-of-five-seating', category='constraint_planning', difficulty='hard',
        prompt='Five people — Ana, Ben, Cara, Dan, Eve — sit in a single row of 5 chairs numbered 1 (leftmost) to 5 (rightmost), one person per chair. All of the following are true:\n(1) Ana sits somewhere to the LEFT of Ben (not necessarily adjacent).\n(2) Cara sits in chair 3.\n(3) Dan sits in a chair immediately adjacent to Cara.\n(4) Eve sits in neither chair 1 nor chair 5.\n(5) Ben is NOT in a chair immediately adjacent to Cara.\n(6) Dan sits somewhere to the LEFT of Eve.\nGive the unique left-to-right seating order (chair 1 to chair 5).',
        answer='Ana, Dan, Cara, Eve, Ben',
        signatures=[['ana', 'dan', 'cara', 'eve', 'ben']],
    ),
    CogTask(
        id='constraint_planning__exam-3-slot-coloring', category='constraint_planning', difficulty='very-hard',
        prompt='Six exams A, B, C, D, E, F must each be assigned to one of three time slots 1, 2, or 3. Two exams sharing students cannot be in the same slot. The conflicting pairs are: A-B, A-C, B-C, B-D, C-E, D-E, D-F, E-F. Additional room constraints: exam A must be in slot 1; exam F must NOT be in slot 1; exam B must be in slot 2; exam E must NOT be in slot 2. Give the unique slot assignment for all six exams.',
        answer='A=1, B=2, C=3, D=3, E=1, F=2',
        signatures=[['a=1', 'b=2', 'c=3', 'd=3', 'e=1', 'f=2'], ['a1', 'b2', 'c3', 'd3', 'e1', 'f2'], ['a:1', 'b:2', 'c:3', 'd:3', 'e:1', 'f:2']],
    ),
    CogTask(
        id='constraint_planning__round-robin-4-teams', category='constraint_planning', difficulty='hard',
        prompt='Four teams T1, T2, T3, T4 play a single round-robin: every pair meets exactly once, for 6 games total, played over 3 rounds. In each round exactly 2 games occur and every team plays exactly once (so each round is a pairing of all 4 teams into 2 games). Two fixtures are pinned: the game T1 vs T3 must be in round 1, and the game T1 vs T2 must be in round 3. Determine the complete schedule: list the two games in each of rounds 1, 2, and 3.',
        answer='Round 1: T1-T3 and T2-T4; Round 2: T1-T4 and T2-T3; Round 3: T1-T2 and T3-T4',
        signatures=[['round 1', 't1-t3', 't2-t4', 'round 2', 't1-t4', 't2-t3', 'round 3', 't1-t2', 't3-t4'], ['round 1', 't1 vs t3', 't2 vs t4', 'round 2', 't1 vs t4', 't2 vs t3', 'round 3', 't1 vs t2', 't3 vs t4']],
    ),
    CogTask(
        id='constraint_planning__two-machine-makespan', category='constraint_planning', difficulty='very-hard',
        prompt='Six jobs A, B, C, D, E, F must run on 2 identical machines (each job runs on exactly one machine, no preemption, no splitting). Durations: A=3, B=2, C=2, D=4, E=1, F=2 (time units). Precedence constraints (X→Y means X must fully finish before Y may start): A→C, A→D, B→D, C→E, D→F. Both machines are available from time 0. What is the minimum possible makespan (completion time of the last job)?',
        answer='9',
        signatures=[['9'], ['nine']],
    ),
    CogTask(
        id='constraint_planning__shift-coverage-min-headcount', category='constraint_planning', difficulty='hard',
        prompt='A workday is divided into 4 consecutive blocks B1, B2, B3, B4. Required staffing per block: B1 needs ≥2 workers, B2 needs ≥3, B3 needs ≥3, B4 needs ≥1. Every hired worker works exactly one shift of two CONSECUTIVE blocks. The only allowed shifts are S12 (covers B1,B2), S23 (covers B2,B3), and S34 (covers B3,B4). What is the minimum total number of workers that must be hired to satisfy all four staffing requirements?',
        answer='5',
        signatures=[['5'], ['five']],
    ),
    CogTask(
        id='constraint_planning__sum-chain-1-to-5', category='constraint_planning', difficulty='hard',
        prompt='Place the digits 1, 2, 3, 4, 5 (each used exactly once) into five positions a, b, c, d, e so that all of the following hold simultaneously: a+b=5, b+c=6, c+d=5, d+e=8. Give the unique assignment as the ordered tuple (a, b, c, d, e).',
        answer='(1, 4, 2, 3, 5)',
        signatures=[['1, 4, 2, 3, 5'], ['1,4,2,3,5'], ['a=1', 'b=4', 'c=2', 'd=3', 'e=5']],
    ),
    CogTask(
        id='constraint_planning__specialist-task-matching', category='constraint_planning', difficulty='hard',
        prompt='Four specialists s1, s2, s3, s4 must each be assigned to exactly one of four tasks T1, T2, T3, T4 (a one-to-one assignment). Each specialist is only qualified for certain tasks: s1 qualifies for {T2, T3}; s2 qualifies for {T2}; s3 qualifies for {T1, T2, T4}; s4 qualifies for {T3, T4}. Give the unique valid assignment of each specialist to a task.',
        answer='s1=T3, s2=T2, s3=T1, s4=T4',
        signatures=[['s1=t3', 's2=t2', 's3=t1', 's4=t4'], ['s1: t3', 's2: t2', 's3: t1', 's4: t4'], ['s1 t3', 's2 t2', 's3 t1', 's4 t4']],
    ),
    CogTask(
        id='constraint_planning__ev-charging-min-stops', category='constraint_planning', difficulty='hard',
        prompt='An electric vehicle drives a 100-mile route from mile 0 to mile 100. Charging stations exist at miles 0, 30, 55, 70, and 100. The car starts fully charged at mile 0 and a full charge gives exactly 40 miles of range. The car may recharge to full only at a station, and can never let its remaining range hit a negative value (it must reach a station while range ≥ 0). What is the minimum number of charging STOPS, not counting the start at mile 0, needed to reach mile 100?',
        answer='2',
        signatures=[['2'], ['two']],
    ),
    CogTask(
        id='constraint_planning__hazmat-truck-knapsack', category='constraint_planning', difficulty='very-hard',
        prompt='A delivery truck has a 100 kg weight capacity. Six packages are available, each (weight kg, value): A=(40,40), B=(30,28), C=(35,30), D=(25,22), E=(20,15), F=(15,12). Each package is loaded whole or not at all. Two safety rules apply: packages A and C may NOT both be loaded together; packages B and E may NOT both be loaded together. Maximize total value without exceeding 100 kg and without violating either safety rule. What is the maximum achievable total value?',
        answer='90',
        signatures=[['90'], ['ninety']],
    ),
    CogTask(
        id='constraint_planning__meeting-rooms-min', category='constraint_planning', difficulty='hard',
        prompt='Six meetings must be scheduled into rooms; each meeting occupies a fixed interval [start, end) in 24-hour time: M1 [9,11), M2 [9,10), M3 [10,12), M4 [11,13), M5 [10,11), M6 [12,14). Two meetings may share a room only if their intervals do not overlap (touching endpoints, e.g. one ending at 11 and another starting at 11, is allowed). What is the minimum number of rooms needed to host all six meetings?',
        answer='3',
        signatures=[['3'], ['three']],
    ),
    CogTask(
        id='constraint_planning__single-machine-deadlines-infeasible', category='constraint_planning', difficulty='very-hard',
        prompt='Five jobs must run one at a time on a single machine starting at time 0, with no idle time and no preemption. Each job has a processing time and a hard deadline (it must be fully completed by its deadline): J1 (proc 2, deadline 4), J2 (proc 3, deadline 5), J3 (proc 1, deadline 6), J4 (proc 2, deadline 7), J5 (proc 3, deadline 10). Either give an ordering in which every job meets its deadline, or state that it is impossible and explain why.',
        answer='Impossible — total processing time is 11 but the deadlines cannot all be met; even the optimal Earliest-Due-Date order finishes a job late, so no ordering satisfies all deadlines.',
        signatures=[['impossible', 'deadline'], ['impossible', 'earliest due date'], ['impossible', 'edd'], ['no', 'ordering', 'deadline'], ['cannot', 'all deadlines']],
    ),
    CogTask(
        id='constraint_planning__committee-chair-hall', category='constraint_planning', difficulty='very-hard',
        prompt='Five people P1, P2, P3, P4, P5 must each chair exactly one of five committees C1, C2, C3, C4, C5 (a one-to-one assignment). Each person is only willing to chair certain committees: P1 willing for {C1, C2}; P2 for {C1, C2}; P3 for {C1, C2}; P4 for {C3, C4, C5}; P5 for {C3, C4, C5}. Either give a valid assignment of every person to a distinct committee, or state that it is impossible and explain precisely why.',
        answer='Impossible — P1, P2, P3 are collectively willing to chair only the two committees {C1, C2}; by the pigeonhole/Hall condition three people cannot be matched one-to-one into two committees, so no valid assignment exists.',
        signatures=[['impossible', 'p1', 'p2', 'p3', 'two committees'], ['impossible', 'hall'], ['impossible', 'pigeonhole'], ['impossible', 'three people', 'two'], ['no', 'assignment', '{c1, c2}']],
    ),
    CogTask(
        id='lateral_insight__blackboard-parity-invariant', category='lateral_insight', difficulty='hard',
        prompt='The integers 1, 2, 3, ..., 2026 are written on a blackboard. You repeatedly perform this operation: erase any two numbers a and b currently on the board, and write a single new number equal to |a - b| (their absolute difference). You keep going until exactly one number remains. Across all possible choices of which pairs to erase, the final remaining number is not always the same value — but it always has a fixed parity (it is always even, or always odd). State whether the final number must be even or must be odd, and give the smallest non-negative value that the final number could possibly be.',
        answer='The final number must be ODD; the smallest possible value is 1.',
        signatures=[['odd', '1']],
    ),
    CogTask(
        id='lateral_insight__down-escalator-steps', category='lateral_insight', difficulty='hard',
        prompt="A man walks down a moving down-escalator at a steady pace and counts 50 steps from top to bottom. Another day, frustrated, he walks down the same escalator at exactly three times his earlier walking pace (his steps are three times as fast, and the escalator runs at the same constant speed as before) and this time he counts 75 steps. Assuming the escalator moves at a constant speed and the man's steps are evenly timed, how many steps are visible on the escalator when it is stopped?",
        answer='100 steps',
        signatures=[['100']],
    ),
    CogTask(
        id='lateral_insight__binary-digit-multiple', category='lateral_insight', difficulty='very-hard',
        prompt="Find the smallest positive integer that is a multiple of 2026 and whose decimal representation uses only the digits 0 and 1 (no other digits may appear). 'Smallest' means smallest in numeric value. Give the integer.",
        answer='100001101010',
        signatures=[['100001101010']],
    ),
    CogTask(
        id='lateral_insight__power-tower-last-digit', category='lateral_insight', difficulty='very-hard',
        prompt='What is the last (units) digit of the number 7^(7^7)? Here the exponent is seven raised to the seventh power, i.e. the value is 7 raised to the power (7^7 = 823543). Give the single digit.',
        answer='3',
        signatures=[['last digit', '3'], ['units digit', '3'], ['answer is 3']],
    ),
    CogTask(
        id='lateral_insight__two-jug-six-liters', category='lateral_insight', difficulty='very-hard',
        prompt="You have two unmarked jugs with capacities exactly 7 liters and 11 liters, and an unlimited water supply plus a drain. In one 'move' you may either (a) completely fill one jug from the supply, (b) completely empty one jug into the drain, or (c) pour water from one jug into the other until either the source jug is empty or the destination jug is full. Both jugs start empty. What is the minimum number of moves needed to have exactly 6 liters of water sitting in one of the jugs?",
        answer='10 moves',
        signatures=[['10']],
    ),
    CogTask(
        id='lateral_insight__consecutive-heads-flips', category='lateral_insight', difficulty='hard',
        prompt='You repeatedly flip a fair coin and stop the instant you have just seen two Heads in a row (the pattern HH). On average (in expectation), how many total coin flips will you make before you stop? Give the exact expected number.',
        answer='6 flips',
        signatures=[['6']],
    ),
    CogTask(
        id='lateral_insight__lattice-avoid-cell', category='lateral_insight', difficulty='hard',
        prompt='On a grid you start at the point (0,0) and want to reach (5,5), moving only one unit right (+1 in x) or one unit up (+1 in y) at each step. How many distinct monotone paths are there from (0,0) to (5,5) that do NOT pass through the point (2,2)?',
        answer='132 paths',
        signatures=[['132']],
    ),
    CogTask(
        id='lateral_insight__prisoners-boxes-strategy', category='lateral_insight', difficulty='brutal',
        prompt='100 prisoners are numbered 1 to 100. In a room are 100 identical closed boxes, and inside each box is a slip with one of the numbers 1 to 100, each number appearing exactly once, placed in a uniformly random arrangement unknown to the prisoners. One at a time (in isolation, no communication, boxes reset closed between visits), each prisoner enters and may open at most 50 boxes, trying to find the slip bearing his own number. If EVERY prisoner finds his own number, all are freed; if even one fails, all are executed. The prisoners may agree on a strategy beforehand. Using the optimal strategy, what is their approximate probability of survival, to the nearest whole percent?',
        answer='About 31% (≈31.18%)',
        signatures=[['31']],
    ),
    CogTask(
        id='lateral_insight__gossip-calls', category='lateral_insight', difficulty='very-hard',
        prompt='There are 2026 people, and each person initially knows exactly one unique secret that the others do not know. They communicate only by one-to-one phone calls. In each call, the two participants share with each other ALL secrets they currently know (so after the call both know the union of what either knew before). What is the minimum total number of calls required so that, in the end, every one of the 2026 people knows all 2026 secrets?',
        answer='4048 calls',
        signatures=[['4048']],
    ),
    CogTask(
        id='lateral_insight__knights-knaves-pair', category='lateral_insight', difficulty='hard',
        prompt="On an island every inhabitant is either a knight (who always tells the truth) or a knave (who always lies). You meet two inhabitants, A and B. A says: 'B is a knave.' B says: 'A and I are of the same type.' Determine the type of A and the type of B. There is exactly one consistent assignment.",
        answer='A is a knight; B is a knave.',
        signatures=[['a', 'knight', 'b', 'knave'], ['a is a knight', 'b is a knave']],
    ),
    CogTask(
        id='lateral_insight__factorial-trailing-zeros', category='lateral_insight', difficulty='hard',
        prompt='Let N = 2026! (2026 factorial, the product of all integers from 1 to 2026). When N is written out in ordinary decimal notation, how many consecutive zeros appear at the very end of the number (i.e. how many trailing zeros does 2026! have)?',
        answer='505 trailing zeros',
        signatures=[['505']],
    ),
    CogTask(
        id='lateral_insight__pirates-coin-split', category='lateral_insight', difficulty='brutal',
        prompt='Five pirates ranked strictly by seniority (A most senior, then B, C, D, E) must divide 100 identical gold coins. Procedure: the most senior surviving pirate proposes how to distribute all the coins; then ALL surviving pirates (including the proposer) vote yes or no. If at least half of the votes are yes, the proposal passes and the game ends. Otherwise the proposer is thrown overboard and the next most senior surviving pirate makes a proposal, repeating. Every pirate is perfectly rational and reasons with this priority order: (1) survive, (2) maximize personal coins, (3) all else equal, prefer to throw another pirate overboard. Coins are indivisible. Under optimal play, how many coins does pirate A keep for himself?',
        answer='A keeps 98 coins.',
        signatures=[['98']],
    ),
    CogTask(
        id='multi_hop_inference__relay-medal-handoff', category='multi_hop_inference', difficulty='hard',
        prompt='Five sprinters run a relay. Facts: (1) The runner who runs leg 2 is taller than the runner who runs leg 4. (2) Priya runs immediately before Quinn. (3) The anchor (leg 4) is the shortest of the four legged runners and is named Rosa. (4) Quinn does not run leg 1. (5) The runner on leg 1 hands off to a teammate who is taller than Rosa but shorter than the leg-2 runner. (6) Sam runs leg 3. (7) There are exactly four legs; the fifth sprinter, Tomi, is a reserve who does not run. (8) Priya is taller than Sam but shorter than Quinn. Each leg is run by exactly one person. Which named person runs leg 1?',
        answer='Priya',
        signatures=[['priya']],
    ),
    CogTask(
        id='multi_hop_inference__train-schedule-meeting', category='multi_hop_inference', difficulty='very-hard',
        prompt="Three trains run between cities. Train Alpha leaves Aria at 09:00 and arrives Bex at 11:30. Train Beta leaves Bex at 11:50 and arrives Cael at 13:10. Train Gamma leaves Cael at 13:00 and arrives Dorn at 15:45. A traveler must go Aria->Bex->Cael->Dorn using these trains, needing at least 15 minutes to change at each station. A decoy 'Train Delta' leaves Bex at 11:35 to Cael but is cancelled today. Given the constraints, can the traveler reach Dorn today using only the listed running trains, and if not, which single connection fails? Answer with the connection that fails (e.g., 'Bex->Cael' or 'Cael->Dorn'), or 'none' if the trip works.",
        answer='Cael->Dorn',
        signatures=[['cael', 'dorn'], ['cael->dorn'], ['cael to dorn']],
    ),
    CogTask(
        id='multi_hop_inference__supply-chain-bottleneck', category='multi_hop_inference', difficulty='hard',
        prompt="A factory's daily output of widgets is limited by the slowest stage. Stages and their max daily capacity: Casting 500, Machining 600, Coating 450, Assembly 700. Facts: (1) Each widget passes through every stage once, in order Casting->Machining->Coating->Assembly. (2) The Coating stage shares its oven with a separate product line that consumes 40% of Coating's capacity on Mondays only. (3) Today is Monday. (4) A new Machining robot was installed that would raise Machining to 900, but it is awaiting inspection and not yet active. (5) Assembly can borrow workers to reach 800 if needed, but only on weekends. What is today's maximum widget output?",
        answer='270',
        signatures=[['270']],
    ),
    CogTask(
        id='multi_hop_inference__genealogy-relation', category='multi_hop_inference', difficulty='very-hard',
        prompt="Facts: (1) Ada is the mother of Ben. (2) Ben is the father of Cleo. (3) Cleo is the mother of Dax. (4) Eli is Ada's only sibling. (5) Eli has one child, Faye. (6) Faye has one child, Gus. (7) A family friend, Hugo, is often called 'uncle' by the children but is not related by blood. Question: What is the most precise blood relationship of Gus to Dax? (Use a standard term like 'second cousin', 'first cousin once removed', etc.)",
        answer='Second cousin once removed',
        signatures=[['second cousin once removed'], ['2nd cousin once removed']],
    ),
    CogTask(
        id='multi_hop_inference__logic-gate-cascade', category='multi_hop_inference', difficulty='hard',
        prompt='A circuit: inputs P, Q, R. Gate G1 = (P AND Q). Gate G2 = (NOT R). Gate G3 = (G1 OR G2). Gate G4 = (G3 XOR P). The final output is G4. A disconnected probe shows a fifth gate G5 = (Q AND R) but G5 is not wired to the output and should be ignored. Given P=1, Q=0, R=1, what is the final output G4?',
        answer='1',
        signatures=[['1'], ['true'], ['high']],
    ),
    CogTask(
        id='multi_hop_inference__version-deploy-rollback', category='multi_hop_inference', difficulty='very-hard',
        prompt="A service deploy log: v1.0 deployed Mon. v1.1 deployed Tue, introduced a bug in the billing module. v1.2 deployed Wed, fixed the billing bug but introduced a bug in the email module. v1.3 deployed Thu, was an immediate rollback that reverts ONLY to the previous version's code. v1.4 deployed Fri, a hotfix applied on top of whatever was live Thursday night, fixing the email bug. Note: a parallel 'canary' channel ran v2.0-beta all week but never served production traffic. Question: After Friday's deploy, which module(s), if any, have an active bug in production? Answer 'none' or list the module(s).",
        answer='billing',
        signatures=[['billing']],
    ),
    CogTask(
        id='multi_hop_inference__tournament-points-standings', category='multi_hop_inference', difficulty='very-hard',
        prompt="A round-robin among 4 teams: W, X, Y, Z. Win=3 pts, draw=1, loss=0. Facts: (1) Every pair played exactly once (6 games). (2) W beat X and Y, drew Z. (3) X beat Y and Z. (4) Y beat Z. (5) No other results. Distractor: a friendly match where Y 'beat' W is unofficial and not counted. Compute each team's points, then name the team that finished SECOND in the standings. If there is a tie for second on points, break it by head-to-head result between the tied teams.",
        answer='X',
        signatures=[['x'], ['team x']],
    ),
]
