# Data Platform Security Bayesian Inference

This project runs a multi-expert Bayesian inference engine for data platform security. It collects evidence, evaluates expert risk models, and combines their risk probabilities into a higher-level incident probability.

## What the code does

- Loads security expert models from `experts/`.
- Normalizes raw evidence using `control_registry.json` aliases.
- Performs inference on each expert model to compute risk probabilities.
- Aggregates expert outputs into a final risk score.
- Feeds expert risk probabilities into an incident model defined in `incident_model.json`.
- Saves the full output to `result.json` next to `main.py`.

## How to run

1. Install dependencies (assumes Python is available):
   ```powershell
   python -m pip install pgmpy
   ```

2. Run the app:
   ```powershell
   python main.py
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

When a control value is `1`, it is treated as `True` and matched to the `True` state of any corresponding `prior` node.
For example, `CICD_PIPELINE_EXISTS = 1` is equivalent to setting `P(CICD_PIPELINE_EXISTS = True) = 1` during inference.

If a control does not appear in the evidence dictionary, the model uses the prior distribution defined in the expert JSON.

## Expert JSON format

Expert definitions in `experts/` use a Bayesian network structure with:

- `cpds`: a dictionary of conditional probability distributions for each node.
- Each node is either a `control` or a `cpt`.

### `control` nodes

A `control` node defines the prior probability of a control being false or true when no evidence is provided.

Example:

```json
"CICD_PIPELINE_EXISTS": {
  "type": "control",
  "values": [0.3, 0.7]
}
```

This means:
- `P(CICD_PIPELINE_EXISTS = False) = 0.3`
- `P(CICD_PIPELINE_EXISTS = True) = 0.7`

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

- `evidence.py`
  - Contains evidence normalization logic.
  - Maps input aliases to canonical control names and converts values to binary states.

- `security_experts.py`
  - Loads expert Bayesian network definitions.
  - Builds and evaluates expert models.
  - Computes evidence contributions for each expert.

- `security_architect.py`
  - Loads the incident-level Bayesian model.
  - Combines expert risk outputs to infer incident probabilities.

- `incident_model.json`
  - Defines the incident-level network and how expert risk nodes influence a security incident.

- `experts/`
  - Contains expert model JSON files used for individual expert inference.

## Output

- `result.json`
  - Contains the full inference result object.
  - Overwrites any existing file each run.
