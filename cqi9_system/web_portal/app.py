#!/usr/bin/env python3
"""
CQI-9 Web Portal Application
===========================

This module provides the web interface for the CQI-9 Compliance Analysis System.
"""

import os
import logging
import json
import requests
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename

# Set up basic configuration
class Config:
    """Simple configuration class for the web portal."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-cqi9-system')
    DEBUG = True
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data/uploads")
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs/cqi9_system.log")

# Set up logging
os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Config.LOG_FILE)
    ]
)

logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Create upload directory if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/audit/new')
def new_audit():
    """Render the new audit page with all tabs."""
    return render_template('audit_original.html')

@app.route('/audit/save', methods=['POST'])
def save_audit():
    """Save the audit data."""
    try:
        audit_data = request.json
        
        # Generate a unique ID for the audit
        audit_id = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Add metadata
        audit_data['audit_id'] = audit_id
        audit_data['created_at'] = datetime.now().isoformat()
        audit_data['updated_at'] = datetime.now().isoformat()
        
        # Save to file (in a real application, this would go to a database)
        audits_dir = os.path.join(app.config["UPLOAD_FOLDER"], "audits")
        os.makedirs(audits_dir, exist_ok=True)
        
        file_path = os.path.join(audits_dir, f"audit_{audit_id}.json")
        with open(file_path, 'w') as f:
            json.dump(audit_data, f, indent=2)
        
        return jsonify({"success": True, "audit_id": audit_id})
    
    except Exception as e:
        logger.error(f"Error saving audit: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/audit/<audit_id>')
def view_audit(audit_id):
    """View an existing audit."""
    try:
        # In a real application, this would come from a database
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], "audits", f"audit_{audit_id}.json")
        
        if not os.path.exists(file_path):
            flash("Audit not found")
            return redirect(url_for('index'))
        
        with open(file_path, 'r') as f:
            audit_data = json.load(f)
        
        return render_template('audit_original.html', audit_data=audit_data)
    
    except Exception as e:
        logger.error(f"Error viewing audit {audit_id}: {str(e)}")
        flash(f"Error loading audit: {str(e)}")
        return redirect(url_for('index'))

@app.route('/audits')
def list_audits():
    """List all audits."""
    try:
        audits = []
        audits_dir = os.path.join(app.config["UPLOAD_FOLDER"], "audits")
        
        if os.path.exists(audits_dir):
            for filename in os.listdir(audits_dir):
                if filename.startswith("audit_") and filename.endswith(".json"):
                    file_path = os.path.join(audits_dir, filename)
                    with open(file_path, 'r') as f:
                        audit_data = json.load(f)
                    
                    audits.append({
                        'id': audit_data.get('audit_id'),
                        'supplier': audit_data.get('cover_sheet', {}).get('supplier_name', 'Unknown'),
                        'date': audit_data.get('cover_sheet', {}).get('audit_date', 'Unknown'),
                        'status': audit_data.get('status', 'In Progress')
                    })
        
        return render_template('audits.html', audits=audits)
    
    except Exception as e:
        logger.error(f"Error listing audits: {str(e)}")
        flash(f"Error loading audits: {str(e)}")
        return render_template('audits.html', audits=[])

@app.route('/api/analyze', methods=['POST'])
def analyze_requirement():
    data = request.json
    requirement_id = data.get('requirement_id')
    requirement = data.get('requirement')
    evidence = data.get('evidence')

    if not requirement_id or not requirement or not evidence:
        return jsonify({
            'compliant': False,
            'explanation': 'Missing required data for analysis.',
            'confidence': 0.0
        }), 400

    # For testing/debugging
    app.logger.info(f"Analyzing requirement {requirement_id}: {requirement[:50]}...")
    app.logger.info(f"Evidence: {evidence[:50]}...")

    # Use Deepseek API for analysis
    deepseek_api_key = "sk-5f9e03d0ca764c0bb2913ab6751b897a"

    # Special handling for section 1.1 requirements
    if requirement_id.startswith('1.1.'):
        return analyze_section_1_1(requirement_id, requirement, evidence, deepseek_api_key)

    # General analysis for other sections
    try:
        response = analyze_general_requirement(requirement_id, requirement, evidence, deepseek_api_key)
        if not response or 'compliant' not in response:
            raise ValueError("Invalid response format from DeepSeek API")
        return response
    except Exception as e:
        app.logger.error(f"Error during analysis: {str(e)}")
        return jsonify({
            'compliant': False,
            'explanation': 'Error during analysis.',
            'confidence': 0.0
        }), 500

def analyze_section_1_1(requirement_id, requirement, evidence, api_key):
    """
    Special analysis for section 1.1 requirements that evaluates whether the evidence
    is explanatory rather than just simple yes/no answers.
    """
    prompt = f"""
