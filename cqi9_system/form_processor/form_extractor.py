"""
Form Extractor
=============

This module identifies and extracts structured data from CQI-9 forms and documents.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union
import json
import os

from .document_processor import DocumentProcessor, DocumentType

logger = logging.getLogger(__name__)


class FormType(str):
    """String constants for CQI-9 form types."""
    TEMPERATURE_UNIFORMITY_SURVEY = "temperature_uniformity_survey"
    SYSTEM_ACCURACY_TEST = "system_accuracy_test"
    THERMOCOUPLE_CALIBRATION = "thermocouple_calibration"
    INSTRUMENTATION_CALIBRATION = "instrumentation_calibration"
    HEAT_TREATMENT_RECORD = "heat_treatment_record"
    PROCESS_CAPABILITY = "process_capability"
    EQUIPMENT_MAINTENANCE = "equipment_maintenance"
    UNKNOWN = "unknown"


class FormExtractor:
    """
    Extracts structured data from CQI-9 forms and documents.
    
    This class identifies the type of CQI-9 form and extracts relevant
    data fields based on form-specific extraction rules.
    """
    
    def __init__(self, document_processor: Optional[DocumentProcessor] = None):
        """
        Initialize the Form Extractor.
        
        Args:
            document_processor: An optional DocumentProcessor instance.
                If not provided, a new one will be created.
        """
        self.document_processor = document_processor or DocumentProcessor()
        
    def identify_form_type(self, document_data: Dict[str, Any]) -> str:
        """
        Identify the type of CQI-9 form based on content analysis.
        
        Args:
            document_data: Document data extracted by the document processor.
            
        Returns:
            The identified form type.
        """
        try:
            # Check if this is a PDF
            if "pages" in document_data:
                text = ""
                for page in document_data["pages"]:
                    text += page.get("text", "")
            # Check if this is a Word document
            elif "content" in document_data and "paragraphs" in document_data["content"]:
                text = ""
                for para in document_data["content"]["paragraphs"]:
                    text += para.get("text", "")
            # Otherwise, convert to string representation
            else:
                text = str(document_data)
                
            # Use regex patterns to identify form types
            if re.search(r"temperature\s+uniformity\s+survey", text, re.IGNORECASE) or \
               re.search(r"TUS\s+report", text, re.IGNORECASE):
                return FormType.TEMPERATURE_UNIFORMITY_SURVEY
                
            elif re.search(r"system\s+accuracy\s+test", text, re.IGNORECASE) or \
                 re.search(r"SAT\s+report", text, re.IGNORECASE):
                return FormType.SYSTEM_ACCURACY_TEST
                
            elif re.search(r"thermocouple\s+calibration", text, re.IGNORECASE):
                return FormType.THERMOCOUPLE_CALIBRATION
                
            elif re.search(r"instrumentation\s+calibration", text, re.IGNORECASE):
                return FormType.INSTRUMENTATION_CALIBRATION
                
            elif re.search(r"heat\s+treatment\s+record", text, re.IGNORECASE) or \
                 re.search(r"heat\s+treat\s+record", text, re.IGNORECASE):
                return FormType.HEAT_TREATMENT_RECORD
                
            elif re.search(r"process\s+capability", text, re.IGNORECASE) or \
                 re.search(r"capability\s+study", text, re.IGNORECASE):
                return FormType.PROCESS_CAPABILITY
                
            elif re.search(r"equipment\s+maintenance", text, re.IGNORECASE) or \
                 re.search(r"maintenance\s+record", text, re.IGNORECASE):
                return FormType.EQUIPMENT_MAINTENANCE
                
            return FormType.UNKNOWN
            
        except Exception as e:
            logger.error(f"Error identifying form type: {str(e)}")
            return FormType.UNKNOWN
            
    def extract_form_data(self, file_path: str) -> Dict[str, Any]:
        """
        Process a document and extract structured form data.
        
        Args:
            file_path: Path to the document file.
            
        Returns:
            Dictionary containing the extracted form data.
        """
        try:
            # Process the document
            document_data = self.document_processor.process_document(file_path)
            
            if not document_data.get("success", False):
                logger.error(f"Failed to process document: {document_data.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": document_data.get("error", "Failed to process document"),
                    "file_path": file_path
                }
                
            # Identify form type
            form_type = self.identify_form_type(document_data)
            
            # Extract data based on form type
            form_data = {
                "success": True,
                "file_path": file_path,
                "form_type": form_type,
                "raw_document_data": document_data
            }
            
            # Extract form-specific data
            if form_type == FormType.TEMPERATURE_UNIFORMITY_SURVEY:
                extracted_data = self.extract_temperature_uniformity_survey(document_data)
                form_data["extracted_data"] = extracted_data
                
            elif form_type == FormType.SYSTEM_ACCURACY_TEST:
                extracted_data = self.extract_system_accuracy_test(document_data)
                form_data["extracted_data"] = extracted_data
                
            elif form_type == FormType.THERMOCOUPLE_CALIBRATION:
                extracted_data = self.extract_thermocouple_calibration(document_data)
                form_data["extracted_data"] = extracted_data
                
            elif form_type == FormType.INSTRUMENTATION_CALIBRATION:
                extracted_data = self.extract_instrumentation_calibration(document_data)
                form_data["extracted_data"] = extracted_data
                
            elif form_type == FormType.HEAT_TREATMENT_RECORD:
                extracted_data = self.extract_heat_treatment_record(document_data)
                form_data["extracted_data"] = extracted_data
                
            elif form_type == FormType.PROCESS_CAPABILITY:
                extracted_data = self.extract_process_capability(document_data)
                form_data["extracted_data"] = extracted_data
                
            elif form_type == FormType.EQUIPMENT_MAINTENANCE:
                extracted_data = self.extract_equipment_maintenance(document_data)
                form_data["extracted_data"] = extracted_data
                
            else:
                form_data["extracted_data"] = {"message": "Unknown form type, no specific data extracted"}
                
            return form_data
            
        except Exception as e:
            logger.error(f"Error extracting form data from {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
            
    def extract_temperature_uniformity_survey(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract data from a Temperature Uniformity Survey (TUS) report.
        
        Args:
            document_data: Document data extracted by the document processor.
            
        Returns:
            Dictionary containing the extracted TUS data.
        """
        try:
            extracted_data = {
                "equipment_info": {},
                "test_info": {},
                "temperature_readings": [],
                "conformance": None
            }
            
            # Extract text from document
            text = ""
            if "pages" in document_data:  # PDF
                for page in document_data["pages"]:
                    text += page.get("text", "")
            elif "content" in document_data:  # Word
                for para in document_data["content"].get("paragraphs", []):
                    text += para.get("text", "")
            
            # Extract equipment information
            equipment_patterns = {
                "furnace_id": r"(?:furnace|equipment)\s+id.*?:?\s*([A-Za-z0-9\-]+)",
                "manufacturer": r"(?:furnace|equipment)\s+manufacturer.*?:?\s*([A-Za-z0-9\-\s]+)(?:$|\n)",
                "model": r"model.*?:?\s*([A-Za-z0-9\-\s]+)(?:$|\n)",
                "serial_number": r"serial.*?(?:number|no|#).*?:?\s*([A-Za-z0-9\-]+)"
            }
            
            for key, pattern in equipment_patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    extracted_data["equipment_info"][key] = match.group(1).strip()
            
            # Extract test information
            test_patterns = {
                "test_date": r"(?:test|survey)\s+date.*?:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})",
                "test_number": r"(?:test|survey)\s+(?:number|no|#).*?:?\s*([A-Za-z0-9\-]+)",
                "setpoint": r"(?:setpoint|set\s+point).*?:?\s*(\d+(?:\.\d+)?)\s*[°℃Cc]",
                "uniformity_tolerance": r"(?:uniformity|tolerance).*?:?\s*(?:±|\+/-)?\s*(\d+(?:\.\d+)?)\s*[°℃Cc]"
            }
            
            for key, pattern in test_patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    extracted_data["test_info"][key] = match.group(1).strip()
            
            # Try to extract temperature readings from tables
            if "content" in document_data and "tables" in document_data["content"]:
                for table in document_data["content"]["tables"]:
                    # Look for tables that contain temperature data
                    table_data = table.get("data", [])
                    if table_data and len(table_data) > 1:
                        # Check if this looks like a temperature data table
                        header_row = table_data[0]
                        if any(re.search(r"(?:temperature|temp|reading)", cell, re.IGNORECASE) for cell in header_row):
                            for row in table_data[1:]:
                                # Try to extract position/thermocouple and temperature
                                if len(row) >= 2:
                                    try:
                                        # Assuming first column is position/TC, second is temperature
                                        position = row[0].strip()
                                        temp_str = re.search(r"(\d+(?:\.\d+)?)", row[1])
                                        if temp_str:
                                            temperature = float(temp_str.group(1))
                                            extracted_data["temperature_readings"].append({
                                                "position": position,
                                                "temperature": temperature
                                            })
                                    except (ValueError, IndexError) as e:
                                        logger.warning(f"Error parsing temperature row: {str(e)}")
            
            # Extract conformance statement
            conformance_pattern = r"(?:conformance|compliance|result).*?:?\s*(pass|fail|conforms|does\s+not\s+conform)"
            match = re.search(conformance_pattern, text, re.IGNORECASE)
            if match:
                result = match.group(1).lower()
                if "pass" in result or "conform" in result:
                    extracted_data["conformance"] = "pass"
                else:
                    extracted_data["conformance"] = "fail"
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting TUS data: {str(e)}")
            return {"error": str(e)}
            
    def extract_system_accuracy_test(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract data from a System Accuracy Test (SAT) report.
        
        Args:
            document_data: Document data extracted by the document processor.
            
        Returns:
            Dictionary containing the extracted SAT data.
        """
        try:
            extracted_data = {
                "equipment_info": {},
                "test_info": {},
                "measurements": [],
                "conformance": None
            }
            
            # Extract text from document
            text = ""
            if "pages" in document_data:  # PDF
                for page in document_data["pages"]:
                    text += page.get("text", "")
            elif "content" in document_data:  # Word
                for para in document_data["content"].get("paragraphs", []):
                    text += para.get("text", "")
            
            # Extract equipment information
            equipment_patterns = {
                "equipment_id": r"(?:equipment|system)\s+id.*?:?\s*([A-Za-z0-9\-]+)",
                "manufacturer": r"(?:equipment|system)\s+manufacturer.*?:?\s*([A-Za-z0-9\-\s]+)(?:$|\n)",
                "instrument_id": r"(?:instrument|controller)\s+id.*?:?\s*([A-Za-z0-9\-]+)"
            }
            
            for key, pattern in equipment_patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    extracted_data["equipment_info"][key] = match.group(1).strip()
            
            # Extract test information
            test_patterns = {
                "test_date": r"(?:test|survey)\s+date.*?:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})",
                "test_number": r"(?:test|survey)\s+(?:number|no|#).*?:?\s*([A-Za-z0-9\-]+)",
                "accuracy_tolerance": r"(?:accuracy|tolerance).*?:?\s*(?:±|\+/-)?\s*(\d+(?:\.\d+)?)\s*[°℃Cc]"
            }
            
            for key, pattern in test_patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    extracted_data["test_info"][key] = match.group(1).strip()
            
            # Try to extract measurements from tables
            if "content" in document_data and "tables" in document_data["content"]:
                for table in document_data["content"]["tables"]:
                    table_data = table.get("data", [])
                    if table_data and len(table_data) > 1:
                        # Check if this looks like a SAT data table
                        header_row = table_data[0]
                        if any(re.search(r"(?:standard|reference|measured|reading|deviation)", cell, re.IGNORECASE) for cell in header_row):
                            for row in table_data[1:]:
                                # Try to extract standard, measured, and deviation values
                                if len(row) >= 2:
                                    try:
                                        measurement = {}
                                        
                                        # Look for standard/reference value
                                        std_idx = next((i for i, cell in enumerate(header_row) 
                                                    if re.search(r"(?:standard|reference)", cell, re.IGNORECASE)), None)
                                        if std_idx is not None and std_idx < len(row):
                                            std_str = re.search(r"(\d+(?:\.\d+)?)", row[std_idx])
                                            if std_str:
                                                measurement["standard"] = float(std_str.group(1))
                                        
                                        # Look for measured/instrument value
                                        meas_idx = next((i for i, cell in enumerate(header_row) 
                                                    if re.search(r"(?:measured|instrument|reading)", cell, re.IGNORECASE)), None)
                                        if meas_idx is not None and meas_idx < len(row):
                                            meas_str = re.search(r"(\d+(?:\.\d+)?)", row[meas_idx])
                                            if meas_str:
                                                measurement["measured"] = float(meas_str.group(1))
                                        
                                        # Look for deviation/difference value
                                        dev_idx = next((i for i, cell in enumerate(header_row) 
                                                    if re.search(r"(?:deviation|difference)", cell, re.IGNORECASE)), None)
                                        if dev_idx is not None and dev_idx < len(row):
                                            dev_str = re.search(r"(\d+(?:\.\d+)?)", row[dev_idx])
                                            if dev_str:
                                                measurement["deviation"] = float(dev_str.group(1))
                                        
                                        # Calculate deviation if not provided
                                        if "standard" in measurement and "measured" in measurement and "deviation" not in measurement:
                                            measurement["deviation"] = abs(measurement["measured"] - measurement["standard"])
                                        
                                        if measurement:
                                            extracted_data["measurements"].append(measurement)
                                            
                                    except (ValueError, IndexError) as e:
                                        logger.warning(f"Error parsing SAT measurement row: {str(e)}")
            
            # Extract conformance statement
            conformance_pattern = r"(?:conformance|compliance|result).*?:?\s*(pass|fail|conforms|does\s+not\s+conform)"
            match = re.search(conformance_pattern, text, re.IGNORECASE)
            if match:
                result = match.group(1).lower()
                if "pass" in result or "conform" in result:
                    extracted_data["conformance"] = "pass"
                else:
                    extracted_data["conformance"] = "fail"
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting SAT data: {str(e)}")
            return {"error": str(e)}
    
    def extract_thermocouple_calibration(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a thermocouple calibration document."""
        # Implementation similar to the above methods
        return {"message": "Thermocouple calibration extraction not fully implemented"}
    
    def extract_instrumentation_calibration(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from an instrumentation calibration document."""
        # Implementation similar to the above methods
        return {"message": "Instrumentation calibration extraction not fully implemented"}
    
    def extract_heat_treatment_record(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a heat treatment record."""
        # Implementation similar to the above methods
        return {"message": "Heat treatment record extraction not fully implemented"}
    
    def extract_process_capability(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a process capability document."""
        # Implementation similar to the above methods
        return {"message": "Process capability extraction not fully implemented"}
    
    def extract_equipment_maintenance(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from an equipment maintenance record."""
        # Implementation similar to the above methods
        return {"message": "Equipment maintenance extraction not fully implemented"} 