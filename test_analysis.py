#!/usr/bin/env python3
"""
Test Analysis Script
===================

This script tests the CQI-9 Compliance Analysis System using sample data.
"""

import os
import json
import logging
from pprint import pprint

from ai_engine.analysis_agent import AnalysisAgent
from knowledge_graph.graph_manager import KnowledgeGraphManager
from knowledge_graph.loader import KnowledgeGraphLoader

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def load_sample_data(file_path):
    """Load sample data from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading sample data: {str(e)}")
        return None


def initialize_knowledge_graph():
    """Initialize the knowledge graph with sample data."""
    try:
        # Create graph manager and connect
        graph_manager = KnowledgeGraphManager()
        if not graph_manager.connect():
            logger.error("Failed to connect to Neo4j. Test cannot proceed.")
            return None
            
        # Create loader and load data
        loader = KnowledgeGraphLoader(graph_manager)
        
        # Check if data directory exists
        data_dir = "data"
        if not os.path.isdir(data_dir):
            logger.error(f"Data directory '{data_dir}' not found. Test cannot proceed.")
            return None
            
        # Load knowledge graph data
        results = loader.load_dir(data_dir)
        
        logger.info(f"Loaded {len(results['sections'])} sections, "
                  f"{len(results['requirements'])} requirements, "
                  f"{len(results['process_tables'])} process tables, and "
                  f"{len(results['relationships'])} relationships")
        
        return graph_manager
        
    except Exception as e:
        logger.error(f"Error initializing knowledge graph: {str(e)}")
        return None


def run_analysis_test(graph_manager):
    """Run analysis test using sample data."""
    try:
        # Create analysis agent
        agent = AnalysisAgent(graph_manager)
        
        # Test TUS analysis
        logger.info("Testing Temperature Uniformity Survey (TUS) analysis...")
        tus_data = load_sample_data("data/sample_tus_data.json")
        if tus_data:
            tus_result = agent.analyze_form(tus_data)
            print("\n=== TUS Analysis Result ===")
            pprint(tus_result)
            print("\n")
        
        # Test SAT analysis
        logger.info("Testing System Accuracy Test (SAT) analysis...")
        sat_data = load_sample_data("data/sample_sat_data.json")
        if sat_data:
            sat_result = agent.analyze_form(sat_data)
            print("\n=== SAT Analysis Result ===")
            pprint(sat_result)
            print("\n")
            
    except Exception as e:
        logger.error(f"Error running analysis test: {str(e)}")


def main():
    """Main function."""
    logger.info("Starting CQI-9 analysis test")
    
    # Initialize knowledge graph
    graph_manager = initialize_knowledge_graph()
    if not graph_manager:
        logger.error("Knowledge graph initialization failed. Test aborted.")
        return
    
    # Run analysis test
    run_analysis_test(graph_manager)
    
    logger.info("CQI-9 analysis test completed")


if __name__ == "__main__":
    main() 