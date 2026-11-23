"""Attack-path explanations - why the graph was considered malicious (doc §68).

One paragraph per finding, naming origin, chain, violated policy, and
decision. Labels and tool names only - never raw content.
"""

from __future__ import annotations

import networkx as nx

from crosstoolguard.detection.correlation import Finding
from crosstoolguard.graph.nodes import NodeType


def _sensitivity_word(graph: nx.DiGraph, finding: Finding) -> str:
    classes = {graph.nodes[n].get("data_class") for n in finding.path}
    if "CREDENTIAL" in classes:
        return "Sensitive credential"
    if "SECRET" in classes:
        return "Sensitive"
    return "Low-trust"


def explain_finding(graph: nx.DiGraph, finding: Finding, *, verdict: str, policy: str) -> str:
    seq = finding.tool_sequence
    origin = seq[0] if seq else "unknown"
    if len(seq) > 2:
        middle = ", then ".join(f"`{t}`" for t in seq[1:-1])
        chain = f"continues through {middle}, then reaches `{seq[-1]}`"
    elif len(seq) == 2:
        chain = f"links to `{seq[1]}`"
    else:
        chain = "has no downstream tool in this finding"
    caps = {c for n in finding.path for c in
            set(graph.nodes[n].get("capabilities", []))
            | set(graph.nodes[n].get("origin_capabilities", []))}
    cap_note = ("which has external-transfer capability"
                if "EXTERNAL_TRANSFER" in caps else "which has privileged capability"
                if "PRIVILEGED" in caps else "which is not privileged")
    data_word = _sensitivity_word(graph, finding)
    chain_str = " → ".join(seq) if seq else "-"
    return (f"{data_word} evidence starts at `{origin}`. The graph {chain}, "
            f"{cap_note}. The path ({chain_str}) matches `{finding.pattern}` "
            f"({finding.severity}, risk {finding.risk:.2f}). "
            f"The `{policy}` policy gives this path a {verdict} assessment.")
