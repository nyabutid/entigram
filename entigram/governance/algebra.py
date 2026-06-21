import networkx as nx
from typing import Any, Dict

class RelationalAlgebraGuard:
    def __init__(self, catalog: Dict[str, Any], broker: Any):
        self.catalog = catalog
        self.broker = broker

    def validate_alignment_proposal(
        self,
        source_domain: str,
        target_domain: str,
        src_concept: str,
        tgt_concept: str,
    ):
        src_entity = src_concept.split('.')[0] if '.' in src_concept else src_concept
        tgt_entity = tgt_concept.split('.')[0] if '.' in tgt_concept else tgt_concept

        src_attrs = self.catalog["entities"].get(src_entity)
        tgt_attrs = self.catalog["entities"].get(tgt_entity)
        if src_attrs is None or tgt_attrs is None:
            raise ValueError("RA Union-Compatibility Violation: Concept missing from schema.")
        relationships = self.catalog.get("relationships", [])
        dag = nx.DiGraph()
        for rel in relationships:
            if rel["part_a"] == "MUST":
                dag.add_edge(rel["entity_a"], rel["entity_b"])
            if rel["part_b"] == "MUST":
                dag.add_edge(rel["entity_b"], rel["entity_a"])
        if src_entity in dag:
            ancestors = nx.ancestors(dag, src_entity)
            if ancestors:
                target_ancestors = nx.ancestors(dag, tgt_entity) if tgt_entity in dag else set()
                target_parent_candidates = target_ancestors or {tgt_entity}
                alignments = self.broker.ledger.get_alignments(
                    source_domain=source_domain,
                    trusted_only=True,
                )
                aligned_pairs = {
                    (
                        a["source_concept"].split('.')[0] if '.' in a["source_concept"] else a["source_concept"],
                        a["target_concept"].split('.')[0] if '.' in a["target_concept"] else a["target_concept"],
                    )
                    for a in alignments
                    if a.get("target_domain") == target_domain
                }
                for ancestor in ancestors:
                    if not any((ancestor, target_parent) in aligned_pairs for target_parent in target_parent_candidates):
                        raise ValueError(f"RA Precedence Violation: Must align parent entity '{ancestor}' before aligning '{src_concept}'.")
