"""
Knowledge Graph Schema
=====================

This module defines the schema for the CQI-9 knowledge graph, including
node types, relationship types, and properties.
"""

from enum import Enum

class NodeType(str, Enum):
    """Enum representing the different types of nodes in the knowledge graph."""
    SECTION = "Section"
    REQUIREMENT = "Requirement"
    PROCESS_TABLE = "ProcessTable"
    PARAMETER = "Parameter"
    EVIDENCE = "Evidence"
    INTERPRETATION = "Interpretation"


class RelationshipType(str, Enum):
    """Enum representing the different types of relationships in the knowledge graph."""
    CONTAINS = "CONTAINS"  # Section contains subsections or requirements
    REFERENCES = "REFERENCES"  # Requirement references a table or parameter
    DEPENDS_ON = "DEPENDS_ON"  # Requirement depends on another requirement
    CONTRADICTS = "CONTRADICTS"  # Requirement contradicts another requirement
    CLARIFIES = "CLARIFIES"  # Requirement clarifies another requirement
    SUPPORTS = "SUPPORTS"  # Evidence supports a requirement
    INTERPRETS = "INTERPRETS"  # Interpretation explains a requirement
    APPLIES_TO = "APPLIES_TO"  # Requirement applies to a specific scenario/condition


class RequirementCategory(str, Enum):
    """Enum representing the different categories of requirements."""
    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class RequirementCriticality(str, Enum):
    """Enum representing the different levels of criticality for requirements."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Schema definitions for each node type
SECTION_SCHEMA = {
    "number": str,  # Section number (e.g., "3.1.2")
    "title": str,  # Section title
    "description": str,  # Section description/content
    "level": int,  # Hierarchical level (1 for top-level sections, 2 for subsections, etc.)
}

REQUIREMENT_SCHEMA = {
    "id": str,  # Unique identifier (e.g., "REQ-3.1-1")
    "text": str,  # Full text of the requirement
    "category": RequirementCategory,  # Category of the requirement
    "criticality": RequirementCriticality,  # Importance level
    "rationale": str,  # Explanation of why this requirement exists
    "verification_method": str,  # How compliance is verified
}

PROCESS_TABLE_SCHEMA = {
    "id": str,  # Unique identifier (e.g., "TABLE-3.1")
    "name": str,  # Table name
    "description": str,  # Table description
    "parameters": list,  # List of parameter names
    "units": dict,  # Dict mapping parameter names to their units
    "limits": dict,  # Dict mapping parameter names to their limits
}

PARAMETER_SCHEMA = {
    "id": str,  # Unique identifier 
    "name": str,  # Parameter name
    "description": str,  # Parameter description
    "unit": str,  # Unit of measurement
    "min_value": float,  # Minimum allowed value
    "max_value": float,  # Maximum allowed value
    "typical_value": float,  # Typical value
    "tolerance": float,  # Allowed tolerance
}

EVIDENCE_SCHEMA = {
    "id": str,  # Unique identifier
    "type": str,  # Type of evidence (e.g., "document", "record", "measurement")
    "description": str,  # Description of the evidence
    "source": str,  # Source of the evidence
}

INTERPRETATION_SCHEMA = {
    "id": str,  # Unique identifier
    "text": str,  # Interpretation text
    "source": str,  # Source of the interpretation
    "context": str,  # Context in which the interpretation applies
}

# Complete schema mapping
SCHEMA = {
    NodeType.SECTION: SECTION_SCHEMA,
    NodeType.REQUIREMENT: REQUIREMENT_SCHEMA,
    NodeType.PROCESS_TABLE: PROCESS_TABLE_SCHEMA,
    NodeType.PARAMETER: PARAMETER_SCHEMA,
    NodeType.EVIDENCE: EVIDENCE_SCHEMA,
    NodeType.INTERPRETATION: INTERPRETATION_SCHEMA,
} 