"""
Flask Application
===============

This module defines the Flask application and API routes for the CQI-9 system.
"""

import os
import logging
import json
from typing import Dict, List, Any
from datetime import datetime
import uuid

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_restx import Api, Resource, fields, reqparse
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest

from ..config.config import active_config
from ..form_processor.document_processor import DocumentProcessor
from ..form_processor.form_extractor import FormExtractor
from ..knowledge_graph.graph_manager import KnowledgeGraphManager
from ..ai_engine.analysis_agent import AnalysisAgent

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

# Create Flask application
app = Flask(__name__)
app.config.from_object(active_config)

# Create upload directory if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Enable CORS
CORS(app)

# Create API
api = Api(
    app,
    version="1.0",
    title="CQI-9 Compliance Analysis API",
    description="API for analyzing CQI-9 compliance in thermal processing"
)

# Define namespaces
ns_analysis = api.namespace("analysis", description="Analysis operations")
ns_forms = api.namespace("forms", description="Form operations")
ns_knowledge = api.namespace("knowledge", description="Knowledge graph operations")

# Define models for API documentation
form_model = api.model("Form", {
    "id": fields.String(description="Form ID"),
    "filename": fields.String(description="Original filename"),
    "upload_date": fields.DateTime(description="Date of upload"),
    "form_type": fields.String(description="Detected form type"),
    "status": fields.String(description="Processing status")
})

analysis_model = api.model("Analysis", {
    "id": fields.String(description="Analysis ID"),
    "form_id": fields.String(description="Associated form ID"),
    "timestamp": fields.DateTime(description="Analysis timestamp"),
    "overall_compliance": fields.Boolean(description="Overall compliance status"),
    "confidence": fields.Float(description="Confidence score")
})

requirement_model = api.model("Requirement", {
    "id": fields.String(description="Requirement ID"),
    "text": fields.String(description="Requirement text"),
    "section": fields.String(description="Section number"),
    "category": fields.String(description="Requirement category"),
    "criticality": fields.String(description="Criticality level")
})

# Initialize components
doc_processor = DocumentProcessor()
form_extractor = FormExtractor(doc_processor)
graph_manager = KnowledgeGraphManager()
graph_manager.connect()  # Connect to Neo4j
analysis_agent = AnalysisAgent(graph_manager)


