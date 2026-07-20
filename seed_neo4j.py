"""Seed the complete security model into Neo4j and export its controls."""

import argparse
import json
from pathlib import Path

from neo4j_store import get_store


ROOT = Path(__file__).resolve().parent
DEFAULT_CONTROLS_PATH = ROOT / "controls.json"


def cpt(evidence, false_probabilities, true_probabilities):
    return {
        "type": "cpt",
        "evidence": evidence,
        "values": [false_probabilities, true_probabilities],
    }


CONTROL_ALIASES = {
    "IAM_MFA_ENFORCED": ["mfa", "2fa", "multi factor", "authentication enforced"],
    "IAM_SERVICE_ACCOUNTS": ["service accounts", "machine identities", "non-human accounts"],
    "CICD_PIPELINE_EXISTS": ["cicd pipeline", "ci/cd pipeline", "continuous integration", "continuous delivery"],
    "CICD_SECURITY_SCANNING": ["cicd security scanning", "ci/cd security scanning", "continuous security testing"],
    "CICD_BRANCH_PROTECTION": ["cicd branch protection", "ci/cd branch protection", "protected branches"],
    "IAM_SHARED_ACCOUNTS": ["shared accounts", "shared credentials", "shared access"],
}


EXPERTS = {
    "cicd_expert": {
        "weight": 0.5,
        "controls": [
            "CICD_PIPELINE_EXISTS", "CICD_SECURITY_SCANNING", "CICD_BRANCH_PROTECTION",
            "CHANGE_MANAGEMENT", "DEPENDENCY_SCANNING", "SBOM_AVAILABLE",
            "PIPELINE_ISOLATION", "SIGNED_ARTIFACTS",
        ],
        "risks": {
            "OPERATIONAL_ERROR_RISK": cpt(
                ["CHANGE_MANAGEMENT", "CICD_PIPELINE_EXISTS"],
                [0.05, 0.45, 0.50, 0.95], [0.95, 0.55, 0.50, 0.05],
            ),
            "DEPENDENCY_RISK": cpt(
                ["DEPENDENCY_SCANNING", "SBOM_AVAILABLE"],
                [0.05, 0.40, 0.50, 0.95], [0.95, 0.60, 0.50, 0.05],
            ),
            "CI_CD_COMPROMISE_RISK": cpt(
                ["PIPELINE_ISOLATION", "SIGNED_ARTIFACTS"],
                [0.05, 0.35, 0.45, 0.95], [0.95, 0.65, 0.55, 0.05],
            ),
        },
    },
    "data_protection_expert": {
        "weight": 0.5,
        "controls": ["DATA_ENCRYPTION", "DATA_CLASSIFICATION"],
        "risks": {
            "DATA_EXPOSURE_RISK": cpt(
                ["DATA_ENCRYPTION", "DATA_CLASSIFICATION"],
                [0.05, 0.30, 0.40, 0.90], [0.95, 0.70, 0.60, 0.10],
            ),
        },
    },
    "iam_expert": {
        "weight": 0.5,
        "controls": [
            "IAM_MFA_ENFORCED", "IAM_PRIVILEGED_ACCESS_MANAGEMENT",
            "IAM_NO_SHARED_ACCOUNTS", "IAM_EXCESSIVE_PERMISSIONS",
            "ADMIN_ACCOUNT_SEPARATION",
        ],
        "risks": {
            "CREDENTIAL_THEFT_RISK": cpt(
                ["IAM_MFA_ENFORCED", "IAM_NO_SHARED_ACCOUNTS"],
                [0.10, 0.40, 0.70, 0.95], [0.90, 0.60, 0.30, 0.05],
            ),
            "PRIVILEGE_ESCALATION_RISK": cpt(
                ["IAM_PRIVILEGED_ACCESS_MANAGEMENT", "ADMIN_ACCOUNT_SEPARATION"],
                [0.10, 0.45, 0.65, 0.95], [0.90, 0.55, 0.35, 0.05],
            ),
        },
    },
    "monitoring_expert": {
        "weight": 0.5,
        "controls": ["AUDIT_LOGGING", "SECURITY_ALERTING"],
        "risks": {
            "DETECTION_GAP_RISK": cpt(
                ["AUDIT_LOGGING", "SECURITY_ALERTING"],
                [0.05, 0.45, 0.55, 0.95], [0.95, 0.55, 0.45, 0.05],
            ),
        },
    },
    "network_expert": {
        "weight": 0.5,
        "controls": [
            "NETWORK_NO_PUBLIC_EXPOSURE", "NETWORK_SEGMENTATION",
            "NETWORK_EGRESS_CONTROLS", "NETWORK_ISOLATION",
        ],
        "risks": {
            "NETWORK_INTRUSION_RISK": cpt(
                ["NETWORK_NO_PUBLIC_EXPOSURE", "NETWORK_SEGMENTATION"],
                [0.05, 0.40, 0.75, 0.95], [0.95, 0.60, 0.25, 0.05],
            ),
        },
    },
    "platform_expert": {
        "weight": 0.5,
        "controls": ["PLATFORM_BACKUPS_AVAILABLE", "PLATFORM_RECOVERY_TESTED"],
        "risks": {
            "RECOVERY_FAILURE_RISK": cpt(
                ["PLATFORM_BACKUPS_AVAILABLE", "PLATFORM_RECOVERY_TESTED"],
                [0.05, 0.50, 0.40, 0.95], [0.95, 0.50, 0.60, 0.05],
            ),
        },
    },
    "secrets_expert": {
        "weight": 0.5,
        "controls": ["SECRETS_ROTATION", "SECRETS_STORAGE"],
        "risks": {
            "SECRETS_RISK": cpt(
                ["SECRETS_ROTATION", "SECRETS_STORAGE"],
                [0.95, 0.80, 0.90, 0.60], [0.05, 0.20, 0.10, 0.40],
            ),
        },
    },
}


