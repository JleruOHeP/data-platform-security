import json
import os
from glob import glob

from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination


def load_expert(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def _build_node_cpd(node, cfg, prior_overrides=None):
    if cfg["type"] == "control" or cfg["type"] == "risk":
        if prior_overrides and node in prior_overrides:
            p_true = max(0.0, min(1.0, float(prior_overrides[node])))
            return TabularCPD(
                variable=node,
                variable_card=2,
                values=[[1.0 - p_true], [p_true]],
            )

        # Control/risk nodes are deterministic: [[P(False)], [P(True)]]
        # When soft evidence is applied during inference, this acts as the base CPD
        # Default: control not implemented (False), risk present (True)
        default_value = [[0.0], [1.0]] if cfg["type"] == "risk" else [[1.0], [0.0]]
        return TabularCPD(
            variable=node,
            variable_card=2,
            values=default_value,  # Default: control not implemented (False) or risk present (True)
        )

    if cfg["type"] == "cpt":
        parents = cfg["evidence"]
        return TabularCPD(
            variable=node,
            variable_card=2,
            values=cfg["values"],
            evidence=parents,
            evidence_card=[2] * len(parents),
        )

    raise ValueError(f"Unknown CPD type '{cfg['type']}' for node '{node}'")


def _build_bn(cpds, prior_overrides=None):
    model = DiscreteBayesianNetwork()
    for node in cpds:
        model.add_node(node)

    for node, cfg in cpds.items():
        if cfg["type"] == "cpt":
            for parent in cfg["evidence"]:
                model.add_edge(parent, node)

    cpd_objects = [
        _build_node_cpd(node, cfg, prior_overrides)
        for node, cfg in cpds.items()
    ]

    model.add_cpds(*cpd_objects)
    model.check_model()
    return model


def infer(model, target_node, evidence):
    inference = VariableElimination(model)

    if target_node is None:
        target_node = list(model.nodes())[-1]

    # Separate hard evidence (0 or 1) from soft evidence (0-1 floats)
    hard_evidence = {}
    soft_evidence_dict = {}
    
    model_nodes = set(model.nodes())
    for node, value in evidence.items():
        if node not in model_nodes:
            continue
        
        if value == 0 or value == 1:
            hard_evidence[node] = int(value)
        else:
            # Soft evidence: P(node=1) = value, P(node=0) = 1-value
            soft_evidence_dict[node] = {0: 1.0 - value, 1: value}
    
    # If we have soft evidence, use it; otherwise use hard evidence
    if soft_evidence_dict:
        result = inference.map_query(
            variables=[target_node],
            evidence=hard_evidence if hard_evidence else None,
            soft_evidence=soft_evidence_dict if soft_evidence_dict else None,
        )
    else:
        result = inference.query(
            variables=[target_node],
            evidence=hard_evidence if hard_evidence else None,
        )

    return float(result.values[1])



def build_bn_from_expert(expert_json):
    return _build_bn(expert_json["cpds"])


def build_bn_from_config(model_json, prior_overrides=None):
    return _build_bn(model_json["cpds"], prior_overrides=prior_overrides)


def load_all_experts(folder="experts"):
    experts = {}

    for file in glob(os.path.join(folder, "*.json")):
        expert_json = load_expert(file)
        model = build_bn_from_expert(expert_json)
        name = os.path.basename(file).replace(".json", "")
        risk_nodes = [node for node, cfg in expert_json["cpds"].items() if cfg["type"] == "cpt"]
        experts[name] = {
            "model": model,
            "target": expert_json.get("target") or (expert_json.get("nodes") or [None])[-1],
            "weight": expert_json["weight"],
            "risk_nodes": risk_nodes,
        }

    return experts


EXPERTS = load_all_experts()


def analyze_evidence_contribution(model, target_node, evidence):
    relevant_evidence = {k: v for k, v in evidence.items() if k in model.nodes()}
    if not relevant_evidence:
        return []

    base_prob = infer(model, target_node, evidence)
    contributions = []

    for var in relevant_evidence.keys():
        reduced_evidence = {k: v for k, v in evidence.items() if k != var}
        prob_without = infer(model, target_node, reduced_evidence)
        contribution = abs(base_prob - prob_without)
        contributions.append((var, contribution, base_prob, prob_without))

    contributions.sort(key=lambda x: x[1], reverse=True)
    return contributions
