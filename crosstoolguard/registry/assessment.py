"""Deterministic pre-use review of MCP-advertised metadata.

This scanner reports review signals, not a safety certification. It never
executes a tool and does not infer server implementation behavior from text.
"""

from __future__ import annotations

import json
import re
from typing import Any

from crosstoolguard.registry.capabilities import extract_capabilities
from crosstoolguard.registry.integrity import fingerprint

_RULES = [
    ("metadata_instruction_override", "HIGH", re.compile(
        r"\b(ignore|disregard|override)\b.{0,60}\b(previous|prior|system|developer)\b"
        r".{0,40}\b(instruction|prompt|rule|policy)s?\b", re.I),
        "The advertised metadata contains instructions that attempt to replace higher-priority instructions."),
    ("metadata_secrecy_or_exfiltration", "CRITICAL", re.compile(
        r"\b(exfiltrat\w*|steal|leak|quietly copy|send|upload|email|transmit)\b"
        r".{0,100}\b(secret|credential|password|private key|\.env|database|token)\b", re.I),
        "The advertised metadata describes moving sensitive information to another destination."),
    ("metadata_concealment", "HIGH", re.compile(
        r"\b(do not tell|don't tell|hide this|conceal|silently|without the user|avoid detection)\b", re.I),
        "The advertised metadata asks for concealment or action without the user's knowledge."),
    ("metadata_policy_bypass", "HIGH", re.compile(
        r"\b(bypass|disable|evade|jailbreak)\b.{0,60}\b(safety|security|approval|policy|guardrail)s?\b", re.I),
        "The advertised metadata suggests bypassing safety, security, approval, or policy controls."),
]

