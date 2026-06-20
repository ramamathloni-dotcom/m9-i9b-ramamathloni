### Integration 9B — Learner Notes

## 1. Intents you handled and how you classified them

I implemented a rule-based classifier using string matching and regex, strictly ordered by priority (most specific to least specific). For example, negation shapes (Q14: "but not") had to be evaluated before simple ingredient inclusions (Q1: "use") to prevent premature and incorrect matching.

Ambiguity frequently arose with conjunction queries. For instance, the question *"Find Sichuan recipes that use ginger"* contains both a cuisine ("Sichuan") and an ingredient ("ginger"). This makes it a plausible candidate for Q1 (ingredient only), Q3 (cuisine only), or Q5/Q6 (conjunctions). 
To resolve this, my logic first verifies the presence of both entity types. Then, it checks if the extracted cuisine belongs to a predefined hierarchical subset (`{"asian", "chinese", "world"}`). Since "Sichuan" is not in that root list, the classifier correctly routes it to Q5 (direct match) rather than Q6 (subclass traversal).

## 2. A question that worked end-to-end

**Question:** "Find Italian recipes"

* **`detect_shape` returned:** `ShapeId.Q3` (triggered by the exact cuisine name match).
* **`extract_slots` returned:** `{'cuisine': 'Italian'}`
* **Compiled Cypher:**
    MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine})
    RETURN r.name AS recipe
    ORDER BY r.name
    LIMIT 50
* **Bound params dict:** `{'cuisine': 'Italian'}`
* **CLI Output:**
    $ python cli.py "Find Italian recipes"
    {'recipe': 'Biscotti'}
    {'recipe': 'Bolognese'}
    {'recipe': 'Cacio e Pepe'}
    {'recipe': 'Caprese Salad'}

## 3. A failure mode you diagnosed

During the slot extraction phase, I initially mapped the author extraction for Q2 ("Find recipes by author Maria Rossi") to the dictionary key `{'name': 'Maria Rossi'}`. However, the canonical Cypher template rigorously expected the parameter key to be `$author`. This discrepancy triggered a Neo4j `ParameterMissing` error at execution time (`Neo.ClientError.Statement.ParameterMissing`). 

I diagnosed this by analyzing the pipeline's fail-loud behavior in `pytest`. The fix required aligning the extracted dictionary keys exactly with the `CANONICAL_CYPHER` placeholders (i.e., changing it to `slots["author"] = ...`). Furthermore, when an adversarial query like "Find tomato (which is a fruit)" was passed, the intent classifier correctly found no valid cues, returned `None`, and the orchestrator successfully trapped it, raising an `UnsupportedQueryError` to explicitly inform the caller of the 15 supported shapes.

## 4. A design tradeoff between the deterministic mapper and the Tier 3 chain

The **deterministic mapper** is highly preferable in environments that demand strict operational security and low latency. Because it relies on static templates, it guarantees zero Cypher injection risk and offers complete auditability (every returned row can be traced to a specific, hardcoded path). However, its schema-coverage cost is high; scaling it to accommodate new intents requires manual engineering.

Conversely, the **Tier 3 live-LLM chain** is superior when the input distribution is wide, open, and unpredictable. It excels at adapting to diverse user phrasing without requiring code updates. The tradeoff is non-deterministic execution, higher latency, and the absolute necessity of defensive engineering surfaces (like the Python-side allowlist) to prevent the LLM from executing destructive clauses like `DELETE` or `DROP`. 

Ultimately, the choice depends on the deployment context: the deterministic mapper prioritizes predictability and safety, while the LLM chain prioritizes flexibility and linguistic coverage.