INCIDENTS = {
    "UNAUTHORIZED_ACCESS": cpt(
        ["CREDENTIAL_THEFT_RISK", "NETWORK_INTRUSION_RISK", "PRIVILEGE_ESCALATION_RISK"],
        [0.95, 0.55, 0.65, 0.22, 0.60, 0.20, 0.25, 0.03],
        [0.05, 0.45, 0.35, 0.78, 0.40, 0.80, 0.75, 0.97],
    ),
    "DATA_EXFILTRATION": cpt(
        ["CREDENTIAL_THEFT_RISK", "DATA_EXPOSURE_RISK", "DETECTION_GAP_RISK"],
        [0.98, 0.90, 0.88, 0.65, 0.85, 0.50, 0.40, 0.05],
        [0.02, 0.10, 0.12, 0.35, 0.15, 0.50, 0.60, 0.95],
    ),
    "SERVICE_DISRUPTION": cpt(
        ["NETWORK_INTRUSION_RISK", "RECOVERY_FAILURE_RISK", "OPERATIONAL_ERROR_RISK"],
        [0.97, 0.88, 0.85, 0.65, 0.75, 0.45, 0.35, 0.05],
        [0.03, 0.12, 0.15, 0.35, 0.25, 0.55, 0.65, 0.95],
    ),
    "SUPPLY_CHAIN_COMPROMISE": cpt(
        ["DEPENDENCY_RISK", "CI_CD_COMPROMISE_RISK", "THIRD_PARTY_TRUST_RISK"],
        [0.99, 0.92, 0.90, 0.70, 0.80, 0.55, 0.45, 0.05],
        [0.01, 0.08, 0.10, 0.30, 0.20, 0.45, 0.55, 0.95],
    ),
}


BUSINESS_OUTCOMES = {
    "REVENUE_IMPACT": cpt(
        ["UNAUTHORIZED_ACCESS", "DATA_EXFILTRATION", "SERVICE_DISRUPTION"],
        [0.98, 0.92, 0.90, 0.72, 0.84, 0.65, 0.55, 0.20],
        [0.02, 0.08, 0.10, 0.28, 0.16, 0.35, 0.45, 0.80],
    ),
    "REGULATORY_IMPACT": cpt(
        ["DATA_EXFILTRATION", "SUPPLY_CHAIN_COMPROMISE"],
        [0.95, 0.70, 0.55, 0.15], [0.05, 0.30, 0.45, 0.85],
    ),
    "CUSTOMER_IMPACT": cpt(
        ["SERVICE_DISRUPTION", "SUPPLY_CHAIN_COMPROMISE"],
        [0.90, 0.70, 0.50, 0.20], [0.10, 0.30, 0.50, 0.80],
    ),
}


def all_controls():
    names = set(CONTROL_ALIASES)
    for definition in EXPERTS.values():
        names.update(definition["controls"])
    return [
        {"name": name, "aliases": CONTROL_ALIASES.get(name, [])}
        for name in sorted(names)
    ]


