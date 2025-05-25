# CQI-9 Compliance Analysis System

A comprehensive solution for analyzing thermal processing requirement compliance with CQI-9 standards.

## Overview

This system provides automated analysis of CQI-9 compliance in the automotive industry's thermal processing domain. It combines document processing, knowledge graph technology, and AI-powered analysis to help organizations ensure their processes meet CQI-9 requirements.

Key features:
- Processing of CQI-9 forms and documentation (TUS, SAT, etc.)
- Knowledge graph representation of CQI-9 requirements
- AI-powered compliance analysis with detailed findings
- REST API for integration with other systems
- Command-line interface for direct processing and analysis

## Installation

### Prerequisites
- Python 3.9+
- Neo4j (4.4+) for the knowledge graph
- Tesseract OCR for document processing

### Setup

1. Clone the repository:
```
git clone <repository-url>
cd cqi9_system
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Start Neo4j database (required for knowledge graph features):
```
# Using Docker (recommended)
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:latest
```

4. Configure environment variables (optional):
```
# Create a .env file in the project root
OPENAI_API_KEY=your_openai_api_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

## Usage

### Running the API Server

```
python main.py server --host 0.0.0.0 --port 5000
```

### Processing a Form

```
python main.py process path/to/form.pdf
```

### Analyzing a Form for Compliance

```
python main.py analyze path/to/form.pdf
```

### Initializing the Knowledge Graph

```
python main.py init-kg --data-dir path/to/data
```

## API Endpoints

The system provides a REST API for integration with other systems:

- `POST /forms/upload` - Upload a form for processing
- `GET /forms` - List all uploaded forms
- `GET /forms/{form_id}` - Get details for a specific form
- `POST /analysis/analyze/{form_id}` - Analyze a form for compliance
- `GET /analysis/{analysis_id}` - Get analysis results
- `GET /knowledge/requirements` - Get a list of requirements
- `GET /knowledge/requirements/{requirement_id}` - Get details for a specific requirement

## System Architecture

The system consists of the following components:

1. **Knowledge Graph** - Neo4j database storing CQI-9 requirements and their relationships
2. **Form Processor** - Extracts structured data from CQI-9 forms and documents
3. **AI Engine** - Analyzes form data for compliance with CQI-9 requirements
4. **API** - REST API for integration with other systems
5. **CLI** - Command-line interface for direct processing and analysis

## Development

### Project Structure

```
cqi9_system/
├── api/              # REST API components
├── ai_engine/        # AI analysis components
├── config/           # Configuration
├── form_processor/   # Document processing
├── knowledge_graph/  # Knowledge graph components
├── utils/            # Utility functions
├── tests/            # Test cases
├── requirements.txt  # Dependencies
└── main.py           # Main entry point
```

### Running Tests

```
pytest tests/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- OpenAI for AI capabilities
- Neo4j for graph database technology
- AIAG for CQI-9 standard documentation