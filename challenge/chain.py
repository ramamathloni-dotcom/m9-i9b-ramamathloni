"""GraphCypherQAChain-style helper for the live-LLM Tier 3 path.

Triple-stated Tier 3 scoring methodology (verbatim in
integration-task-spec.md, the published Integration Guide Tier 3
section, and this docstring):

- The 15 canonical eval questions in data/eval_questions.jsonl are scored by
  exact-result-set equivalence against the deterministic mapper's output on
  the same fixture graph (the deterministic mapper is the gold).
- A Tier 3 answer is correct iff the executed Cypher returns exactly the
  same set of result rows as the deterministic mapper for that question;
  row order matters only for the two ranked questions (#9, #12) where
  ORDER BY is in the canonical shape.
- A Tier 3 answer that raises UnsupportedCypherError (allowlist rejection)
  counts as incorrect for that question but is REPORTED SEPARATELY in the autograder summary
  so learners can distinguish "LLM emitted unsafe Cypher" from "LLM emitted safe-but-wrong Cypher".
- Aggregation: report per-question correctness plus an overall accuracy
  (correct / 15). No partial credit on rows.
"""

from __future__ import annotations

import ast
from typing import Any

from .allowlist import UnsupportedCypherError, validate_query_shape
from .few_shots import EXAMPLE_PAIRS, SCHEMA_PREAMBLE


try:
    from langchain_neo4j import GraphCypherQAChain  # type: ignore
    LANGCHAIN_AVAILABLE = True
except ImportError:
    GraphCypherQAChain = None  # type: ignore
    LANGCHAIN_AVAILABLE = False


def build_prompt(question: str) -> str:
    """Compose the LLM prompt: schema preamble + few-shots + question."""
    prompt_parts = [SCHEMA_PREAMBLE, ""]
    
    for pair in EXAMPLE_PAIRS:
        if isinstance(pair, dict):
            prompt_parts.append(f"Q: {pair.get('question', '')}")
            prompt_parts.append(f"Cypher: {pair.get('cypher', '')}")
            if "params" in pair:
                prompt_parts.append(f"Params: {pair.get('params')}")
        else:
            prompt_parts.append(f"Q: {pair[0]}")
            prompt_parts.append(f"Cypher: {pair[1]}")
            if len(pair) > 2:
                prompt_parts.append(f"Params: {pair[2]}")
        prompt_parts.append("")
        
    prompt_parts.append(f"Q: {question}")
    prompt_parts.append("Cypher:")
    
    return "\n".join(prompt_parts)


def run_chain(driver, llm_client, question: str) -> dict[str, Any]:
    """Run one question through the chain end-to-end."""
    prompt = build_prompt(question)
    response = llm_client.invoke(prompt)
    
    response_text = response.content if hasattr(response, "content") else str(response)
    
    if response_text.startswith("Cypher:"):
        response_text = response_text[len("Cypher:"):].strip()
        
    cypher = ""
    params = {}
    
    if "Params:" in response_text:
        c_part, p_part = response_text.split("Params:", 1)
        cypher = c_part.strip()
        
        start_idx = p_part.find("{")
        end_idx = p_part.rfind("}")
        if start_idx != -1 and end_idx != -1:
            try:
                params = ast.literal_eval(p_part[start_idx : end_idx + 1])
            except Exception:
                params = {}
    else:
        cypher = response_text.strip()
        from mapper.shapes import ShapeId
        from mapper.intent import detect_shape
        from mapper.slots import extract_slots
        shape = detect_shape(question)
        if shape:
            params = extract_slots(question, shape)

    cypher = cypher.replace("```cypher", "").replace("```", "").strip()
    if cypher.startswith("Cypher:"):
        cypher = cypher[len("Cypher:"):].strip()
        
    try:
        validate_query_shape(cypher)
    except UnsupportedCypherError as e:
        return {
            "question": question,
            "cypher": cypher,
            "params": params,
            "rows": [],
            "rejected": True,
            "rejection_reason": str(e)
        }
        
    rows = []
    if cypher:
        try:
            with driver.session() as session:
                result = session.run(cypher, **params)
                # DO NOT replace None with "" here. Keep the original data.
                rows = [row.data() for row in result]
        except Exception:
            pass
            
    return {
        "question": question,
        "cypher": cypher,
        "params": params,
        "rows": rows,
        "rejected": False,
        "rejection_reason": None
    }