"""
CQI-9 Compliance Analysis System - Main Application
=================================================

This is the main entry point for the CQI-9 Compliance Analysis System.
"""

import os
import logging
import argparse
from typing import Dict, List, Any
import json

from config.config import config_by_name, active_config
from api.app import app as api_app
from web_portal.app import app as web_portal_app
from knowledge_graph.graph_manager import KnowledgeGraphManager
from knowledge_graph.loader import KnowledgeGraphLoader
from form_processor.document_processor import DocumentProcessor
from form_processor.form_extractor import FormExtractor
from ai_engine.analysis_agent import AnalysisAgent

# Set up logging
logging.basicConfig(
    level=getattr(logging, active_config.LOG_LEVEL),
    format=active_config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(active_config.LOG_FILE)
    ]
)

logger = logging.getLogger(__name__)


def init_directories():
    """Initialize required directories."""
    # Create upload directory
    os.makedirs(active_config.UPLOAD_FOLDER, exist_ok=True)
    
    # Create logs directory
    log_dir = os.path.dirname(active_config.LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)
    
    logger.info("Initialized required directories")


def init_knowledge_graph(data_dir: str = None):
    """
    Initialize and populate the knowledge graph.
    
    Args:
        data_dir: Optional directory containing knowledge graph data files.
    """
    try:
        # Create graph manager and connect
        graph_manager = KnowledgeGraphManager()
        if not graph_manager.connect():
            logger.error("Failed to connect to Neo4j. Knowledge graph will not be available.")
            return
            
        # Create constraints
        graph_manager.create_constraints()
        
        # Load data if directory provided
        if data_dir and os.path.isdir(data_dir):
            loader = KnowledgeGraphLoader(graph_manager)
            results = loader.load_dir(data_dir)
            
            logger.info(f"Loaded {len(results['sections'])} sections, "
                      f"{len(results['requirements'])} requirements, "
                      f"{len(results['process_tables'])} process tables, and "
                      f"{len(results['relationships'])} relationships")
        else:
            logger.info("No knowledge graph data directory provided, skipping data load")
            
        logger.info("Knowledge graph initialization complete")
            
    except Exception as e:
        logger.error(f"Error initializing knowledge graph: {str(e)}")


def run_api_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = None):
    """
    Run the Flask API server.
    
    Args:
        host: Host to bind to.
        port: Port to bind to.
        debug: Whether to run in debug mode. If None, uses the config setting.
    """
    debug = debug if debug is not None else active_config.DEBUG
    logger.info(f"Starting API server on {host}:{port} (debug={debug})")
    api_app.run(host=host, port=port, debug=debug)


def run_web_portal(host: str = "0.0.0.0", port: int = 5050, debug: bool = None):
    """
    Run the Flask web portal server.
    
    Args:
        host: Host to bind to.
        port: Port to bind to.
        debug: Whether to run in debug mode. If None, uses the config setting.
    """
    debug = debug if debug is not None else active_config.DEBUG
    logger.info(f"Starting web portal on {host}:{port} (debug={debug})")
    web_portal_app.run(host=host, port=port, debug=debug)


def process_form(file_path: str):
    """
    Process a form file and print the extracted data.
    
    Args:
        file_path: Path to the form file.
    """
    try:
        logger.info(f"Processing form: {file_path}")
        
        # Create processors
        doc_processor = DocumentProcessor()
        form_extractor = FormExtractor(doc_processor)
        
        # Process the form
        form_data = form_extractor.extract_form_data(file_path)
        
        if form_data.get("success", False):
            logger.info(f"Successfully extracted form data. Form type: {form_data.get('form_type', 'unknown')}")
            print(json.dumps(form_data, indent=2))
        else:
            logger.error(f"Failed to extract form data: {form_data.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error processing form: {str(e)}")


def analyze_form(file_path: str):
    """
    Process and analyze a form file.
    
    Args:
        file_path: Path to the form file.
    """
    try:
        logger.info(f"Analyzing form: {file_path}")
        
        # Create processors
        doc_processor = DocumentProcessor()
        form_extractor = FormExtractor(doc_processor)
        graph_manager = KnowledgeGraphManager()
        
        if not graph_manager.connect():
            logger.error("Failed to connect to Neo4j. Analysis will not be accurate.")
            
        analysis_agent = AnalysisAgent(graph_manager)
        
        # Process the form
        form_data = form_extractor.extract_form_data(file_path)
        
        if not form_data.get("success", False):
            logger.error(f"Failed to extract form data: {form_data.get('error', 'Unknown error')}")
            return
            
        # Analyze the form
        analysis_result = analysis_agent.analyze_form(form_data)
        
        # Print the results
        print(json.dumps(analysis_result, indent=2))
        
    except Exception as e:
        logger.error(f"Error analyzing form: {str(e)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="CQI-9 Compliance Analysis System")
    
    # Global arguments
    parser.add_argument(
        "--config", 
        type=str, 
        default="development",
        choices=list(config_by_name.keys()),
        help="Configuration to use"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # API server command
    api_parser = subparsers.add_parser("api", help="Run the API server")
    api_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    api_parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    api_parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    api_parser.add_argument("--init-kg", type=str, help="Initialize knowledge graph with data from directory")
    
    # Web portal command
    web_parser = subparsers.add_parser("web", help="Run the web portal")
    web_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    web_parser.add_argument("--port", type=int, default=5050, help="Port to bind to")
    web_parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    web_parser.add_argument("--init-kg", type=str, help="Initialize knowledge graph with data from directory")
    
    # Process form command
    process_parser = subparsers.add_parser("process", help="Process a form file")
    process_parser.add_argument("file", type=str, help="Path to the form file")
    
    # Analyze form command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a form file")
    analyze_parser.add_argument("file", type=str, help="Path to the form file")
    analyze_parser.add_argument("--init-kg", type=str, help="Initialize knowledge graph with data from directory")
    
    # Initialize knowledge graph command
    init_kg_parser = subparsers.add_parser("init-kg", help="Initialize the knowledge graph")
    init_kg_parser.add_argument("--data-dir", type=str, help="Directory containing knowledge graph data files")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Initialize directories
    init_directories()
    
    # Process command
    if args.command == "api":
        # Initialize knowledge graph if requested
        if args.init_kg:
            init_knowledge_graph(args.init_kg)
            
        # Run API server
        run_api_server(args.host, args.port, args.debug)
        
    elif args.command == "web":
        # Initialize knowledge graph if requested
        if args.init_kg:
            init_knowledge_graph(args.init_kg)
            
        # Run web portal
        run_web_portal(args.host, args.port, args.debug)
        
    elif args.command == "process":
        # Process form
        process_form(args.file)
        
    elif args.command == "analyze":
        # Initialize knowledge graph if requested
        if args.init_kg:
            init_knowledge_graph(args.init_kg)
            
        # Analyze form
        analyze_form(args.file)
        
    elif args.command == "init-kg":
        # Initialize knowledge graph
        init_knowledge_graph(args.data_dir)
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 