_CAPABILITY_LEVEL = {
    "SHELL_EXEC": ("CRITICAL", "The tool advertises command-execution capability."),
    "CREDENTIAL_READ": ("HIGH", "The tool appears able to access credentials or secrets."),
    "EXTERNAL_TRANSFER": ("HIGH", "The tool appears able to transfer data outside the local workflow."),
    "EMAIL_SEND": ("HIGH", "The tool appears able to send email."),
    "FILE_WRITE": ("MEDIUM", "The tool appears able to modify or delete files."),
    "DB_WRITE": ("MEDIUM", "The tool appears able to modify database records."),
}
_SCORE = {"CRITICAL": 1.0, "HIGH": 0.8, "MEDIUM": 0.55, "LOW": 0.25}
_SECRET_PATTERNS = (
    re.compile(r"(?i)(\b(?:api[_ -]?key|access[_ -]?token|password|secret|private[_ -]?key)\b\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
)


def _redact(text: str) -> str:
    safe_text = text
    for pattern in _SECRET_PATTERNS:
        safe_text = pattern.sub(r"\1[REDACTED]" if pattern.groups else "[REDACTED]", safe_text)
    return safe_text


def _non_local_schema_refs(value: Any, path: str = "inputSchema") -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"$ref", "$dynamicRef", "$recursiveRef"} and (
                not isinstance(child, str) or not child.startswith("#")
            ):
                yield child_path
            yield from _non_local_schema_refs(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _non_local_schema_refs(child, f"{path}[{index}]")


def _finding(rule: str, severity: str, confidence: str, path: str,
             evidence: str, explanation: str, recommendation: str) -> dict[str, Any]:
    return {
        "id": rule,
        "severity": severity,
        "confidence": confidence,
        "evidence_path": _redact(path)[:240],
        "evidence": _redact(evidence)[:240],
        "explanation": explanation,
        "recommendation": recommendation,
        "risk_weight": _SCORE[severity],
    }


def assess_tool(definition: dict[str, Any], *, infer_capabilities: bool = True) -> dict[str, Any]:
    """Return deterministic findings for one complete server-advertised tool."""
    name = str(definition.get("name") or "<unnamed>")
    findings: list[dict[str, Any]] = []
    advertised_text = " ".join(
        str(definition.get(field) or "") for field in ("title", "description")
    )
    capabilities = sorted(extract_capabilities(name, advertised_text)) if infer_capabilities else []

    description = definition.get("description")
    if isinstance(description, str):
        for rule, severity, pattern, explanation in _RULES:
            match = pattern.search(description)
            if match and rule == "metadata_secrecy_or_exfiltration":
                prefix = description[max(0, match.start() - 28):match.start()]
                if re.search(r"\b(never|not|no|cannot|prohibit|prevent|block)\s+(?:\w+\s+){0,2}$", prefix):
                    match = None
            if match:
                findings.append(_finding(
                    rule, severity, "high", "description", match.group(0), explanation,
                    "Review the source and intended purpose; do not expose this definition to an agent until resolved.",
                ))

    for capability in capabilities:
        if capability in _CAPABILITY_LEVEL:
            severity, explanation = _CAPABILITY_LEVEL[capability]
            findings.append(_finding(
                f"capability_{capability.lower()}", severity, "medium", "name/description/schema",
                capability, explanation,
                "Grant only the permissions required for the task; require approval for sensitive or external side effects.",
            ))

    schema = definition.get("inputSchema", definition.get("input_schema", {})) or {}
    annotations = definition.get("annotations", {}) or {}
    if isinstance(schema, dict) and schema.get("additionalProperties", True) is not False and (
        schema.get("type") == "object" or "properties" in schema or "patternProperties" in schema
    ):
        evidence = "true" if schema.get("additionalProperties") is True else "omitted (defaults to true)"
        findings.append(_finding(
            "schema_accepts_unspecified_fields", "MEDIUM", "high", "inputSchema.additionalProperties",
            evidence, "The input schema accepts fields that are not explicitly declared.",
            "Prefer a closed schema or document and validate every additional field.",
        ))
    for path in _non_local_schema_refs(schema):
        findings.append(_finding(
            "schema_external_reference", "HIGH", "high", path,
            "non-local JSON Schema reference",
            "The input schema references a remote or invalid schema location that could create an unreviewed dependency.",
            "Vendor and review the schema locally; CrossToolGuard refuses non-local schema references at runtime.",
        ))
    if isinstance(annotations, dict) and annotations.get("readOnlyHint") is True and (
        {"FILE_WRITE", "DB_WRITE", "EXTERNAL_TRANSFER", "EMAIL_SEND", "SHELL_EXEC"} & set(capabilities)
    ):
        findings.append(_finding(
            "read_only_annotation_conflicts_with_capability", "HIGH", "medium", "annotations.readOnlyHint",
            "readOnlyHint=true", "A read-only hint conflicts with capabilities inferred from the advertised definition.",
            "Treat annotations as untrusted hints; inspect implementation and enforce permissions independently.",
        ))

    findings.sort(key=lambda item: (-item["risk_weight"], item["id"], item["evidence_path"]))
    score = max((item["risk_weight"] for item in findings), default=0.0)
    return {
        "tool": name,
        "definition_hash": fingerprint(definition),
        "capabilities": capabilities,
        "risk_score": score,
        "risk_band": "CRITICAL" if score >= 1.0 else "HIGH" if score >= 0.8 else "MEDIUM" if score >= 0.55 else "LOW",
        "findings": findings,
    }


def assess_inventory(inventory: dict[str, Any]) -> dict[str, Any]:
    """Assess inventory metadata and clearly report unobserved dimensions."""
    tools = [assess_tool(tool) for tool in inventory.get("tools", [])]
    server_findings: list[dict[str, Any]] = []
    instructions = inventory.get("instructions")
    if isinstance(instructions, str):
        server_findings.extend(assess_tool(
            {"name": "server instructions", "description": instructions}, infer_capabilities=False
        )["findings"])
    max_score = max([item["risk_score"] for item in tools] +
                    [item["risk_weight"] for item in server_findings] + [0.0])
    inventory_fingerprint = {
        "transport": inventory.get("transport"),
        "server_info": inventory.get("server_info"),
        "protocol_version": inventory.get("protocol_version"),
        "instructions": inventory.get("instructions"),
        "capabilities": inventory.get("capabilities"),
        "tools": sorted(inventory.get("tools", []), key=lambda item: str(item.get("name", ""))),
    }
    if inventory.get("endpoint_url"):
        inventory_fingerprint["endpoint_url"] = inventory["endpoint_url"]
    return {
        "server_id": inventory.get("server_id"),
        "inventory_hash": fingerprint(inventory_fingerprint),
        "assessment_type": "metadata_only",
        "risk_score": max_score,
        "risk_band": "CRITICAL" if max_score >= 1.0 else "HIGH" if max_score >= 0.8 else "MEDIUM" if max_score >= 0.55 else "LOW",
        "tool_count": len(tools),
        "finding_count": len(server_findings) + sum(len(item["findings"]) for item in tools),
        "server_findings": server_findings,
        "tools": tools,
        "coverage": {
            "tool_definitions_reviewed": True,
            "server_instructions_reviewed": instructions is not None,
            "source_code_reviewed": False,
            "dependencies_reviewed": False,
            "tool_behavior_exercised": False,
            "process_and_network_side_effects_observed": False,
        },
        "limitations": [
            "Heuristic metadata review only; it does not prove server behavior safe.",
            "A malicious implementation can hide behavior behind an innocent definition.",
            "Dormant and environment-triggered payloads are not tested by inventory.",
        ],
    }
