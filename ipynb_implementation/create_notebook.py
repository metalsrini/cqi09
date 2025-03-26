import nbformat as nbf

# Create a new notebook
nb = nbf.v4.new_notebook()

# Create markdown cell for introduction
intro_md = """# WPS/PQR Document Comparison Tool

This notebook provides a standalone implementation of the WPS/PQR comparison functionality. It allows you to:

1. Upload WPS and PQR documents (PDF, JPG, PNG formats)
2. Extract text using advanced OCR
3. Extract structured information using DeepSeek API
4. Compare WPS and PQR data
5. View detailed comparison results

## Setup and Requirements

First, let's install and import all necessary packages:"""

# Create code cell for package installation
install_code = """# Install required packages
!pip install openai python-dotenv pandas numpy plotly ipywidgets unstract-llmwhisperer"""

# Create code cell for imports and setup
setup_code = """# Import required libraries
import os
import json
import tempfile
import time
import re
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from IPython.display import display, HTML, clear_output
import ipywidgets as widgets
from openai import OpenAI
from unstract.llmwhisperer import LLMWhispererClientV2
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-3a1f47e0f1734d9d87f520401c338fa1")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_WHISPERER_API_KEY = os.environ.get("LLM_WHISPERER_API_KEY", "VrhdIbiToy-LNtrnSeq5fnVeSE3MCAj3myKc-ZGUZG8")
LLM_WHISPERER_API_URL = os.environ.get("LLM_WHISPERER_API_URL", "https://llmwhisperer-api.us-central.unstract.com/api/v2")

# Initialize OpenAI client for DeepSeek
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)"""

# Create markdown cell for helper functions
helper_md = """## Helper Functions

Let's define the core functions for processing and comparing documents:"""

# Create code cell for helper functions
helper_code = """def init_llmwhisperer_client():
    if not LLM_WHISPERER_API_KEY:
        logger.error("LLMWhisperer API key is not set")
        return None
    return LLMWhispererClientV2(
        base_url=LLM_WHISPERER_API_URL,
        api_key=LLM_WHISPERER_API_KEY
    )

def process_document(file_path, file_type):
    client = init_llmwhisperer_client()
    if client is None:
        return {"success": False, "error": "LLMWhisperer client initialization failed"}
        
    try:
        # Process with LLMWhisperer
        print(f"Starting document processing for {file_type}...")
        result = client.whisper(
            file_path=file_path,
            wait_for_completion=True,
            wait_timeout=600,
            mode='form',
            output_mode='layout_preserving',
            lang='eng'
        )
        
        print(f"LLMWhisperer response: {result}")
        
        if not result:
            return {"success": False, "error": "No response from LLMWhisperer"}
            
        if not isinstance(result, dict):
            return {"success": False, "error": f"Unexpected response format: {type(result)}"}
            
        if 'text' not in result:
            return {"success": False, "error": f"No text in response. Response keys: {result.keys()}"}
            
        if not result['text'].strip():
            return {"success": False, "error": "Extracted text is empty"}
            
        return {"success": True, "text": result['text']}
        
    except Exception as e:
        print(f"Error details: {str(e)}")
        return {"success": False, "error": str(e)}

def query_llm(document_text, system_prompt, user_prompt, temperature=0.3):
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_prompt}\\n\\n{document_text}"}
        ]
        
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=temperature,
            max_tokens=4000
        )
        
        if not response or not response.choices:
            return {"success": False, "error": "No response from API"}
            
        content = response.choices[0].message.content
        
        # Clean JSON response if needed
        if '```json' in content or '```' in content:
            content = re.sub(r'```json', '', content)
            content = re.sub(r'```', '', content)
            
        return {"success": True, "content": content}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def extract_structured_info(text, doc_type):
    # Define prompts based on document type
    if doc_type.upper() == 'WPS':
        system_prompt = '''
        You are an expert in analyzing Welding Procedure Specifications (WPS).
        Extract structured information from the WPS document provided.
        Your response must be valid JSON without markdown formatting.
        '''
    else:  # PQR
        system_prompt = '''
        You are an expert in analyzing Procedure Qualification Records (PQR).
        Extract structured information from the PQR document provided.
        Your response must be valid JSON without markdown formatting.
        '''
    
    user_prompt = f"Extract structured information from this {doc_type} document."
    
    response = query_llm(text, system_prompt, user_prompt, temperature=0.2)
    
    if response["success"]:
        try:
            data = json.loads(response["content"].strip())
            return {"success": True, "data": data}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON parsing error: {str(e)}"}
    
    return response"""

