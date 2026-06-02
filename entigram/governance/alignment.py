from typing import List, Dict, Optional
import json
from .grounding import (
    EVIDENCE_SCHEMA_MATCH,
    LIFECYCLE_PROPOSED,
    LIFECYCLE_VERIFIED,
)

class AlignmentProtocol:
    """
    Implements the Semantic Alignment Protocol for Entigram.
    Allows isolated domains to negotiate data exchange without merging ontologies.
    """
    def __init__(self, source_ontology_path: str, target_ontology_path: str):
        self.source_path = source_ontology_path
        self.target_path = target_ontology_path
        self.mappings = []

    def propose_alignment(
        self,
        source_concept: str,
        target_concept: str,
        relation: str = "skos:exactMatch",
        confidence: float = 1.0,
        *,
        evidence_type: str = EVIDENCE_SCHEMA_MATCH,
        source_artifact: Optional[str] = None,
        semantic_confidence: Optional[float] = None,
        schema_confidence: Optional[float] = None,
        data_confidence: Optional[float] = None,
        human_review_confidence: Optional[float] = None,
        runtime_observation_confidence: Optional[float] = None,
    ) -> Dict:
        """
        Proposes a mapping between two concepts from different domains.
        Proposals are hypotheses by default and are not operationally trusted
        until promoted through approve_alignment().
        """
        mapping = {
            "source": source_concept,
            "target": target_concept,
            "relation": relation,
            "confidence": confidence,
            "status": "pending",
            "lifecycle_status": LIFECYCLE_PROPOSED,
            "verified": False,
            "evidence_type": evidence_type,
            "source_artifact": source_artifact,
            "semantic_confidence": semantic_confidence,
            "schema_confidence": schema_confidence,
            "data_confidence": data_confidence,
            "human_review_confidence": human_review_confidence,
            "runtime_observation_confidence": runtime_observation_confidence,
        }
        self.mappings.append(mapping)
        return mapping

    def approve_alignment(
        self,
        source_concept: str,
        target_concept: str,
        *,
        verified_by: str,
        evidence_type: str,
        source_artifact: Optional[str] = None,
    ) -> Optional[Dict]:
        for mapping in self.mappings:
            if mapping["source"] == source_concept and mapping["target"] == target_concept:
                mapping["status"] = "approved"
                mapping["lifecycle_status"] = LIFECYCLE_VERIFIED
                mapping["verified"] = True
                mapping["verified_by"] = verified_by
                mapping["evidence_type"] = evidence_type
                if source_artifact is not None:
                    mapping["source_artifact"] = source_artifact
                return mapping
        return None

    def export_alignment_api(self) -> str:
        """
        Exports the alignment in the EXMO Align API (RDF/XML) format.
        """
        xml = [
            '<?xml version="1.0" encoding="utf-8" standalone="no"?>',
            '<rdf:RDF xmlns="http://knowledgeweb.semanticweb.org/heterogeneity/alignment"',
            '    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
            '    xmlns:xsd="http://www.w3.org/2001/XMLSchema#">',
            '<Alignment>',
            '    <xml>yes</xml>',
            '    <level>0</level>',
            '    <type>??</type>',
            f'    <onto1>{self.source_path}</onto1>',
            f'    <onto2>{self.target_path}</onto2>'
        ]

        for mapping in self.mappings:
            xml.append('    <map>')
            xml.append('        <Cell>')
            xml.append(f'            <entity1 rdf:resource="{mapping["source"]}"/>')
            xml.append(f'            <entity2 rdf:resource="{mapping["target"]}"/>')
            xml.append(f'            <measure rdf:datatype="http://www.w3.org/2001/XMLSchema#float">{mapping["confidence"]}</measure>')
            xml.append(f'            <relation>{mapping["relation"]}</relation>')
            xml.append('        </Cell>')
            xml.append('    </map>')

        xml.append('</Alignment>')
        xml.append('</rdf:RDF>')
        
        return "\n".join(xml)

    def import_alignment_api(self, xml_content: str):
        """
        Imports alignments from EXMO Align API (RDF/XML) format.
        """
        import xml.etree.ElementTree as ET
        self.mappings = []

        RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        ALIGN = "http://knowledgeweb.semanticweb.org/heterogeneity/alignment"

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"Warning: Could not parse alignment XML: {e}")
            return

        # Namespace-agnostic element search helper
        def find_text(el, tag):
            node = el.find(f"{{{ALIGN}}}{tag}")
            if node is None:
                node = el.find(tag)
            return node.text.strip() if node is not None and node.text else None

        alignment_el = root.find(f"{{{ALIGN}}}Alignment") or root.find("Alignment") or root
        onto1 = find_text(alignment_el, "onto1")
        onto2 = find_text(alignment_el, "onto2")
        if onto1:
            self.source_path = onto1
        if onto2:
            self.target_path = onto2

        for map_el in alignment_el.iter("map"):
            for cell in map_el.iter("Cell"):
                e1 = cell.find(f"{{{ALIGN}}}entity1") or cell.find("entity1")
                e2 = cell.find(f"{{{ALIGN}}}entity2") or cell.find("entity2")
                if e1 is None or e2 is None:
                    continue

                src = e1.get(f"{{{RDF}}}resource") or e1.get("rdf:resource") or ""
                tgt = e2.get(f"{{{RDF}}}resource") or e2.get("rdf:resource") or ""
                if not src or not tgt:
                    continue

                meas_el = cell.find(f"{{{ALIGN}}}measure") or cell.find("measure")
                rel_el = cell.find(f"{{{ALIGN}}}relation") or cell.find("relation")
                try:
                    confidence = float(meas_el.text.strip()) if meas_el is not None and meas_el.text else 1.0
                except ValueError:
                    confidence = 1.0

                self.mappings.append({
                    "source": src,
                    "target": tgt,
                    "relation": rel_el.text.strip() if rel_el is not None and rel_el.text else "skos:exactMatch",
                    "confidence": confidence,
                    "status": "pending",
                    "lifecycle_status": LIFECYCLE_PROPOSED,
                    "verified": False,
                    "evidence_type": EVIDENCE_SCHEMA_MATCH,
                    "source_artifact": None,
                })

    def save_alignment(self, output_path: str):
        with open(output_path, 'w') as f:
            json.dump(self.mappings, f, indent=4)
