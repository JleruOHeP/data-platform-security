# Data Platform Security Bayesian Inference

This project runs a multi-expert Bayesian inference engine for data platform security. Neo4j is the runtime source of truth for controls, risks, incidents, business outcomes, CPTs, aliases, and expert ownership.

## What the code does

- Loads expert models and control aliases from Neo4j.
- Performs inference on each expert model to compute risk probabilities.
- Aggregates expert outputs into a final risk score.
- Reconstructs incident and business-outcome models from Neo4j relationships.
- Saves the full output to `result.json` next to `main.py`.

## How to run

1. Install dependencies:
  ```powershell
  python -m pip install -r requirements.txt
  ```

2. Run neo4j locally:
```powershell
  docker run --name my-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:latest
```

3. Configure a Neo4j instance:
  ```powershell
  $env:NEO4J_URI = "bolt://localhost:7687"
  $env:NEO4J_USER = "neo4j"
  $env:NEO4J_PASSWORD = "password123"
  $env:NEO4J_DATABASE = "neo4j"
  ```

4. Seed the hardcoded graph model and generate the interview inventory:
  ```powershell
  python seed_neo4j.py
  ```

  Use `python seed_neo4j.py --clear` only when you intentionally want to delete all data in the selected database first.

5. Run the app with a scenario file (JSON of user evidence):
  ```powershell
  python main.py scenarios/1.json
  ```

6. The result is printed to the console and saved to `result.json`.

## Neo4j graph model

- `(:Expert)-[:OWNS]->(:Control|Risk)` assigns definitions to an expert.
- `(:Control|Risk|Incident)-[:INFLUENCES {position}]->(:Risk|Incident|BusinessOutcome)` represents causality and preserves CPT parent order.
- `(:BayesianModel {layer: "incident"|"business"})-[:TARGET]->(...)` identifies layer outputs.
- Every modeled entity also has the `BayesianNode` label. CPT matrices use the `values_json` property and controls use the `aliases` property.

`seed_neo4j.py` contains every node, CPT, alias, and relationship directly; it does not read model JSON files. After the database is seeded it writes `controls.json`, containing every control and its aliases for the interview skill. Scenario input and `result.json` remain JSON because they are assessment I/O rather than model storage.

### Input evidence

The app uses a `user_evidence` dictionary in `main.py` to describe control states. Controls are matched using aliases stored on Neo4j `Control` nodes.

Example evidence:

```python
user_evidence = {
    "mfa": True,
    "CICD_PIPELINE_EXISTS": 1,
}
```

This means:
- `mfa` is normalized to `IAM_MFA_ENFORCED`
- `CICD_PIPELINE_EXISTS` remains the same

When a control value is `1`, it is treated as `True` and matched to the `True` state of the corresponding control node.
For example, `CICD_PIPELINE_EXISTS = 1` is used as hard evidence `CICD_PIPELINE_EXISTS=True` during inference.
- `P(CICD_PIPELINE_EXISTS = False) = 0`
- `P(CICD_PIPELINE_EXISTS = True) = 1`

If a control does not appear in the evidence dictionary, the model assumes it is missing (set to 0).
- `P(MISSING_CONTROL = False) = 1`
- `P(MISSING_CONTROL = True) = 0`

## Bayesian model format

The hardcoded definitions in `seed_neo4j.py` use a Bayesian network structure with:

- `cpds`: a dictionary of **conditional probability distributions** for each node.
- Each node is either a `control` or a `cpt` - target risks of this expert.

An expert may contain multiple target risk nodes. The Neo4j loader treats every owned `cpt` node as an expert target.

### `cpt` nodes

A `cpt` node defines a conditional probability table based on parent variables.

Example:

```json
"CICD_RISK": {
  "type": "cpt",
  "evidence": ["CICD_PIPELINE_EXISTS", "CICD_SECURITY_SCANNING"],
  "values": [
    [0.80, 0.50, 0.60, 0.30],
    [0.20, 0.50, 0.40, 0.70]
  ]
}
```

This table means:
- The first row contains `P(CICD_RISK = False | parents)` for each parent combination.
- The second row contains `P(CICD_RISK = True | parents)` for each parent combination.

The parent combinations are ordered lexicographically by the listed evidence variables, with `False` = 0 and `True` = 1. For the example above, the columns correspond to:

1. `CICD_PIPELINE_EXISTS=False`, `CICD_SECURITY_SCANNING=False`
2. `CICD_PIPELINE_EXISTS=False`, `CICD_SECURITY_SCANNING=True`
3. `CICD_PIPELINE_EXISTS=True`, `CICD_SECURITY_SCANNING=False`
4. `CICD_PIPELINE_EXISTS=True`, `CICD_SECURITY_SCANNING=True`

So the second row means:
- `P(CICD_RISK = True | False, False) = 0.20`
- `P(CICD_RISK = True | False, True) = 0.50`
- `P(CICD_RISK = True | True, False) = 0.40`
- `P(CICD_RISK = True | True, True) = 0.70`

## Module structure

- `main.py`
  - Application entrypoint.
  - Orchestrates evidence normalization, expert inference, incident inference, and output persistence.
  - Prints a compact per-expert summary and incident probabilities.
  - After an initial run the app will attempt to suggest a control to implement for the highest incident and will re-run the inference with that control set to `1` to show the updated incident probability.

- `evidence.py`
  - Contains evidence normalization logic.
  - Maps input aliases to canonical control names and converts values to 0/1 floats.

- `security_experts.py`
  - Builds and evaluates the expert definitions loaded from Neo4j.
  - Builds and evaluates expert models.
  - Each expert exposes a `targets` list (all `cpt` nodes) and `risk_nodes` used as priors for incidents.
  - Provides helpers to compute evidence contributions and to suggest a control (by simulating each parent control set to 1).

- `security_architect.py`
  - Loads the incident-level Bayesian model from Neo4j and injects expert-provided priors.
  - Provides a helper to identify which risk node (from the incident CPT parents) contributes most to a chosen incident.

- `neo4j_store.py`
  - Queries Neo4j and reconstructs the dictionaries consumed by the inference engine.

- `seed_neo4j.py`
  - Self-contained graph seed and `controls.json` generator.

## Output

- `result.json`
  - Contains the full inference result object and per-expert targets.
  - Overwrites any existing file each run.

Console output summary includes:
- Compact per-expert line: `risks: RISK1=0.1234, RISK2=0.0500` and `weight`.
- `Final Risk` scalar (weighted aggregate across experts).
- `Incident Level Results` listing each incident and its probability.
- `Business Outcome Results` listing each business outcome and its probability.
- A suggested control line (if found) that shows the incident probability after re-running inference with that control set to `1`.
