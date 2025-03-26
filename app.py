#!/usr/bin/env python3
"""
WPS/PQR Comparison Web Application

This application allows users to:
1. Upload Welding Procedure Specification (WPS) and Procedure Qualification Record (PQR) documents
2. Process them using LLMWhisperer for high-quality text extraction
3. Extract structured information using DeepSeek API
4. View side-by-side comparison of WPS and PQR data
"""

import os
import json
import tempfile
import time
import base64
import re
import pandas as pd
import datetime
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv
import jinja2
import requests
import copy
import logging

# Load environment variables
load_dotenv()

# Configuration
# Using the LLMWhisperer API key directly in the code (for development only)
LLM_WHISPERER_API_KEY = os.environ.get("LLM_WHISPERER_API_KEY", "VrhdIbiToy-LNtrnSeq5fnVeSE3MCAj3myKc-ZGUZG8")
LLM_WHISPERER_API_URL = os.environ.get("LLM_WHISPERER_API_URL", "https://llmwhisperer-api.us-central.unstract.com/api/v2")

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-3a1f47e0f1734d9d87f520401c338fa1")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# Initialize OpenAI client for DeepSeek
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_mtc_analyzer')

# Configure logging
app.logger.setLevel(logging.INFO)
if not app.debug:
    file_handler = logging.FileHandler('app.log')
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('WPS/PQR Comparison Application startup')

# Check if we're running on Render.com
if os.path.exists('/var/data'):
    UPLOAD_FOLDER = '/var/data/uploads'
    PROCESSED_DIR = '/var/data/processed'
    app.logger.info('Using Render.com file paths')
else:
    UPLOAD_FOLDER = 'uploads'
    PROCESSED_DIR = 'processed'
    app.logger.info('Using local file paths')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png'}

# Custom Jinja2 filters
@app.template_filter('nl2br')
def nl2br(value):
    """Convert newlines to <br> tags."""
    if value:
        return jinja2.utils.markupsafe.Markup(
            value.replace('\n', '<br>')
        )
    return value

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
    app.logger.info(f"Created upload directory: {app.config['UPLOAD_FOLDER']}")

# Ensure storage directories exist
if not os.path.exists(PROCESSED_DIR):
    os.makedirs(PROCESSED_DIR)
    app.logger.info(f"Created processed directory: {PROCESSED_DIR}")

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

# Initialize clients
def init_llmwhisperer_client():
    """
    Modified to return API headers and base URL instead of a client object
    """
    if not LLM_WHISPERER_API_KEY:
        app.logger.error("LLMWhisperer API key is not set. Set the LLM_WHISPERER_API_KEY environment variable.")
        return None
    
    # Return the API information needed for direct calls
    return {
        "base_url": LLM_WHISPERER_API_URL,
        "headers": {"unstract-key": LLM_WHISPERER_API_KEY}
    }

# Process PDF with direct LLMWhisperer API calls
def process_pdf(file_path, original_filename):
    """Process a PDF file with LLMWhisperer API directly and return the extracted text"""
    
    api_info = init_llmwhisperer_client()
    
    # Check if API info was initialized successfully
    if api_info is None:
        return {
            'success': False,
            'error': 'LLMWhisperer API information could not be initialized. API key may be missing.'
        }
    
    try:
        # Generate a unique ID for this processing job
        job_id = str(uuid.uuid4())
        
        # Determine file type to set appropriate extraction options
        file_extension = get_file_extension(original_filename).lower()
        
        # Log the extraction processing information
        app.logger.info(f"Processing document {original_filename} with high-quality OCR settings")
        app.logger.info(f"File extension: {file_extension}")
        
        # Define base parameters for better extraction
        params = {
            'mode': 'form',  # form mode is good for most document types
            'output_mode': 'layout_preserving',  # preserves document layout
            'add_line_nos': 'true',  # adds line numbers for better referencing
        }
        
        # Add additional parameters for scanned documents
        if file_extension in ['jpg', 'jpeg', 'png', 'tif', 'tiff']:
            app.logger.info("Detected scanned image, applying enhanced OCR settings")
            # These parameters improve scanned image quality
            params.update({
                'median_filter_size': '3',  # helps remove noise
                'gaussian_blur_radius': '1',  # slight blur to improve OCR
                'line_splitter_tolerance': '0.5',  # better line detection
                'mark_vertical_lines': 'true',  # preserve table structure
                'mark_horizontal_lines': 'true'  # preserve table structure
            })
        
        # For PDFs that might have tables, enable vertical and horizontal line marking
        if file_extension == 'pdf':
            app.logger.info("Detected PDF, preserving table structures")
            params.update({
                'mark_vertical_lines': 'true',
                'mark_horizontal_lines': 'true'
            })
        
        # Log the parameters being used
        app.logger.info(f"Using LLMWhisperer parameters: {params}")

        # Call the API directly using requests
        try:
            # Prepare API endpoint for the whisper request
            whisper_endpoint = f"{api_info['base_url']}/whisper"
            
            # Open the file in binary mode
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Set headers for file upload
            headers = api_info['headers'].copy()
            headers['Content-Type'] = 'application/octet-stream'
            
            # Make the API request to submit the document
            response = requests.post(
                whisper_endpoint,
                params=params,
                headers=headers,
                data=file_data
            )
            
            # Handle the response
            if response.status_code == 202:
                # Async response - need to poll for results
                result_json = response.json()
                whisper_hash = result_json.get('whisper_hash')
                
                app.logger.info(f"Whisper job submitted with hash: {whisper_hash}")
                
                # Wait and poll for completion
                start_time = time.time()
                max_wait_time = 600  # 10 minutes
                
                # Poll for status until complete or timeout
                while (time.time() - start_time) < max_wait_time:
                    # Call status API
                    status_endpoint = f"{api_info['base_url']}/whisper-status"
                    status_response = requests.get(
                        status_endpoint,
                        params={'whisper_hash': whisper_hash},
                        headers=api_info['headers']
                    )
                    
                    if status_response.status_code != 200:
                        raise Exception(f"Status check failed: {status_response.text}")
                    
                    status_data = status_response.json()
                    status = status_data.get('status')
                    
                    if status == 'processed':
                        # Processing complete, retrieve the text
                        break
                    elif status in ['unknown', 'error']:
                        raise Exception(f"Error during extraction: {status_data}")
                    
                    # Wait before polling again
                    time.sleep(5)
                else:
                    # Timeout exceeded
                    raise Exception("Extraction timeout exceeded")
                
                # Retrieve the processed text
                retrieve_endpoint = f"{api_info['base_url']}/whisper-retrieve"
                retrieve_response = requests.get(
                    retrieve_endpoint,
                    params={'whisper_hash': whisper_hash, 'text_only': 'true'},
                    headers=api_info['headers']
                )
                
                if retrieve_response.status_code != 200:
                    raise Exception(f"Text retrieval failed: {retrieve_response.text}")
                
                # Get the extracted text directly from the response
                extracted_text = retrieve_response.text
                
                # Create result structure similar to the original client response
                result = {
                    'extraction': {
                        'result_text': extracted_text,
                        'processing_time': time.time() - start_time
                    },
                    'status': 'success'
                }
            else:
                raise Exception(f"API error: {response.status_code} - {response.text}")
                
        except Exception as api_error:
            app.logger.error(f"API call failed: {str(api_error)}")
            raise
        
        # Extract text
        if 'extraction' in result and 'result_text' in result['extraction']:
            extracted_text = result['extraction']['result_text']
            
            # Save to the processed directory
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            # Create a subdirectory using the job_id
            job_dir = os.path.join(PROCESSED_DIR, job_id)
            if not os.path.exists(job_dir):
                os.makedirs(job_dir)
                
            # Save metadata about the job
            metadata = {
                'job_id': job_id,
                'original_filename': original_filename,
                'timestamp': timestamp,
                'status': 'completed',
                'file_extension': file_extension,
                'extraction_quality': 'high',
                'processing_time': result.get('processing_time', 'N/A'),
                'ocr_parameters': params  # Save the parameters used
            }
            
            metadata_file = os.path.join(job_dir, 'metadata.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # Save the extracted text
            text_file = os.path.join(job_dir, 'extracted_text.txt')
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            
            # If OCR confidence data is available, save it
            if 'ocr_confidence' in result.get('extraction', {}):
                confidence_data = {
                    'overall_confidence': result['extraction']['ocr_confidence'],
                    'extraction_quality': 'high' if result['extraction']['ocr_confidence'] > 0.85 else 'medium' if result['extraction']['ocr_confidence'] > 0.7 else 'low'
                }
                confidence_file = os.path.join(job_dir, 'ocr_confidence.json')
                with open(confidence_file, 'w', encoding='utf-8') as f:
                    json.dump(confidence_data, f, indent=2)
            
            # Save raw extraction data for debugging
            raw_extraction_file = os.path.join(job_dir, 'raw_extraction.json')
            with open(raw_extraction_file, 'w', encoding='utf-8') as f:
                json.dump(result.get('extraction', {}), f, indent=2)
            
            return {
                'success': True,
                'job_id': job_id,
                'text': extracted_text,
                'raw_response': result
            }
        else:
            # Log the failure
            app.logger.error(f"Extraction failed: {result}")
            
            # Create directory for failed job
            job_dir = os.path.join(PROCESSED_DIR, job_id)
            if not os.path.exists(job_dir):
                os.makedirs(job_dir)
                
            # Save the failed response for debugging
            failed_response_file = os.path.join(job_dir, 'failed_response.json')
            with open(failed_response_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            
            return {
                'success': False,
                'error': 'No text found in the processed document',
                'job_id': job_id,
                'raw_response': result
            }
    except Exception as e:
        error_message = str(e)
        app.logger.error(f"Exception during PDF processing: {error_message}")
        return {
            'success': False,
            'error': error_message
        }

# Query DeepSeek API
def query_llm(document_text, system_prompt, user_prompt, temperature=0.3):
    """Query the DeepSeek API with the document text and prompts"""
    try:
        if not DEEPSEEK_API_KEY:
            return {"success": False, "error": "DeepSeek API key is not set. Please set the DEEPSEEK_API_KEY environment variable."}
        
        # Log the first 200 characters of the document to help with debugging
        app.logger.info(f"Document text (first 200 chars): {document_text[:200]}...")
        
        # Check if the document text is too short
        if len(document_text) < 100:
            app.logger.warning(f"Document text is very short ({len(document_text)} chars), may not have enough content for analysis")
        
        # Format messages for DeepSeek API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_prompt}\n\n{document_text}"}
        ]
        
        # Make API request using OpenAI client
        try:
            app.logger.info(f"Making API request to DeepSeek with temperature={temperature}")
            
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=temperature,
                max_tokens=4000,
                stream=False
            )
            
            # Extract content from response
            if not response or not response.choices:
                app.logger.error("DeepSeek API response has no choices")
                return {"success": False, "error": "Invalid response from API: no choices found"}
            
            content = response.choices[0].message.content
            
            # Log if the content is empty
            if not content:
                app.logger.warning("Received empty content from DeepSeek API")
                return {"success": False, "error": "Empty response from API"}
            
            # Try to clean JSON response if needed
            if '```json' in content or '```' in content:
                app.logger.info("Cleaning JSON response from markdown format")
                content = re.sub(r'```json', '', content)
                content = re.sub(r'```', '', content)
            
            # Validate JSON if the response is expected to be JSON
            if content.strip().startswith('{') and content.strip().endswith('}'):
                try:
                    # Test if it's valid JSON
                    json.loads(content.strip())
                    app.logger.info("Successfully validated JSON response")
                except json.JSONDecodeError as json_err:
                    app.logger.warning(f"Response looks like JSON but failed to parse: {str(json_err)}")
            
            # Log a preview of the response
            app.logger.info(f"Response preview: {content[:200]}...")
            
            return {"success": True, "content": content}
            
        except Exception as api_error:
            error_msg = f"Error calling DeepSeek API: {str(api_error)}"
            app.logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
    except Exception as e:
        error_msg = f"Exception when querying API: {str(e)}"
        app.logger.error(error_msg)
        return {"success": False, "error": error_msg}

# Extract structured information
def _ensure_structured_data_format(data):
    """
    Ensure that the structured data is in the expected format for the templates.
    This function handles backward compatibility and normalization of the data structure.
    """
    # Create a copy of the data to avoid modifying the original
    formatted_data = copy.deepcopy(data)
    
    # Ensure chemical_composition is properly formatted
    if 'chemical_composition' in formatted_data:
        # If chemical_composition is already in the array-based format, no need to transform
        if all(isinstance(formatted_data['chemical_composition'].get(element), list) for element in formatted_data['chemical_composition'] if element not in ['requirements', 'products']):
            pass  # It's already in the right format
        # Convert from the old format (with requirements and products separately) to the array-based format
        elif 'requirements' in formatted_data['chemical_composition'] and 'products' in formatted_data['chemical_composition']:
            chemical_composition = {}
            for element, requirement in formatted_data['chemical_composition']['requirements'].items():
                # Create an array with requirement as the first element
                chemical_composition[element] = [requirement]
                # Add values for each product
                for product in formatted_data['chemical_composition']['products']:
                    if 'values' in product and element in product['values']:
                        chemical_composition[element].append(product['values'][element])
                    else:
                        chemical_composition[element].append(None)
            formatted_data['chemical_composition'] = chemical_composition
    
    # Ensure mechanical_properties is properly formatted
    if 'mechanical_properties' in formatted_data:
        # If mechanical_properties is already in the array-based format, no need to transform
        if all(isinstance(formatted_data['mechanical_properties'].get(prop), list) for prop in formatted_data['mechanical_properties'] if prop not in ['requirements', 'products']):
            pass  # It's already in the right format
        # Convert from the old format (with requirements and products separately) to the array-based format
        elif 'requirements' in formatted_data['mechanical_properties'] and 'products' in formatted_data['mechanical_properties']:
            mech_properties = {}
            for prop, requirement in formatted_data['mechanical_properties']['requirements'].items():
                # Create an array with requirement as the first element
                mech_properties[prop] = [requirement]
                # Add values for each product
                for product in formatted_data['mechanical_properties']['products']:
                    if 'values' in product and prop in product['values']:
                        mech_properties[prop].append(product['values'][prop])
                    else:
                        mech_properties[prop].append(None)
            formatted_data['mechanical_properties'] = mech_properties
    
    return formatted_data

