"""
Knowledge Graph Loader
=====================

This module provides utilities for loading CQI-9 data into the knowledge graph.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
import csv

from .graph_manager import KnowledgeGraphManager
from .schema import NodeType, RelationshipType, RequirementCategory, RequirementCriticality

logger = logging.getLogger(__name__)


class KnowledgeGraphLoader:
    """
    Handles loading of CQI-9 data into the Neo4j knowledge graph.
    
    This class provides methods to load sections, requirements, process tables,
    and relationships from various data sources.
    """
    
    def __init__(self, graph_manager: Optional[KnowledgeGraphManager] = None):
        """
        Initialize the Knowledge Graph Loader.
        
        Args:
            graph_manager: An optional existing KnowledgeGraphManager instance.
                If not provided, a new one will be created.
        """
        self.graph_manager = graph_manager or KnowledgeGraphManager()
        if not self.graph_manager.graph:
            self.graph_manager.connect()
            self.graph_manager.create_constraints()
            
    def load_sections_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load section data from a JSON file and add to the knowledge graph.
        
        Args:
            file_path: Path to the JSON file containing section data.
            
        Returns:
            List of section data dictionaries that were added.
        """
        try:
            with open(file_path, 'r') as f:
                sections_data = json.load(f)
                
            added_sections = []
            for section_data in sections_data:
                section_node = self.graph_manager.add_section(section_data)
                if section_node:
                    added_sections.append(dict(section_node))
                    
            logger.info(f"Successfully loaded {len(added_sections)} sections from {file_path}")
            return added_sections
            
        except Exception as e:
            logger.error(f"Error loading sections from {file_path}: {str(e)}")
            raise
            
    def load_requirements_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load requirement data from a JSON file and add to the knowledge graph.
        
        Args:
            file_path: Path to the JSON file containing requirement data.
            
        Returns:
            List of requirement data dictionaries that were added.
        """
        try:
            with open(file_path, 'r') as f:
                requirements_data = json.load(f)
                
            added_requirements = []
            for req_data in requirements_data:
                # Ensure category and criticality are valid enums
                if "category" in req_data and req_data["category"]:
                    try:
                        req_data["category"] = RequirementCategory(req_data["category"])
                    except ValueError:
                        logger.warning(f"Invalid category value: {req_data['category']} for requirement {req_data.get('id')}")
                        req_data["category"] = RequirementCategory.MANDATORY
                
                if "criticality" in req_data and req_data["criticality"]:
                    try:
                        req_data["criticality"] = RequirementCriticality(req_data["criticality"])
                    except ValueError:
                        logger.warning(f"Invalid criticality value: {req_data['criticality']} for requirement {req_data.get('id')}")
                        req_data["criticality"] = RequirementCriticality.MEDIUM
                
                req_node = self.graph_manager.add_requirement(req_data)
                if req_node:
                    added_requirements.append(dict(req_node))
                    
            logger.info(f"Successfully loaded {len(added_requirements)} requirements from {file_path}")
            return added_requirements
            
        except Exception as e:
            logger.error(f"Error loading requirements from {file_path}: {str(e)}")
            raise
            
    def load_process_tables_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load process table data from a JSON file and add to the knowledge graph.
        
        Args:
            file_path: Path to the JSON file containing process table data.
            
        Returns:
            List of process table data dictionaries that were added.
        """
        try:
            with open(file_path, 'r') as f:
                tables_data = json.load(f)
                
            added_tables = []
            for table_data in tables_data:
                table_node = self.graph_manager.add_process_table(table_data)
                if table_node:
                    added_tables.append(dict(table_node))
                    
            logger.info(f"Successfully loaded {len(added_tables)} process tables from {file_path}")
            return added_tables
            
        except Exception as e:
            logger.error(f"Error loading process tables from {file_path}: {str(e)}")
            raise
            
    def load_relationships_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load relationship data from a JSON file and add to the knowledge graph.
        
        Args:
            file_path: Path to the JSON file containing relationship data.
            
        Returns:
            List of relationships that were added.
        """
        try:
            with open(file_path, 'r') as f:
                relationships_data = json.load(f)
                
            added_relationships = []
            for rel_data in relationships_data:
                source_id = rel_data.get("source_id")
                target_id = rel_data.get("target_id")
                rel_type = rel_data.get("type")
                properties = rel_data.get("properties", {})
                
                # Validate relationship type
                try:
                    rel_type = RelationshipType(rel_type)
                except ValueError:
                    logger.warning(f"Invalid relationship type: {rel_type}. Skipping.")
                    continue
                    
                if not source_id or not target_id:
                    logger.warning(f"Missing source_id or target_id in relationship data. Skipping.")
                    continue
                    
                rel = self.graph_manager.add_relationship(source_id, target_id, rel_type, properties)
                if rel:
                    added_relationships.append({
                        "source_id": source_id,
                        "target_id": target_id,
                        "type": rel_type,
                        "properties": properties
                    })
                    
            logger.info(f"Successfully loaded {len(added_relationships)} relationships from {file_path}")
            return added_relationships
            
        except Exception as e:
            logger.error(f"Error loading relationships from {file_path}: {str(e)}")
            raise
            
    def load_sections_from_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load section data from a CSV file and add to the knowledge graph.
        
        Expected CSV columns: number, title, description, parent, level
        
        Args:
            file_path: Path to the CSV file containing section data.
            
        Returns:
            List of section data dictionaries that were added.
        """
        try:
            added_sections = []
            
            with open(file_path, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Convert level to int if present
                    if "level" in row and row["level"]:
                        try:
                            row["level"] = int(row["level"])
                        except ValueError:
                            logger.warning(f"Invalid level value for section {row.get('number')}: {row['level']}")
                            row["level"] = 1
                    
                    section_node = self.graph_manager.add_section(row)
                    if section_node:
                        added_sections.append(dict(section_node))
            
            logger.info(f"Successfully loaded {len(added_sections)} sections from CSV {file_path}")
            return added_sections
            
        except Exception as e:
            logger.error(f"Error loading sections from CSV {file_path}: {str(e)}")
            raise
            
    def load_requirements_from_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load requirement data from a CSV file and add to the knowledge graph.
        
        Expected CSV columns: id, text, section, category, criticality, rationale, verification_method
        
        Args:
            file_path: Path to the CSV file containing requirement data.
            
        Returns:
            List of requirement data dictionaries that were added.
        """
        try:
            added_requirements = []
            
            with open(file_path, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Ensure category and criticality are valid enums
                    if "category" in row and row["category"]:
                        try:
                            row["category"] = RequirementCategory(row["category"])
                        except ValueError:
                            logger.warning(f"Invalid category value: {row['category']} for requirement {row.get('id')}")
                            row["category"] = RequirementCategory.MANDATORY
                    
                    if "criticality" in row and row["criticality"]:
                        try:
                            row["criticality"] = RequirementCriticality(row["criticality"])
                        except ValueError:
                            logger.warning(f"Invalid criticality value: {row['criticality']} for requirement {row.get('id')}")
                            row["criticality"] = RequirementCriticality.MEDIUM
                    
                    req_node = self.graph_manager.add_requirement(row)
                    if req_node:
                        added_requirements.append(dict(req_node))
            
            logger.info(f"Successfully loaded {len(added_requirements)} requirements from CSV {file_path}")
            return added_requirements
            
        except Exception as e:
            logger.error(f"Error loading requirements from CSV {file_path}: {str(e)}")
            raise
            
    def load_dir(self, directory_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load all data files from a directory.
        
        This method looks for specific filenames and loads them appropriately:
        - sections.json or sections.csv: Section data
        - requirements.json or requirements.csv: Requirement data
        - process_tables.json: Process table data
        - relationships.json: Relationship data
        
        Args:
            directory_path: Path to the directory containing data files.
            
        Returns:
            Dictionary with counts of loaded entities by type.
        """
        try:
            results = {
                "sections": [],
                "requirements": [],
                "process_tables": [],
                "relationships": []
            }
            
            # Check for JSON files
            if os.path.exists(os.path.join(directory_path, "sections.json")):
                results["sections"] = self.load_sections_from_json(
                    os.path.join(directory_path, "sections.json")
                )
                
            if os.path.exists(os.path.join(directory_path, "requirements.json")):
                results["requirements"] = self.load_requirements_from_json(
                    os.path.join(directory_path, "requirements.json")
                )
                
            if os.path.exists(os.path.join(directory_path, "process_tables.json")):
                results["process_tables"] = self.load_process_tables_from_json(
                    os.path.join(directory_path, "process_tables.json")
                )
                
            if os.path.exists(os.path.join(directory_path, "relationships.json")):
                results["relationships"] = self.load_relationships_from_json(
                    os.path.join(directory_path, "relationships.json")
                )
                
            # Check for CSV files
            if os.path.exists(os.path.join(directory_path, "sections.csv")):
                csv_sections = self.load_sections_from_csv(
                    os.path.join(directory_path, "sections.csv")
                )
                results["sections"].extend(csv_sections)
                
            if os.path.exists(os.path.join(directory_path, "requirements.csv")):
                csv_requirements = self.load_requirements_from_csv(
                    os.path.join(directory_path, "requirements.csv")
                )
                results["requirements"].extend(csv_requirements)
                
            logger.info(f"Successfully loaded data from directory {directory_path}")
            return results
            
        except Exception as e:
            logger.error(f"Error loading data from directory {directory_path}: {str(e)}")
            raise 