"""Extract the answer-bearing subgraph of the benchmark graph for the released Type I and II problems.

A node is "needed" if a Type I/II problem names it (descriptor, option, path step or answer object).
The subgraph keeps, for every needed node, all of its parent edges up to the root (so any ancestor,
root-category, sibling or path claim, including a negative one, is decided exactly as in the full
graph), plus one undirected shortest path for each target-candidate pair in T2.1/T2.2 (E1/E2), whose
answers are graph distances. Edges keep their original order, so the first-listed parent is unchanged.

Checks: (1) every needed node has the same ordered parent list as in the full graph; (2) every E1/E2
distance is the same; (3) the answer key of every problem is re-derived on the subgraph and on the full
graph and compared with the released key.

Usage: python scripts/revision/answer_subgraph.py <full_graph.json> <benchmark_questions.json> <out_dir>
"""
import collections
import json
import sys
from pathlib import Path

GRAPH, QUESTIONS, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
ROOT = "ROOT:SYSTEM"
ALIAS = {"other": "defected"}   # the problems show the graph's root 'defected' as the wheel's 'other' (with a footnote)
g = json.load(open(GRAPH))
qs = [q for q in json.load(open(QUESTIONS))["questions"] if q["category"] in ("A", "E")]
nodes = set(g["descriptions"])


class G:
    def __init__(self, edges):
        self.edges = edges
        self.par = collections.defaultdict(list)
        self.adj = collections.defaultdict(set)
        for e in edges:
            self.par[e["target"]].append(e["source"])
            self.adj[e["source"]].add(e["target"])
            self.adj[e["target"]].add(e["source"])

    def closure(self, n):
        """All ancestors over every parent (DAG-aware), excluding n and ROOT:SYSTEM."""
        seen, st = set(), list(self.par[n])
        while st:
            p = st.pop()
            if p not in seen:
                seen.add(p)
                st.extend(self.par[p])
        return seen - {ROOT}

    def chain(self, n):
        """First-parent chain (the generator's get_ancestors)."""
        out = []
        while self.par[n]:
            n = self.par[n][0]
            out.append(n)
        return [a for a in out if a != ROOT]

    def roots(self, n):
        return {a for a in self.closure(n) | {n} if ROOT in self.par[a]}

    def path(self, s, t):
        prev, q = {s: None}, collections.deque([s])
        while q:
            u = q.popleft()
            if u == t:
                break
            for v in sorted(self.adj[u]):
                if v not in prev:
                    prev[v] = u
                    q.append(v)
        if t not in prev:
            return None
        p = [t]
        while prev[p[-1]] is not None:
            p.append(prev[p[-1]])
        return p[::-1]

    def dist(self, s, t):
        p = self.path(s, t)
        return None if p is None else len(p) - 1


full = G(g["connections"])


def named(o, acc):
    if isinstance(o, str):
        for part in [o] + [x.strip() for x in o.split(">")]:
            if part in nodes and part != ROOT:
                acc.add(part)
    elif isinstance(o, list):
        for i in o:
            named(i, acc)
    elif isinstance(o, dict):
        for v in o.values():
            named(v, acc)


def pairs(q):
    """Target-candidate pairs whose distance sets the E1/E2 answer."""
    o = q["_objects"]
    if q["task_type"].startswith("E1"):
        return [(o["target"], c) for c in o["candidates"]]
    if q["task_type"].startswith("E2"):
        return [(o["target"], o[k]) for k in ("closer", "middle", "farther")]
    return []


# ---- build
need, prs = set(), set()
for q in qs:
    named(q["text"], need)
    named(q["options"], need)
    named(q["_objects"], need)
    prs.update(pairs(q))
keep = set()
for n in need:
    for a in full.closure(n) | {n}:
        keep.update((p, a) for p in full.par[a])
for s, t in prs:
    p = full.path(s, t)
    keep.update((a, b) if (a, b) in {(e["source"], e["target"]) for e in g["connections"]} else (b, a) for a, b in zip(p, p[1:]))
sub_edges = [e for e in g["connections"] if (e["source"], e["target"]) in keep]
sub = G(sub_edges)
sub_nodes = sorted({e["source"] for e in sub_edges} | {e["target"] for e in sub_edges})

# ---- check 1 and 2
bad_par = [n for n in need if sub.par[n] != full.par[n] or any(sub.par[a] != full.par[a] for a in full.closure(n))]
bad_dist = [(s, t) for s, t in prs if sub.dist(s, t) != full.dist(s, t)]