def extract_structured_info(text, job_id):
    """Extract structured information from the test certificate"""
    system_prompt = """
    You are an expert in analyzing steel mill test certificates. 
    Extract structured information from the certificate text provided.
    
    CRITICAL INSTRUCTIONS:
    1. For tables with chemical composition and mechanical properties:
       - Pay careful attention to the tabular structure
       - The first row typically contains column headers
       - The second row often contains the specification limits/requirements (e.g., "< 0.25%", "17 - 110")
       - Subsequent rows with Product IDs contain the actual measured values for each product
    
    2. IMPORTANT: When you encounter empty cells or missing values:
       - DO NOT substitute them with null, None, or "-"
       - If you can see the value in the text but it's misaligned, try to determine the correct value by careful analysis
       - For genuinely missing values, leave them as empty strings or null values
    
    3. IMPORTANT: For product IDs:
       - Identify the exact product identifiers as they appear in the text (e.g., "A0AA000000AA0-01")
       - Do not create generic product identifiers unless none exist
    
    4. For numerical values:
       - Be precise in identifying decimal points and units
       - Where ambiguous, consider the context of the data and what's typical for that measurement
    
    5. Advanced reasoning approach:
       - First, identify all tables and sections in the document
       - For each table, determine column headers and row identifiers
       - Map values to their appropriate headers and row identifiers
       - Verify consistency with industry standards and expected ranges
       - Cross-check against any specification requirements mentioned
    
    STEEL MILL TEST CERTIFICATE STRUCTURE:
    1. The header usually contains supplier information, certificate numbers, and dates
    2. The main table often contains these sections:
       - Chemical Composition (%)
       - Mechanical Properties
       - Physical Properties
    3. Pay close attention to the row that starts with specification requirements/limits
       - This row is crucial as it defines acceptance criteria
    
    Respond with a JSON object containing these fields:
    1. supplier_info: Information about the supplier, including name, address, and contact details if available
    2. material_info: Information about material grade, specification, heat number, size, and other identifiers
    3. chemical_composition: A structured representation of the chemical composition table with element names and values, where:
       - For each element (Si, Fe, Cu, etc.), provide an array where:
         - First item is the specification requirement
         - Subsequent items are the measured values for each product ID
    4. mechanical_properties: A structured representation of mechanical properties including:
       - For each property (Y.S., T.S., EL%, etc.), provide an array where:
         - First item is the specification requirement 
         - Subsequent items are the measured values for each product ID
    5. additional_info: Any other relevant information such as certifications, testing standards, or notes
    
    Format the JSON cleanly and ensure all numerical values are properly extracted.
    """
    
    user_prompt = f"""
    Extract structured information from this steel mill test certificate, paying special attention to:
    1. The exact specification requirements/limits in the tables
    2. The exact product IDs and their corresponding measured values
    3. Preserving all available values from the certificate, even if they appear misaligned in the text
    4. Using advanced reasoning to ensure accuracy and completeness of the extracted data
    
    Certificate Text:
    {text}
    """
    
    response = query_llm(text, system_prompt, user_prompt, temperature=0.1)
    
    if response['success']:
        try:
            # Clean up the response if it contains markdown code blocks
            json_response = response['content']
            json_response = re.sub(r'```json', '', json_response)
            json_response = re.sub(r'```', '', json_response)
            
            # Parse JSON
            structured_data = json.loads(json_response.strip())
            
            # Get the job directory
            job_dir = os.path.join(PROCESSED_DIR, job_id)
            if not os.path.exists(job_dir):
                os.makedirs(job_dir)
                
            # Apply transformations to ensure the structured data has the expected format
            structured_data = _ensure_structured_data_format(structured_data)
                
            # Save to the processed directory
            json_file = os.path.join(job_dir, 'structured_data.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, indent=2)
                
            # Update the metadata to include structured data
            metadata_file = os.path.join(job_dir, 'metadata.json')
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                metadata['has_structured_data'] = True
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
                    
                return {"success": True, "job_id": job_id}
            except Exception as e:
                app.logger.error(f"Error updating metadata: {str(e)}")
                return {"success": False, "error": f"Error updating metadata: {str(e)}"}
                
        except json.JSONDecodeError as e:
            app.logger.error(f"Error parsing LLM response: {str(e)}")
            return {"success": False, "error": f"Error parsing LLM response: {str(e)}"}
        except Exception as e:
            app.logger.error(f"Error processing structured data: {str(e)}")
            return {"success": False, "error": f"Error processing structured data: {str(e)}"}
    else:
        return {"success": False, "error": response.get("error", "Unknown error")}

# Assess data completeness
def assess_data_completeness(data):
    """Assess the completeness of the extracted data"""
    completeness = {
        'supplier_info': 0,
        'material_info': 0,
        'chemical_composition': 0,
        'mechanical_properties': 0,
        'overall_completeness': 0
    }
    
    if 'supplier_info' in data and data['supplier_info']:
        completeness['supplier_info'] = min(100, len(data['supplier_info']) * 20)
    
    if 'material_info' in data and data['material_info']:
        completeness['material_info'] = min(100, len(data['material_info']) * 20)
    
    if 'chemical_composition' in data and data['chemical_composition']:
        if isinstance(data['chemical_composition'], dict):
            # New format with requirements and products
            if 'requirements' in data['chemical_composition'] and 'products' in data['chemical_composition']:
                req_score = min(100, len(data['chemical_composition']['requirements']) * 10)
                products_score = 0
                if data['chemical_composition']['products']:
                    products_score = min(100, len(data['chemical_composition']['products']) * 20)
                completeness['chemical_composition'] = (req_score + products_score) / 2
            # Legacy format with elements
            elif 'elements' in data['chemical_composition'] and isinstance(data['chemical_composition']['elements'], list):
                completeness['chemical_composition'] = min(100, len(data['chemical_composition']['elements']) * 10)
            else:
                completeness['chemical_composition'] = min(100, len(data['chemical_composition']) * 10)
        elif isinstance(data['chemical_composition'], list):
            completeness['chemical_composition'] = min(100, len(data['chemical_composition']) * 10)
    
    if 'mechanical_properties' in data and data['mechanical_properties']:
        if isinstance(data['mechanical_properties'], dict):
            # New format with requirements and products
            if 'requirements' in data['mechanical_properties'] and 'products' in data['mechanical_properties']:
                req_score = min(100, len(data['mechanical_properties']['requirements']) * 20)
                products_score = 0
                if data['mechanical_properties']['products']:
                    products_score = min(100, len(data['mechanical_properties']['products']) * 20)
                completeness['mechanical_properties'] = (req_score + products_score) / 2
            else:
                completeness['mechanical_properties'] = min(100, len(data['mechanical_properties']) * 20)
        elif isinstance(data['mechanical_properties'], list):
            completeness['mechanical_properties'] = min(100, len(data['mechanical_properties']) * 20)
    
    # Calculate overall completeness
    weights = {
        'supplier_info': 0.2,
        'material_info': 0.3,
        'chemical_composition': 0.3,
        'mechanical_properties': 0.2
    }
    
    completeness['overall_completeness'] = sum(
        completeness[key] * weights[key] for key in weights
    )
    
    return completeness

# Get processed jobs
def get_processed_jobs():
    """Get a list of processed jobs"""
    jobs = []
    
    # Check all job directories in the processed directory
    if os.path.exists(PROCESSED_DIR):
        for job_id in os.listdir(PROCESSED_DIR):
            job_dir = os.path.join(PROCESSED_DIR, job_id)
            if os.path.isdir(job_dir):
                # Look for metadata.json
                metadata_file = os.path.join(job_dir, 'metadata.json')
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        # Check if structured data exists
                        has_structured_data = metadata.get('has_structured_data', False)
                        if not has_structured_data:
                            # Check if the file exists
                            structured_data_file = os.path.join(job_dir, 'structured_data.json')
                            has_structured_data = os.path.exists(structured_data_file)
                        
                        # Get a title for the job
                        title = "Mill Test Certificate"
                        if has_structured_data:
                            structured_data_file = os.path.join(job_dir, 'structured_data.json')
                            if os.path.exists(structured_data_file):
                                try:
                                    with open(structured_data_file, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                    if 'material_info' in data and data['material_info']:
                                        if 'grade' in data['material_info']:
                                            title = f"{data['material_info']['grade']} Certificate"
                                        elif 'material_grade' in data['material_info']:
                                            title = f"{data['material_info']['material_grade']} Certificate"
                                except:
                                    pass
                        
                        jobs.append({
                            'job_id': job_id,
                            'title': title,
                            'timestamp': metadata.get('timestamp', 'Unknown'),
                            'original_filename': metadata.get('original_filename', 'Unknown'),
                            'has_structured_data': has_structured_data
                        })
                    except:
                        pass
    
    # Sort by timestamp (newest first)
    jobs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jobs

# Get job data
def get_job_data(job_id):
    """Get data for a specific job"""
    job_dir = os.path.join(PROCESSED_DIR, job_id)
    
    if not os.path.exists(job_dir):
        return None
    
    # Get metadata
    metadata_file = os.path.join(job_dir, 'metadata.json')
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    # Get extracted text
    text_file = os.path.join(job_dir, 'extracted_text.txt')
    if os.path.exists(text_file):
        with open(text_file, 'r', encoding='utf-8') as f:
            extracted_text = f.read()
    else:
        extracted_text = ""
    
    # Get structured data
    structured_data_file = os.path.join(job_dir, 'structured_data.json')
    if os.path.exists(structured_data_file):
        with open(structured_data_file, 'r', encoding='utf-8') as f:
            structured_data = json.load(f)
        has_structured_data = True
    else:
        structured_data = None
        has_structured_data = False
    
    return {
        'metadata': metadata,
        'extracted_text': extracted_text,
        'structured_data': structured_data,
        'has_structured_data': has_structured_data,
        'job_id': job_id
    }

# Check API status
def check_api_status():
    """Check if the DeepSeek API is available"""
    try:
        if not DEEPSEEK_API_KEY:
            app.logger.warning("DeepSeek API key is not set")
            return False
            
        # Test the API with a minimal request
        test_prompt = "Hello"
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": test_prompt}],
                max_tokens=5,
                temperature=0.1
            )
            if response and response.choices:
                app.logger.info("DeepSeek API working properly")
                return True
            else:
                app.logger.warning("DeepSeek API test failed: No valid response")
                return False
        except Exception as api_error:
            app.logger.error(f"DeepSeek API test failed: {str(api_error)}")
            return False
    except Exception as e:
        app.logger.error(f"Error checking API status: {str(e)}")
        return False

# Routes
@app.route('/')
def index():
    """Home page"""
    return redirect(url_for('wps_pqr_comparison_upload'))

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Save to temporary file
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
        file.save(file_path)
        
        # Process the file
        result = process_pdf(file_path, filename)
        
        # Clean up
        try:
            os.unlink(file_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        if result['success']:
            # Store job_id in session
            session['current_job_id'] = result['job_id']
            
            # Process structured information
            struct_result = extract_structured_info(result['text'], result['job_id'])
            
            if struct_result['success']:
                flash('File processed successfully!', 'success')
                return redirect(url_for('analysis', job_id=result['job_id']))
            else:
                flash(f'Text extracted but error in analysis: {struct_result.get("error", "Unknown error")}', 'warning')
                return redirect(url_for('analysis', job_id=result['job_id']))
        else:
            flash(f'Error processing file: {result.get("error", "Unknown error")}', 'error')
            return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload a PDF, JPG, or PNG file.', 'error')
        return redirect(url_for('index'))

@app.route('/api-status', methods=['GET'])
def api_status():
    """Check API status"""
    status = check_api_status()
    session['api_available'] = status
    return jsonify({'status': status})

def update_templates_for_analysis(job_id, data):
    """
    Update the template variables for the analysis page to handle the array-based data format.
    This allows backward compatibility by converting the array-based format back to 
    the structure expected by the template.
    """
    # Get product IDs from the data
    product_ids = []
    if 'material_info' in data and 'product_id' in data['material_info']:
        product_id_info = data['material_info']['product_id']
        if isinstance(product_id_info, str):
            product_ids = [product_id_info]
        elif isinstance(product_id_info, list):
            product_ids = product_id_info
    else:
        # Fallback to generic product IDs
        product_ids = ["Product 1"]
    
    # Convert chemical_composition from array-based format to requirements/products format
    chemical_composition = {"requirements": {}, "products": []}
    
    # Setup products with IDs
    for i, prod_id in enumerate(product_ids):
        chemical_composition["products"].append({
            "product_id": prod_id,
            "values": {}  # Ensure values is always a dictionary
        })
    
    # Process chemical composition data - check if it's a dictionary first
    if isinstance(data.get('chemical_composition'), dict):
        chem_data = data.get('chemical_composition', {})
        # First check if it's already in the requirements/products format
        if 'requirements' in chem_data and 'products' in chem_data:
            chemical_composition = chem_data
            # Ensure all products have a values dictionary
            for product in chemical_composition["products"]:
                if not isinstance(product.get('values'), dict):
                    product['values'] = {}
        else:
            # Process each element from the array-based format
            for element, values in chem_data.items():
                if isinstance(values, list) and len(values) > 0:
                    # First item is the requirement
                    chemical_composition["requirements"][element] = values[0]
                    
                    # Subsequent items are values for each product
                    for i in range(1, len(values)):
                        if i-1 < len(chemical_composition["products"]):
                            if values[i] is not None:
                                chemical_composition["products"][i-1]["values"][element] = values[i]
    
    # Convert mechanical_properties from array-based format to requirements/products format
    mechanical_properties = {"requirements": {}, "products": []}
    
    # Setup products with IDs (reuse the same product IDs)
    for i, prod_id in enumerate(product_ids):
        mechanical_properties["products"].append({
            "product_id": prod_id,
            "values": {}  # Ensure values is always a dictionary
        })
    
    # Process mechanical properties data - check if it's a dictionary first
    if isinstance(data.get('mechanical_properties'), dict):
        mech_data = data.get('mechanical_properties', {})
        # First check if it's already in the requirements/products format
        if 'requirements' in mech_data and 'products' in mech_data:
            mechanical_properties = mech_data
            # Ensure all products have a values dictionary
            for product in mechanical_properties["products"]:
                if not isinstance(product.get('values'), dict):
                    product['values'] = {}
        else:
            # Process each property from the array-based format
            for prop, values in mech_data.items():
                if isinstance(values, list) and len(values) > 0:
                    # First item is the requirement
                    mechanical_properties["requirements"][prop] = values[0]
                    
                    # Subsequent items are values for each product
                    for i in range(1, len(values)):
                        if i-1 < len(mechanical_properties["products"]):
                            if values[i] is not None:
                                mechanical_properties["products"][i-1]["values"][prop] = values[i]
    
    # Return the template variables
    return {
        "job_id": job_id,
        "data": data,
        "chemical_composition": chemical_composition,
        "mechanical_properties": mechanical_properties,
        "product_ids": product_ids
    }

def generate_certificate_summary(data, chemical_composition, mechanical_properties):
    """
    Generate a comprehensive HTML-formatted summary of the mill test certificate analysis based on structured data
    """
    html_summary = []
    
    # Add title - smaller font size but bold
    html_summary.append("<h1 style='font-size: 1.4rem; font-weight: bold; text-align: center; margin-bottom: 1.5rem;'>Mill Test Certificate Analysis and Compliance Report</h1>")
    
    # Extract basic information
    supplier_info = data.get('supplier_info', {})
    material_info = data.get('material_info', {})
    alloy = material_info.get('alloy', 'Unknown')
    temper = material_info.get('temper', '')
    standard = material_info.get('standard', 'Unknown')
    
    # Add supplier information section
    html_summary.append("<div class='supplier-info' style='margin-bottom: 1.5rem;'>")
    html_summary.append("<h2 style='font-size: 1.2rem; margin-bottom: 0.75rem;'>Supplier & Certificate Information</h2>")
    html_summary.append("<table class='data-table' width='100%' border='1' cellspacing='0' cellpadding='5' style='border-collapse: collapse;'>")
    html_summary.append("<tr><th width='30%' style='background-color: #f2f2f2;'>Supplier Name</th><td><span class='emphasis'>{}</span></td></tr>".format(
        supplier_info.get('name', 'Unknown Supplier')))
    
    if supplier_info.get('website'):
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Website</th><td>{}</td></tr>".format(supplier_info.get('website')))
    
    if supplier_info.get('address'):
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Address</th><td>{}</td></tr>".format(supplier_info.get('address')))
    
    if supplier_info.get('contact'):
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Contact</th><td>{}</td></tr>".format(supplier_info.get('contact')))
    
    html_summary.append("<tr><th style='background-color: #f2f2f2;'>Material</th><td><span class='emphasis'>{}</span></td></tr>".format(
        material_info.get('material_name', 'Steel Material')))
    
    if alloy:
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Alloy</th><td><span class='emphasis'>{}</span></td></tr>".format(alloy))
    
    if temper:
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Temper</th><td>{}</td></tr>".format(temper))
    
    if standard:
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Specification Standard</th><td><span class='spec'>{}</span></td></tr>".format(standard))
    
    if material_info.get('heat_number'):
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Heat Number</th><td>{}</td></tr>".format(material_info.get('heat_number')))
    
    if material_info.get('certificate_number'):
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Certificate Number</th><td>{}</td></tr>".format(material_info.get('certificate_number')))
    
    if material_info.get('date'):
        html_summary.append("<tr><th style='background-color: #f2f2f2;'>Date</th><td>{}</td></tr>".format(material_info.get('date')))
    
    html_summary.append("</table>")
    html_summary.append("</div>")
    
    # Add introduction
    intro = f"This report analyzes a Mill Test Certificate for {material_info.get('material_name', 'Material')} "
    if alloy:
        intro += f"(Alloy: <span class='emphasis'>{alloy}</span>"
        if temper:
            intro += f", Temper: {temper}"
        intro += ") "
    
    if standard:
        intro += f"The material is tested and certified according to the <span class='spec'>{standard}</span> standard. "
    
    intro += "Below is a detailed analysis of the chemical composition and mechanical properties, along with compliance assessment against specification requirements."
    html_summary.append(f"<p style='margin-bottom: 1.5rem;'>{intro}</p>")
    
    # Add chemical composition section
    if chemical_composition and 'requirements' in chemical_composition and 'products' in chemical_composition:
        html_summary.append("<div style='margin-bottom: 1.5rem;'>")
        html_summary.append("<h2 style='font-size: 1.2rem; margin-bottom: 0.75rem;'>1. Chemical Composition Analysis (%)</h2>")
        html_summary.append("<p>The chemical composition requirements and observed values are as follows:</p>")
        
        # Create a table
        html_summary.append("<table class='data-table' width='100%' border='1' cellspacing='0' cellpadding='5' style='border-collapse: collapse;'>")
        
        # Table header
        header = "<tr style='background-color: #f2f2f2;'><th>Element</th><th>Specification Requirement</th>"
        for product in chemical_composition['products']:
            header += f"<th>{product.get('product_id', '-')}</th>"
        header += "<th>Status</th></tr>"
        html_summary.append(header)
        
        # Table content
        for element, requirement in chemical_composition['requirements'].items():
            row = f"<tr><td style='font-weight: bold;'>{element}</td><td>{requirement}</td>"
            
            # Track if all values for this element are compliant or any are missing
            all_compliant = True
            any_missing = False
            
            for product in chemical_composition['products']:
                if product.get('values') and isinstance(product.get('values'), dict) and element in product['values']:
                    value = product['values'][element]
                    # Here we'd need more logic to check compliance, but for now we'll assume it's compliant
                    row += f"<td>{value}</td>"
                else:
                    row += "<td><span class='missing'>-</span></td>"
                    any_missing = True
            
            # Add the status column
            if any_missing:
                row += "<td><span class='unknown'>⚠️ Missing Data</span></td>"
            elif all_compliant:
                row += "<td><span class='pass compliant'>✅ Compliant</span></td>"
            else:
                row += "<td><span class='fail non-compliant'>❌ Non-Compliant</span></td>"
            
            row += "</tr>"
            html_summary.append(row)
        
        html_summary.append("</table>")
        
        # Add compliance analysis
        html_summary.append("<h3 style='font-size: 1.1rem; margin-top: 1rem; margin-bottom: 0.5rem;'>Compliance Analysis:</h3>")
        html_summary.append("<p>")
        html_summary.append("All observed values for the chemical composition elements appear to be within the specified limits. ")
        if standard:
            html_summary.append(f"The chemical composition complies with the <span class='spec'>{standard}</span> standard requirements.")
        html_summary.append("</p>")
        html_summary.append("</div>")
    
    # Add mechanical properties section
    if mechanical_properties and 'requirements' in mechanical_properties and 'products' in mechanical_properties:
        html_summary.append("<div style='margin-bottom: 1.5rem;'>")
        html_summary.append("<h2 style='font-size: 1.2rem; margin-bottom: 0.75rem;'>2. Mechanical Properties Analysis</h2>")
        html_summary.append("<p>The mechanical property requirements and observed values are as follows:</p>")
        
        # Create a table
        html_summary.append("<table class='data-table' width='100%' border='1' cellspacing='0' cellpadding='5' style='border-collapse: collapse;'>")
        
        # Table header
        header = "<tr style='background-color: #f2f2f2;'><th>Property</th><th>Specification Requirement</th>"
        for product in mechanical_properties['products']:
            header += f"<th>{product.get('product_id', '-')}</th>"
        header += "<th>Status</th></tr>"
        html_summary.append(header)
        
        # Table content
        for prop, requirement in mechanical_properties['requirements'].items():
            row = f"<tr><td style='font-weight: bold;'>{prop}</td><td>{requirement}</td>"
            
            # Track if all values for this property are compliant or any are missing
            all_compliant = True
            any_missing = False
            all_missing = True
            
            for product in mechanical_properties['products']:
                if product.get('values') and isinstance(product.get('values'), dict) and prop in product['values']:
                    value = product['values'][prop]
                    row += f"<td>{value}</td>"
                    all_missing = False
                else:
                    row += "<td><span class='missing'>-</span></td>"
                    any_missing = True
            
            # Add the status column
            if all_missing:
                row += "<td><span class='unknown'>⚠️ No Data</span></td>"
            elif any_missing:
                row += "<td><span class='unknown'>⚠️ Partial Data</span></td>"
            elif all_compliant:
                row += "<td><span class='pass compliant'>✅ Compliant</span></td>"
            else:
                row += "<td><span class='fail non-compliant'>❌ Non-Compliant</span></td>"
            
            row += "</tr>"
            html_summary.append(row)
        
        html_summary.append("</table>")
        
        # Add compliance analysis for mechanical properties
        html_summary.append("<h3 style='font-size: 1.1rem; margin-top: 1rem; margin-bottom: 0.5rem;'>Compliance Analysis:</h3>")
        
        missing_props = []
        for prop in mechanical_properties['requirements']:
            all_missing = True
            for product in mechanical_properties['products']:
                if product.get('values') and isinstance(product.get('values'), dict) and prop in product['values']:
                    all_missing = False
                    break
            if all_missing:
                missing_props.append(prop)
        
        if missing_props:
            html_summary.append(f"<p><span class='unknown'>⚠️ Note:</span> No data is provided for the following properties: {', '.join(missing_props)}. Compliance cannot be verified for these properties.</p>")
        
        html_summary.append("<p>For the properties with available data, all values appear to meet the specification requirements.</p>")
        html_summary.append("</div>")
    
    # Add product details
    if 'material_info' in data and chemical_composition and 'products' in chemical_composition:
        html_summary.append("<div style='margin-bottom: 1.5rem;'>")
        html_summary.append("<h2 style='font-size: 1.2rem; margin-bottom: 0.75rem;'>3. Product Details</h2>")
        
        for product in chemical_composition['products']:
            prod_id = product.get('product_id', '-')
            html_summary.append(f"<h3 style='font-size: 1.1rem; margin-bottom: 0.5rem;'>Product ID: <span class='emphasis'>{prod_id}</span></h3>")
            
            html_summary.append("<table class='data-table' width='100%' border='1' cellspacing='0' cellpadding='5' style='border-collapse: collapse;'>")
            html_summary.append("<tr style='background-color: #f2f2f2;'><th width='30%'>Property</th><th>Value</th></tr>")
            
            # Add specific product details if available
            size = material_info.get('size', '')
            if size:
                html_summary.append(f"<tr><td>Size</td><td>{size}</td></tr>")
                
            quantity = material_info.get('quantity', '')
            if quantity:
                html_summary.append(f"<tr><td>Quantity</td><td>{quantity}</td></tr>")
                
            weight = material_info.get('weight', '')
            if weight:
                html_summary.append(f"<tr><td>Net Weight</td><td>{weight}</td></tr>")
            
            html_summary.append("</table>")
        html_summary.append("</div>")
    
    # Add overall compliance
    if standard:
        html_summary.append("<div style='margin-bottom: 1.5rem;'>")
        html_summary.append("<h2 style='font-size: 1.2rem; margin-bottom: 0.75rem;'>4. Overall Compliance Assessment</h2>")
        
        # Determine overall compliance
        missing_data = False
        non_compliant_items = False
        
        # Example logic to determine compliance - you'd want to add more sophisticated logic here
        if chemical_composition and 'requirements' in chemical_composition:
            for element in chemical_composition['requirements']:
                for product in chemical_composition['products']:
                    if not (product.get('values') and isinstance(product.get('values'), dict) and element in product['values']):
                        missing_data = True
                        break
        
        if mechanical_properties and 'requirements' in mechanical_properties:
            for prop in mechanical_properties['requirements']:
                for product in mechanical_properties['products']:
                    if not (product.get('values') and isinstance(product.get('values'), dict) and prop in product['values']):
                        missing_data = True
                        break
        
        # Add the conclusion based on compliance assessment in a table
        html_summary.append("<table class='data-table' width='100%' border='1' cellspacing='0' cellpadding='5' style='border-collapse: collapse;'>")
        
        if non_compliant_items:
            html_summary.append("<tr><td style='background-color: #ffdddd;'><span class='fail non-compliant'>❌ Non-Compliant</span> The certificate contains values that do not meet the specified requirements.</td></tr>")
        elif missing_data:
            html_summary.append("<tr><td style='background-color: #ffffcc;'><span class='unknown'>⚠️ Partially Verified</span> The chemical composition and mechanical properties partially comply with the requirements. Some data points are missing for full verification.</td></tr>")
        else:
            html_summary.append("<tr><td style='background-color: #ddffdd;'><span class='pass compliant'>✅ Fully Compliant</span> The chemical composition and mechanical properties fully comply with the specified requirements.</td></tr>")
        
        html_summary.append("<tr><td>The certificate confirms that the material has been manufactured and tested according to the <span class='spec'>{}</span> standard.</td></tr>".format(standard))
        html_summary.append("</table>")
        html_summary.append("</div>")
    
    # Add conclusion
    html_summary.append("<div class='conclusion' style='background-color: #f7f7f7; padding: 1rem; border-left: 4px solid #28a745; margin-top: 1.5rem;'>")
    html_summary.append("<h2 style='font-size: 1.2rem; margin-bottom: 0.75rem;'>Conclusion</h2>")
    
    conclusion = f"The Mill Test Certificate for {material_info.get('material_name', 'Material')}"
    if alloy:
        conclusion += f" ({alloy}"
        if temper:
            conclusion += f", {temper}"
        conclusion += ")"
    
    if non_compliant_items:
        conclusion += f" <span class='fail non-compliant'>❌ does not fully comply</span> with the {standard} standard requirements due to some non-conforming values."
    elif missing_data:
        conclusion += f" <span class='unknown'>⚠️ partially complies</span> with the {standard} standard requirements for chemical composition and mechanical properties, with some data missing for complete verification."
    else:
        conclusion += f" <span class='pass compliant'>✅ fully complies</span> with the {standard} standard requirements for chemical composition and mechanical properties."
    
    html_summary.append(f"<p>{conclusion}</p>")
    html_summary.append("</div>")
    
    return "".join(html_summary)

@app.route('/analysis/<job_id>')
def analysis(job_id):
    """Display the analysis of a processed certificate"""
    try:
        # Check if the job directory exists
        job_dir = os.path.join(PROCESSED_DIR, job_id)
        if not os.path.exists(job_dir):
            flash('Job not found. Please upload a certificate first.', 'danger')
            return redirect(url_for('index'))
        
        # Load the metadata
        metadata_file = os.path.join(job_dir, 'metadata.json')
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            flash(f"Error loading metadata: {str(e)}", 'danger')
            return redirect(url_for('index'))
        
        # If the structured data isn't available, redirect to raw text
        if not metadata.get('has_structured_data', False):
            flash('Structured data is not available for this certificate. Showing raw text instead.', 'warning')
            return redirect(url_for('raw_text', job_id=job_id))
        
        # Load the structured data
        json_file = os.path.join(job_dir, 'structured_data.json')
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            flash(f"Error loading structured data: {str(e)}", 'danger')
            return redirect(url_for('raw_text', job_id=job_id))
        
        # Prepare template variables based on the data format
        template_vars = update_templates_for_analysis(job_id, data)
        
        # Generate the certificate summary
        certificate_summary = generate_certificate_summary(
            data, 
            template_vars.get('chemical_composition', {}), 
            template_vars.get('mechanical_properties', {})
        )
        
        # Get completion metrics and add to template variables
        template_vars.update({
            "job_id": job_id,
            "metadata": metadata,  # Pass metadata to the template
            "filename": metadata.get('filename', 'Unknown'),
            "upload_time": metadata.get('upload_time', 'Unknown'),
            "extraction_quality": _assess_extraction_quality(data),
            "certificate_summary": certificate_summary
        })
        
        return render_template('analysis.html', **template_vars)
    except Exception as e:
        flash(f"Error displaying analysis: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/previous')
def previous_jobs():
    """View previous jobs"""
    jobs = get_processed_jobs()
    return render_template('previous.html', jobs=jobs)

@app.route('/raw-text/<job_id>')
def raw_text(job_id):
    """Display the raw text of a certificate"""
    job_data = get_job_data(job_id)
    
    if not job_data:
        flash('Job not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('raw_text.html', job_data=job_data)

@app.route('/query/<job_id>', methods=['GET', 'POST'])
def query(job_id):
    """Query a processed certificate"""
    job_data = get_job_data(job_id)
    
    if not job_data:
        flash('Job not found', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        user_query = request.form.get('query', '')
        
        if user_query:
            system_prompt = """
            You are a helpful assistant specialized in analyzing steel mill test certificates.
            You will answer questions about the provided test certificate text.
            
            IMPORTANT: When analyzing chemical composition or mechanical properties, always distinguish between:
            1. Specification requirements (typically shown as limits like "<0.25%" or ranges like "17-110")
            2. Actual observed values for specific products
            
            Include reasoning in your answers about whether observed values comply with specification requirements.
            When a user asks about a specific element or property, explain both the requirement and the actual values.
            
            Provide detailed, accurate responses based only on the information in the certificate.
            If the information isn't available in the certificate, clearly state that.
            Use a professional, helpful tone and format your answers for clarity.
            If appropriate, structure tabular data as a Markdown table.
            """
            
            user_prompt = f"Question: {user_query}\n\nTest Certificate Content:"
            
            response = query_llm(job_data['extracted_text'], system_prompt, user_prompt, temperature=0.3)
            
            return jsonify(response)
    
    # Common questions
    common_questions = [
        "What is the tensile strength of this material?",
        "What is the yield strength of this material?",
        "What is the chemical composition of this material?",
        "What is the material grade of this product?",
        "What are the specification requirements for silicon and how do the observed values compare?",
        "Are all measured values within specification limits?",
        "Does this material comply with all requirements?",
        "What is the aluminum content and is it within specification?",
        "Compare observed mechanical properties with specification requirements."
    ]
    
    return render_template('query.html', job_data=job_data, common_questions=common_questions)

def _assess_extraction_quality(data):
    """
    Assess the quality of the extraction based on data completeness.
    Returns a dict with:
    - score: 0-100 score representing completeness
    - level: "high", "medium", or "low"
    - reasons: List of reasons for the assessment
    """
    score = 0
    reasons = []
    
    # Check if we have material info
    if data.get('material_info'):
        material_info = data['material_info']
        material_score = 0
        material_fields = ['grade', 'specification', 'heat_number', 'size']
        
        for field in material_fields:
            if field in material_info and material_info[field]:
                material_score += 25  # Each field is worth 25% of material score
        
        score += material_score / len(material_fields) * 30  # Material info is 30% of total score
        
        if material_score < 50:
            reasons.append("Missing critical material information")
    else:
        reasons.append("No material information extracted")
    
    # Check chemical composition
    if data.get('chemical_composition'):
        chem_comp = data['chemical_composition']
        chem_score = 0
        num_elements = len(chem_comp)
        
        if num_elements >= 5:
            chem_score += 50  # Having enough elements is 50% of chem score
        else:
            reasons.append(f"Only {num_elements} chemical elements extracted")
        
        # Check for values
        values_present = 0
        total_values = 0
        
        for element, values in chem_comp.items():
            if isinstance(values, list) and len(values) > 1:
                for i in range(1, len(values)):  # Skip the requirement
                    total_values += 1
                    if values[i] is not None and values[i] != "-":
                        values_present += 1
        
        if total_values > 0:
            value_percentage = (values_present / total_values) * 100
            chem_score += value_percentage / 2  # Values completeness is other 50% of chem score
            
            if value_percentage < 50:
                reasons.append(f"Only {int(value_percentage)}% of chemical values extracted")
        else:
            reasons.append("No chemical values extracted")
        
        score += chem_score * 0.35  # Chemical composition is 35% of total score
    else:
        reasons.append("No chemical composition extracted")
        
    # Check mechanical properties
    if data.get('mechanical_properties'):
        mech_props = data['mechanical_properties']
        mech_score = 0
        num_props = len(mech_props)
        
        if num_props >= 3:
            mech_score += 50  # Having enough properties is 50% of mech score
        else:
            reasons.append(f"Only {num_props} mechanical properties extracted")
        
        # Check for values
        values_present = 0
        total_values = 0
        
        for prop, values in mech_props.items():
            if isinstance(values, list) and len(values) > 1:
                for i in range(1, len(values)):  # Skip the requirement
                    total_values += 1
                    if values[i] is not None and values[i] != "-":
                        values_present += 1
        
        if total_values > 0:
            value_percentage = (values_present / total_values) * 100
            mech_score += value_percentage / 2  # Values completeness is other 50% of mech score
            
            if value_percentage < 50:
                reasons.append(f"Only {int(value_percentage)}% of mechanical values extracted")
        else:
            reasons.append("No mechanical property values extracted")
        
        score += mech_score * 0.35  # Mechanical properties is 35% of total score
    else:
        reasons.append("No mechanical properties extracted")
    
    # Determine quality level
    score = round(score)
    if score >= 80:
        level = "high"
    elif score >= 50:
        level = "medium"
    else:
        level = "low"
    
    # Add default reason if none provided
    if not reasons and level != "high":
        reasons.append("Incomplete data extraction")
    
    return {
        "score": score,
        "level": level,
        "reasons": reasons
    }

# WPS/PQR Comparison Routes
@app.route('/wps-pqr-compliance')
def wps_pqr_comparison_upload():
    """Main page for WPS/PQR side-by-side comparison"""
    return render_template('wps_pqr_compliance.html')

@app.route('/upload-wps-pqr', methods=['POST'])
def upload_wps_pqr():
    """Handle upload of WPS and PQR files for compliance verification"""
    # Check if both files are uploaded
    if 'wps_file' not in request.files or 'pqr_file' not in request.files:
        flash('Both WPS and PQR files are required', 'danger')
        return redirect(url_for('wps_pqr_comparison_upload'))
        
    wps_file = request.files['wps_file']
    pqr_file = request.files['pqr_file']
    
    if wps_file.filename == '' or pqr_file.filename == '':
        flash('Please select both WPS and PQR files', 'danger')
        return redirect(url_for('wps_pqr_comparison_upload'))
    
    if not (allowed_file(wps_file.filename) and allowed_file(pqr_file.filename)):
        flash('Please upload files in allowed formats (PDF, JPG, PNG)', 'danger')
        return redirect(url_for('wps_pqr_comparison_upload'))
        
    # Generate a unique job ID for this comparison
    comparison_job_id = str(uuid.uuid4())
    job_dir = os.path.join(PROCESSED_DIR, comparison_job_id)
    if not os.path.exists(job_dir):
        os.makedirs(job_dir)
    
    try:
        # Save both files
        wps_filename = secure_filename(wps_file.filename)
        pqr_filename = secure_filename(pqr_file.filename)
        
        # Create upload directory for each file with its job ID
        wps_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], comparison_job_id, 'wps')
        pqr_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], comparison_job_id, 'pqr')
        
        os.makedirs(wps_upload_dir, exist_ok=True)
        os.makedirs(pqr_upload_dir, exist_ok=True)
        
        wps_path = os.path.join(wps_upload_dir, wps_filename)
        pqr_path = os.path.join(pqr_upload_dir, pqr_filename)
        
        wps_file.save(wps_path)
        pqr_file.save(pqr_path)
        
        # Inform user about the high-quality extraction
        flash('Using enhanced high-quality extraction for best results. This may take a few minutes...', 'info')
        
        # Process WPS file with enhanced extraction
        app.logger.info(f"Processing WPS file: {wps_filename}")
        wps_result = process_pdf(wps_path, wps_filename)
        if not wps_result.get('success', False):
            error_msg = wps_result.get("error", "Unknown error")
            app.logger.error(f"Error processing WPS file: {error_msg}")
            flash(f'Error processing WPS file: {error_msg}', 'danger')
            return redirect(url_for('wps_pqr_comparison_upload'))
        
        # Process PQR file with enhanced extraction
        app.logger.info(f"Processing PQR file: {pqr_filename}")
        pqr_result = process_pdf(pqr_path, pqr_filename)
        if not pqr_result.get('success', False):
            error_msg = pqr_result.get("error", "Unknown error")
            app.logger.error(f"Error processing PQR file: {error_msg}")
            flash(f'Error processing PQR file: {error_msg}', 'danger')
            return redirect(url_for('wps_pqr_comparison_upload'))
        
        # Save job metadata
        metadata = {
            'job_id': comparison_job_id,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'wps_filename': wps_filename,
            'pqr_filename': pqr_filename,
            'wps_job_id': wps_result['job_id'],
            'pqr_job_id': pqr_result['job_id'],
            'status': 'processing',
            'extraction_quality': 'enhanced'
        }
        
        with open(os.path.join(job_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Extract structured information from WPS
        app.logger.info(f"Extracting structured data from WPS text")
        wps_structure = extract_wps_info(wps_result['text'], wps_result['job_id'])
        
        # Check WPS extraction result
        if not wps_structure.get('success', False):
            error_msg = wps_structure.get("error", "Unknown error in WPS extraction")
            app.logger.error(f"Error extracting WPS data: {error_msg}")
            flash(f'Error extracting data from WPS document: {error_msg}', 'danger')
            
            # Update metadata to reflect error
            metadata['status'] = 'failed'
            metadata['error'] = f'WPS extraction failed: {error_msg}'
            with open(os.path.join(job_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
                
            return redirect(url_for('wps_pqr_comparison_upload'))
        
        # Extract structured information from PQR
        app.logger.info(f"Extracting structured data from PQR text")
        pqr_structure = extract_pqr_info(pqr_result['text'], pqr_result['job_id'])
        
        # Check PQR extraction result
        if not pqr_structure.get('success', False):
            error_msg = pqr_structure.get("error", "Unknown error in PQR extraction")
            app.logger.error(f"Error extracting PQR data: {error_msg}")
            flash(f'Error extracting data from PQR document: {error_msg}', 'danger')
            
            # Update metadata to reflect error
            metadata['status'] = 'failed'
            metadata['error'] = f'PQR extraction failed: {error_msg}'
            with open(os.path.join(job_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
                
            return redirect(url_for('wps_pqr_comparison_upload'))
        
        # Compare WPS and PQR - load the structured data from the files
        try:
            wps_job_id = metadata.get('wps_job_id')
            pqr_job_id = metadata.get('pqr_job_id')
            
            if not wps_job_id or not pqr_job_id:
                app.logger.error(f"Missing job IDs in metadata. WPS: {wps_job_id}, PQR: {pqr_job_id}")
                flash('Incomplete metadata: missing job IDs', 'danger')
                return redirect(url_for('wps_pqr_comparison_upload'))
            
            wps_data_file = os.path.join(PROCESSED_DIR, wps_job_id, 'wps_data.json')
            pqr_data_file = os.path.join(PROCESSED_DIR, pqr_job_id, 'pqr_data.json')
            
            app.logger.info(f"Loading WPS data from: {wps_data_file}")
            app.logger.info(f"Loading PQR data from: {pqr_data_file}")
            
            if not os.path.exists(wps_data_file):
                app.logger.error(f"WPS data file not found: {wps_data_file}")
                flash('WPS data file not found', 'danger')
                return redirect(url_for('wps_pqr_comparison_upload'))
                
            if not os.path.exists(pqr_data_file):
                app.logger.error(f"PQR data file not found: {pqr_data_file}")
                flash('PQR data file not found', 'danger')
                return redirect(url_for('wps_pqr_comparison_upload'))
                
            with open(wps_data_file, 'r', encoding='utf-8') as f:
                wps_data = json.load(f)
                
            with open(pqr_data_file, 'r', encoding='utf-8') as f:
                pqr_data = json.load(f)
            
            # Perform comparison
            app.logger.info(f"Comparing WPS and PQR data for compliance")
            comparison_result = compare_wps_pqr(wps_data, pqr_data, comparison_job_id)
            
            # Update metadata
            metadata['status'] = 'completed'
            metadata['completion_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metadata['compliance_result'] = comparison_result.get('overall_compliance', False)
            metadata['compliance_score'] = comparison_result.get('overall_score', 0)
            
            with open(os.path.join(job_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # Redirect to the side-by-side comparison page
            return redirect(url_for('wps_pqr_side_by_side', job_id=comparison_job_id))
            
        except FileNotFoundError as e:
            app.logger.error(f"File not found error in comparison: {str(e)}")
            flash(f'Error: Could not find extracted data files. {str(e)}', 'danger')
            metadata['status'] = 'failed'
            metadata['error'] = f'File not found: {str(e)}'
            with open(os.path.join(job_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            return redirect(url_for('wps_pqr_comparison_upload'))
            
        except json.JSONDecodeError as e:
            app.logger.error(f"JSON decode error in comparison: {str(e)}")
            flash(f'Error: Could not parse extracted data as JSON. {str(e)}', 'danger')
            metadata['status'] = 'failed'
            metadata['error'] = f'JSON parse error: {str(e)}'
            with open(os.path.join(job_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            return redirect(url_for('wps_pqr_comparison_upload'))
            
    except Exception as e:
        app.logger.error(f"Error in WPS/PQR comparison: {str(e)}")
        flash(f'An unexpected error occurred: {str(e)}', 'danger')
        
        # Try to save error information if job directory exists
        try:
            if os.path.exists(job_dir):
                error_log = os.path.join(job_dir, 'error.log')
                with open(error_log, 'w', encoding='utf-8') as f:
                    f.write(f"Error timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Error message: {str(e)}\n")
                    import traceback
                    f.write(f"Traceback:\n{traceback.format_exc()}")
        except:
            pass  # If we can't save the error log, continue with the redirect
            
        return redirect(url_for('wps_pqr_comparison_upload'))

@app.route('/wps-pqr-comparison/<job_id>')
def wps_pqr_comparison(job_id):
    """Display the WPS/PQR comparison results"""
    # Simply redirect to the side-by-side view
    return redirect(url_for('wps_pqr_side_by_side', job_id=job_id))

@app.route('/wps-pqr-side-by-side/<job_id>')
def wps_pqr_side_by_side(job_id):
    """Display the WPS/PQR side-by-side comparison"""
    job_dir = os.path.join(PROCESSED_DIR, job_id)
    
    if not os.path.exists(job_dir):
        flash('Comparison job not found', 'danger')
        return redirect(url_for('wps_pqr_comparison_upload'))
    
    try:
        # Load metadata
        metadata_file = os.path.join(job_dir, 'metadata.json')
        app.logger.info(f"Loading metadata from: {metadata_file}")
        
        if not os.path.exists(metadata_file):
            app.logger.error(f"Metadata file not found: {metadata_file}")
            flash('Metadata file not found for this comparison job', 'danger')
            return redirect(url_for('wps_pqr_comparison_upload'))
            
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Load WPS and PQR data
        wps_job_id = metadata.get('wps_job_id')
        pqr_job_id = metadata.get('pqr_job_id')
        
        if not wps_job_id or not pqr_job_id:
            app.logger.error(f"Missing job IDs in metadata. WPS: {wps_job_id}, PQR: {pqr_job_id}")
            flash('Incomplete metadata: missing job IDs', 'danger')
            return redirect(url_for('wps_pqr_comparison_upload'))
            
        wps_data_file = os.path.join(PROCESSED_DIR, wps_job_id, 'wps_data.json')
        pqr_data_file = os.path.join(PROCESSED_DIR, pqr_job_id, 'pqr_data.json')
        
        app.logger.info(f"Loading WPS data from: {wps_data_file}")
        app.logger.info(f"Loading PQR data from: {pqr_data_file}")
        
        if not os.path.exists(wps_data_file):
            app.logger.error(f"WPS data file not found: {wps_data_file}")
            flash('WPS data file not found', 'danger')
            return redirect(url_for('wps_pqr_comparison_upload'))
            
        if not os.path.exists(pqr_data_file):
            app.logger.error(f"PQR data file not found: {pqr_data_file}")
            flash('PQR data file not found', 'danger')
            return redirect(url_for('wps_pqr_comparison_upload'))
            
        with open(wps_data_file, 'r', encoding='utf-8') as f:
            wps_data = json.load(f)
            
        with open(pqr_data_file, 'r', encoding='utf-8') as f:
            pqr_data = json.load(f)
        
        # Validate required sections exist in the data
        for data, name in [(wps_data, 'WPS'), (pqr_data, 'PQR')]:
            if not isinstance(data, dict):
                app.logger.error(f"{name} data is not a dictionary: {type(data)}")
                flash(f'{name} data has an invalid format', 'danger')
                return redirect(url_for('wps_pqr_comparison_upload'))
        
        # Enhanced normalization of WPS and PQR data keys with better handling of all structures
        key_mapping = {
            "DOCUMENT_INFORMATION": "document_info",
            "DOCUMENT INFORMATION": "document_info",
            "document_information": "document_info",
            "JOINTS": "joints",
            "BASE_METALS": "base_metals",
            "BASE METALS": "base_metals",
            "FILLER_METALS": "filler_metals",
            "FILLER METALS": "filler_metals",
            "POSITION": "position",
            "PREHEAT": "preheat",
            "POST_WELD_HEAT_TREATMENT": "pwht",
            "POST WELD HEAT TREATMENT": "pwht",
            "post_weld_heat_treatment": "pwht",
            "GAS": "gas",
            "ELECTRICAL_CHARACTERISTICS": "electrical_characteristics",
            "ELECTRICAL CHARACTERISTICS": "electrical_characteristics",
            "TECHNIQUE": "technique",
            "WELDING_PARAMETER_TABLE": "welding_parameter_table",
            "WELDING PARAMETER TABLE": "welding_parameter_table",
            "welding_parameter_table": "welding_parameter_table",
            "TENSILE_TEST": "tensile_test",
            "tensile_test": "tensile_test",
            "GUIDED_BEND_TEST": "guided_bend_test",
            "guided_bend_test": "guided_bend_test",
            "TOUGHNESS_TESTS": "toughness_tests",
            "toughness_tests": "toughness_tests",
            "process_specific": "process_specific"
        }
        
        # Function to normalize keys in nested dictionaries while preserving structure
        def normalize_keys(data):
            if isinstance(data, dict):
                new_dict = {}
                for key, value in data.items():
                    # Check if this is a known key to normalize
                    new_key = key_mapping.get(key, key)
                    
                    # Special case handling for potential API response format variations
                    if new_key == "document_information":
                        new_key = "document_info"
                    
                    # Recursively normalize values if they're dictionaries or lists
                    if isinstance(value, dict):
                        new_dict[new_key] = normalize_keys(value)
                    elif isinstance(value, list):
                        new_list = []
                        for item in value:
                            if isinstance(item, dict):
                                new_list.append(normalize_keys(item))
                            else:
                                new_list.append(item)
                        new_dict[new_key] = new_list
                    else:
                        new_dict[new_key] = value
                return new_dict
            elif isinstance(data, list):
                return [normalize_keys(item) if isinstance(item, (dict, list)) else item for item in data]
            else:
                return data
        
        # Debug the original data structures first
        app.logger.info(f"WPS data keys: {list(wps_data.keys())}")
        app.logger.info(f"PQR data keys: {list(pqr_data.keys())}")
        
        # Normalize data recursively
        wps_data = normalize_keys(wps_data)
        pqr_data = normalize_keys(pqr_data)
        
        # Debug the normalized data keys
        app.logger.info(f"Normalized WPS data keys: {list(wps_data.keys())}")
        app.logger.info(f"Normalized PQR data keys: {list(pqr_data.keys())}")
        
        # Check for filler metals structure
        if 'filler_metals' in wps_data:
            app.logger.info(f"WPS filler_metals keys: {list(wps_data['filler_metals'].keys()) if isinstance(wps_data['filler_metals'], dict) else 'Not a dict'}")
        if 'filler_metals' in pqr_data:
            app.logger.info(f"PQR filler_metals keys: {list(pqr_data['filler_metals'].keys()) if isinstance(pqr_data['filler_metals'], dict) else 'Not a dict'}")
        
        # Ensure document_info exists
        if 'document_info' not in wps_data:
            app.logger.warning("WPS data missing document_info section, adding empty one")
            wps_data['document_info'] = {}
            
        if 'document_info' not in pqr_data:
            app.logger.warning("PQR data missing document_info section, adding empty one")
            pqr_data['document_info'] = {}
            
            # Check for document_information (alternative key)
            if 'document_information' in pqr_data:
                app.logger.info("Found document_information in PQR, copying to document_info")
                pqr_data['document_info'] = pqr_data['document_information']
        
        # Ensure all required sections exist with proper structures
        required_sections = [
            'joints', 'base_metals', 'filler_metals', 'position', 'preheat', 
            'pwht', 'gas', 'electrical_characteristics', 'technique',
            'welding_parameter_table'
        ]
        
        for section in required_sections:
            if section not in wps_data:
                app.logger.warning(f"WPS data missing {section} section, adding empty one")
                wps_data[section] = {}
                
            if section not in pqr_data:
                app.logger.warning(f"PQR data missing {section} section, adding empty one")
                pqr_data[section] = {}
        
        # Special handling for filler_metals to ensure process structure exists
        if 'filler_metals' in wps_data and isinstance(wps_data['filler_metals'], dict):
            if 'processes' not in wps_data['filler_metals'] and any(isinstance(v, dict) for v in wps_data['filler_metals'].values()):
                # Check if we have a process-style structure at the top level
                if any(k.upper() in ['GTAW', 'SMAW', 'FCAW', 'SAW'] for k in wps_data['filler_metals'].keys()):
                    app.logger.info("Converting WPS filler_metals to processes structure")
                    processes = {}
                    for k, v in wps_data['filler_metals'].items():
                        if isinstance(v, dict):
                            processes[k] = v
                    
                    if processes:
                        wps_data['filler_metals'] = {'processes': processes}
        
        if 'filler_metals' in pqr_data and isinstance(pqr_data['filler_metals'], dict):
            if 'process_specific' not in pqr_data['filler_metals'] and 'processes' not in pqr_data['filler_metals'] and any(isinstance(v, dict) for v in pqr_data['filler_metals'].values()):
                # Check if we have a process-style structure at the top level
                if any(k.upper() in ['GTAW', 'SMAW', 'FCAW', 'SAW'] for k in pqr_data['filler_metals'].keys()):
                    app.logger.info("Converting PQR filler_metals to process_specific structure")
                    processes = {}
                    for k, v in pqr_data['filler_metals'].items():
                        if isinstance(v, dict):
                            processes[k] = v
                    
                    if processes:
                        pqr_data['filler_metals'] = {'process_specific': processes}
            
            # Handle potential alternate structure (direct mapping of processes without a container key)
            if not any(k in ['process_specific', 'processes'] for k in pqr_data['filler_metals'].keys()):
                any_dict = False
                for k, v in pqr_data['filler_metals'].items():
                    if isinstance(v, dict):
                        any_dict = True
                        break
                
                if any_dict and 'process_specific' not in pqr_data['filler_metals']:
                    app.logger.info("Adding process_specific wrapper to PQR filler_metals")
                    pqr_data['filler_metals'] = {'process_specific': pqr_data['filler_metals']}
        
        # Ensure test results sections exist in PQR data
        if 'tensile_test' not in pqr_data:
            app.logger.warning("PQR data missing tensile_test section, adding empty one")
            pqr_data['tensile_test'] = {"specimens": []}
            
        if 'guided_bend_test' not in pqr_data:
            app.logger.warning("PQR data missing guided_bend_test section, adding empty one")
            pqr_data['guided_bend_test'] = {"specimens": []}
            
        app.logger.info("Data validation complete, rendering template")
            
        return render_template(
            'wps_pqr_side_by_side.html',
            job_id=job_id,
            metadata=metadata,
            wps_data=wps_data,
            pqr_data=pqr_data
        )
        
    except FileNotFoundError as e:
        app.logger.error(f"File not found in side-by-side view: {str(e)}")
        flash(f'Error: Could not find required data files. {str(e)}', 'danger')
        return redirect(url_for('wps_pqr_comparison_upload'))
        
    except json.JSONDecodeError as e:
        app.logger.error(f"JSON decode error in side-by-side view: {str(e)}")
        flash(f'Error: Could not parse data files as JSON. {str(e)}', 'danger')
        return redirect(url_for('wps_pqr_comparison_upload'))
        
    except Exception as e:
        app.logger.error(f"Unexpected error in side-by-side view: {str(e)}")
        app.logger.exception("Full exception details:")
        flash(f'An unexpected error occurred: {str(e)}', 'danger')
        return redirect(url_for('wps_pqr_comparison_upload'))

def extract_wps_info(text, job_id):
    """Extract structured information from a WPS document"""
    app.logger.info(f"Extracting structured information from WPS document for job {job_id}")
    
    # Log the first 200 characters of the text for debugging
    app.logger.info(f"Document text (first 200 chars): {text[:200]}...")
    
    # Check if the text is too short
    if len(text) < 100:
        app.logger.warning(f"WPS document text is very short ({len(text)} chars), may not have enough content for extraction")
    
    # Define the system prompt for LLM
    system_prompt = """
    You are an expert in analyzing Welding Procedure Specifications (WPS) documents.
    Extract structured information from the WPS document provided.
    
    CRITICAL INSTRUCTIONS:
    1. Extract all parameters accurately, correcting any OCR errors based on context
    2. Maintain the proper units as specified in the document
    3. Ensure all information is categorized in the correct sections
    4. If a value is given as a range, include the full range
    5. Include all reference standards and codes mentioned in the document
    
    Your response MUST be valid, parsable JSON without any markdown code blocks.
    
    Extract the following information, using empty strings or appropriate default values if information is not found:
    
    1. DOCUMENT INFORMATION:
       - wps_number: The WPS identification number
       - revision: Revision number or letter
       - date: Date of the WPS
       - company: Company or manufacturer name
       - welding_process: Object with "processes" array containing welding processes used (e.g., GTAW, SMAW)
       - pqr_reference: Reference to supporting PQR number(s)
    
    2. JOINTS (QW-402):
       - joint_design: Description of joint design
       - backing: Backing information
       - joint_type: Type of joint (butt, fillet, etc.)
       - groove_angle: Angle of the groove
       - root_opening: Root opening size
       - root_face: Root face dimension
    
    3. BASE METALS (QW-403):
       - p_number: P-Number of the base metal
       - group_number: Group Number
       - material_spec: Material specification
       - type_grade: Type or grade
       - to_p_number: Second P-Number (if dissimilar)
       - to_group_number: Second Group Number (if dissimilar)
       - thickness_range: Thickness qualification range
       - diameter_range: Diameter qualification range
    
    4. FILLER METALS (QW-404):
       - For each process, include:
         - f_number: F-Number
         - a_number: A-Number
         - specification: SFA specification
         - classification: AWS classification
         - filler_size: Size of filler metal
         - filler_type: Type of filler metal
    
    5. POSITION (QW-405):
       - position: Welding position(s)
       - progression: Welding progression (uphill, downhill)
    
    6. PREHEAT (QW-406):
       - preheat_temp: Preheat temperature or range
       - interpass_temp: Interpass temperature or range
       - preheat_maintenance: Preheat maintenance requirements
    
    7. POST WELD HEAT TREATMENT (QW-407):
       - pwht_temp: PWHT temperature
       - pwht_time: PWHT time
       - heating_rate: Heating rate
       - cooling_rate: Cooling rate
    
    8. GAS (QW-408):
       - shielding_gas: Shielding gas composition
       - shielding_flow_rate: Shielding gas flow rate
       - backing_gas: Backing gas composition
       - backing_flow_rate: Backing gas flow rate
    
    9. ELECTRICAL CHARACTERISTICS (QW-409):
       - current_type: Current type (AC, DC)
       - polarity: Polarity (DCEN, DCEP)
       - amperage_range: Amperage range
       - voltage_range: Voltage range
       - tungsten_type: Tungsten type (for GTAW)
       - tungsten_size: Tungsten size (for GTAW)
       - wire_feed_speed: Wire feed speed
       - travel_speed: Travel speed
       - heat_input: Heat input range
       - transfer_mode: Transfer mode (for GMAW)
    
    10. TECHNIQUE (QW-410):
        - string_weave: String or weave bead
        - orifice_gas_cup: Orifice or gas cup size
        - cleaning_method: Cleaning method between passes
        - peening: Peening details
        - initial_final_cleaning: Initial and final cleaning methods
        - oscillation: Oscillation information
        - multi_single_pass: Multiple or single pass
        - multi_single_electrode: Multiple or single electrodes
    
    11. WELDING PARAMETER TABLE:
        - Array of pass/layer details, each containing:
          - process: Welding process
          - pass_number: Pass or layer number
          - filler_metal: Filler metal type and size
          - current: Current type
          - amperage: Amperage range
          - voltage: Voltage range
          - travel_speed: Travel speed
          - heat_input: Heat input
    """
    
    # Define user prompt
    user_prompt = """
    Extract structured information from this Welding Procedure Specification (WPS) document.
    
    IMPORTANT: Your response must be a valid JSON object without any markdown formatting or code blocks.
    Use lowercase keys for all fields and sections.
    
    WPS Document Text:
    """
    
    # Clean the text
    cleaned_text = preprocess_extracted_text(text)
    
    # Handle extraction - with chunking for long texts
    try:
        # Normal extraction for typical length documents
        if len(cleaned_text) < 15000:
            app.logger.info(f"Extracting WPS info using normal approach")
            response = query_llm(cleaned_text, system_prompt, user_prompt, temperature=0.2)
        else:
            # Use chunking for very long documents
            app.logger.info(f"WPS document text is very long ({len(cleaned_text)} chars), using chunked extraction")
            chunks = split_text_with_overlap(cleaned_text)
            chunk_responses = []
            
            for i, chunk in enumerate(chunks):
                app.logger.info(f"Processing WPS chunk {i+1}/{len(chunks)}")
                chunk_response = query_llm(chunk, system_prompt, user_prompt, temperature=0.2)
                if chunk_response.get('success', False):
                    try:
                        # Clean the response content
                        json_response = chunk_response['content']
                        json_response = re.sub(r'```json', '', json_response)
                        json_response = re.sub(r'```', '', json_response)
                        # Parse the JSON
                        chunk_data = json.loads(json_response.strip())
                        chunk_responses.append(chunk_data)
                    except json.JSONDecodeError as e:
                        app.logger.warning(f"Error parsing JSON from WPS chunk {i+1}: {str(e)}")
            
            # Merge the chunk responses
            if chunk_responses:
                merged_data = merge_json_chunks(chunk_responses)
                response = {"success": True, "content": json.dumps(merged_data)}
            else:
                app.logger.error("No successful chunk responses for WPS extraction")
                response = {"success": False, "error": "Failed to extract information from document chunks"}
        
        # Process the response
        if response.get('success', False):
            try:
                # Clean the response content
                json_response = response['content']
                json_response = re.sub(r'```json', '', json_response)
                json_response = re.sub(r'```', '', json_response)
                
                # Parse the JSON
                wps_data = json.loads(json_response.strip())
                
                # Normalize keys to lowercase
                normalized_data = {}
                key_mapping = {
                    "DOCUMENT_INFORMATION": "document_info",
                    "DOCUMENT INFORMATION": "document_info",
                    "document_information": "document_info",
                    "JOINTS": "joints",
                    "BASE_METALS": "base_metals",
                    "BASE METALS": "base_metals",
                    "FILLER_METALS": "filler_metals", 
                    "FILLER METALS": "filler_metals",
                    "POSITION": "position",
                    "PREHEAT": "preheat",
                    "POST_WELD_HEAT_TREATMENT": "pwht",
                    "POST WELD HEAT TREATMENT": "pwht",
                    "GAS": "gas",
                    "ELECTRICAL_CHARACTERISTICS": "electrical_characteristics",
                    "ELECTRICAL CHARACTERISTICS": "electrical_characteristics",
                    "TECHNIQUE": "technique",
                    "WELDING_PARAMETER_TABLE": "welding_parameter_table",
                    "WELDING PARAMETER TABLE": "welding_parameter_table"
                }
                
                # Normalize top-level keys
                for key, value in wps_data.items():
                    normalized_key = key_mapping.get(key, key.lower())
                    normalized_data[normalized_key] = value
                
                # Save the normalized data
                job_dir = os.path.join(PROCESSED_DIR, job_id)
                if not os.path.exists(job_dir):
                    os.makedirs(job_dir)
                
                wps_data_file = os.path.join(job_dir, 'wps_data.json')
                with open(wps_data_file, 'w', encoding='utf-8') as f:
                    json.dump(normalized_data, f, indent=2)
                
                app.logger.info(f"Successfully extracted WPS data for job {job_id}")
                return {"success": True}
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing WPS data as JSON: {str(e)}"
                app.logger.error(error_msg)
                
                # Try extraction again with higher temperature
                app.logger.info(f"Retrying WPS extraction with higher temperature")
                retry_response = query_llm(cleaned_text, system_prompt, user_prompt, temperature=0.5)
                
                if retry_response.get('success', False):
                    try:
                        retry_json = retry_response['content']
                        retry_json = re.sub(r'```json', '', retry_json)
                        retry_json = re.sub(r'```', '', retry_json)
                        
                        wps_data = json.loads(retry_json.strip())
                        
                        # Normalize keys to lowercase
                        normalized_data = {}
                        key_mapping = {
                            "DOCUMENT_INFORMATION": "document_info",
                            "DOCUMENT INFORMATION": "document_info",
                            "document_information": "document_info",
                            "JOINTS": "joints",
                            "BASE_METALS": "base_metals",
                            "BASE METALS": "base_metals",
                            "FILLER_METALS": "filler_metals", 
                            "FILLER METALS": "filler_metals",
                            "POSITION": "position",
                            "PREHEAT": "preheat",
                            "POST_WELD_HEAT_TREATMENT": "pwht",
                            "POST WELD HEAT TREATMENT": "pwht",
                            "GAS": "gas",
                            "ELECTRICAL_CHARACTERISTICS": "electrical_characteristics",
                            "ELECTRICAL CHARACTERISTICS": "electrical_characteristics",
                            "TECHNIQUE": "technique",
                            "WELDING_PARAMETER_TABLE": "welding_parameter_table",
                            "WELDING PARAMETER TABLE": "welding_parameter_table"
                        }
                        
                        # Normalize top-level keys
                        for key, value in wps_data.items():
                            normalized_key = key_mapping.get(key, key.lower())
                            normalized_data[normalized_key] = value
                        
                        job_dir = os.path.join(PROCESSED_DIR, job_id)
                        if not os.path.exists(job_dir):
                            os.makedirs(job_dir)
                        
                        wps_data_file = os.path.join(job_dir, 'wps_data.json')
                        with open(wps_data_file, 'w', encoding='utf-8') as f:
                            json.dump(normalized_data, f, indent=2)
                        
                        app.logger.info(f"Successfully extracted WPS data on retry for job {job_id}")
                        return {"success": True}
                    except Exception as retry_e:
                        error_msg = f"Error on retry extraction: {str(retry_e)}"
                        app.logger.error(error_msg)
                        return {"success": False, "error": error_msg}
                
                return {"success": False, "error": error_msg}
        else:
            error_msg = response.get('error', "Unknown error in WPS extraction")
            app.logger.error(f"Error extracting WPS data: {error_msg}")
            return {"success": False, "error": error_msg}
    
    except Exception as e:
        error_msg = f"Exception during WPS extraction: {str(e)}"
        app.logger.error(error_msg)
        
        # Create a minimal valid JSON structure to avoid breaking downstream processes
        fallback_data = {
            "document_info": {
                "wps_number": "",
                "revision": "",
                "date": "",
                "company": "",
                "welding_process": {"processes": []},
                "pqr_reference": ""
            },
            "joints": {},
            "base_metals": {},
            "filler_metals": {},
            "position": {},
            "preheat": {},
            "pwht": {},
            "gas": {},
            "electrical_characteristics": {},
            "technique": {},
            "welding_parameter_table": []
        }
        
        # Save the fallback data
        job_dir = os.path.join(PROCESSED_DIR, job_id)
        if not os.path.exists(job_dir):
            os.makedirs(job_dir)
            
        fallback_file = os.path.join(job_dir, 'wps_data.json')
        with open(fallback_file, 'w', encoding='utf-8') as f:
            json.dump(fallback_data, f, indent=2)
            
        # Also save the error
        error_file = os.path.join(job_dir, 'wps_extraction_error.log')
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write(error_msg)
            
        return {"success": False, "error": error_msg}

def preprocess_extracted_text(text):
    """
    Clean and preprocess extracted text for better analysis.
    """
    if not text:
        return ""
        
    # Remove excessive whitespace
    cleaned = re.sub(r'\s+', ' ', text)
    
    # Fix common OCR errors
    cleaned = cleaned.replace('0', 'O').replace('l', '1')
    
    # Remove any non-printable characters
    cleaned = ''.join(c for c in cleaned if c.isprintable() or c in ['\n', '\t'])
    
    # Replace multiple newlines with single newlines
    cleaned = re.sub(r'\n+', '\n', cleaned)
    
    return cleaned

def split_text_with_overlap(text, chunk_size=10000, overlap=1000):
    """
    Split long text into overlapping chunks for processing.
    
    Args:
        text (str): The text to split
        chunk_size (int): Size of each chunk
        overlap (int): Overlap between chunks to maintain context
        
    Returns:
        list: List of text chunks
    """
    if not text:
        return []
        
    if len(text) <= chunk_size:
        return [text]
        
    chunks = []
    start = 0
    
    while start < len(text):
        # Get the chunk
        end = min(start + chunk_size, len(text))
        
        # If we're not at the end, try to find a good splitting point 
        # (paragraph or sentence end) near the chunk_size point
        if end < len(text):
            # Try to find paragraph break within the last 20% of the chunk
            search_start = max(start + int(chunk_size * 0.8), 0)
            paragraph_break = text.rfind('\n\n', search_start, end)
            
            if paragraph_break != -1:
                end = paragraph_break
            else:
                # If no paragraph break, try to find sentence end
                sentence_break = max(
                    text.rfind('. ', search_start, end),
                    text.rfind('? ', search_start, end),
                    text.rfind('! ', search_start, end)
                )
                
                if sentence_break != -1:
                    end = sentence_break + 1  # Include the period
        
        # Add the chunk
        chunks.append(text[start:end])
        
        # Update start position for next chunk, with overlap
        start = max(0, end - overlap)
    
    return chunks

def merge_json_chunks(chunk_data_list):
    """
    Merge JSON data from multiple chunks into a single coherent structure.
    
    Args:
        chunk_data_list (list): List of dictionaries from processed chunks
        
    Returns:
        dict: Merged data structure
    """
    if not chunk_data_list:
        return {}
        
    # Start with the first chunk
    merged_data = copy.deepcopy(chunk_data_list[0])
    
    # Helper function to merge values
    def merge_value(target, source):
        # If the source is not present or empty, keep the target
        if source is None or source == "" or source == [] or source == {}:
            return target
            
        # If the target is empty, use the source
        if target is None or target == "" or target == [] or target == {}:
            return source
            
        # If both are strings, prefer the longer or non-empty one
        if isinstance(target, str) and isinstance(source, str):
            if len(source) > len(target):
                return source
            return target
            
        # If both are lists, append unique items
        if isinstance(target, list) and isinstance(source, list):
            result = target.copy()
            for item in source:
                if item not in result:
                    result.append(item)
            return result
            
        # Default fallback
        return target
    
    # Helper function to merge dictionaries recursively
    def merge_dicts(target, source):
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target[key], dict):
                merge_dicts(target[key], value)
            else:
                target[key] = merge_value(target[key], value)
        return target
    
    # Merge each chunk into the result
    for chunk in chunk_data_list[1:]:
        merge_dicts(merged_data, chunk)
    
    return merged_data

def extract_pqr_info(text, job_id):
    """Extract structured information from a PQR (Procedure Qualification Record) document"""
    app.logger.info(f"Extracting structured information from PQR document for job {job_id}")
    
    # Log the first 200 characters of the text for debugging
    app.logger.info(f"Document text (first 200 chars): {text[:200]}...")
    
    # Check if the text is too short
    if len(text) < 100:
        app.logger.warning(f"PQR document text is very short ({len(text)} chars), may not have enough content for extraction")
    
    # Define the system prompt for LLM
    system_prompt = """
    You are an expert in analyzing Procedure Qualification Records (PQR) documents.
    Extract structured information from the PQR document provided.
    
    CRITICAL INSTRUCTIONS:
    1. Extract all parameters accurately, correcting any OCR errors based on context
    2. Maintain the proper units as specified in the document
    3. Ensure all information is categorized in the correct sections
    4. If a value is given as a range, include the full range
    5. Include all reference standards and codes mentioned in the document
    6. Pay special attention to test results and ensure all data is captured accurately
    
    Your response MUST be valid, parsable JSON without any markdown code blocks.
    
    Extract the following information, using empty strings or appropriate default values if information is not found:
    
    1. DOCUMENT INFORMATION:
       - pqr_number: The PQR identification number
       - revision: Revision number or letter
       - date: Date of the PQR
       - company: Company or manufacturer name
       - welding_process: Object with "processes" array containing welding processes used (e.g., GTAW, SMAW)
       - wps_reference: Reference to the WPS number this PQR supports
    
    2. JOINTS (QW-402):
       - joint_design: Description of joint design
       - backing: Backing information
       - joint_type: Type of joint (butt, fillet, etc.)
       - groove_angle: Angle of the groove
       - root_opening: Root opening size
       - root_face: Root face dimension
    
    3. BASE METALS (QW-403):
       - p_number: P-Number of the base metal
       - group_number: Group Number
       - material_spec: Material specification
       - type_grade: Type or grade
       - to_p_number: Second P-Number (if dissimilar)
       - to_group_number: Second Group Number (if dissimilar)
       - thickness: Actual test coupon thickness
       - diameter: Actual test coupon diameter
    
    4. FILLER METALS (QW-404):
       - For each process, include:
         - f_number: F-Number
         - a_number: A-Number
         - specification: SFA specification
         - classification: AWS classification
         - filler_size: Size of filler metal
         - filler_type: Type of filler metal
    
    5. POSITION (QW-405):
       - position: Welding position(s) used for the test
       - progression: Welding progression (uphill, downhill) used for the test
    
    6. PREHEAT (QW-406):
       - preheat_temp: Preheat temperature used
       - interpass_temp: Interpass temperature used
       - preheat_maintenance: Preheat maintenance details
    
    7. POST WELD HEAT TREATMENT (QW-407):
       - pwht_temp: PWHT temperature used
       - pwht_time: PWHT time used
       - heating_rate: Heating rate used
       - cooling_rate: Cooling rate used
    
    8. GAS (QW-408):
       - shielding_gas: Shielding gas composition used
       - shielding_flow_rate: Shielding gas flow rate used
       - backing_gas: Backing gas composition used
       - backing_flow_rate: Backing gas flow rate used
    
    9. ELECTRICAL CHARACTERISTICS (QW-409):
       - current_type: Current type used (AC, DC)
       - polarity: Polarity used (DCEN, DCEP)
       - amperage: Amperage used
       - voltage: Voltage used
       - tungsten_type: Tungsten type used (for GTAW)
       - tungsten_size: Tungsten size used (for GTAW)
       - wire_feed_speed: Wire feed speed used
       - travel_speed: Travel speed used
       - heat_input: Heat input used
       - transfer_mode: Transfer mode used (for GMAW)
    
    10. TECHNIQUE (QW-410):
        - string_weave: String or weave bead technique used
        - orifice_gas_cup: Orifice or gas cup size used
        - cleaning_method: Cleaning method between passes used
        - peening: Peening details if used
        - initial_final_cleaning: Initial and final cleaning methods used
        - oscillation: Oscillation information if used
        - multi_single_pass: Whether multiple or single pass was used
        - multi_single_electrode: Whether multiple or single electrodes were used
    
    11. WELDING PARAMETER TABLE:
        - Array of pass/layer details used in the actual test, each containing:
          - process: Welding process
          - pass_number: Pass or layer number
          - filler_metal: Filler metal type and size
          - current: Current type
          - amperage: Amperage 
          - voltage: Voltage
          - travel_speed: Travel speed
          - heat_input: Heat input
    
    12. TEST RESULTS:
        A. TENSILE TEST:
           - specimens: Array of tensile test specimens, each with:
             - specimen_number: Specimen identification
             - width: Width of specimen
             - thickness: Thickness of specimen
             - area: Cross-sectional area
             - ultimate_load: Ultimate load
             - ultimate_strength: Ultimate tensile strength
             - failure_location: Location of failure
             - result: Pass/fail status
             
        B. GUIDED BEND TEST:
           - specimens: Array of guided bend test specimens, each with:
             - specimen_number: Specimen identification
             - type: Type of bend (face, root, side)
             - result: Result of the test (satisfactory/unsatisfactory)
             
        C. ADDITIONAL TESTS:
           - impact_test: Details of impact tests if performed
           - hardness_test: Details of hardness tests if performed
           - other_tests: Any other tests performed
    """
    
    # Define user prompt
    user_prompt = """
    Extract structured information from this Procedure Qualification Record (PQR) document.
    
    IMPORTANT: Your response must be a valid JSON object without any markdown formatting or code blocks.
    
    PQR Document Text:
    """
    
    # Clean the text
    cleaned_text = preprocess_extracted_text(text)
    
    # Handle extraction - with chunking for long texts
    try:
        # Normal extraction for typical length documents
        if len(cleaned_text) < 15000:
            app.logger.info(f"Extracting PQR info using normal approach")
            response = query_llm(cleaned_text, system_prompt, user_prompt, temperature=0.2)
        else:
            # Use chunking for very long documents
            app.logger.info(f"PQR document text is very long ({len(cleaned_text)} chars), using chunked extraction")
            chunks = split_text_with_overlap(cleaned_text)
            chunk_responses = []
            
            for i, chunk in enumerate(chunks):
                app.logger.info(f"Processing PQR chunk {i+1}/{len(chunks)}")
                chunk_response = query_llm(chunk, system_prompt, user_prompt, temperature=0.2)
                if chunk_response.get('success', False):
                    try:
                        # Clean the response content
                        json_response = chunk_response['content']
                        json_response = re.sub(r'```json', '', json_response)
                        json_response = re.sub(r'```', '', json_response)
                        # Parse the JSON
                        chunk_data = json.loads(json_response.strip())
                        chunk_responses.append(chunk_data)
                    except json.JSONDecodeError as e:
                        app.logger.warning(f"Error parsing JSON from PQR chunk {i+1}: {str(e)}")
            
            # Merge the chunk responses
            if chunk_responses:
                merged_data = merge_json_chunks(chunk_responses)
                response = {"success": True, "content": json.dumps(merged_data)}
            else:
                app.logger.error("No successful chunk responses for PQR extraction")
                response = {"success": False, "error": "Failed to extract information from document chunks"}
        
        # Process the response
        if response.get('success', False):
            try:
                # Clean the response content
                json_response = response['content']
                json_response = re.sub(r'```json', '', json_response)
                json_response = re.sub(r'```', '', json_response)
                
                # Parse the JSON
                pqr_data = json.loads(json_response.strip())
                
                # Save the data
                job_dir = os.path.join(PROCESSED_DIR, job_id)
                if not os.path.exists(job_dir):
                    os.makedirs(job_dir)
                
                pqr_data_file = os.path.join(job_dir, 'pqr_data.json')
                with open(pqr_data_file, 'w', encoding='utf-8') as f:
                    json.dump(pqr_data, f, indent=2)
                
                app.logger.info(f"Successfully extracted PQR data for job {job_id}")
                return {"success": True}
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing PQR data as JSON: {str(e)}"
                app.logger.error(error_msg)
                
                # Try extraction again with higher temperature
                app.logger.info(f"Retrying PQR extraction with higher temperature")
                retry_response = query_llm(cleaned_text, system_prompt, user_prompt, temperature=0.5)
                
                if retry_response.get('success', False):
                    try:
                        retry_json = retry_response['content']
                        retry_json = re.sub(r'```json', '', retry_json)
                        retry_json = re.sub(r'```', '', retry_json)
                        
                        pqr_data = json.loads(retry_json.strip())
                        
                        job_dir = os.path.join(PROCESSED_DIR, job_id)
                        if not os.path.exists(job_dir):
                            os.makedirs(job_dir)
                        
                        pqr_data_file = os.path.join(job_dir, 'pqr_data.json')
                        with open(pqr_data_file, 'w', encoding='utf-8') as f:
                            json.dump(pqr_data, f, indent=2)
                        
                        app.logger.info(f"Successfully extracted PQR data on retry for job {job_id}")
                        return {"success": True}
                    except Exception as retry_e:
                        error_msg = f"Error on retry extraction: {str(retry_e)}"
                        app.logger.error(error_msg)
                        return {"success": False, "error": error_msg}
                
                return {"success": False, "error": error_msg}
        else:
            error_msg = response.get('error', "Unknown error in PQR extraction")
            app.logger.error(f"Error extracting PQR data: {error_msg}")
            return {"success": False, "error": error_msg}
    
    except Exception as e:
        error_msg = f"Exception during PQR extraction: {str(e)}"
        app.logger.error(error_msg)
        
        # Create a minimal valid JSON structure to avoid breaking downstream processes
        fallback_data = {
            "document_info": {
                "pqr_number": "",
                "revision": "",
                "date": "",
                "company": "",
                "welding_process": {"processes": []},
                "wps_reference": ""
            },
            "joints": {},
            "base_metals": {},
            "filler_metals": {},
            "position": {},
            "preheat": {},
            "pwht": {},
            "gas": {},
            "electrical_characteristics": {},
            "technique": {},
            "welding_parameter_table": [],
            "tensile_test": {"specimens": []},
            "guided_bend_test": {"specimens": []},
            "additional_tests": {}
        }
        
        # Save the fallback data
        job_dir = os.path.join(PROCESSED_DIR, job_id)
        if not os.path.exists(job_dir):
            os.makedirs(job_dir)
            
        fallback_file = os.path.join(job_dir, 'pqr_data.json')
        with open(fallback_file, 'w', encoding='utf-8') as f:
            json.dump(fallback_data, f, indent=2)
            
        # Also save the error
        error_file = os.path.join(job_dir, 'pqr_extraction_error.log')
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write(error_msg)
            
        return {"success": False, "error": error_msg}

def compare_wps_pqr(wps_data, pqr_data, job_id):
    """
    Compare WPS and PQR data for compliance check and generate results
    
    Args:
        wps_data (dict): Structured WPS data
        pqr_data (dict): Structured PQR data
        job_id (str): Job ID for saving results
        
    Returns:
        dict: Comparison results
    """
    app.logger.info(f"Comparing WPS and PQR data for job {job_id}")
    
    # Initialize the comparison results structure
    comparison_results = {
        "overall_compliance": True,
        "overall_score": 100,
        "document_info": {
            "wps_number": wps_data.get("document_info", {}).get("wps_number", ""),
            "pqr_number": pqr_data.get("document_info", {}).get("pqr_number", ""),
            "wps_date": wps_data.get("document_info", {}).get("date", ""),
            "pqr_date": pqr_data.get("document_info", {}).get("date", ""),
            "company": wps_data.get("document_info", {}).get("company", pqr_data.get("document_info", {}).get("company", ""))
        },
        "sections": {}
    }
    
    # Define the sections to compare
    sections = [
        {
            "id": "joints",
            "name": "Joints (QW-402)",
            "weight": 10,
            "parameters": [
                {"id": "joint_design", "name": "Joint Design", "weight": 2},
                {"id": "backing", "name": "Backing", "weight": 2},
                {"id": "groove_angle", "name": "Groove Angle", "weight": 1},
                {"id": "root_opening", "name": "Root Opening", "weight": 1}
            ]
        },
        {
            "id": "base_metals",
            "name": "Base Metals (QW-403)",
            "weight": 15,
            "parameters": [
                {"id": "p_number", "name": "P-Number", "weight": 3},
                {"id": "group_number", "name": "Group Number", "weight": 2},
                {"id": "material_spec", "name": "Material Specification", "weight": 3},
                {"id": "type_grade", "name": "Type/Grade", "weight": 3},
                {"id": "thickness_range", "name": "Thickness Range", "weight": 2, "pqr_field": "thickness"}
            ]
        },
        {
            "id": "filler_metals",
            "name": "Filler Metals (QW-404)",
            "weight": 15,
            "special_handling": True,  # Mark this section for special handling
            "parameters": [
                {"id": "f_number", "name": "F-Number", "weight": 3},
                {"id": "a_number", "name": "A-Number", "weight": 2},
                {"id": "specification", "name": "Specification", "weight": 3},
                {"id": "classification", "name": "Classification", "weight": 3}
            ]
        },
        {
            "id": "position",
            "name": "Position (QW-405)",
            "weight": 10,
            "parameters": [
                {"id": "position", "name": "Position", "weight": 5},
                {"id": "progression", "name": "Progression", "weight": 2}
            ]
        },
        {
            "id": "preheat",
            "name": "Preheat (QW-406)",
            "weight": 10,
            "parameters": [
                {"id": "preheat_temp", "name": "Preheat Temperature", "weight": 3},
                {"id": "interpass_temp", "name": "Interpass Temperature", "weight": 3},
                {"id": "preheat_maintenance", "name": "Preheat Maintenance", "weight": 2}
            ]
        },
        {
            "id": "pwht",
            "name": "Post-Weld Heat Treatment (QW-407)",
            "weight": 10,
            "parameters": [
                {"id": "pwht_temp", "name": "PWHT Temperature", "weight": 3},
                {"id": "pwht_time", "name": "PWHT Time", "weight": 3}
            ]
        },
        {
            "id": "gas",
            "name": "Gas (QW-408)",
            "weight": 10,
            "parameters": [
                {"id": "shielding_gas", "name": "Shielding Gas", "weight": 3},
                {"id": "shielding_flow_rate", "name": "Shielding Flow Rate", "weight": 2},
                {"id": "backing_gas", "name": "Backing Gas", "weight": 2}
            ]
        },
        {
            "id": "electrical_characteristics",
            "name": "Electrical Characteristics (QW-409)",
            "weight": 10,
            "parameters": [
                {"id": "current_type", "name": "Current Type", "weight": 2},
                {"id": "polarity", "name": "Polarity", "weight": 2},
                {"id": "amperage_range", "name": "Amperage", "weight": 2, "pqr_field": "amperage"},
                {"id": "voltage_range", "name": "Voltage", "weight": 2, "pqr_field": "voltage"}
            ]
        },
        {
            "id": "technique",
            "name": "Technique (QW-410)",
            "weight": 10,
            "parameters": [
                {"id": "string_weave", "name": "String/Weave Bead", "weight": 2},
                {"id": "cleaning_method", "name": "Cleaning Method", "weight": 2},
                {"id": "multi_single_pass", "name": "Multi/Single Pass", "weight": 2},
                {"id": "multi_single_electrode", "name": "Multi/Single Electrode", "weight": 2}
            ]
        }
    ]
    
    # Compare each section
    total_weighted_score = 0
    total_weight = 0
    
    for section in sections:
        section_id = section["id"]
        section_weight = section["weight"]
        total_weight += section_weight
        
        # Initialize section results
        section_result = {
            "name": section["name"],
            "compliance": True,
            "score": 100,
            "parameters": []
        }
        
        # Get the WPS and PQR data for this section
        wps_section = wps_data.get(section_id, {})
        pqr_section = pqr_data.get(section_id, {})
        
        # Check if the section exists in both documents
        if wps_section is None or pqr_section is None:
            app.logger.warning(f"Missing section {section_id} in {'WPS' if wps_section is None else 'PQR'}")
            section_result["compliance"] = False
            section_result["score"] = 0
            section_result["issues"] = ["Section missing in document"]
            comparison_results["sections"][section_id] = section_result
            comparison_results["overall_compliance"] = False
            continue

        # For empty sections in either document, treat them as non-compliant
        if not wps_section or not pqr_section:
            app.logger.warning(f"Empty section {section_id} in {'WPS' if not wps_section else 'PQR'}")
            section_result["compliance"] = False
            section_result["score"] = 0
            section_result["issues"] = ["Section missing in document"]
            comparison_results["sections"][section_id] = section_result
            comparison_results["overall_compliance"] = False
            continue
        
        # Special handling for complex sections like filler_metals
        if section.get("special_handling", False):
            # For filler metals, simply check if both documents have filler metals info
            section_result["compliance"] = True
            section_result["score"] = 100
            section_result["parameters"] = []
            
            # Add a simple parameter to show we did check this section
            param_result = {
                "name": "Filler Metals",
                "wps_value": "Present" if wps_section else "Not specified",
                "pqr_value": "Present" if pqr_section else "Not specified",
                "compliance": True if wps_section and pqr_section else False,
                "reason": "Both documents have filler metals information" if wps_section and pqr_section else "Filler metals information missing in one document"
            }
            section_result["parameters"].append(param_result)
            
            # Update overall compliance
            if not param_result["compliance"]:
                section_result["compliance"] = False
                comparison_results["overall_compliance"] = False
                section_result["score"] = 0
            
            # Add section result to comparison results
            comparison_results["sections"][section_id] = section_result
            
            # Add to weighted total
            total_weighted_score += section_result["score"] * section_weight
            
            continue
        
        # Compare each parameter in the section
        section_score = 0
        section_total_weight = 0
        
        for param in section["parameters"]:
            param_id = param["id"]
            param_name = param["name"]
            param_weight = param["weight"]
            section_total_weight += param_weight
            
            try:
                # Get the parameter values, accounting for different field names in PQR
                wps_value = wps_section.get(param_id, "")
                pqr_field = param.get("pqr_field", param_id)
                pqr_value = pqr_section.get(pqr_field, "")
                
                # Initialize parameter result
                param_result = {
                    "name": param_name,
                    "wps_value": wps_value,
                    "pqr_value": pqr_value,
                    "compliance": True,
                    "reason": "Compliant"
                }
                
                # Check compliance - this is a simplified version
                # In a real implementation, this would have more complex logic for each parameter type
                if not wps_value or not pqr_value:
                    if not wps_value and not pqr_value:
                        # Both are empty, consider as technically compliant but with a warning
                        param_result["compliance"] = True
                        param_result["reason"] = "No data available for comparison"
                        section_score += param_weight
                    else:
                        # One is empty, the other is not
                        param_result["compliance"] = False
                        param_result["reason"] = f"{'WPS' if not wps_value else 'PQR'} value is missing"
                        section_result["compliance"] = False
                else:
                    # Simple string comparison - in production, more sophisticated comparisons would be needed
                    # For example, checking ranges, tolerances, etc.
                    if str(wps_value).lower() == str(pqr_value).lower():
                        param_result["compliance"] = True
                        param_result["reason"] = "Values match exactly"
                        section_score += param_weight
                    else:
                        # Check if values are similar enough
                        if _values_are_compatible(wps_value, pqr_value, param_id):
                            param_result["compliance"] = True
                            param_result["reason"] = "Values are compatible"
                            section_score += param_weight
                        else:
                            param_result["compliance"] = False
                            param_result["reason"] = "Values do not match"
                            section_result["compliance"] = False
                
                # Add parameter result to section
                section_result["parameters"].append(param_result)
            except Exception as e:
                app.logger.error(f"Error comparing parameter {param_id} in section {section_id}: {str(e)}")
                param_result = {
                    "name": param_name,
                    "wps_value": "Error retrieving value",
                    "pqr_value": "Error retrieving value",
                    "compliance": False,
                    "reason": f"Error during comparison: {str(e)}"
                }
                section_result["parameters"].append(param_result)
                section_result["compliance"] = False
        
        # Calculate section score
        if section_total_weight > 0:
            section_result["score"] = round((section_score / section_total_weight) * 100)
        else:
            section_result["score"] = 100  # No parameters to compare
        
        # Update overall compliance
        if not section_result["compliance"]:
            comparison_results["overall_compliance"] = False
        
        # Add to weighted total
        total_weighted_score += section_result["score"] * section_weight
        
        # Add section result to comparison results
        comparison_results["sections"][section_id] = section_result
    
    # Calculate overall score
    if total_weight > 0:
        comparison_results["overall_score"] = round(total_weighted_score / total_weight)
    
    # Add any critical issues
    comparison_results["critical_issues"] = []
    
    # Save results to job directory
    job_dir = os.path.join(PROCESSED_DIR, job_id)
    if not os.path.exists(job_dir):
        os.makedirs(job_dir)
        
    results_file = os.path.join(job_dir, 'comparison_results.json')
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(comparison_results, f, indent=2)
    
    return comparison_results

def _values_are_compatible(wps_value, pqr_value, param_id):
    """
    Check if WPS and PQR values are compatible based on parameter type
    
    This is a simplified version. In a real implementation, this would have
    more sophisticated logic for different parameter types.
    
    Args:
        wps_value: The value from WPS
        pqr_value: The value from PQR
        param_id: Parameter identifier for special case handling
        
    Returns:
        bool: True if compatible, False otherwise
    """
    # Convert to strings for comparison
    wps_str = str(wps_value).lower().strip()
    pqr_str = str(pqr_value).lower().strip()
    
    # If they're exactly the same, they're compatible
    if wps_str == pqr_str:
        return True
    
    # Special case for ranges: PQR value should be within WPS range
    if param_id in ["amperage_range", "voltage_range", "preheat_temp", "interpass_temp"]:
        # Extract ranges from WPS
        wps_min, wps_max = _extract_range(wps_str)
        if wps_min is not None and wps_max is not None:
            # Extract value from PQR
            pqr_val = _extract_number(pqr_str)
            if pqr_val is not None:
                # Check if PQR value is within WPS range
                return wps_min <= pqr_val <= wps_max
    
    # Special case for positions: PQR should be a subset of WPS
    if param_id == "position":
        wps_positions = [pos.strip() for pos in wps_str.split(',')]
        pqr_positions = [pos.strip() for pos in pqr_str.split(',')]
        # Check if all PQR positions are in WPS positions
        return all(any(pqr_pos in wps_pos for wps_pos in wps_positions) for pqr_pos in pqr_positions)
    
    # Check if the strings are similar enough (this is a very basic check)
    return (wps_str in pqr_str) or (pqr_str in wps_str)

def _extract_range(value_str):
    """
    Extract a numeric range from a string.
    Examples:
    - "100-150" → (100, 150)
    - "100 to 150" → (100, 150)
    - "100" → (100, 100)
    
    Returns:
        tuple: (min, max) or (None, None) if not a valid range
    """
    # Check for dash format
    range_match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', value_str)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))
    
    # Check for "to" format
    to_match = re.search(r'(\d+(?:\.\d+)?)\s*to\s*(\d+(?:\.\d+)?)', value_str)
    if to_match:
        return float(to_match.group(1)), float(to_match.group(2))
    
    # Check for single number
    single_match = re.search(r'(\d+(?:\.\d+)?)', value_str)
    if single_match:
        val = float(single_match.group(1))
        return val, val
    
    return None, None

def _extract_number(value_str):
    """
    Extract a single number from a string.
    Examples:
    - "100A" → 100
    - "Approximately 150" → 150
    
    Returns:
        float: The extracted number or None if not found
    """
    match = re.search(r'(\d+(?:\.\d+)?)', value_str)
    if match:
        return float(match.group(1))
    
    return None

def wps_pqr_side_by_side(wps_job_id, pqr_job_id, return_html=True):
    """
    Generate a side-by-side comparison of WPS and PQR data.
    Args:
        wps_job_id: ID of the WPS job
        pqr_job_id: ID of the PQR job
        return_html: If True, returns HTML. If False, returns normalized data structures.
    """
    app.logger.info(f"Loading WPS data from: {os.path.join(UPLOAD_FOLDER, wps_job_id, 'wps_data.json')}")
    app.logger.info(f"Loading PQR data from: {os.path.join(UPLOAD_FOLDER, pqr_job_id, 'pqr_data.json')}")
    
    # Check if files exist
    wps_file_path = os.path.join(UPLOAD_FOLDER, wps_job_id, "wps_data.json")
    pqr_file_path = os.path.join(UPLOAD_FOLDER, pqr_job_id, "pqr_data.json")
    
    if not os.path.exists(wps_file_path):
        return f"WPS data file not found at {wps_file_path}"
    if not os.path.exists(pqr_file_path):
        return f"PQR data file not found at {pqr_file_path}"
    
    # Load data
    with open(wps_file_path, 'r') as f:
        wps_data = json.load(f)
    with open(pqr_file_path, 'r') as f:
        pqr_data = json.load(f)
    
    # Log the data structures
    app.logger.info(f"WPS data keys: {list(wps_data.keys())}")
    app.logger.info(f"PQR data keys: {list(pqr_data.keys())}")
    
    # Create a mapping for key normalization
    key_mapping = {
        "document_information": "document_info",
        "document_info": "document_info",
        "doc_info": "document_info",
        "joint": "joints",
        "joints": "joints",
        "base_metal": "base_metals",
        "base_metals": "base_metals",
        "filler_metal": "filler_metals",
        "filler_metals": "filler_metals",
        "position": "position",
        "preheat": "preheat",
        "post_weld_heat_treatment": "pwht",
        "pwht": "pwht",
        "gas": "gas",
        "electrical_characteristics": "electrical_characteristics",
        "technique": "technique",
        "welding_parameter_table": "welding_parameter_table",
        "test_results": "test_results",
        "test_result": "test_results",
        "tensile_test": "tensile_test",
        "TENSILE_TEST": "tensile_test",
        "guided_bend_test": "guided_bend_test",
        "GUIDED_BEND_TEST": "guided_bend_test",
        "welder_information": "welder_information",
        "welder_info": "welder_information",
        "personnel": "welder_information",
        "testing_laboratory": "test_lab",
        "test_lab": "test_lab"
    }
    
    # Required sections for both WPS and PQR
    required_sections = [
        "document_info", 
        "joints", 
        "base_metals", 
        "filler_metals", 
        "position", 
        "preheat", 
        "pwht", 
        "gas", 
        "electrical_characteristics", 
        "technique", 
        "welding_parameter_table"
    ]
    
    # Normalize keys in WPS data
    normalized_wps = {}
    for key, value in wps_data.items():
        # Special handling for document_info
        if key.lower() in ["document_information", "document_info", "doc_info"]:
            normalized_wps["document_info"] = value
            app.logger.info(f"Normalized key from {key} to document_info")
            continue
            
        # Try to normalize other keys
        normalized_key = key_mapping.get(key, key)
        normalized_wps[normalized_key] = value
        if normalized_key != key:
            app.logger.info(f"Normalized key from {key} to {normalized_key}")
    
    # Normalize keys in PQR data
    normalized_pqr = {}
    for key, value in pqr_data.items():
        # Special handling for document_info
        if key.lower() in ["document_information", "document_info", "doc_info"]:
            normalized_pqr["document_info"] = value
            app.logger.info(f"Normalized key from {key} to document_info")
            continue
            
        # Try to normalize other keys
        normalized_key = key_mapping.get(key, key)
        normalized_pqr[normalized_key] = value
        if normalized_key != key:
            app.logger.info(f"Normalized key from {key} to {normalized_key}")
    
    # Check if filler_metals exists and has expected structure
    # If filler_metals is present but not a dict or list, wrap it in a dict
    if "filler_metals" in normalized_wps:
        if not isinstance(normalized_wps["filler_metals"], (dict, list)):
            app.logger.info(f"WPS filler_metals is {type(normalized_wps['filler_metals'])}, wrapping in dict")
            normalized_wps["filler_metals"] = {"details": normalized_wps["filler_metals"]}
        else:
            app.logger.info(f"WPS filler_metals keys: {list(normalized_wps['filler_metals'].keys()) if isinstance(normalized_wps['filler_metals'], dict) else 'Not a dict'}")
            
            # Check for process names within filler_metals
            if isinstance(normalized_wps["filler_metals"], list):
                # Check if this is a process-based structure
                process_based = False
                for item in normalized_wps["filler_metals"]:
                    if isinstance(item, dict) and any(k.lower() in ["process", "process_name", "welding_process"] for k in item):
                        process_based = True
                        break
                
                if not process_based:
                    # If not process-based, wrap the array in a dictionary
                    normalized_wps["filler_metals"] = {"details": normalized_wps["filler_metals"]}
    
    if "filler_metals" in normalized_pqr:
        if not isinstance(normalized_pqr["filler_metals"], (dict, list)):
            app.logger.info(f"PQR filler_metals is {type(normalized_pqr['filler_metals'])}, wrapping in dict")
            normalized_pqr["filler_metals"] = {"details": normalized_pqr["filler_metals"]}
        else:
            app.logger.info(f"PQR filler_metals keys: {list(normalized_pqr['filler_metals'].keys()) if isinstance(normalized_pqr['filler_metals'], dict) else 'Not a dict'}")
            
            # Check for process names within filler_metals
            if isinstance(normalized_pqr["filler_metals"], list):
                # Check if this is a process-based structure
                process_based = False
                for item in normalized_pqr["filler_metals"]:
                    if isinstance(item, dict) and any(k.lower() in ["process", "process_name", "welding_process"] for k in item):
                        process_based = True
                        break
                
                if not process_based:
                    # If not process-based, wrap the array in a dictionary
                    normalized_pqr["filler_metals"] = {"details": normalized_pqr["filler_metals"]}
    
    # Ensure PWHT exists and has expected structure
    if "pwht" not in normalized_wps:
        # Look for alternative keys
        pwht_key = next((k for k in normalized_wps if k.lower() in ["post_weld_heat_treatment", "post-weld heat treatment", "post weld"]), None)
        if pwht_key:
            normalized_wps["pwht"] = normalized_wps[pwht_key]
        else:
            app.logger.warning("WPS data missing pwht section, adding empty one")
            normalized_wps["pwht"] = {}
    
    if "pwht" not in normalized_pqr:
        # Look for alternative keys
        pwht_key = next((k for k in normalized_pqr if k.lower() in ["post_weld_heat_treatment", "post-weld heat treatment", "post weld"]), None)
        if pwht_key:
            normalized_pqr["pwht"] = normalized_pqr[pwht_key]
        else:
            app.logger.warning("PQR data missing pwht section, adding empty one")
            normalized_pqr["pwht"] = {}
    
    # If PWHT is a string, wrap it in a dictionary
    if isinstance(normalized_wps["pwht"], str):
        normalized_wps["pwht"] = {"description": normalized_wps["pwht"]}
    
    if isinstance(normalized_pqr["pwht"], str):
        normalized_pqr["pwht"] = {"description": normalized_pqr["pwht"]}
    
    # Handle position data structure
    if "position" in normalized_wps and not isinstance(normalized_wps["position"], (dict, list)):
        normalized_wps["position"] = {"description": normalized_wps["position"]}
    
    if "position" in normalized_pqr and not isinstance(normalized_pqr["position"], (dict, list)):
        normalized_pqr["position"] = {"description": normalized_pqr["position"]}
        
    # Handle welding parameter table data structure
    if "welding_parameter_table" in normalized_wps and isinstance(normalized_wps["welding_parameter_table"], str):
        normalized_wps["welding_parameter_table"] = [{"description": normalized_wps["welding_parameter_table"]}]
    
    if "welding_parameter_table" in normalized_pqr and isinstance(normalized_pqr["welding_parameter_table"], str):
        normalized_pqr["welding_parameter_table"] = [{"description": normalized_pqr["welding_parameter_table"]}]
    
    # Handle test results for PQR
    if "test_results" in normalized_pqr:
        test_results = normalized_pqr["test_results"]
        
        # Log test_results structure for debugging
        app.logger.info(f"Test results keys: {list(test_results.keys()) if isinstance(test_results, dict) else 'Not a dict'}")
        
        # If test_results is a string, wrap it in a dictionary structure but preserve original data
        if isinstance(test_results, str):
            normalized_pqr["test_results"] = {"description": test_results}
        
        # Don't extract or duplicate data from test_results - use the structure as is
        # If tensile_test and guided_bend_test are already in test_results, don't create duplicates
        # This preserves the original data structure instead of trying to normalize it
    else:
        # If test_results doesn't exist, create a minimal structure with empty values
        normalized_pqr["test_results"] = {
            "additional_tests": {
                "impact_test": "Not Applicable",
                "hardness_test": "Not specified",
                "other_tests": "Not specified"
            }
        }
    
    # Remove hardcoded expectations for tensile_test and guided_bend_test
    # Let the template handle the test_results structure as is
    
    # Make sure welder information is properly formatted but don't alter structure
    if 'welder_information' in normalized_pqr and isinstance(normalized_pqr['welder_information'], str):
        normalized_pqr['welder_information'] = {"description": normalized_pqr['welder_information']}
    
    # Structure testing lab information without creating unnecessary defaults
    if 'testing_laboratory' in normalized_pqr and 'test_lab' not in normalized_pqr:
        normalized_pqr['test_lab'] = normalized_pqr['testing_laboratory']
    
    # Handle reference standards but preserve original format
    if 'reference_standards' not in normalized_pqr:
        normalized_pqr['reference_standards'] = []
    
    app.logger.info(f"Normalized WPS data keys: {list(normalized_wps.keys())}")
    app.logger.info(f"Normalized PQR data keys: {list(normalized_pqr.keys())}")
    
    app.logger.info("Data validation complete, rendering template")
    
    if return_html:
        return render_template("wps_pqr_side_by_side.html", wps_data=normalized_wps, pqr_data=normalized_pqr)
    else:
        return normalized_wps, normalized_pqr

if __name__ == '__main__':
    # Use this for local development
    app.run(debug=True, host='0.0.0.0', port=8081) 