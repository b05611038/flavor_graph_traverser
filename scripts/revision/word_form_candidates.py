#!/usr/bin/env python3
"""List unresolved tool queries from the original run that are word forms of a tool-graph
node (plural/singular, -y/-ey/-ic/-ed/-ish/-ness endings). The output was reviewed by hand to
build DEFAULT_WORD_FORMS in label_resolver.py. Usage: python scripts/revision/word_form_candidates.py
"""
import json, collections, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation.tools import LabelResolver
from FlavorGraphTraverser.evaluation.tools.label_resolver import normalize_label
d = load_graph_data(str(ROOT / 'data/graphs/coffee_flavor_wheel.json')); g = CoffeeDescriptionGraph(d['descriptions'], d['connections'], root=d['root'])
r = LabelResolver.from_graph(g)
R = json.load(open(ROOT / 'results_revision/run1/original_run.json'))['results']
q = collections.Counter(); who = collections.defaultdict(set)
for x in R:
    if x['condition'] != 'tool' or 'grok-4.1' in x['model'] or 'gpt-oss-20b' in x['model']: continue
    for m in x['conversation_history']:
        calls = []
        for tc in m.get('tool_calls') or []:
            a = tc.get('function', {}).get('arguments')
            try: calls.append(json.loads(a) if isinstance(a, str) else a)
            except Exception: pass
        if m.get('role') == 'assistant' and 'TOOL_CALL' in (m.get('content') or ''):
            for line in m['content'].splitlines():
                if line.strip().startswith('TOOL_CALL'):
                    try: calls.append(json.loads(line.split(':', 1)[1])['args'])
                    except Exception: pass
        for a in calls:
            if not isinstance(a, dict): continue
            for s in a.get('descriptors') or ([a['descriptor']] if a.get('descriptor') else []):
                if isinstance(s, str) and r.resolve(s) is None:
                    k = normalize_label(s); q[k] += 1; who[k].add(x['model'])
SUF = ['s', 'es', 'y', 'ey', 'ic', 'ed', 'ish', 'sy', 'ty', 'iness', 'ness']
def last_word_forms(w):
    out = {w}
    for sfx in SUF:
        out.add(w + sfx)
        if w.endswith(sfx) and len(w) - len(sfx) >= 3: out.add(w[:-len(sfx)])
    if w.endswith('y') and len(w) > 4: out.add(w[:-1] + 'ey'); out.add(w[:-1])
    if w.endswith('ey'): out.add(w[:-2] + 'y')
    if w.endswith('e'): out.add(w[:-1] + 'y')       # smoke -> smoky
    if w.endswith('y'): out.add(w[:-1] + 'e')       # smoky -> smoke
    return out
nodes = {normalize_label(n): n for n in g.descriptions if not n.startswith('ROOT')}
cands = collections.defaultdict(list)
for s, c in q.items():
    words = s.split(' ')
    if len(words[-1]) < 3: continue
    for f in last_word_forms(words[-1]):
        t = ' '.join(words[:-1] + [f])
        if t != s and t in nodes:
            cands[s].append(nodes[t])
for s in sorted(cands, key=lambda s: -q[s]):
    print(f'{q[s]:4}  {s!r:22} -> {cands[s]}  models={len(who[s])}')
