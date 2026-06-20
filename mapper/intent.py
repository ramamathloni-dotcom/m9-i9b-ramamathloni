"""Intent classifier — map NL question to a canonical ShapeId.

This file is your responsibility. Read the 15 supported shapes in
`shapes.ShapeId` and `shapes.CANONICAL_CYPHER`, then implement
`detect_shape` so that each of the 15 canonical eval questions in
`data/eval_questions.jsonl` is classified to the gold shape, and
adversarial / off-template questions return None.

The deterministic mapper is the production-discipline arm of M9B; a
classifier that returns the wrong shape on a supported question is a
real bug, and a classifier that returns a confident answer on an
off-template question is the silent-failure mode the Reading warns
against. Prefer None over a false positive.
"""

import re
from .shapes import ShapeId


def detect_shape(question: str) -> ShapeId | None:
    """Classify the question into one of the 15 ShapeId values, or None.

    Suggested approach: a small set of keyword / regex rules over the
    question text that match the shape vocabulary used by the recipe
    KG. Look for cues such as:
      - "by author <name>", "by <Name>"   → author shapes
      - "<cuisine name>"                  → cuisine shapes
      - "use <ingredient>", "with <ingredient>" → ingredient shapes
      - "but not <ingredient>"            → q14 (negation)
      - "ranked by popularity" / "most popular" → q9
      - "under <N> minutes"               → q10
      - "ingredients used in"             → q11 (inverse)
      - "authors of"                      → q12
      - "or any subtype" / "or any kind"  → q13
      - "optionally tagged"               → q15
      - "require <technique>"             → q7

    For cuisines and ingredients, you can use the schema label vocabulary
    (Cuisine.name values, Ingredient.name values) to disambiguate which
    slot type the question is naming. A spaCy NER pass on PERSON entities
    helps for q2 / q8.

    Returns None when no rule fires — the orchestrator raises
    UnsupportedQueryError in that case, which is the correct behaviour
    for an out-of-scope question.
    """
    question_lower = question.lower()

    if "but not" in question_lower or "without" in question_lower:
        return ShapeId.Q14
    if "or any subtype" in question_lower or "or any kind" in question_lower:
        return ShapeId.Q13
    if "optionally tagged" in question_lower:
        return ShapeId.Q15
    if "ingredients used in" in question_lower:
        return ShapeId.Q11
    if "authors of" in question_lower:
        return ShapeId.Q12
    if "ranked by popularity" in question_lower or "most popular" in question_lower:
        return ShapeId.Q9
    if re.search(r"under \d+\s*minutes", question_lower):
        return ShapeId.Q10
    if "require" in question_lower:
        return ShapeId.Q7

    has_author = "by author" in question_lower or re.search(r"\bby\b", question_lower)
    has_ingredient = "use " in question_lower or "with " in question_lower

    if has_author and has_ingredient:
        return ShapeId.Q8

    cuisine_match = re.search(r"find (\w+) recipes", question_lower)
    if cuisine_match:
        cuisine = cuisine_match.group(1)
        hierarchical_cuisines = {"asian", "chinese", "world"}
        is_hierarchical = cuisine in hierarchical_cuisines

        if has_ingredient:
            return ShapeId.Q6 if is_hierarchical else ShapeId.Q5
        else:
            return ShapeId.Q4 if is_hierarchical else ShapeId.Q3

    if has_author:
        return ShapeId.Q2

    if has_ingredient:
        return ShapeId.Q1

    return None