def upsert_node(tx, name, config, layer, aliases=None):
    node_type = config["type"]
    label = {"control": "Control", "risk": "Risk", "cpt": {
        "expert": "Risk", "incident": "Incident", "business": "BusinessOutcome"
    }[layer]}[node_type]
    tx.run(
        f"MERGE (n:BayesianNode:{label} {{name: $name}}) "
        "SET n.node_type = $node_type, n.layer = $layer, "
        "n.values_json = $values_json, n.aliases = $aliases",
        name=name,
        node_type=node_type,
        layer=layer,
        values_json=json.dumps(config.get("values")) if node_type == "cpt" else None,
        aliases=aliases or [],
    ).consume()


def link_parents(tx, child, config):
    for position, parent in enumerate(config.get("evidence", [])):
        tx.run(
            "MATCH (p:BayesianNode {name: $parent}), (n:BayesianNode {name: $child}) "
            "MERGE (p)-[r:INFLUENCES]->(n) SET r.position = $position",
            parent=parent, child=child, position=position,
        ).consume()


def ensure_parent_node(tx, name, layer, node_type, label):
    tx.run(
        f"MERGE (n:BayesianNode:{label} {{name: $name}}) "
        "ON CREATE SET n.node_type = $node_type, n.layer = $layer, n.aliases = []",
        name=name, layer=layer, node_type=node_type,
    ).consume()


def seed_layer(session, layer, definitions):
    session.run("MERGE (:BayesianModel {layer: $layer})", layer=layer).consume()
    parents = {parent for cfg in definitions.values() for parent in cfg["evidence"]}
    for parent in parents - set(definitions):
        parent_layer = "expert" if layer == "incident" else "incident"
        parent_type = "risk" if layer == "incident" else "cpt"
        parent_label = "Risk" if layer == "incident" else "Incident"
        session.execute_write(
            ensure_parent_node, parent, parent_layer, parent_type, parent_label
        )
    for name, config in definitions.items():
        session.execute_write(upsert_node, name, config, layer)
        session.run(
            "MATCH (m:BayesianModel {layer: $layer}), (n:BayesianNode {name: $node}) "
            "MERGE (m)-[:TARGET]->(n)", layer=layer, node=name,
        ).consume()


def write_controls_file(path=DEFAULT_CONTROLS_PATH):
    path = Path(path)
    payload = {"controls": all_controls()}
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    return path, len(payload["controls"])


def seed(clear=False, controls_path=DEFAULT_CONTROLS_PATH):
    store = get_store()
    controls = all_controls()
    with store.driver.session(database=store.database) as session:
        if clear:
            session.run("MATCH (n) DETACH DELETE n").consume()
        session.run(
            "CREATE CONSTRAINT bayesian_node_name IF NOT EXISTS "
            "FOR (n:BayesianNode) REQUIRE n.name IS UNIQUE"
        ).consume()
        session.run(
            "CREATE CONSTRAINT expert_name IF NOT EXISTS "
            "FOR (e:Expert) REQUIRE e.name IS UNIQUE"
        ).consume()

        for control in controls:
            session.execute_write(
                upsert_node, control["name"], {"type": "control"},
                "expert", control["aliases"],
            )

        for expert_name, definition in EXPERTS.items():
            session.run(
                "MERGE (e:Expert {name: $name}) SET e.weight = $weight",
                name=expert_name, weight=definition["weight"],
            ).consume()
            nodes = [(name, {"type": "control"}) for name in definition["controls"]]
            nodes.extend(definition["risks"].items())
            for name, config in nodes:
                session.execute_write(
                    upsert_node, name, config, "expert", CONTROL_ALIASES.get(name, [])
                )
                session.run(
                    "MATCH (e:Expert {name: $expert}), (n:BayesianNode {name: $node}) "
                    "MERGE (e)-[:OWNS]->(n)", expert=expert_name, node=name,
                ).consume()

        seed_layer(session, "incident", INCIDENTS)
        seed_layer(session, "business", BUSINESS_OUTCOMES)

        for definition in EXPERTS.values():
            for name, config in definition["risks"].items():
                session.execute_write(link_parents, name, config)
        for definitions in (INCIDENTS, BUSINESS_OUTCOMES):
            for name, config in definitions.items():
                session.execute_write(link_parents, name, config)

    output_path, count = write_controls_file(controls_path)
    return {"controls_path": output_path, "control_count": count}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clear", action="store_true", help="delete existing graph data first")
    parser.add_argument(
        "--controls-output", type=Path, default=DEFAULT_CONTROLS_PATH,
        help="path for the generated controls JSON file",
    )
    args = parser.parse_args()
    result = seed(clear=args.clear, controls_path=args.controls_output)
    print("1) Seeded Neo4j database successfully.")
    print(f"2) Wrote {result['control_count']} controls to {result['controls_path']}.")
