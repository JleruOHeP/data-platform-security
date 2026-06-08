import json
import os
from glob import glob

from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination


# ----------------------------
# 1. Load Control Registry
# ----------------------------

def build_alias_map(control_registry):
    alias_map = {}

    for canonical, metadata in control_registry.items():
        alias_map[canonical.lower()] = canonical
        for alias in metadata.get("aliases", []):
            alias_map[alias.strip().lower()] = canonical

    return alias_map


def normalize_evidence(raw_evidence, control_registry_path="control_registry.json"):
    control_registry: dict
    with open(control_registry_path) as f:
        control_registry = json.load(f)
    
    alias_map = build_alias_map(control_registry)
    normalized = {}

    for raw_key, raw_value in raw_evidence.items():
        key = str(raw_key).strip().lower()
        canonical_key = alias_map.get(key, raw_key)

        if isinstance(raw_value, bool):
            normalized[canonical_key] = 1 if raw_value else 0
        elif isinstance(raw_value, str):
            lowered = raw_value.strip().lower()
            if lowered in {"true", "yes", "y", "1", "on"}:
                normalized[canonical_key] = 1
            elif lowered in {"false", "no", "n", "0", "off"}:
                normalized[canonical_key] = 0
            else:
                normalized[canonical_key] = raw_value
        else:
            normalized[canonical_key] = raw_value

    return normalized

# ----------------------------
# 2. Load Expert Models
# ----------------------------

def load_expert(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def build_bn_from_expert(expert_json):
    cpds = expert_json["cpds"]

    model = DiscreteBayesianNetwork()

    # FIX 1: explicitly add all nodes first so prior-only nodes aren't silently
    # dropped (add_edge only adds nodes that appear in at least one edge).
    for node in cpds:
        model.add_node(node)

    # Add edges from CPT definitions
    for node, cfg in cpds.items():
        if cfg["type"] == "cpt":
            for parent in cfg["evidence"]:
                model.add_edge(parent, node)

    # Build CPD objects
    cpd_objects = []

    for node, cfg in cpds.items():

        if cfg["type"] == "prior":
            # FIX 2: values must be shape [[p(0)], [p(1)]] for a binary variable.
            # Normalise whatever the JSON provides into that shape.
            raw = cfg["values"]
            if isinstance(raw[0], list):
                # already nested, e.g. [[0.3], [0.7]]
                values = raw
            else:
                # flat list, e.g. [0.3, 0.7]
                values = [[v] for v in raw]

            cpd = TabularCPD(
                variable=node,
                variable_card=2,
                values=values,
            )

        elif cfg["type"] == "cpt":
            parents = cfg["evidence"]
            cpd = TabularCPD(
                variable=node,
                variable_card=2,
                values=cfg["values"],
                evidence=parents,
                evidence_card=[2] * len(parents),
            )

        else:
            raise ValueError(f"Unknown CPD type '{cfg['type']}' for node '{node}'")

        cpd_objects.append(cpd)

    model.add_cpds(*cpd_objects)
    model.check_model()

    return model


def load_all_experts(folder="experts"):
    experts = {}

    for file in glob(os.path.join(folder, "*.json")):
        expert_json = load_expert(file)
        model = build_bn_from_expert(expert_json)
        name = os.path.basename(file).replace(".json", "")
        experts[name] = {
            "model": model,
            # FIX 3: store the target node explicitly from the JSON so inference
            # doesn't rely on non-deterministic dict/set ordering.
            "target": expert_json.get("target"),
            "weight": expert_json["weight"],
        }

    return experts


EXPERTS = load_all_experts()


# ----------------------------
# 3. Inference per expert
# ----------------------------

def infer(model, target_node, evidence):
    inference = VariableElimination(model)

    # FIX 3 (cont.): use the declared target node; fall back to last node only
    # if not specified (ordering is unreliable, so warn the caller).
    if target_node is None:
        target_node = list(model.nodes())[-1]

    # Filter evidence to only include variables in this model's graph
    filtered_evidence = {k: v for k, v in evidence.items() if k in model.nodes()}

    result = inference.query(
        variables=[target_node],
        evidence=filtered_evidence,
    )

    return float(result.values[1])  # P(high risk)


def analyze_evidence_contribution(model, target_node, evidence):
    """
    For each evidence variable, compute its contribution to the output probability
    by measuring the difference when that variable is excluded.
    Returns a list of (variable, contribution) tuples sorted by impact.
    """
    # Only analyze evidence variables that are in this expert's model
    relevant_evidence = {k: v for k, v in evidence.items() if k in model.nodes()}
    
    if not relevant_evidence:
        return []
    
    base_prob = infer(model, target_node, evidence)
    contributions = []

    for var in relevant_evidence.keys():
        # Remove this variable and re-infer
        reduced_evidence = {k: v for k, v in evidence.items() if k != var}
        prob_without = infer(model, target_node, reduced_evidence)
        
        # Contribution is the absolute change
        contribution = abs(base_prob - prob_without)
        contributions.append((var, contribution, base_prob, prob_without))

    # Sort by contribution descending
    contributions.sort(key=lambda x: x[1], reverse=True)
    return contributions


# ----------------------------
# 4. Mixture Engine
# ----------------------------

def run_mixture(evidence):
    results = []

    for name, cfg in EXPERTS.items():
        model = cfg["model"]
        target = cfg["target"]
        weight = cfg["weight"]

        p = infer(model, target, evidence)
        
        # Analyze which evidence contributed most to this expert's probability
        contributions = analyze_evidence_contribution(model, target, evidence)
        top_contributor = contributions[0] if contributions else None

        results.append({
            "expert": name,
            "probability": p,
            "weight": weight,
            "top_evidence": {
                "variable": top_contributor[0],
                "contribution": top_contributor[1],
            } if top_contributor else None,
            "evidence_analysis": [
                {"variable": var, "contribution": contrib}
                for var, contrib, _, _ in contributions
            ] if contributions else [],
        })

    # FIX 4: normalise weights so the final score stays in [0, 1].
    total_weight = sum(r["weight"] for r in results)
    if total_weight == 0:
        raise ValueError("All expert weights are zero.")

    final = sum(r["probability"] * r["weight"] for r in results) / total_weight

    # Find the expert with the highest weighted contribution
    max_contributor = max(results, key=lambda r: r["probability"] * r["weight"])

    return {
        "per_expert": results,
        "final_risk_probability": final,
        "top_contributor_expert": {
            "expert": max_contributor["expert"],
            "contribution": max_contributor["probability"] * max_contributor["weight"],
        },
    }


# ----------------------------
# 5. Example Run
# ----------------------------

if __name__ == "__main__":

    # This comes from LLM (already mapped using control registry)
    user_evidence = {
        "mfa": True,
        "CICD_PIPELINE_EXISTS": 1
    }

    evidence = normalize_evidence(user_evidence)

    output = run_mixture(evidence)

    print("\n=== Expert Results ===")
    for r in output["per_expert"]:
        print(f"\nExpert: {r['expert']}")
        print(f"  Probability: {r['probability']:.4f}")
        print(f"  Weight: {r['weight']}")
        if r["top_evidence"]:
            print(f"  Top evidence contributor: {r['top_evidence']['variable']} (Δ={r['top_evidence']['contribution']:.4f})")
        if r["evidence_analysis"]:
            print(f"  All evidence impact:")
            for ea in r["evidence_analysis"]:
                print(f"    - {ea['variable']}: {ea['contribution']:.4f}")

    print("\n=== Final Risk ===")
    print(output["final_risk_probability"])

    print("\n=== Top Contributor Expert ===")
    print(output["top_contributor_expert"])