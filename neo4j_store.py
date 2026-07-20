import json
import os
from functools import lru_cache

class Neo4jModelStore:
    """Persistence adapter for Bayesian model definitions stored in Neo4j."""

    def __init__(self, uri=None, user=None, password=None, database=None):
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("Neo4j driver is not installed; run 'pip install -r requirements.txt'") from exc
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        if not self.password:
            raise RuntimeError("NEO4J_PASSWORD must be set")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        self.driver.close()

    @staticmethod
    def _node_config(record):
        node_type = record["node_type"]
        config = {"type": node_type}
        if node_type == "cpt":
            config["evidence"] = record["evidence"]
            config["values"] = json.loads(record["values_json"])
        return config

    def load_experts(self):
        query = """
        MATCH (e:Expert)-[:OWNS]->(n:BayesianNode)
        OPTIONAL MATCH (p:BayesianNode)-[r:INFLUENCES]->(n)
        WITH e, n, p, r ORDER BY e.name, n.name, r.position
        WITH e, n, collect(p.name) AS evidence
        RETURN e.name AS expert, e.weight AS weight,
               collect({name: n.name, node_type: n.node_type,
                        values_json: n.values_json, evidence: evidence}) AS nodes
        ORDER BY expert
        """
        experts = {}
        with self.driver.session(database=self.database) as session:
            for record in session.run(query):
                cpds = {
                    item["name"]: self._node_config(item)
                    for item in record["nodes"]
                }
                targets = [name for name, cfg in cpds.items() if cfg["type"] == "cpt"]
                experts[record["expert"]] = {
                    "weight": float(record["weight"]),
                    "cpds": cpds,
                    "targets": targets,
                    "risk_nodes": targets.copy(),
                }
        return experts

    def load_model(self, layer):
        query = """
        MATCH (m:BayesianModel {layer: $layer})-[:TARGET]->(n:BayesianNode)
        OPTIONAL MATCH (p:BayesianNode)-[r:INFLUENCES]->(n)
        WITH m, n, p, r ORDER BY n.name, r.position
        WITH m, n, collect(p.name) AS evidence
        RETURN collect({name: n.name, node_type: n.node_type,
                        values_json: n.values_json, evidence: evidence}) AS nodes
        """
        with self.driver.session(database=self.database) as session:
            record = session.run(query, layer=layer).single()
        if not record or not record["nodes"]:
            raise RuntimeError(f"No Bayesian model found in Neo4j for layer '{layer}'")
        cpds = {item["name"]: self._node_config(item) for item in record["nodes"]}
        return {"targets": list(cpds), "cpds": cpds}

    def load_control_registry(self):
        query = """
        MATCH (c:Control)
        RETURN c.name AS name, coalesce(c.aliases, []) AS aliases
        ORDER BY name
        """
        with self.driver.session(database=self.database) as session:
            return {
                record["name"]: {"aliases": list(record["aliases"])}
                for record in session.run(query)
            }


@lru_cache(maxsize=1)
def get_store():
    return Neo4jModelStore()