You are a CQI-9 audit assessment expert analyzing objective evidence for heat treatment quality requirements.

Requirement ID: {requirement_id}
Requirement: {requirement}

Objective Evidence provided: 
"{evidence}"

Evaluate the objective evidence against the requirement based on these criteria:
1. Is the evidence relevant to the specific requirement?
2. Is the evidence detailed and explanatory, rather than just simple "yes/no" statements?
3. Does the evidence provide specific examples, details, or references to documents?
4. Can you determine if the requirement is being met based on the evidence?

Your analysis must follow these rules:
- If the evidence consists of only simple answers like "yes", "no", "followed", or similarly brief statements, the evidence is NOT SATISFACTORY with a remark that "very limited objective evidence observed".
- Evidence must be explanatory with specific details to be considered satisfactory.
- Base your assessment solely on the evidence provided, not assumptions.

Provide your analysis in this JSON format:
{{
  "compliant": true or false,
  "explanation": "Your detailed analysis explaining why the evidence is either satisfactory or not satisfactory",
  "confidence": 0.0 to 1.0 (your confidence in this assessment)
}}
"""

    try:
        # Call the Deepseek API
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a CQI-9 heat treatment quality audit expert."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=30  # 30 second timeout
        )
        
        response_data = response.json()
        
        if 'choices' in response_data and len(response_data['choices']) > 0:
            ai_response = response_data['choices'][0]['message']['content']
            try:
                analysis_result = json.loads(ai_response)
                return jsonify(analysis_result)
            except json.JSONDecodeError:
                app.logger.error(f"Failed to parse Deepseek JSON response: {ai_response}")
                return jsonify({
                    'compliant': False,
                    'explanation': f"Error analyzing evidence: Could not parse AI response. Please try again.",
                    'confidence': 0.0
                }), 500
        else:
            app.logger.error(f"Unexpected response from Deepseek API: {response_data}")
            return jsonify({
                'compliant': False,
                'explanation': "Error analyzing evidence: Unexpected API response. Please try again.",
                'confidence': 0.0
            }), 500
            
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error calling Deepseek API: {str(e)}")
        return jsonify({
            'compliant': False,
            'explanation': f"Error analyzing evidence: {str(e)}",
            'confidence': 0.0
        }), 500

def analyze_general_requirement(requirement_id, requirement, evidence, api_key):
    """
    General analysis for other requirement sections.
    """
    prompt = f"""
You are a CQI-9 audit assessment expert analyzing objective evidence for heat treatment quality requirements.

Requirement ID: {requirement_id}
Requirement: {requirement}

Objective Evidence provided: 
"{evidence}"

Evaluate whether the provided objective evidence satisfies the requirement. 
Give a detailed explanation of your assessment.

Your analysis must follow these rules:
- If the evidence consists of only simple answers like "yes", "no", "followed", without further explanation, the evidence is NOT SATISFACTORY.
- Evidence must be explanatory with specific details to be considered satisfactory.
- Base your assessment solely on the evidence provided, not assumptions.

Provide your analysis in this JSON format:
{{
  "compliant": true or false,
  "explanation": "Your detailed analysis explaining why the evidence is either satisfactory or not satisfactory",
  "confidence": 0.0 to 1.0 (your confidence in this assessment)
}}
"""

    try:
        # Call the Deepseek API
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a CQI-9 heat treatment quality audit expert."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=30  # 30 second timeout
        )
        
        response_data = response.json()
        
        if 'choices' in response_data and len(response_data['choices']) > 0:
            ai_response = response_data['choices'][0]['message']['content']
            try:
                analysis_result = json.loads(ai_response)
                return jsonify(analysis_result)
            except json.JSONDecodeError:
                app.logger.error(f"Failed to parse Deepseek JSON response: {ai_response}")
                return jsonify({
                    'compliant': False,
                    'explanation': f"Error analyzing evidence: Could not parse AI response. Please try again.",
                    'confidence': 0.0
                }), 500
        else:
            app.logger.error(f"Unexpected response from Deepseek API: {response_data}")
            return jsonify({
                'compliant': False,
                'explanation': "Error analyzing evidence: Unexpected API response. Please try again.",
                'confidence': 0.0
            }), 500
            
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error calling Deepseek API: {str(e)}")
        return jsonify({
            'compliant': False,
            'explanation': f"Error analyzing evidence: {str(e)}",
            'confidence': 0.0
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)