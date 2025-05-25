"""
Knowledge Graph Visualizer
=========================

This module provides visualization tools for the CQI-9 knowledge graph.
"""

import logging
import os
from typing import Dict, List, Any, Optional, Tuple
import json
import networkx as nx
import matplotlib.pyplot as plt
from py2neo import Graph

from .graph_manager import KnowledgeGraphManager
from .schema import NodeType, RelationshipType

logger = logging.getLogger(__name__)


class KnowledgeGraphVisualizer:
    """
    Provides visualization utilities for the CQI-9 knowledge graph.
    
    This class generates visualizations and exports of the knowledge graph
    for documentation and interactive exploration.
    """
    
    def __init__(self, graph_manager: Optional[KnowledgeGraphManager] = None):
        """
        Initialize the Knowledge Graph Visualizer.
        
        Args:
            graph_manager: An optional existing KnowledgeGraphManager instance.
                If not provided, a new one will be created.
        """
        self.graph_manager = graph_manager or KnowledgeGraphManager()
        if not self.graph_manager.graph:
            self.graph_manager.connect()
    
    def export_to_networkx(self, query: str = None, params: Dict = None) -> nx.DiGraph:
        """
        Export a subset of the Neo4j graph to a NetworkX graph.
        
        Args:
            query: Optional Cypher query to filter the graph. If None, exports everything.
            params: Parameters for the Cypher query.
            
        Returns:
            A NetworkX DiGraph representing the knowledge graph.
        """
        try:
            G = nx.DiGraph()
            
            # If no specific query provided, get all nodes and relationships
            if not query:
                # Get all nodes
                nodes_query = """
                MATCH (n)
                RETURN n, labels(n) as labels
                """
                nodes_result = self.graph_manager.graph.run(nodes_query).data()
                
                # Get all relationships
                rels_query = """
                MATCH (a)-[r]->(b)
                RETURN a, r, b, type(r) as type, ID(a) as a_id, ID(b) as b_id
                """
                rels_result = self.graph_manager.graph.run(rels_query).data()
            else:
                # Execute custom query
                result = self.graph_manager.graph.run(query, params or {}).data()
                
                # Extract nodes and relationships from the result
                nodes_result = []
                rels_result = []
                seen_node_ids = set()
                
                for record in result:
                    for key, value in record.items():
                        # Check if this is a node
                        if hasattr(value, "__node_id__"):
                            node_id = value.__node_id__
                            if node_id not in seen_node_ids:
                                nodes_result.append({
                                    "n": value,
                                    "labels": list(value.labels)
                                })
                                seen_node_ids.add(node_id)
                        # Check if this is a relationship
                        elif hasattr(value, "__rel_id__"):
                            rels_result.append({
                                "r": value,
                                "type": value.type,
                                "a_id": value.start_node.__node_id__,
                                "b_id": value.end_node.__node_id__,
                                "a": value.start_node,
                                "b": value.end_node
                            })
            
            # Add nodes to the NetworkX graph
            for node_data in nodes_result:
                node = node_data["n"]
                labels = node_data["labels"]
                node_id = node.__node_id__
                
                # Convert Node properties to a regular dict
                attrs = dict(node)
                attrs["labels"] = labels
                
                G.add_node(node_id, **attrs)
            
            # Add edges to the NetworkX graph
            for rel_data in rels_result:
                source_id = rel_data["a_id"]
                target_id = rel_data["b_id"]
                rel_type = rel_data["type"]
                rel = rel_data["r"]
                
                # Convert Relationship properties to a regular dict
                attrs = dict(rel)
                attrs["type"] = rel_type
                
                G.add_edge(source_id, target_id, **attrs)
                
            logger.info(f"Exported graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            return G
            
        except Exception as e:
            logger.error(f"Error exporting to NetworkX graph: {str(e)}")
            raise
    
    def visualize_graph(self, graph: nx.DiGraph = None, query: str = None, params: Dict = None,
                       figsize: Tuple[int, int] = (12, 10), save_path: str = None,
                       node_size: int = 300, font_size: int = 8) -> None:
        """
        Visualize the knowledge graph using matplotlib.
        
        Args:
            graph: Optional pre-exported NetworkX graph. If None, will be created.
            query: Optional Cypher query to filter the graph. If None, exports everything.
            params: Parameters for the Cypher query.
            figsize: Figure size tuple (width, height).
            save_path: Optional path to save the visualization. If None, displays it.
            node_size: Size of nodes in the visualization.
            font_size: Size of font for node labels.
        """
        try:
            # Get the graph if not provided
            if graph is None:
                graph = self.export_to_networkx(query, params)
                
            # Create labels and get node colors
            labels = {}
            node_colors = []
            
            color_map = {
                NodeType.SECTION.value: 'lightblue',
                NodeType.REQUIREMENT.value: 'lightgreen',
                NodeType.PROCESS_TABLE.value: 'salmon',
                NodeType.PARAMETER.value: 'yellow',
                NodeType.EVIDENCE.value: 'lightgrey',
                NodeType.INTERPRETATION.value: 'pink'
            }
            
            for node, attrs in graph.nodes(data=True):
                # Determine label
                if "number" in attrs:
                    label = attrs["number"]
                elif "id" in attrs:
                    label = attrs["id"]
                elif "name" in attrs:
                    label = attrs["name"]
                else:
                    label = str(node)
                    
                labels[node] = label
                
                # Determine color based on node type
                if "labels" in attrs and attrs["labels"]:
                    node_label = attrs["labels"][0]
                    node_colors.append(color_map.get(node_label, 'lightgrey'))
                else:
                    node_colors.append('lightgrey')
            
            # Create the figure
            plt.figure(figsize=figsize)
            
            # Choose a layout algorithm
            if graph.number_of_nodes() < 50:
                pos = nx.spring_layout(graph, k=0.5, iterations=50)
            else:
                pos = nx.kamada_kawai_layout(graph)
            
            # Draw the graph
            nx.draw_networkx_nodes(graph, pos, node_size=node_size, node_color=node_colors, alpha=0.8)
            nx.draw_networkx_edges(graph, pos, width=1.0, alpha=0.5, arrowsize=15)
            nx.draw_networkx_labels(graph, pos, labels=labels, font_size=font_size)
            
            plt.title("CQI-9 Knowledge Graph")
            plt.axis('off')
            
            # Save or display the visualization
            if save_path:
                plt.savefig(save_path, bbox_inches='tight', dpi=300)
                logger.info(f"Saved visualization to {save_path}")
            else:
                plt.show()
                
        except Exception as e:
            logger.error(f"Error visualizing graph: {str(e)}")
            raise
    
    def export_to_d3_format(self, query: str = None, params: Dict = None,
                          output_file: str = "knowledge_graph.json") -> str:
        """
        Export the knowledge graph to a JSON format suitable for D3.js visualization.
        
        Args:
            query: Optional Cypher query to filter the graph. If None, exports everything.
            params: Parameters for the Cypher query.
            output_file: Path to save the JSON output.
            
        Returns:
            Path to the exported JSON file.
        """
        try:
            # Get the graph
            graph = self.export_to_networkx(query, params)
            
            # Prepare D3.js compatible format
            nodes = []
            links = []
            
            # Node ID mapping (Neo4j ID to array index)
            id_map = {}
            
            # Process nodes
            for i, (node_id, attrs) in enumerate(graph.nodes(data=True)):
                # Map Neo4j ID to array index
                id_map[node_id] = i
                
                # Determine node type and label
                node_type = attrs.get("labels", ["Unknown"])[0]
                
                if "number" in attrs:
                    label = attrs["number"]
                elif "id" in attrs:
                    label = attrs["id"]
                elif "name" in attrs:
                    label = attrs["name"]
                else:
                    label = str(node_id)
                
                # Create node object
                node_obj = {
                    "id": i,
                    "neo4j_id": node_id,
                    "label": label,
                    "type": node_type
                }
                
                # Add other attributes
                for key, value in attrs.items():
                    if key not in ["labels"]:
                        node_obj[key] = value
                
                nodes.append(node_obj)
            
            # Process links (edges)
            for source, target, attrs in graph.edges(data=True):
                source_idx = id_map[source]
                target_idx = id_map[target]
                
                link_obj = {
                    "source": source_idx,
                    "target": target_idx,
                    "type": attrs.get("type", "UNKNOWN")
                }
                
                # Add other attributes
                for key, value in attrs.items():
                    if key not in ["type"]:
                        link_obj[key] = value
                
                links.append(link_obj)
            
            # Create the complete graph object
            d3_data = {
                "nodes": nodes,
                "links": links
            }
            
            # Save to file
            with open(output_file, 'w') as f:
                json.dump(d3_data, f, indent=2)
                
            logger.info(f"Exported D3.js format to {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error exporting to D3 format: {str(e)}")
            raise
    
    def generate_section_hierarchy_visualization(self, output_file: str = "section_hierarchy.png") -> str:
        """
        Generate a visualization of the CQI-9 section hierarchy.
        
        Args:
            output_file: Path to save the visualization.
            
        Returns:
            Path to the saved visualization.
        """
        try:
            # Query the section hierarchy
            query = """
            MATCH (s1:Section)-[:CONTAINS]->(s2:Section)
            RETURN s1, s2
            """
            
            # Create a subgraph with only sections
            graph = self.export_to_networkx(query)
            
            # Visualize as a tree
            plt.figure(figsize=(15, 12))
            
            # Use hierarchical layout
            pos = nx.nx_agraph.graphviz_layout(graph, prog="dot")
            
            # Create labels
            labels = {}
            for node, attrs in graph.nodes(data=True):
                if "number" in attrs and "title" in attrs:
                    labels[node] = f"{attrs['number']}: {attrs['title']}"
                elif "number" in attrs:
                    labels[node] = attrs["number"]
                else:
                    labels[node] = str(node)
            
            # Draw the graph
            nx.draw_networkx_nodes(graph, pos, node_size=300, node_color="lightblue", alpha=0.8)
            nx.draw_networkx_edges(graph, pos, width=1.0, alpha=0.5, arrowsize=15)
            nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8)
            
            plt.title("CQI-9 Section Hierarchy")
            plt.axis('off')
            
            # Save the visualization
            plt.savefig(output_file, bbox_inches='tight', dpi=300)
            logger.info(f"Saved section hierarchy visualization to {output_file}")
            
            return output_file
            
        except Exception as e:
            logger.error(f"Error generating section hierarchy visualization: {str(e)}")
            raise
    
    def generate_requirement_dependency_visualization(self, output_file: str = "requirement_dependencies.png") -> str:
        """
        Generate a visualization of requirement dependencies.
        
        Args:
            output_file: Path to save the visualization.
            
        Returns:
            Path to the saved visualization.
        """
        try:
            # Query the requirement dependencies
            query = """
            MATCH (r1:Requirement)-[rel:DEPENDS_ON|CONTRADICTS|CLARIFIES]->(r2:Requirement)
            RETURN r1, rel, r2, type(rel) as rel_type
            """
            
            # Create a subgraph with requirements and their dependencies
            graph = self.export_to_networkx(query)
            
            if graph.number_of_nodes() == 0:
                logger.warning("No requirement dependencies found in the knowledge graph")
                return None
            
            # Visualize the graph
            plt.figure(figsize=(15, 12))
            
            # Use spring layout for relationship visualization
            pos = nx.spring_layout(graph, k=0.5, iterations=100)
            
            # Create labels and edge colors
            labels = {}
            edge_colors = []
            
            for node, attrs in graph.nodes(data=True):
                if "id" in attrs:
                    labels[node] = attrs["id"]
                else:
                    labels[node] = str(node)
            
            edge_color_map = {
                "DEPENDS_ON": "blue",
                "CONTRADICTS": "red",
                "CLARIFIES": "green"
            }
            
            for u, v, attrs in graph.edges(data=True):
                rel_type = attrs.get("type", "UNKNOWN")
                edge_colors.append(edge_color_map.get(rel_type, "gray"))
            
            # Draw the graph
            nx.draw_networkx_nodes(graph, pos, node_size=300, node_color="lightgreen", alpha=0.8)
            nx.draw_networkx_edges(graph, pos, width=1.5, alpha=0.7, arrowsize=15, edge_color=edge_colors)
            nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8)
            
            # Add a legend
            legend_elements = [
                plt.Line2D([0], [0], color="blue", lw=2, label="DEPENDS_ON"),
                plt.Line2D([0], [0], color="red", lw=2, label="CONTRADICTS"),
                plt.Line2D([0], [0], color="green", lw=2, label="CLARIFIES")
            ]
            plt.legend(handles=legend_elements, loc="upper right")
            
            plt.title("CQI-9 Requirement Dependencies")
            plt.axis('off')
            
            # Save the visualization
            plt.savefig(output_file, bbox_inches='tight', dpi=300)
            logger.info(f"Saved requirement dependency visualization to {output_file}")
            
            return output_file
            
        except Exception as e:
            logger.error(f"Error generating requirement dependency visualization: {str(e)}")
            raise