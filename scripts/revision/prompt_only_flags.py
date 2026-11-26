"""
Classify responses in the tool-prompt-without-tools control (condition prompt_only_noaccess).

classify() returns every kind found: a response that acts as if tools were available (simulated_call,
reported_result), gives no final answer (no_final_answer), notes that tools are absent (notes_no_tools),
speculates about a tool result (hypothetical_tool), or merely mentions the tools (mentions_tools).
FLAG_KINDS are the kinds that act out a tool or lack an answer. analyze_revision.py excludes every response
with any kind, i.e. all responses that mention, simulate or report tool calls, or give no final answer, and
reports the control's results with and without them.
"""
import re

TOOLS = r"(?:validate_descriptors|get_parents?|get_children)"

# Patterns (case-insensitive), kept explicit so they can be reported.
PATTERNS = {
    # writes or announces a call
    "simulated_call": re.compile(
        r"TOOL_CALL|TOOL_RESULT|<tool_call>|\"name\"\s*:\s*\"" + TOOLS + r"\"|"
        + TOOLS + r"\s*\(|"
        r"\b(?:let me|i(?:'ll| will)|i need to|i should|first,? i)\s+(?:call|use|run|query|invoke|check|look up|validate)\b"
        r"[^.\n]{0,40}\b(?:tools?|function|" + TOOLS + r")\b",
        re.I),
    # reports a result it could not have received
    "reported_result": re.compile(
        r"\b(?:" + TOOLS + r"|the tool|tool call|lookup|the query|the database|the graph search)\b[^.\n]{0,60}"
        r"\b(?:returns?|returned|came back|shows?|showed|confirms?|confirmed|reports?|reported|yields?|gave|gives)\b"
        r"|" + TOOLS + r"\s*\([^)\n]{0,80}\)\s*(?:→|->|=>)",   # get_parent('milk') → 'dairy'
        re.I),
    # notes that tools are absent (not in FLAG_KINDS)
    "notes_no_tools": re.compile(
        r"\b(?:no|don't have|do not have|without|cannot|can't|unable to|not (?:been )?(?:provided|available|given))\b"
        r"[^.\n]{0,40}\b(?:tools?|function(?:s| calls?)?|database access|access to the (?:graph|database))\b",
        re.I),
    # any mention of the tool names / database (not in FLAG_KINDS)
    "mentions_tools": re.compile(TOOLS + r"|\btools?\b|\bdatabase\b", re.I),
}
FLAG_KINDS = ("simulated_call", "reported_result", "no_final_answer")
# Hedged statements about what a tool would return (not in FLAG_KINDS)
HEDGE = re.compile(r"\b(?:would|might|may|could|likely|if|maybe|probably|perhaps|assume|suppose|hypothetical|presumably)\b", re.I)



def assistant_texts(rec):
    visible, thinking = [], []
    for m in rec.get("conversation_history") or []:
        if m.get("role") == "assistant":
            visible.append(m.get("content") or "")
            thinking.append(m.get("thinking_content") or "")
    if not visible and rec.get("model_response_text"):
        visible.append(rec["model_response_text"])
    return "\n".join(visible), "\n".join(thinking)


def classify(rec):
    visible, thinking = assistant_texts(rec)
    kinds, where = set(), {}
    for name, pat in PATTERNS.items():
        for label, text in (("visible", visible), ("thinking", thinking)):
            for m in pat.finditer(text):
                kind = name
                if name == "reported_result":
                    # "get_parent('x') would/might/likely return ..." is speculation about the
                    # tool, not a fabricated observation
                    window = text[max(0, m.start() - 60):m.end() + 20]
                    if HEDGE.search(window):
                        kind = "hypothetical_tool"
                if kind in kinds:
                    continue
                kinds.add(kind)
                where.setdefault(kind, f"{label}: …{text[max(0, m.start() - 60):m.end() + 60]}…".replace("\n", " "))
                if kind == name:
                    break
            if name in kinds:
                break
    # F answers have model_answer None by design; only a parse failure counts
    if rec.get("status") == "parse_error":
        kinds.add("no_final_answer")
        where["no_final_answer"] = f"status={rec.get('status')}"
    return kinds, where


def is_none(answer):
    return answer == [] or answer == ["NONE"] or answer == "NONE"