# Create markdown cell for document upload section
upload_md = """## Document Upload and Processing

Now let's create interactive widgets for document upload and processing:"""

# Create code cell for document upload widgets
upload_code = """# Create file upload widgets
wps_upload = widgets.FileUpload(
    description='Upload WPS',
    accept='.pdf,.jpg,.jpeg,.png',
    multiple=False
)

pqr_upload = widgets.FileUpload(
    description='Upload PQR',
    accept='.pdf,.jpg,.jpeg,.png',
    multiple=False
)

process_button = widgets.Button(
    description='Compare Documents',
    button_style='primary',
    disabled=True
)

output = widgets.Output()

def on_upload_change(_):
    process_button.disabled = not (len(wps_upload.value) > 0 and len(pqr_upload.value) > 0)

wps_upload.observe(on_upload_change, names='value')
pqr_upload.observe(on_upload_change, names='value')

def process_documents(_):
    with output:
        clear_output()
        print("Processing documents...")
        
        # Save uploaded files
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(wps_upload.value[0].name)[1], delete=False) as tmp_wps:
            tmp_wps.write(wps_upload.value[0].content)
            wps_path = tmp_wps.name
            
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(pqr_upload.value[0].name)[1], delete=False) as tmp_pqr:
            tmp_pqr.write(pqr_upload.value[0].content)
            pqr_path = tmp_pqr.name
        
        try:
            # Process WPS
            print("Extracting text from WPS...")
            wps_result = process_document(wps_path, 'WPS')
            if not wps_result["success"]:
                print(f"Error processing WPS: {wps_result['error']}")
                return
                
            # Process PQR
            print("Extracting text from PQR...")
            pqr_result = process_document(pqr_path, 'PQR')
            if not pqr_result["success"]:
                print(f"Error processing PQR: {pqr_result['error']}")
                return
                
            # Extract structured information
            print("Extracting structured information from WPS...")
            wps_info = extract_structured_info(wps_result["text"], "WPS")
            if not wps_info["success"]:
                print(f"Error extracting WPS info: {wps_info['error']}")
                return
                
            print("Extracting structured information from PQR...")
            pqr_info = extract_structured_info(pqr_result["text"], "PQR")
            if not pqr_info["success"]:
                print(f"Error extracting PQR info: {pqr_info['error']}")
                return
                
            # Display results
            display_comparison(wps_info["data"], pqr_info["data"])
            
        finally:
            # Cleanup temporary files
            os.unlink(wps_path)
            os.unlink(pqr_path)

process_button.on_click(process_documents)

# Display widgets
display(widgets.VBox([
    widgets.HBox([wps_upload, pqr_upload]),
    process_button,
    output
]))"""

# Create markdown cell for results display section
results_md = """## Results Display Functions

Functions to display the comparison results in a clear, organized format:"""

