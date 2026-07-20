# Data Platform Security Bayesian Inference

This project runs a multi-expert Bayesian inference engine for data platform security. It collects evidence, evaluates expert risk models, and combines their risk probabilities into higher-level incident probabilities.

## What the code does

- Loads security expert models from `experts/`.
- Normalizes raw evidence using `control_registry.json` aliases.
- Performs inference on each expert model to compute risk probabilities.
- Aggregates expert outputs into a final risk score.
- Feeds expert risk probabilities into an incident model defined in `incident_model.json`.
- Feeds incident probabilities into a business-outcome model defined in `business_outcomes.json`.
- Saves the full output to `result.json` next to `main.py`.

## How to run

1. Install dependencies (assumes Python is available):
  ```powershell
  python -m pip install pgmpy
  ```

2. Run the app with a scenario file (JSON of user evidence):
  ```powershell
  python main.py scenarios/1.json
  ```

3. The result is printed to the console and saved to `result.json`.

### Input evidence

The app uses a `user_evidence` dictionary in `main.py` to describe control states. Controls are matched to expert model nodes through the alias map in `control_registry.json`.

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

## Expert JSON format

Expert definitions in `experts/` use a Bayesian network structure with:

- `cpds`: a dictionary of **conditional probability distributions** for each node.
- Each node is either a `control` or a `cpt` - target risks of this expert.

Important: expert files may contain multiple target risk nodes. The loader automatically treats every `cpt` node from an expert as an expert target (no single `target` field is required).

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
  - Loads expert Bayesian network definitions.
  - Builds and evaluates expert models.
  - Each expert exposes a `targets` list (all `cpt` nodes) and `risk_nodes` used as priors for incidents.
  - Provides helpers to compute evidence contributions and to suggest a control (by simulating each parent control set to 1).

- `security_architect.py`
  - Loads the incident-level Bayesian model.
  - Builds the incident BN by combining CPTs from `incident_model.json` and injecting expert-provided priors for risk nodes.
  - Provides a helper to identify which risk node (from the incident CPT parents) contributes most to a chosen incident.

- `incident_model.json`
  - Contains only the final incident CPTs (no duplicated risk nodes). The incident BN builder will add missing prior nodes and set their prior according to expert outputs when available.

- `business_outcomes.json`
  - Contains the third-level business-outcome CPTs that map incident probabilities to likely business outcomes.

- `experts/`
  - Contains expert model JSON files used for individual expert inference. Each expert may provide multiple `cpt` risk nodes.

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
