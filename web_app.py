#!/usr/bin/env python3
"""
CQI-9 Web Application
===================

Standalone web application for the CQI-9 Compliance Analysis System.
"""

import os
import sys
import logging
import json
import io
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename

# Try importing PDF extraction libraries
try:
    import PyPDF2
    from pdfminer.high_level import extract_text
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logging.warning("PDF extraction libraries (PyPDF2, pdfminer.six) not installed. PDF upload functionality will be limited.")

# Create Flask application
app = Flask(__name__, 
            template_folder='web_portal/templates',
            static_folder='web_portal/static')

# Configuration
app.secret_key = 'cqi9-compliance-system-secret-key'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'data/uploads')
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'logs/web_app.log'))
    ]
)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file using pdfminer."""
    if not PDF_SUPPORT:
        return "PDF extraction libraries not installed."
    
    try:
        # First try with pdfminer
        try:
            text = extract_text(pdf_path)
        except Exception as e:
            logger.warning(f"pdfminer.six extraction failed: {str(e)}")
            text = ""
        
        # If pdfminer fails or returns empty text, try PyPDF2 as backup
        if not text.strip():
            logger.info("Falling back to PyPDF2 for text extraction")
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
        
        # Clean up the extracted text
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        # Add newlines before section titles to improve readability
        text = re.sub(r'(Section \d+|Management Responsibility|Shop Floor|Equipment|Job Audit)', r'\n\n\1', text)
        # Add newlines before requirement numbers
        text = re.sub(r'(\d+\.\d+|JA\.\d+)', r'\n\1', text)
        
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return f"Error extracting text: {str(e)}"

def extract_data_from_pdf(pdf_path):
    """
    Extract structured data from a CQI-9 audit PDF.
    Returns a JSON structure that matches our audit template.
    """
    if not PDF_SUPPORT:
        return {"error": "PDF extraction libraries not installed."}
    
    try:
        # Extract raw text from PDF
        text = extract_text_from_pdf(pdf_path)
        
        # Check if we got any meaningful text
        if not text or len(text.strip()) < 50:
            return {
                "error": "Could not extract meaningful text from the PDF. It may be scanned or contain images only.",
                "cover_sheet": {},
                "section1": {},
                "section2": {},
                "section3": {},
                "job_audit": {},
                "_metadata": {
                    "extraction_timestamp": datetime.now().isoformat(),
                    "pdf_filename": os.path.basename(pdf_path),
                    "pdf_size_bytes": os.path.getsize(pdf_path),
                    "text_extract_length": len(text) if text else 0,
                    "extraction_status": "limited",
                    "extraction_message": "Limited or no text extracted from PDF"
                }
            }
        
        # Preprocess the text to improve extraction
        # Replace multiple spaces and newlines with single spaces
        text = re.sub(r'\s+', ' ', text)
        # Add line breaks before section headers to help with extraction
        text = re.sub(r'(Section \d+[A-Za-z\s\-]*|Job Audit)', r'\n\1', text)
        # Add line breaks before requirement numbers
        text = re.sub(r'(\d+\.\d+|JA\.\d+)', r'\n\1', text)
        
        # Initialize the data structure
        audit_data = {
            "cover_sheet": {},
            "section1": {},
            "section2": {},
            "section3": {},
            "job_audit": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Extract organization information with more robust patterns
        org_patterns = {
            "supplier_name": r"(?:Supplier|Organization|Company)\s+Name:?\s*([^,\n\.]{2,50})",
            "supplier_code": r"(?:Supplier|Vendor|Organization)\s+Code:?\s*([A-Za-z0-9\-]{2,20})",
            "supplier_address": r"(?:Address|Location):?\s*([^,\n\.]{5,100})",
            "audit_date": r"(?:Assessment|Audit)\s+Date:?\s*(\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            "auditor_name": r"(?:Lead\s+)?(?:Assessor|Auditor)(?:'s)?\s+Name:?\s*([A-Za-z\.\s]{2,50})",
            "audit_type": r"Assessment\s+Type:?\s*([A-Za-z\s]{2,30})",
            "audit_scope": r"(?:Assessment|Audit)\s+Scope:?\s*([^,\n\.]{5,100})"
        }
        
        for field, pattern in org_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Take the first match
                audit_data["cover_sheet"][field] = matches[0].strip()
        
        # Extract job audit data with more robust patterns
        job_patterns = {
            "job_number": r"(?:Job|Part)\s*(?:Number|#|ID):?\s*([A-Za-z0-9\-]{2,30})",
            "part_name": r"Part\s+Name:?\s*([A-Za-z0-9\s\-]{2,50})",
            "material_spec": r"Material\s+(?:Specification|Spec):?\s*([A-Za-z0-9\s\-\.]{2,50})",
            "heat_treat_spec": r"Heat\s+Treat(?:ment)?\s+(?:Specification|Spec):?\s*([A-Za-z0-9\s\-\.]{2,50})",
            "equipment_used": r"Equipment\s+(?:Used|Utilized|Applied):?\s*([A-Za-z0-9\s\-\.]{2,100})",
            "process_class": r"Process\s+(?:Table\s+)?Class:?\s*([A-Za-z0-9\s\-\.]{1,20})",
            "set_temperature": r"Set\s+Temperature:?\s*(\d+\.?\d*)\s*[°℃CF]",
            "actual_temperature": r"Actual\s+Temperature:?\s*(\d+\.?\d*)\s*[°℃CF]",
            "soak_time": r"Soak\s+Time:?\s*(\d+\.?\d*)\s*(?:min|minutes)",
            "quench_media": r"Quench\s+Media:?\s*([A-Za-z0-9\s\-\.]{2,30})",
            "quench_temperature": r"Quench\s+Temperature:?\s*(\d+\.?\d*)\s*[°℃CF]",
            "quench_time": r"Quench\s+Time:?\s*(\d+\.?\d*)\s*(?:sec|min|seconds|minutes)"
        }
        
        for field, pattern in job_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                audit_data["job_audit"][field] = matches[0].strip()
        
        # Extract evidence for requirements with improved patterns
        # First divide the text into sections
        section_texts = {
            "section1": "",
            "section2": "",
            "section3": "",
            "job_audit": ""  # Note: Changed from "jobaudit" to "job_audit" to match our data structure
        }
        
        # Extract section text with more robust patterns
        section_matches = {
            "section1": re.search(r'Section\s+1.*?Management\s+Responsibility(.*?)(?:Section\s+2|$)', text, re.DOTALL | re.IGNORECASE),
            "section2": re.search(r'Section\s+2.*?Shop\s+Floor(.*?)(?:Section\s+3|$)', text, re.DOTALL | re.IGNORECASE),
            "section3": re.search(r'Section\s+3.*?Equipment(.*?)(?:Job\s+Audit|$)', text, re.DOTALL | re.IGNORECASE),
            "job_audit": re.search(r'Job\s+Audit(.*?)$', text, re.DOTALL | re.IGNORECASE)
        }
        
        for section, match in section_matches.items():
            if match:
                section_texts[section] = match.group(1)
        
        # Process each section to extract requirements and evidence
        for section, section_text in section_texts.items():
            if not section_text:
                continue
                
            # Extract requirements with evidence
            # Format: requirement number (like 1.1 or JA.1) followed by requirement text and evidence
            if section == "job_audit":
                requirement_pattern = r'(JA\.\d+)[:\.\s]+(.*?)(?=JA\.\d+|$)'
                prefix = "JA."
                target_section = "job_audit"  # Map to correct section in audit_data
            else:
                # For sections 1-3, extract requirements like 1.1, 2.3, etc.
                section_num = section[-1]  # Gets the number from section1, section2, etc.
                requirement_pattern = r'(' + section_num + r'\.\d+)[:\.\s]+(.*?)(?=' + section_num + r'\.\d+|$)'
                prefix = section_num + "."
                target_section = section  # Map to correct section in audit_data
            
            requirements = re.finditer(requirement_pattern, section_text, re.DOTALL)
            
            for req in requirements:
                req_id = req.group(1).strip()
                req_text = req.group(2).strip()
                
                # Extract evidence from requirement text
                evidence_match = re.search(r'(?:Evidence|Objective\s+Evidence):?\s*([^\n]+)', req_text, re.IGNORECASE)
                
                if evidence_match:
                    evidence = evidence_match.group(1).strip()
                else:
                    # If no explicit evidence tag, use the last sentence or part of text as evidence
                    sentences = re.split(r'[.!?]\s+', req_text)
                    evidence = sentences[-1].strip() if sentences else "N/A"
                
                # Format the requirement ID to match the form field names
                field_name = f"evidence_{req_id.replace('.', '_')}"
                
                # Clean up the evidence text
                evidence = re.sub(r'\s+', ' ', evidence).strip()
                evidence = "N/A" if not evidence or evidence.lower() == "n/a" else evidence
                
                audit_data[target_section][field_name] = evidence
            
            # If no requirements found, try a simpler pattern
            if not audit_data[target_section]:
                simple_pattern = r'(\d+\.\d+|JA\.\d+).*?(?:Evidence|Objective\s+Evidence):?\s*([^\n]+)'
                simple_matches = re.finditer(simple_pattern, section_text, re.IGNORECASE)
                
                for match in simple_matches:
                    req_id = match.group(1).strip()
                    evidence = match.group(2).strip()
                    
                    # Only add if this requirement belongs to this section
                    if req_id.startswith(prefix):
                        field_name = f"evidence_{req_id.replace('.', '_')}"
                        audit_data[target_section][field_name] = evidence
        
        # If there are still no extracted requirements, make one more attempt with a very simple pattern
        for section in ["section1", "section2", "section3", "job_audit"]:
            if not audit_data[section]:
                prefix = "JA." if section == "job_audit" else section[-1] + "."
                numbers_pattern = r'(' + prefix + r'\d+)'
                
                # Find all requirement numbers in the text
                req_numbers = re.findall(numbers_pattern, text)
                
                for req_id in req_numbers:
                    field_name = f"evidence_{req_id.replace('.', '_')}"
                    audit_data[section][field_name] = "See PDF for evidence"
        
        # Add sample data if no data was extracted at all
        if (not audit_data["cover_sheet"] and 
            not audit_data["section1"] and 
            not audit_data["section2"] and 
            not audit_data["section3"] and 
            not audit_data["job_audit"]):
            
            # Add some basic fields so the import doesn't completely fail
            audit_data["cover_sheet"] = {
                "supplier_name": "Unknown Supplier",
                "audit_date": datetime.now().strftime("%Y-%m-%d"),
                "auditor_name": "Unknown Auditor"
            }
            
            # Add a few sample requirements from each section
            audit_data["section1"]["evidence_1_1"] = "PDF extraction could not identify evidence. Please add manually."
            audit_data["section2"]["evidence_2_1"] = "PDF extraction could not identify evidence. Please add manually."
            audit_data["section3"]["evidence_3_1"] = "PDF extraction could not identify evidence. Please add manually."
            audit_data["job_audit"]["job_number"] = "Unknown"
        
        # Add metadata for debugging
        audit_data["_metadata"] = {
            "extraction_timestamp": datetime.now().isoformat(),
            "pdf_filename": os.path.basename(pdf_path),
            "pdf_size_bytes": os.path.getsize(pdf_path),
            "text_extract_length": len(text) if text else 0,
            "extraction_status": "partial" if any([
                audit_data["cover_sheet"], 
                audit_data["section1"],
                audit_data["section2"],
                audit_data["section3"],
                audit_data["job_audit"]
            ]) else "failed"
        }
        
        return audit_data
        
    except Exception as e:
        logger.error(f"Error extracting data from PDF: {str(e)}")
        # Return a basic structure with error info
        return {
            "error": f"Error extracting data: {str(e)}",
            "cover_sheet": {},
            "section1": {},
            "section2": {},
            "section3": {},
            "job_audit": {},
            "_metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "pdf_filename": os.path.basename(pdf_path) if pdf_path else "unknown",
                "extraction_status": "error",
                "error_message": str(e)
            }
        }

def generate_template_data():
    """
    Generate template data with placeholders when PDF extraction fails.
    This allows users to still get a structured template they can fill in.
    """
    now = datetime.now()
    
    # Create the basic template structure
    template_data = {
        "cover_sheet": {
            "supplier_name": "[Enter Supplier Name]",
            "supplier_code": "[Enter Supplier Code]",
            "supplier_address": "[Enter Supplier Address]",
            "audit_date": now.strftime("%Y-%m-%d"),
            "auditor_name": "[Enter Auditor Name]",
            "audit_type": "Regular Assessment",
            "audit_scope": "Heat Treatment Process Assessment"
        },
        "section1": {},  # Management Responsibility
        "section2": {},  # Shop Floor
        "section3": {},  # Equipment
        "job_audit": {
            "job_number": "[Enter Job Number]",
            "part_name": "[Enter Part Name]",
            "material_spec": "[Enter Material Specification]",
            "heat_treat_spec": "[Enter Heat Treatment Specification]",
            "equipment_used": "[Enter Equipment Used]",
            "process_class": "[Enter Process Class]",
            "set_temperature": "0",
            "actual_temperature": "0",
            "soak_time": "0",
            "quench_media": "[Enter Quench Media]",
            "quench_temperature": "0",
            "quench_time": "0"
        },
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "_metadata": {
            "extraction_timestamp": now.isoformat(),
            "extraction_status": "template",
            "template_reason": "PDF extraction failed or was not possible"
        }
    }
    
    # Add Section 1 - Management Responsibility placeholders
    for i in range(1, 15):
        req_id = f"1_{i}"
        template_data["section1"][f"evidence_{req_id}"] = f"[Enter evidence for requirement 1.{i}]"
    
    # Add Section 2 - Shop Floor placeholders
    for i in range(1, 10):
        req_id = f"2_{i}"
        template_data["section2"][f"evidence_{req_id}"] = f"[Enter evidence for requirement 2.{i}]"
    
    # Add Section 3 - Equipment placeholders
    for i in range(1, 13):
        req_id = f"3_{i}"
        template_data["section3"][f"evidence_{req_id}"] = f"[Enter evidence for requirement 3.{i}]"
    
    return template_data

@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/audit/new')
def new_audit():
    """Render the new audit page with all tabs."""
    return render_template('audit.html')

@app.route('/audit/upload', methods=['GET', 'POST'])
def upload_audit():
    """Handle PDF audit file upload and extraction."""
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'pdf_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['pdf_file']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Secure the filename to prevent any security issues
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Extract data from the PDF
            audit_data = extract_data_from_pdf(file_path)
            
            if "error" in audit_data:
                flash(f"Error extracting data: {audit_data['error']}")
                return redirect(request.url)
            
            # Generate a unique ID for the audit
            audit_id = datetime.now().strftime("%Y%m%d%H%M%S")
            audit_data['audit_id'] = audit_id
            
            # Save the extracted data
            audits_dir = os.path.join(app.config["UPLOAD_FOLDER"], "audits")
            os.makedirs(audits_dir, exist_ok=True)
            
            file_path = os.path.join(audits_dir, f"audit_{audit_id}.json")
            with open(file_path, 'w') as f:
                json.dump(audit_data, f, indent=2)
            
            # Redirect to the audit page with the extracted data
            return redirect(url_for('view_audit', audit_id=audit_id))
        else:
            flash('File type not allowed. Please upload a PDF file.')
            return redirect(request.url)
    
    # GET request - show upload form
    return render_template('upload.html')

@app.route('/audit/save', methods=['POST'])
def save_audit():
    """Save the audit data."""
    try:
        audit_data = request.json
        
        # Generate a unique ID for the audit if not already present
        audit_id = audit_data.get('audit_id', datetime.now().strftime("%Y%m%d%H%M%S"))
        
        # Add/update metadata
        audit_data['audit_id'] = audit_id
        if 'created_at' not in audit_data:
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
        
        return render_template('audit.html', audit_data=audit_data)
    
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
    """Analyze a requirement against evidence using AI."""
    try:
        data = request.json
        requirement = data.get('requirement')
        evidence = data.get('evidence')
        
        # In a real application, this would call the AI engine
        # For now, we'll return a dummy response
        analysis = {
            'compliant': True,
            'confidence': 0.85,
            'explanation': f"The provided evidence appears to satisfy the requirement. Evidence shows appropriate documentation and process controls in place."
        }
        
        return jsonify(analysis)
        
    except Exception as e:
        logger.error(f"Error analyzing requirement: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/extract-pdf-preview', methods=['POST'])
def extract_pdf_preview():
    """Extract and preview text from a PDF file."""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['pdf_file']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
            
        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed. Please upload a PDF."}), 400
        
        # Create a temporary file
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_' + secure_filename(file.filename))
        file.save(temp_path)
        
        # Check if user requested template mode
        template_mode = request.form.get('template_mode', 'false').lower() == 'true'
        
        if template_mode:
            # Generate template data without attempting extraction
            structured_data = generate_template_data()
            
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            return jsonify({
                "success": True,
                "extraction_quality": "template",
                "warning": "Using template mode as requested. No actual extraction was performed.",
                "text_preview": "Template mode activated. No text extraction was performed.",
                "structured_data": structured_data
            })
        
        # Extract text
        extracted_text = extract_text_from_pdf(temp_path)
        
        # Check if we have meaningful text
        if not extracted_text or len(extracted_text.strip()) < 50:
            # Generate template data for fallback
            structured_data = generate_template_data()
            
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            return jsonify({
                "success": False,
                "warning": "Limited or no text could be extracted from this PDF.",
                "text_preview": "The PDF appears to contain mostly images or scanned content that cannot be extracted as text.",
                "extraction_issues": [
                    "PDF may be scanned or contain mostly images",
                    "PDF may be encrypted or have security settings",
                    "PDF structure may not be machine-readable"
                ],
                "structured_data": structured_data
            })
        
        # Extract structured data
        structured_data = extract_data_from_pdf(temp_path)
        
        # Check if extraction completely failed
        if (not structured_data.get("cover_sheet") and 
            not structured_data.get("section1") and 
            not structured_data.get("section2") and 
            not structured_data.get("section3") and 
            not structured_data.get("job_audit")):
            
            # Use template data but preserve the extracted text
            template_data = generate_template_data()
            structured_data = template_data
            
            # Add metadata about partial extraction
            structured_data["_metadata"]["extraction_status"] = "template_with_text"
            structured_data["_metadata"]["extraction_message"] = "Using template with extracted text"
        
        # Assess extraction quality
        extraction_quality = "high"
        extraction_issues = []
        
        # Check for error
        if "error" in structured_data:
            extraction_quality = "error"
            extraction_issues.append(structured_data["error"])
        else:
            # Check metadata
            metadata = structured_data.get("_metadata", {})
            if metadata.get("extraction_status") in ["failed", "error", "limited", "template", "template_with_text"]:
                extraction_quality = "low"
                if metadata.get("extraction_status").startswith("template"):
                    extraction_issues.append("Using template data as fallback")
                else:
                    extraction_issues.append("Failed to extract structured data from the PDF")
            
            # Check for empty sections
            empty_sections = []
            if not structured_data.get("cover_sheet"):
                empty_sections.append("Organization Information")
            if not structured_data.get("job_audit"):
                empty_sections.append("Job Audit Information")
            if not structured_data.get("section1"):
                empty_sections.append("Section 1 Requirements")
            if not structured_data.get("section2"):
                empty_sections.append("Section 2 Requirements")
            if not structured_data.get("section3"):
                empty_sections.append("Section 3 Requirements")
                
            if empty_sections:
                extraction_quality = "medium" if extraction_quality == "high" else extraction_quality
                extraction_issues.append(f"No data extracted for: {', '.join(empty_sections)}")
        
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Prepare response with quality assessment
        response_data = {
            "success": True, 
            "extraction_quality": extraction_quality,
            "extraction_issues": extraction_issues if extraction_issues else None,
            "text_preview": extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text,
            "structured_data": structured_data
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error extracting PDF preview: {str(e)}")
        
        # Generate template data for error fallback
        structured_data = generate_template_data()
        
        return jsonify({
            "error": str(e),
            "extraction_quality": "error",
            "extraction_issues": [f"Error processing PDF: {str(e)}"],
            "structured_data": structured_data
        }), 500

if __name__ == '__main__':
    # Run the application
    port = int(os.environ.get("PORT", 5555))
    app.run(host='0.0.0.0', port=port, debug=True) 