@ns_forms.route("/upload")
class FormUpload(Resource):
    """
    Form upload endpoint.
    """
    
    upload_parser = reqparse.RequestParser()
    upload_parser.add_argument("file", location="files", type=reqparse.FileStorage, required=True, help="Document file")
    
    @ns_forms.expect(upload_parser)
    @ns_forms.response(201, "Form uploaded successfully", form_model)
    @ns_forms.response(400, "Invalid file")
    def post(self):
        """
        Upload a new form for processing.
        """
        try:
            args = self.upload_parser.parse_args()
            file = args["file"]
            
            if file.filename == "":
                raise BadRequest("No file selected")
                
            # Check allowed file extensions
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
            
            if file_ext not in app.config["ALLOWED_EXTENSIONS"]:
                raise BadRequest(f"File type not allowed. Allowed types: {', '.join(app.config['ALLOWED_EXTENSIONS'])}")
                
            # Generate a unique filename
            form_id = str(uuid.uuid4())
            stored_filename = f"{form_id}.{file_ext}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
            
            # Save the file
            file.save(file_path)
            
            # Process the form asynchronously - for now, we'll do it synchronously
            try:
                form_data = form_extractor.extract_form_data(file_path)
                form_type = form_data.get("form_type", "unknown")
                status = "processed" if form_data.get("success", False) else "error"
            except Exception as e:
                logger.error(f"Error processing form: {str(e)}")
                form_type = "unknown"
                status = "error"
            
            # Create form entry
            form_entry = {
                "id": form_id,
                "filename": filename,
                "stored_filename": stored_filename,
                "file_path": file_path,
                "upload_date": datetime.now().isoformat(),
                "form_type": form_type,
                "status": status,
                "processed": form_data if status == "processed" else {"error": "Processing failed"}
            }
            
            # In a real system, you would store this in a database
            # For now, we'll save it to a JSON file
            forms_file = os.path.join(app.config["UPLOAD_FOLDER"], "forms.json")
            
            try:
                if os.path.exists(forms_file):
                    with open(forms_file, "r") as f:
                        forms = json.load(f)
                else:
                    forms = []
                    
                forms.append(form_entry)
                
                with open(forms_file, "w") as f:
                    json.dump(forms, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving form entry: {str(e)}")
            
            # Return the form entry
            return {
                "id": form_entry["id"],
                "filename": form_entry["filename"],
                "upload_date": form_entry["upload_date"],
                "form_type": form_entry["form_type"],
                "status": form_entry["status"]
            }, 201
            
        except BadRequest as e:
            return {"error": str(e)}, 400
        except Exception as e:
            logger.error(f"Error uploading form: {str(e)}")
            return {"error": "Internal server error"}, 500


@ns_forms.route("/<string:form_id>")
class FormResource(Resource):
    """
    Form resource endpoint.
    """
    
    @ns_forms.response(200, "Form details", form_model)
    @ns_forms.response(404, "Form not found")
    def get(self, form_id):
        """
        Get details for a specific form.
        """
        try:
            # In a real system, you would query a database
            forms_file = os.path.join(app.config["UPLOAD_FOLDER"], "forms.json")
            
            if not os.path.exists(forms_file):
                abort(404, description="No forms found")
                
            with open(forms_file, "r") as f:
                forms = json.load(f)
                
            form = next((f for f in forms if f["id"] == form_id), None)
            
            if not form:
                abort(404, description="Form not found")
                
            return {
                "id": form["id"],
                "filename": form["filename"],
                "upload_date": form["upload_date"],
                "form_type": form["form_type"],
                "status": form["status"]
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting form details: {str(e)}")
            return {"error": "Internal server error"}, 500


@ns_forms.route("")
class FormList(Resource):
    """
    Form list endpoint.
    """
    
    @ns_forms.response(200, "List of forms", [form_model])
    def get(self):
        """
        Get a list of all uploaded forms.
        """
        try:
            # In a real system, you would query a database
            forms_file = os.path.join(app.config["UPLOAD_FOLDER"], "forms.json")
            
            if not os.path.exists(forms_file):
                return [], 200
                
            with open(forms_file, "r") as f:
                forms = json.load(f)
                
            return [
                {
                    "id": form["id"],
                    "filename": form["filename"],
                    "upload_date": form["upload_date"],
                    "form_type": form["form_type"],
                    "status": form["status"]
                }
                for form in forms
            ], 200
            
        except Exception as e:
            logger.error(f"Error getting forms list: {str(e)}")
            return {"error": "Internal server error"}, 500


@ns_analysis.route("/analyze/<string:form_id>")
class AnalyzeForm(Resource):
    """
    Form analysis endpoint.
    """
    
    @ns_analysis.response(200, "Analysis results", analysis_model)
    @ns_analysis.response(404, "Form not found")
    @ns_analysis.response(400, "Analysis failed")
    def post(self, form_id):
        """
        Analyze a specific form for CQI-9 compliance.
        """
        try:
            # Find the form
            forms_file = os.path.join(app.config["UPLOAD_FOLDER"], "forms.json")
            
            if not os.path.exists(forms_file):
                abort(404, description="No forms found")
                
            with open(forms_file, "r") as f:
                forms = json.load(f)
                
            form = next((f for f in forms if f["id"] == form_id), None)
            
            if not form:
                abort(404, description="Form not found")
                
            # Check if form has been processed
            if form["status"] != "processed":
                return {"error": "Form has not been successfully processed"}, 400
                
            # Get processed form data
            form_data = form["processed"]
            
            # Run analysis
            analysis_result = analysis_agent.analyze_form(form_data)
            
            # Generate analysis ID
            analysis_id = str(uuid.uuid4())
            
            # Add analysis entry
            analysis_entry = {
                "id": analysis_id,
                "form_id": form_id,
                "timestamp": datetime.now().isoformat(),
                "result": analysis_result
            }
            
            # In a real system, you would store this in a database
            # For now, we'll save it to a JSON file
            analyses_file = os.path.join(app.config["UPLOAD_FOLDER"], "analyses.json")
            
            try:
                if os.path.exists(analyses_file):
                    with open(analyses_file, "r") as f:
                        analyses = json.load(f)
                else:
                    analyses = []
                    
                analyses.append(analysis_entry)
                
                with open(analyses_file, "w") as f:
                    json.dump(analyses, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving analysis entry: {str(e)}")
            
            # Return the analysis result
            return {
                "id": analysis_id,
                "form_id": form_id,
                "timestamp": analysis_entry["timestamp"],
                "overall_compliance": analysis_result.get("overall_compliance", False),
                "confidence": analysis_result.get("overall_confidence", 0.0),
                "findings": analysis_result.get("findings", []),
                "summary": analysis_result.get("summary", "Analysis completed")
            }, 200
            
        except Exception as e:
            logger.error(f"Error analyzing form: {str(e)}")
            return {"error": "Internal server error"}, 500

@ns_analysis.route("/analyze/requirement")
class AnalyzeRequirement(Resource):
    """
    Requirement analysis endpoint.
    """
    
    @ns_analysis.response(200, "Analysis results", analysis_model)
    @ns_analysis.response(400, "Invalid request")
    def post(self):
        """
        Analyze a specific requirement with provided evidence.
        """
        try:
            data = request.get_json()
            requirement_id = data.get('requirement_id')
            evidence = data.get('evidence')
            
            if not requirement_id or not evidence:
                return {'error': 'Missing requirement_id or evidence'}, 400
                
            analysis_result = analysis_agent.analyze_requirement(requirement_id, evidence)
            return analysis_result, 200
            
        except Exception as e:
            logger.error(f"Error analyzing requirement: {str(e)}")
            return {"error": "Internal server error"}, 500


@ns_analysis.route("/<string:analysis_id>")
class AnalysisResource(Resource):
    """
    Analysis resource endpoint.
    """
    
    @ns_analysis.response(200, "Analysis details", analysis_model)
    @ns_analysis.response(404, "Analysis not found")
    def get(self, analysis_id):
        """
        Get details for a specific analysis.
        """
        try:
            # In a real system, you would query a database
            analyses_file = os.path.join(app.config["UPLOAD_FOLDER"], "analyses.json")
            
            if not os.path.exists(analyses_file):
                abort(404, description="No analyses found")
                
            with open(analyses_file, "r") as f:
                analyses = json.load(f)
                
            analysis = next((a for a in analyses if a["id"] == analysis_id), None)
            
            if not analysis:
                abort(404, description="Analysis not found")
                
            result = analysis["result"]
            
            return {
                "id": analysis["id"],
                "form_id": analysis["form_id"],
                "timestamp": analysis["timestamp"],
                "overall_compliance": result.get("overall_compliance", False),
                "confidence": result.get("overall_confidence", 0.0),
                "findings": result.get("findings", []),
                "summary": result.get("summary", "Analysis completed")
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting analysis details: {str(e)}")
            return {"error": "Internal server error"}, 500


@ns_knowledge.route("/requirements")
class RequirementList(Resource):
    """
    Requirement list endpoint.
    """
    
    req_parser = reqparse.RequestParser()
    req_parser.add_argument("section", type=str, help="Filter by section number")
    req_parser.add_argument("criticality", type=str, help="Filter by criticality level")
    
    @ns_knowledge.expect(req_parser)
    @ns_knowledge.response(200, "List of requirements", [requirement_model])
    def get(self):
        """
        Get a list of CQI-9 requirements, optionally filtered.
        """
        try:
            args = self.req_parser.parse_args()
            section = args.get("section")
            criticality = args.get("criticality")
            
            # Build query based on filters
            query = "MATCH (r:Requirement)"
            
            if section:
                query += "\nMATCH (s:Section {number: $section})-[:CONTAINS]->(r)"
                
            if criticality:
                if "WHERE" not in query:
                    query += "\nWHERE"
                else:
                    query += "\nAND"
                query += " r.criticality = $criticality"
                
            query += "\nRETURN r"
            
            # Execute query
            results = graph_manager.graph.run(
                query,
                section=section,
                criticality=criticality
            ).data()
            
            # Format results
            requirements = []
            for result in results:
                req = dict(result["r"])
                requirements.append({
                    "id": req.get("id", "unknown"),
                    "text": req.get("text", ""),
                    "section": req.get("section", ""),
                    "category": req.get("category", ""),
                    "criticality": req.get("criticality", "")
                })
                
            return requirements, 200
            
        except Exception as e:
            logger.error(f"Error getting requirements: {str(e)}")
            return {"error": "Internal server error"}, 500


@ns_knowledge.route("/requirements/<string:requirement_id>")
class RequirementResource(Resource):
    """
    Requirement resource endpoint.
    """
    
    @ns_knowledge.response(200, "Requirement details", requirement_model)
    @ns_knowledge.response(404, "Requirement not found")
    def get(self, requirement_id):
        """
        Get details for a specific requirement.
        """
        try:
            # Get requirement context
            context = graph_manager.query_requirement_context(requirement_id)
            
            if not context:
                abort(404, description="Requirement not found")
                
            return {
                "id": context.get("id", "unknown"),
                "text": context.get("text", ""),
                "section": context.get("section", {}).get("number", "") if "section" in context else "",
                "category": context.get("category", ""),
                "criticality": context.get("criticality", ""),
                "related_requirements": context.get("related_requirements", {})
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting requirement details: {str(e)}")
            return {"error": "Internal server error"}, 500


if __name__ == "__main__":
    app.run(debug=active_config.DEBUG, host="0.0.0.0", port=5000)