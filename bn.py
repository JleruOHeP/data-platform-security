import json
import os
from glob import glob

from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination


# ----------------------------
# 1. Load Control Registry
# ----------------------------

def load_control_registry(path="control_registry.json"):
    with open(path, "r") as f:
        return json.load(f)


CONTROL_REGISTRY = load_control_registry()


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

    result = inference.query(
        variables=[target_node],
        evidence=evidence,
    )

    return float(result.values[1])  # P(high risk)


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

        results.append({
            "expert": name,
            "probability": p,
            "weight": weight,
        })

    # FIX 4: normalise weights so the final score stays in [0, 1].
    total_weight = sum(r["weight"] for r in results)
    if total_weight == 0:
        raise ValueError("All expert weights are zero.")

    final = sum(r["probability"] * r["weight"] for r in results) / total_weight

    return {
        "per_expert": results,
        "final_risk_probability": final,
    }


# ----------------------------
# 5. Example Run
# ----------------------------

if __name__ == "__main__":

    # This comes from LLM (already mapped using control registry)
    user_evidence = {
        "IAM_MFA_ENFORCED": 1
    }

    output = run_mixture(user_evidence)

    print("\n=== Expert Results ===")
    for r in output["per_expert"]:
        print(r)

    print("\n=== Final Risk ===")
    print(output["final_risk_probability"])