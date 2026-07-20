from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination


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
    all_nodes = set(cpds)

    for node, cfg in cpds.items():
        if cfg["type"] == "cpt":
            for parent in cfg["evidence"]:
                all_nodes.add(parent)

    for node in all_nodes:
        model.add_node(node)

    for node, cfg in cpds.items():
        if cfg["type"] == "cpt":
            for parent in cfg["evidence"]:
                model.add_edge(parent, node)

    cpd_objects = [
        _build_node_cpd(node, cfg, prior_overrides)
        for node, cfg in cpds.items()
    ]

    missing_priors = all_nodes - set(cpds)
    for node in missing_priors:
        prior_value = 1.0
        if prior_overrides and node in prior_overrides:
            prior_value = max(0.0, min(1.0, float(prior_overrides[node])))
        cpd_objects.append(
            TabularCPD(
                variable=node,
                variable_card=2,
                values=[[1.0 - prior_value], [prior_value]],
            )
        )

    model.add_cpds(*cpd_objects)
    model.check_model()
    return model


def infer(model, target_node, evidence):
    inference = VariableElimination(model)

    if target_node is None:
        target_node = list(model.nodes())[-1]

    hard_evidence = {}
    
    model_nodes = set(model.nodes())
    for node, value in evidence.items():
        if node not in model_nodes:
            continue
        
        hard_evidence[node] = int(value)
    
    
    result = inference.query(
        variables=[target_node],
        evidence=hard_evidence if hard_evidence else None,
    )

    return float(result.values[1])



def build_bn_from_expert(expert_json):
    return _build_bn(expert_json["cpds"])


def build_bn_from_config(model_json, prior_overrides=None):
    return _build_bn(model_json["cpds"], prior_overrides=prior_overrides)


def load_all_experts(store=None):
    from neo4j_store import get_store

    definitions = (store or get_store()).load_experts()
    experts = {}
    for name, definition in definitions.items():
        model = build_bn_from_expert(definition)
        experts[name] = {
            "model": model,
            "targets": definition["targets"],
            "weight": definition["weight"],
            "risk_nodes": definition["risk_nodes"],
        }
    return experts


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


def find_expert_by_risk_node(risk_node, experts):
    for name, cfg in experts.items():
        if risk_node in cfg.get("targets", []) or risk_node in cfg.get("risk_nodes", []):
            return name, cfg
    return None, None


def find_top_control_for_risk(model, risk_node, evidence):
    # Find direct parents (controls) of the risk node in the expert model
    try:
        parents = list(model.get_parents(risk_node))
    except Exception:
        # Fallback: no parents available
        parents = []

    if not parents:
        return None

    base_prob = infer(model, risk_node, evidence)
    best = None
    best_delta = 0.0

    for parent in parents:
        # simulate implementing the control (set to 1)
        modified_evidence = dict(evidence)
        modified_evidence[parent] = 1
        prob_with = infer(model, risk_node, modified_evidence)
        delta = base_prob - prob_with
        if delta > best_delta:
            best_delta = delta
            best = (parent, delta, base_prob, prob_with)

    return best