# Create code cell for results display function
results_code = """def display_comparison(wps_data, pqr_data):
    # Document Information
    print("\\n=== Document Information ===")
    doc_info = pd.DataFrame({
        'WPS': [
            wps_data.get('document_info', {}).get('wps_number', ''),
            wps_data.get('document_info', {}).get('revision', ''),
            wps_data.get('document_info', {}).get('date', ''),
            wps_data.get('document_info', {}).get('company', '')
        ],
        'PQR': [
            pqr_data.get('document_info', {}).get('pqr_number', ''),
            pqr_data.get('document_info', {}).get('revision', ''),
            pqr_data.get('document_info', {}).get('date', ''),
            pqr_data.get('document_info', {}).get('company', '')
        ]
    }, index=['Number', 'Revision', 'Date', 'Company'])
    display(doc_info)
    
    # Joints (QW-402)
    print("\\n=== Joints (QW-402) ===")
    joints_df = pd.DataFrame({
        'WPS': [
            wps_data.get('joints', {}).get('joint_design', ''),
            wps_data.get('joints', {}).get('backing', ''),
            wps_data.get('joints', {}).get('groove_angle', ''),
            wps_data.get('joints', {}).get('root_opening', ''),
            wps_data.get('joints', {}).get('root_face', '')
        ],
        'PQR': [
            pqr_data.get('joints', {}).get('joint_design', ''),
            pqr_data.get('joints', {}).get('backing', ''),
            pqr_data.get('joints', {}).get('groove_angle', ''),
            pqr_data.get('joints', {}).get('root_opening', ''),
            pqr_data.get('joints', {}).get('root_face', '')
        ]
    }, index=['Joint Design', 'Backing', 'Groove Angle', 'Root Opening', 'Root Face'])
    display(joints_df)
    
    # Base Metals (QW-403)
    print("\\n=== Base Metals (QW-403) ===")
    metals_df = pd.DataFrame({
        'WPS': [
            wps_data.get('base_metals', {}).get('p_number', ''),
            wps_data.get('base_metals', {}).get('group_number', ''),
            wps_data.get('base_metals', {}).get('material_spec', ''),
            wps_data.get('base_metals', {}).get('type_grade', ''),
            wps_data.get('base_metals', {}).get('thickness_range', '')
        ],
        'PQR': [
            pqr_data.get('base_metals', {}).get('p_number', ''),
            pqr_data.get('base_metals', {}).get('group_number', ''),
            pqr_data.get('base_metals', {}).get('material_spec', ''),
            pqr_data.get('base_metals', {}).get('type_grade', ''),
            pqr_data.get('base_metals', {}).get('thickness', '')
        ]
    }, index=['P-Number', 'Group Number', 'Material Spec', 'Type/Grade', 'Thickness'])
    display(metals_df)
    
    # Display other sections...
    sections = [
        ('Filler Metals (QW-404)', 'filler_metals'),
        ('Position (QW-405)', 'position'),
        ('Preheat (QW-406)', 'preheat'),
        ('PWHT (QW-407)', 'pwht'),
        ('Gas (QW-408)', 'gas'),
        ('Electrical (QW-409)', 'electrical_characteristics'),
        ('Technique (QW-410)', 'technique')
    ]
    
    for title, key in sections:
        print(f"\\n=== {title} ===")
        wps_section = wps_data.get(key, {})
        pqr_section = pqr_data.get(key, {})
        
        # Get all unique keys
        all_keys = set(wps_section.keys()) | set(pqr_section.keys())
        
        if all_keys:
            section_df = pd.DataFrame({
                'WPS': [wps_section.get(k, '') for k in all_keys],
                'PQR': [pqr_section.get(k, '') for k in all_keys]
            }, index=[k.replace('_', ' ').title() for k in all_keys])
            display(section_df)
            
    # Display test results if available in PQR
    if 'test_results' in pqr_data:
        print("\\n=== Test Results ===")
        test_results = pqr_data['test_results']
        
        if 'tensile_test' in test_results:
            print("\\nTensile Test Results:")
            tensile_df = pd.DataFrame(test_results['tensile_test'].get('specimens', []))
            if not tensile_df.empty:
                display(tensile_df)
                
        if 'guided_bend_test' in test_results:
            print("\\nGuided Bend Test Results:")
            bend_df = pd.DataFrame(test_results['guided_bend_test'].get('specimens', []))
            if not bend_df.empty:
                display(bend_df)"""

# Create markdown cell for usage instructions
usage_md = """## Usage Instructions

To use this notebook:

1. Run all cells above
2. Use the file upload widgets to select your WPS and PQR documents
3. Click the "Compare Documents" button
4. View the detailed comparison results

The results will show:
- Document information comparison
- Section-by-section comparison (QW-402 through QW-410)
- Test results from the PQR
- Highlighted differences between WPS and PQR

Note: Make sure you have set up your API keys in the environment variables or .env file:
- DEEPSEEK_API_KEY
- LLM_WHISPERER_API_KEY"""

# Create cells
cells = [
    nbf.v4.new_markdown_cell(intro_md),
    nbf.v4.new_code_cell(install_code),
    nbf.v4.new_code_cell(setup_code),
    nbf.v4.new_markdown_cell(helper_md),
    nbf.v4.new_code_cell(helper_code),
    nbf.v4.new_markdown_cell(upload_md),
    nbf.v4.new_code_cell(upload_code),
    nbf.v4.new_markdown_cell(results_md),
    nbf.v4.new_code_cell(results_code),
    nbf.v4.new_markdown_cell(usage_md)
]

# Add cells to notebook
nb.cells = cells

# Write the notebook to a file
with open('WPS_PQR_Comparison.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f) 