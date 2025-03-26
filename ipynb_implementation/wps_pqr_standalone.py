#!/usr/bin/env python3
"""
WPS/PQR Comparison Standalone Script

This script allows users to:
1. Process Welding Procedure Specification (WPS) and Procedure Qualification Record (PQR) documents
2. Extract text using LLMWhisperer
3. Extract structured information using DeepSeek API
4. Display comparison results in the terminal
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
from openai import OpenAI
from unstract.llmwhisperer import LLMWhispererClientV2
from dotenv import load_dotenv
import logging
import argparse

# Load environment variables
load_dotenv()

# Configuration
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_llmwhisperer_client():
    """Initialize LLMWhisperer client"""
    if not LLM_WHISPERER_API_KEY:
        logger.error("LLMWhisperer API key is not set. Set the LLM_WHISPERER_API_KEY environment variable.")
        return None
    return LLMWhispererClientV2(
        base_url=LLM_WHISPERER_API_URL,
        api_key=LLM_WHISPERER_API_KEY
    )

def process_document(file_path, doc_type):
    """Process a document with LLMWhisperer and return the extracted text"""
    client = init_llmwhisperer_client()
    
    if client is None:
        return None
    
    try:
        logger.info(f"Processing {doc_type} document: {file_path}")
        
        # Define parameters for high-quality extraction
        params = {
            'mode': 'form',
            'output_mode': 'layout_preserving',
            'add_line_nos': 'true',
        }
        
        # Process the document
        result = client.whisper(
            file_path=file_path,
            wait_for_completion=True,
            wait_timeout=600  # 10 minutes timeout
        )
        
        if 'extraction' in result and 'result_text' in result['extraction']:
            return result['extraction']['result_text']
        else:
            logger.error(f"No text found in {doc_type} response")
            return None
            
    except Exception as e:
        logger.error(f"Error processing {doc_type}: {str(e)}")
        return None

def extract_structured_info(text, doc_type):
    """Extract structured information from text using DeepSeek API"""
    try:
        # Print the first 500 characters of the text for debugging
        print(f"\nFirst 500 characters of {doc_type} text:")
        print(text[:500])
        
        # Prepare the prompt based on document type
        if doc_type == "WPS":
            prompt = f"""Extract the following information from this WPS document in JSON format:
            - WPS Number
            - Base Metal
            - Filler Metal
            - Welding Process
            - Position
            - Preheat Temperature
            - Interpass Temperature
            - Current Type
            - Current Range
            - Voltage Range
            - Travel Speed
            - Shielding Gas
            - Backing Gas
            - Post Weld Heat Treatment

            Document text:
            {text}

            Return only the JSON object with these fields. If a field is not found, use "Not specified" as the value."""
        else:  # PQR
            prompt = f"""Extract the following information from this PQR document in JSON format:
            - PQR Number
            - Base Metal
            - Filler Metal
            - Welding Process
            - Position
            - Preheat Temperature
            - Interpass Temperature
            - Current Type
            - Current Range
            - Voltage Range
            - Travel Speed
            - Shielding Gas
            - Backing Gas
            - Post Weld Heat Treatment
            - Test Results

            Document text:
            {text}

            Return only the JSON object with these fields. If a field is not found, use "Not specified" as the value."""

        # Call DeepSeek API
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a welding document analysis expert. Extract structured information from welding documents. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        # Extract the JSON response
        json_str = response.choices[0].message.content.strip()
        print(f"\nDeepSeek API Response for {doc_type}:")
        print(json_str)
        
        # Clean up the response - remove markdown formatting if present
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[1]  # Remove first line with ```json
        if json_str.endswith("```"):
            json_str = json_str.rsplit("\n", 1)[0]  # Remove last line with ```
        json_str = json_str.strip()
        
        # Try to parse the JSON response
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for {doc_type}: {str(e)}")
            print("Raw response:", json_str)
            return None
        
    except Exception as e:
        logger.error(f"Error extracting structured info from {doc_type}: {str(e)}")
        return None

def compare_documents(wps_data, pqr_data):
    """Compare WPS and PQR data and return differences"""
    differences = []
    
    # Define fields to compare
    fields_to_compare = [
        "Base Metal", "Filler Metal", "Welding Process", "Position",
        "Preheat Temperature", "Interpass Temperature", "Current Type",
        "Current Range", "Voltage Range", "Travel Speed", "Shielding Gas",
        "Backing Gas", "Post Weld Heat Treatment"
    ]
    
    for field in fields_to_compare:
        wps_value = wps_data.get(field, "Not specified")
        pqr_value = pqr_data.get(field, "Not specified")
        
        if wps_value != pqr_value:
            differences.append({
                "Field": field,
                "WPS Value": wps_value,
                "PQR Value": pqr_value,
                "Status": "Non-compliant"
            })
        else:
            differences.append({
                "Field": field,
                "WPS Value": wps_value,
                "PQR Value": pqr_value,
                "Status": "Compliant"
            })
    
    return differences

def display_results(differences):
    """Display comparison results in a side-by-side format using pandas DataFrame"""
    # Create separate dictionaries for WPS and PQR data
    wps_data = {}
    pqr_data = {}
    
    for diff in differences:
        field = diff['Field']
        wps_value = str(diff['WPS Value'])
        pqr_value = str(diff['PQR Value'])
        
        # Clean up nested dictionary displays
        if wps_value.startswith('{'):
            try:
                wps_dict = eval(wps_value)
                wps_value = "\n".join(f"{k}: {v}" for k, v in wps_dict.items())
            except:
                pass
        
        if pqr_value.startswith('{'):
            try:
                pqr_dict = eval(pqr_value)
                pqr_value = "\n".join(f"{k}: {v}" for k, v in pqr_dict.items())
            except:
                pass
        
        wps_data[field] = wps_value
        pqr_data[field] = pqr_value
    
    # Create DataFrame for side-by-side comparison
    df = pd.DataFrame({
        'Parameter': wps_data.keys(),
        'WPS': wps_data.values(),
        'PQR': pqr_data.values()
    })
    
    # Set display options for better formatting
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.max_rows', None)
    
    # Print the comparison
    print("\nWPS/PQR Document Comparison")
    print("=" * 120)
    print(df.to_string(index=False))
    print("=" * 120)

def main():
    parser = argparse.ArgumentParser(description='Compare WPS and PQR documents')
    parser.add_argument('wps_file', help='Path to WPS document')
    parser.add_argument('pqr_file', help='Path to PQR document')
    args = parser.parse_args()
    
    # Process WPS document
    print("Processing WPS document...")
    wps_text = process_document(args.wps_file, "WPS")
    if not wps_text:
        print("Failed to process WPS document")
        return
    
    # Process PQR document
    print("Processing PQR document...")
    pqr_text = process_document(args.pqr_file, "PQR")
    if not pqr_text:
        print("Failed to process PQR document")
        return
    
    # Extract structured information
    print("Extracting structured information...")
    wps_data = extract_structured_info(wps_text, "WPS")
    pqr_data = extract_structured_info(pqr_text, "PQR")
    
    if not wps_data or not pqr_data:
        print("Failed to extract structured information")
        return
    
    # Compare documents
    print("Comparing documents...")
    differences = compare_documents(wps_data, pqr_data)
    
    # Display results
    display_results(differences)

if __name__ == "__main__":
    main() 