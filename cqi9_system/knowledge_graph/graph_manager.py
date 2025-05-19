"""
Knowledge Graph Manager
======================

This module provides the core functionality for interacting with the Neo4j database
that stores the CQI-9 knowledge graph.
"""

import logging
from py2neo import Graph, Node, Relationship, NodeMatcher
from ..config.config import active_config

logger = logging.getLogger(__name__)

class KnowledgeGraphManager:
    """
    Manages interactions with the Neo4j graph database for CQI-9 requirements.
    
    This class handles connecting to Neo4j, creating nodes and relationships,
    and querying the knowledge graph for information about CQI-9 requirements.
    """
    
    def __init__(self, uri=None, username=None, password=None):
        """
        Initialize the Knowledge Graph Manager.
        
        Args:
            uri (str, optional): Neo4j connection URI. Defaults to config setting.
            username (str, optional): Neo4j username. Defaults to config setting.
            password (str, optional): Neo4j password. Defaults to config setting.
        """
        self.uri = uri or active_config.NEO4J_URI
        self.username = username or active_config.NEO4J_USER
        self.password = password or active_config.NEO4J_PASSWORD
        self.graph = None
        self.matcher = None
        
    def connect(self):
        """
        Establish connection to the Neo4j database.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            self.graph = Graph(self.uri, auth=(self.username, self.password))
            self.matcher = NodeMatcher(self.graph)
            logger.info("Successfully connected to Neo4j knowledge graph database")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            return False
            
    def create_constraints(self):
        """
        Create necessary constraints in the Neo4j database.
        """
        try:
            # Create constraint to ensure uniqueness of requirement IDs
            self.graph.run("CREATE CONSTRAINT requirement_id IF NOT EXISTS "
                         "FOR (r:Requirement) REQUIRE r.id IS UNIQUE")
            
            # Create constraint for section numbers
            self.graph.run("CREATE CONSTRAINT section_number IF NOT EXISTS "
                         "FOR (s:Section) REQUIRE s.number IS UNIQUE")
            
            # Create constraint for process table IDs
            self.graph.run("CREATE CONSTRAINT process_table_id IF NOT EXISTS "
                         "FOR (t:ProcessTable) REQUIRE t.id IS UNIQUE")
                         
            logger.info("Successfully created Neo4j constraints")
        except Exception as e:
            logger.error(f"Failed to create constraints: {str(e)}")
            
    def add_section(self, section_data):
        """
        Add a section node to the knowledge graph.
        
        Args:
            section_data (dict): Section data including:
                number: Section number (e.g., '3.1.2')
                title: Section title
                description: Section description
                parent: Parent section number (optional)
                
        Returns:
            Node: The created Neo4j section node
        """
        try:
            # Check if section already exists
            existing = self.matcher.match("Section", number=section_data["number"]).first()
            if existing:
                logger.info(f"Section {section_data['number']} already exists, updating properties")
                for key, value in section_data.items():
                    if key != "parent" and key != "number":
                        existing[key] = value
                self.graph.push(existing)
                section_node = existing
            else:
                # Create new section node
                section_props = {k: v for k, v in section_data.items() if k != "parent"}
                section_node = Node("Section", **section_props)
                self.graph.create(section_node)
                logger.info(f"Created section node: {section_data['number']}")
            
            # Connect to parent section if specified
            if "parent" in section_data and section_data["parent"]:
                parent_node = self.matcher.match("Section", number=section_data["parent"]).first()
                if parent_node:
                    rel = Relationship(parent_node, "CONTAINS", section_node)
                    self.graph.create(rel)
                    logger.info(f"Connected section {section_data['number']} to parent {section_data['parent']}")
                else:
                    logger.warning(f"Parent section {section_data['parent']} not found")
                    
            return section_node
        
        except Exception as e:
            logger.error(f"Error adding section {section_data.get('number', 'unknown')}: {str(e)}")
            raise
            
    def add_requirement(self, requirement_data):
        """
        Add a requirement node to the knowledge graph.
        
        Args:
            requirement_data (dict): Requirement data including:
                id: Unique identifier for the requirement
                text: The requirement text
                section: Section number this requirement belongs to
                category: Category of requirement (e.g., 'mandatory', 'recommended')
                criticality: Level of importance (e.g., 'high', 'medium', 'low')
                
        Returns:
            Node: The created Neo4j requirement node
        """
        try:
            # Check if requirement already exists
            existing = self.matcher.match("Requirement", id=requirement_data["id"]).first()
            if existing:
                logger.info(f"Requirement {requirement_data['id']} already exists, updating properties")
                for key, value in requirement_data.items():
                    if key != "section" and key != "id":
                        existing[key] = value
                self.graph.push(existing)
                req_node = existing
            else:
                # Create new requirement node
                req_props = {k: v for k, v in requirement_data.items() if k != "section"}
                req_node = Node("Requirement", **req_props)
                self.graph.create(req_node)
                logger.info(f"Created requirement node: {requirement_data['id']}")
            
            # Connect to section if specified
            if "section" in requirement_data and requirement_data["section"]:
                section_node = self.matcher.match("Section", number=requirement_data["section"]).first()
                if section_node:
                    rel = Relationship(section_node, "CONTAINS", req_node)
                    self.graph.create(rel)
                    logger.info(f"Connected requirement {requirement_data['id']} to section {requirement_data['section']}")
                else:
                    logger.warning(f"Section {requirement_data['section']} not found")
                    
            return req_node
        
        except Exception as e:
            logger.error(f"Error adding requirement {requirement_data.get('id', 'unknown')}: {str(e)}")
            raise
            
    def add_relationship(self, source_id, target_id, rel_type, properties=None):
        """
        Create a relationship between two nodes in the knowledge graph.
        
        Args:
            source_id (str): ID of the source node
            target_id (str): ID of the target node
            rel_type (str): Type of relationship (e.g., 'DEPENDS_ON', 'REFERENCES')
            properties (dict, optional): Properties for the relationship
            
        Returns:
            Relationship: The created Neo4j relationship
        """
        try:
            # Find the source and target nodes
            source_node = self.matcher.match().where(f"_.id = '{source_id}'").first()
            target_node = self.matcher.match().where(f"_.id = '{target_id}'").first()
            
            if not source_node:
                logger.error(f"Source node with ID {source_id} not found")
                return None
                
            if not target_node:
                logger.error(f"Target node with ID {target_id} not found")
                return None
                
            # Create the relationship with properties if provided
            properties = properties or {}
            rel = Relationship(source_node, rel_type, target_node, **properties)
            self.graph.create(rel)
            
            logger.info(f"Created relationship: ({source_id})-[{rel_type}]->({target_id})")
            return rel
            
        except Exception as e:
            logger.error(f"Error adding relationship {source_id}->{target_id}: {str(e)}")
            raise
            
    def add_process_table(self, table_data):
        """
        Add a process table node to the knowledge graph.
        
        Args:
            table_data (dict): Process table data including:
                id: Unique identifier for the table
                name: Table name
                description: Table description
                section: Section number this table belongs to
                parameters: List of parameters in the table
                
        Returns:
            Node: The created Neo4j process table node
        """
        try:
            # Check if table already exists
            existing = self.matcher.match("ProcessTable", id=table_data["id"]).first()
            if existing:
                logger.info(f"Process table {table_data['id']} already exists, updating properties")
                for key, value in table_data.items():
                    if key != "section" and key != "id":
                        existing[key] = value
                self.graph.push(existing)
                table_node = existing
            else:
                # Create new process table node
                table_props = {k: v for k, v in table_data.items() if k != "section"}
                table_node = Node("ProcessTable", **table_props)
                self.graph.create(table_node)
                logger.info(f"Created process table node: {table_data['id']}")
            
            # Connect to section if specified
            if "section" in table_data and table_data["section"]:
                section_node = self.matcher.match("Section", number=table_data["section"]).first()
                if section_node:
                    rel = Relationship(section_node, "CONTAINS", table_node)
                    self.graph.create(rel)
                    logger.info(f"Connected process table {table_data['id']} to section {table_data['section']}")
                else:
                    logger.warning(f"Section {table_data['section']} not found")
                    
            return table_node
        
        except Exception as e:
            logger.error(f"Error adding process table {table_data.get('id', 'unknown')}: {str(e)}")
            raise
            
    def query_section_requirements(self, section_number):
        """
        Query all requirements belonging to a specific section.
        
        Args:
            section_number (str): The section number to query (e.g., '3.1.2')
            
        Returns:
            list: List of requirement dictionaries
        """
        try:
            query = """
            MATCH (s:Section {number: $section_number})-[:CONTAINS]->(r:Requirement)
            RETURN r
            """
            results = self.graph.run(query, section_number=section_number).data()
            requirements = [dict(r["r"]) for r in results]
            logger.info(f"Found {len(requirements)} requirements for section {section_number}")
            return requirements
            
        except Exception as e:
            logger.error(f"Error querying requirements for section {section_number}: {str(e)}")
            return []
            
    def query_related_requirements(self, requirement_id, rel_type=None):
        """
        Query requirements related to a given requirement.
        
        Args:
            requirement_id (str): The ID of the requirement to find relations for
            rel_type (str, optional): Type of relationship to filter by
            
        Returns:
            list: List of related requirement dictionaries with relationship info
        """
        try:
            # Build query based on whether a relationship type is specified
            if rel_type:
                query = f"""
                MATCH (r1:Requirement {{id: $req_id}})-[rel:{rel_type}]->(r2:Requirement)
                RETURN r2, TYPE(rel) as relationship_type, rel
                """
            else:
                query = """
                MATCH (r1:Requirement {id: $req_id})-[rel]->(r2:Requirement)
                RETURN r2, TYPE(rel) as relationship_type, rel
                """
                
            results = self.graph.run(query, req_id=requirement_id).data()
            
            # Format the results
            related_reqs = []
            for result in results:
                req_data = dict(result["r2"])
                req_data["relationship_type"] = result["relationship_type"]
                req_data["relationship_props"] = dict(result["rel"])
                related_reqs.append(req_data)
                
            logger.info(f"Found {len(related_reqs)} related requirements for {requirement_id}")
            return related_reqs
            
        except Exception as e:
            logger.error(f"Error querying related requirements for {requirement_id}: {str(e)}")
            return []
            
    def query_requirement_context(self, requirement_id, depth=2):
        """
        Query the context of a requirement including related requirements,
        parent sections, and process tables.
        
        Args:
            requirement_id (str): The ID of the requirement to find context for
            depth (int, optional): Depth of related requirements to include
            
        Returns:
            dict: Context information including the requirement, related entities
        """
        try:
            # Get the requirement
            req_node = self.matcher.match("Requirement", id=requirement_id).first()
            if not req_node:
                logger.error(f"Requirement {requirement_id} not found")
                return None
                
            req_data = dict(req_node)
            
            # Get the parent section
            section_query = """
            MATCH (s:Section)-[:CONTAINS]->(r:Requirement {id: $req_id})
            RETURN s
            """
            section_result = self.graph.run(section_query, req_id=requirement_id).data()
            if section_result:
                req_data["section"] = dict(section_result[0]["s"])
            
            # Get related requirements
            if depth > 0:
                # Get outgoing relationships (requirements this one affects)
                outgoing_query = """
                MATCH (r1:Requirement {id: $req_id})-[rel]->(r2:Requirement)
                RETURN r2.id as id, TYPE(rel) as relationship_type
                """
                outgoing = self.graph.run(outgoing_query, req_id=requirement_id).data()
                
                # Get incoming relationships (requirements that affect this one)
                incoming_query = """
                MATCH (r1:Requirement)-[rel]->(r2:Requirement {id: $req_id})
                RETURN r1.id as id, TYPE(rel) as relationship_type
                """
                incoming = self.graph.run(incoming_query, req_id=requirement_id).data()
                
                req_data["related_requirements"] = {
                    "outgoing": outgoing,
                    "incoming": incoming
                }
            
            # Get process tables related to this requirement
            tables_query = """
            MATCH (r:Requirement {id: $req_id})-[:REFERENCES]->(t:ProcessTable)
            RETURN t
            """
            tables_result = self.graph.run(tables_query, req_id=requirement_id).data()
            if tables_result:
                req_data["process_tables"] = [dict(t["t"]) for t in tables_result]
            
            return req_data
            
        except Exception as e:
            logger.error(f"Error querying requirement context for {requirement_id}: {str(e)}")
            return None 