# ---- check 3: re-derive answer keys
def a(v):
    return " > ".join(ALIAS.get(x.strip(), x.strip()) for x in v.split(">"))


def letters(q, pred):
    return sorted(k for k, v in q["options"].items() if pred(a(v)))


def derive(gr, q):
    t, o = q["task_type"], q["_objects"]
    if t.startswith("A1"):
        r = gr.roots(o["descriptor"])
        return letters(q, lambda v: v in r)
    if t.startswith("A2"):
        return "A" if a(o["ancestor"]) in gr.closure(o["descriptor"]) else "B"
    if t.startswith("A3"):
        par = gr.par[o["descriptor"]][0]
        hit = letters(q, lambda v: par in gr.par[v])
        return hit[0] if len(hit) == 1 else hit
    if t.startswith("A4"):
        def valid(v):
            steps = [x.strip() for x in v.split(">")]
            return ROOT in gr.par[steps[0]] and all(a in gr.par[b] for a, b in zip(steps, steps[1:]))
        return letters(q, valid)
    if t.startswith("A5"):
        common = (gr.closure(o["descriptor1"]) | {o["descriptor1"]}) & (gr.closure(o["descriptor2"]) | {o["descriptor2"]})
        return letters(q, lambda v: v in common)
    if t.startswith("E1"):
        rank = " > ".join(sorted(o["candidates"], key=lambda c: gr.dist(o["target"], c)))
        hit = letters(q, lambda v: v == rank)
        return hit[0] if len(hit) == 1 else hit
    if t.startswith("E2"):
        d = {v: gr.dist(o["target"], v) for v in q["options"].values()}
        best = min(d.values())
        hit = letters(q, lambda v: d[v] == best)
        return hit[0] if len(hit) == 1 else hit
    if t.startswith("E3"):
        grp = o["similar_group"]
        hit = letters(q, lambda v: v not in grp and o["similar_parent"] not in gr.closure(v))
        return hit[0] if len(hit) == 1 else hit


absent = sorted({(q["id"], d) for q in qs for k, d in q["_objects"].items()
                 if k in ("descriptor", "descriptor1", "descriptor2", "target") and d not in nodes})
rows = []
for q in qs:
    key = q["correct_answer"]
    key = sorted(key) if isinstance(key, list) else key
    df, ds = derive(full, q), derive(sub, q)
    rows.append((q["id"], q["task_type"], key, df, ds))
same_sub = sum(r[3] == r[4] for r in rows)
match_full = collections.Counter(r[1] for r in rows if r[2] == r[3])
total = collections.Counter(r[1] for r in rows)

# ---- write
OUT.mkdir(parents=True, exist_ok=True)
rel = collections.Counter(e["path_type"] for e in sub_edges)
meta = {"source": "FlavorReasonBench-coffee benchmark graph, answer-bearing subgraph for Type I and II problems",
        "num_descriptions": len(sub_nodes), "num_connections": len(sub_edges),
        "full_graph": {"num_descriptions": len(nodes), "num_connections": len(g["connections"])},
        "connections_by_type": dict(rel.most_common()),
        "aliases_in_problems": ALIAS, "rule": __doc__.split("Checks:")[0].strip()}
json.dump({"graph_name": "SYSTEM_answer_subgraph", "root": ROOT, "descriptions": sub_nodes,
           "connections": sub_edges, "metadata": meta}, open(OUT / "answer_subgraph.json", "w"), ensure_ascii=False, indent=1)
with open(OUT / "key_check.csv", "w") as f:
    f.write("id,task_type,released_key,derived_full,derived_subgraph\n")
    for r in rows:
        f.write(",".join([r[0], r[1]] + [json.dumps(x).replace(",", ";") for x in r[2:]]) + "\n")

print(f"needed nodes {len(need)}; E1/E2 pairs {len(prs)}")
print(f"subgraph: {len(sub_nodes)} nodes, {len(sub_edges)} edges "
      f"({len(sub_nodes) / len(nodes):.1%} / {len(sub_edges) / len(g['connections']):.1%} of full)")
print("by type:", dict(rel.most_common()), "| full:", dict(collections.Counter(e['path_type'] for e in g['connections']).most_common()))
print(f"check 1 parent lists differ: {len(bad_par)}; check 2 distances differ: {len(bad_dist)}")
print(f"check 3 subgraph answer == full-graph answer: {same_sub}/{len(rows)}")
print("problems whose descriptor is not in the graph:", absent)
print("released key == full-graph re-derivation, by task:", {t: f"{match_full[t]}/{n}" for t, n in sorted(total.items())})
