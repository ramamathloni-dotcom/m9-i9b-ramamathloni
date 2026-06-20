"""Slot extraction — fill the named slots a shape's Cypher template needs.

Each shape in `shapes.CANONICAL_CYPHER` carries `$param` placeholders.
Your `extract_slots(question, shape)` returns a dict whose keys are the
parameter names the template expects, e.g.:

  ShapeId.Q1 → {"ingredient": "ginger"}
  ShapeId.Q5 → {"cuisine": "Sichuan", "ingredient": "ginger"}
  ShapeId.Q9 → {"cuisine": "Italian"}
  ShapeId.Q10 → {"max_minutes": 30}
  ShapeId.Q14 → {"ingredient": "ginger", "exclude_ingredient": "garlic"}

See `data/eval_questions.jsonl` for the gold (question_text, shape, slots)
triples used by the autograder.
"""

import re
import spacy
from .shapes import ShapeId

nlp = spacy.load("en_core_web_sm")

KG_CUISINES = [
    "Italian", "Asian", "Sichuan", "Chinese", "World", "Mexican", "Indian",
    "French", "Thai", "Japanese", "Spanish", "Greek", "American", "Korean",
    "Vietnamese", "Mediterranean"
]

KG_INGREDIENTS = [
    "ginger", "garlic", "peppercorn", "basil", "tomato", "onion", "chicken",
    "beef", "pork", "fish", "salt", "pepper", "olive oil", "butter", "sugar",
    "flour", "egg", "milk", "cheese", "rice", "pasta", "potato", "carrot",
    "broccoli", "spinach", "mushroom", "soy sauce", "lemon", "lime",
    "cilantro", "parsley", "thyme", "rosemary", "cumin", "coriander",
    "paprika", "chili powder", "cinnamon", "vanilla", "chocolate"
]

KG_TECHNIQUES = [
    "wok", "bake", "fry", "roast", "grill", "boil", "steam", "sauté", "braise"
]


def extract_slots(question: str, shape: ShapeId) -> dict:
    """Extract slot values for the given shape from the question text.

    Suggested approach:
      - spaCy NER for PERSON entities (q2, q8 author slot).
      - A short hand-authored vocabulary list of the cuisines and
        ingredients in the recipe KG — string-match the question against
        it case-insensitively. The lists are small (16 cuisines, 40
        ingredients) so a literal-match approach is fine.
      - For q10: a regex like `under (\\d+)\\s*minutes` to pull the
        integer threshold.
      - For q14: split the question on "but not" / "without" to get the
        positive and negative ingredient slots.

    Return a dict whose keys EXACTLY match the `$param` names in
    shapes.CANONICAL_CYPHER[shape]. Returning a slot dict missing a
    required parameter will surface as a Neo4j ParameterMissing error
    at query time — that is fail-loud and desired.

    Values must be the canonical form the KG uses (e.g., 'Italian' not
    'italian'; 'ginger' not 'Ginger'). Match against the schema vocabulary
    rather than echoing the surface form of the question.
    """
    question_lower = question.lower()
    slots = {}

    def get_cuisine(text):
        for c in KG_CUISINES:
            if c.lower() in text.lower():
                return c
        return None

    def get_ingredient(text):
        for i in KG_INGREDIENTS:
            if i in text.lower():
                return i
        return None

    def get_technique(text):
        for t in KG_TECHNIQUES:
            if t in text.lower():
                return t
        return None

    def get_author(text):
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
        return None

    if shape in [ShapeId.Q1, ShapeId.Q13]:
        slots["ingredient"] = get_ingredient(question_lower)

    elif shape == ShapeId.Q2:
        slots["author"] = get_author(question)

    elif shape in [ShapeId.Q3, ShapeId.Q4, ShapeId.Q9, ShapeId.Q11, ShapeId.Q12]:
        slots["cuisine"] = get_cuisine(question_lower)

    elif shape in [ShapeId.Q5, ShapeId.Q6]:
        slots["cuisine"] = get_cuisine(question_lower)
        slots["ingredient"] = get_ingredient(question_lower)

    elif shape in [ShapeId.Q7, ShapeId.Q15]:
        slots["technique"] = get_technique(question_lower)

    elif shape == ShapeId.Q8:
        slots["author"] = get_author(question)
        slots["ingredient"] = get_ingredient(question_lower)

    elif shape == ShapeId.Q10:
        match = re.search(r"under (\d+)\s*minutes", question_lower)
        if match:
            slots["max_minutes"] = int(match.group(1))

    elif shape == ShapeId.Q14:
        if "but not" in question_lower:
            parts = question_lower.split("but not")
        elif "without" in question_lower:
            parts = question_lower.split("without")
        else:
            parts = [question_lower]

        if len(parts) >= 2:
            slots["ingredient"] = get_ingredient(parts[0])
            slots["exclude_ingredient"] = get_ingredient(parts[1])

    return slots