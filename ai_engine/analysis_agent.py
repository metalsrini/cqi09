"""
AI Analysis Agent
===============

This module provides the core AI agent for analyzing CQI-9 compliance
based on form data and requirements.
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional, Union
import time

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, validator

from ..config.config import active_config
from ..knowledge_graph.graph_manager import KnowledgeGraphManager

logger = logging.getLogger(__name__)


class ComplianceFindings(BaseModel):
    """Model for structuring compliance findings from the AI analysis."""
    is_compliant: bool = Field(description="Whether the form/data is compliant with CQI-9 requirements")
    confidence_score: float = Field(description="Confidence score for the compliance determination (0.0-1.0)")
    requirement_id: str = Field(description="CQI-9 requirement ID being evaluated")
    findings: List[str] = Field(description="List of specific findings related to compliance or non-compliance")
    evidence: List[str] = Field(description="List of evidence from the form supporting the findings")
    suggested_actions: Optional[List[str]] = Field(None, description="Suggested actions to resolve non-compliance issues")
    
    @validator('confidence_score')
    def validate_confidence(cls, v):
        """Validate that confidence score is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v


class AnalysisResponse(BaseModel):
    """Model for the complete analysis response from the AI agent."""
    form_id: str = Field(description="Identifier for the analyzed form/document")
    form_type: str = Field(description="Type of CQI-9 form that was analyzed")
    analysis_timestamp: str = Field(description="Timestamp when the analysis was performed")
    overall_compliance: bool = Field(description="Overall compliance determination for the form")
    overall_confidence: float = Field(description="Overall confidence in the compliance determination (0.0-1.0)")
    findings: List[ComplianceFindings] = Field(description="Detailed compliance findings for each relevant requirement")
    summary: str = Field(description="Summary of the compliance analysis")
    
    @validator('overall_confidence')
    def validate_confidence(cls, v):
        """Validate that confidence score is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v


class AnalysisAgent:
    """
    AI agent for analyzing CQI-9 compliance.
    
    This class leverages large language models and knowledge graph data
    to analyze forms and documents for CQI-9 compliance.
    """
    
    def __init__(self, graph_manager: Optional[KnowledgeGraphManager] = None):
        """
        Initialize the Analysis Agent.
        
        Args:
            graph_manager: An optional KnowledgeGraphManager instance.
                If not provided, a new one will be created.
        """
        self.graph_manager = graph_manager or KnowledgeGraphManager()
        if not self.graph_manager.graph:
            self.graph_manager.connect()
            
        # Initialize LLM
        self.llm = ChatOpenAI(
            api_key="sk-2667a59916924dfe9c66ebab91af3f3c",
            model="deepseek-chat",
            temperature=0.1,
            base_url="https://api.deepseek.com/v1"
        )
        
        # Initialize parsers
        self.findings_parser = PydanticOutputParser(pydantic_object=ComplianceFindings)
        self.response_parser = PydanticOutputParser(pydantic_object=AnalysisResponse)
        
    def analyze_form(self, form_data: Dict[str, Any], requirement_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a form for CQI-9 compliance.
        
        Args:
            form_data: Extracted form data to analyze.
            requirement_ids: Optional list of specific requirement IDs to check.
                If None, relevant requirements will be determined automatically.
                
        Returns:
            Dictionary containing the analysis results.
        """
        try:
            logger.info(f"Starting analysis for form of type: {form_data.get('form_type', 'unknown')}")
            
            # If no specific requirements provided, determine relevant ones based on form type
            if requirement_ids is None:
                requirement_ids = self._get_relevant_requirements(form_data)
                logger.info(f"Identified {len(requirement_ids)} relevant requirements for analysis")
            
            # Analyze each requirement
            findings = []
            for req_id in requirement_ids:
                # Get requirement context from knowledge graph
                req_context = self._get_requirement_context(req_id)
                if not req_context:
                    logger.warning(f"Could not retrieve context for requirement {req_id}, skipping")
                    continue
                    
                # Analyze compliance for this requirement
                finding = self._analyze_requirement_compliance(form_data, req_context)
                findings.append(finding)
                
            # Determine overall compliance
            compliant_findings = [f for f in findings if f.is_compliant]
            overall_compliance = len(compliant_findings) == len(findings)
            
            # Calculate overall confidence
            if findings:
                overall_confidence = sum(f.confidence_score for f in findings) / len(findings)
            else:
                overall_confidence = 0.0
                
            # Create the response
            form_id = form_data.get("file_path", "unknown").split("/")[-1]
            form_type = form_data.get("form_type", "unknown")
            
            response = AnalysisResponse(
                form_id=form_id,
                form_type=form_type,
                analysis_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                overall_compliance=overall_compliance,
                overall_confidence=overall_confidence,
                findings=findings,
                summary=self._generate_summary(findings, overall_compliance)
            )
            
            logger.info(f"Completed analysis for form {form_id} with overall compliance: {overall_compliance}")
            return json.loads(response.json())
            
        except Exception as e:
            logger.error(f"Error analyzing form: {str(e)}")
            return {
                "error": str(e),
                "form_id": form_data.get("file_path", "unknown").split("/")[-1],
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
    def analyze_requirement(self, requirement_id: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single requirement with provided evidence.
        
        Args:
            requirement_id: The ID of the requirement to analyze.
            evidence: Evidence data to analyze against the requirement.
            
        Returns:
            Dictionary containing the analysis results for the single requirement.
        """
        try:
            requirement = self.graph_manager.query_requirement_by_id(requirement_id)
            if not requirement:
                return {'error': 'Requirement not found'}, 404
                
            context = self._get_requirement_context(requirement_id)
            finding = self._analyze_requirement_compliance({'extracted_data': evidence}, context)
            
            return {
                'requirement_id': requirement_id,
                'compliance_status': finding.is_compliant,
                'confidence': finding.confidence_score,
                'findings': finding.findings,
                'suggested_actions': finding.suggested_actions
            }
            
        except Exception as e:
            logger.error(f"Error analyzing requirement {requirement_id}: {str(e)}")
            return {
                'error': str(e),
                'requirement_id': requirement_id,
                'analysis_timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
    def _get_relevant_requirements(self, form_data: Dict[str, Any]) -> List[str]:
        """
        Determine relevant CQI-9 requirements based on form type.
        
        Args:
            form_data: The form data to analyze.
            
        Returns:
            List of relevant requirement IDs.
        """
        form_type = form_data.get("form_type", "unknown")
        
        # Query the knowledge graph for relevant requirements based on form type
        # This is a simplified implementation; in practice, you would use more
        # sophisticated logic to determine relevant requirements
        try:
            # Example query patterns for different form types
            if form_type == "temperature_uniformity_survey":
                query = """
                MATCH (r:Requirement) 
                WHERE r.text CONTAINS "temperature uniformity" OR r.text CONTAINS "TUS"
                RETURN r.id as id
                """
            elif form_type == "system_accuracy_test":
                query = """
                MATCH (r:Requirement) 
                WHERE r.text CONTAINS "system accuracy" OR r.text CONTAINS "SAT"
                RETURN r.id as id
                """
            elif form_type == "thermocouple_calibration":
                query = """
                MATCH (r:Requirement) 
                WHERE r.text CONTAINS "thermocouple" AND r.text CONTAINS "calibration"
                RETURN r.id as id
                """
            else:
                # Generic query for unknown form types
                query = """
                MATCH (r:Requirement) 
                WHERE r.criticality = "high"
                RETURN r.id as id LIMIT 5
                """
                
            results = self.graph_manager.graph.run(query).data()
            req_ids = [result["id"] for result in results]
            
            # If no requirements found, use a default set
            if not req_ids:
                logger.warning(f"No requirements found for form type: {form_type}, using defaults")
                req_ids = ["REQ-3.1-1", "REQ-3.2-1", "REQ-3.3-1"]  # Default IDs
                
            return req_ids
            
        except Exception as e:
            logger.error(f"Error getting relevant requirements: {str(e)}")
            return ["REQ-3.1-1", "REQ-3.2-1", "REQ-3.3-1"]  # Default IDs in case of error
            
    def _get_requirement_context(self, requirement_id: str) -> Dict[str, Any]:
        """
        Get the context of a requirement from the knowledge graph.
        
        Args:
            requirement_id: The ID of the requirement.
            
        Returns:
            Dictionary containing the requirement context.
        """
        try:
            context = self.graph_manager.query_requirement_context(requirement_id)
            return context
        except Exception as e:
            logger.error(f"Error getting requirement context for {requirement_id}: {str(e)}")
            return None
            
    def _analyze_requirement_compliance(self, form_data: Dict[str, Any], requirement_context: Dict[str, Any]) -> ComplianceFindings:
        """
        Analyze compliance with a specific requirement.
        
        Args:
            form_data: The form data to analyze.
            requirement_context: Context of the requirement from the knowledge graph.
            
        Returns:
            ComplianceFindings object with the analysis results.
        """
        try:
            # Create prompt for the LLM
            prompt_template = PromptTemplate(
                input_variables=["form_data", "requirement_text", "requirement_id", "format_instructions"],
                template="""
                You are an expert AI system analyzing CQI-9 compliance for thermal processing in the automotive industry.
                
                Analyze the following form data for compliance with the CQI-9 requirement below.
                
                CQI-9 Requirement ID: {requirement_id}
                Requirement Text: {requirement_text}
                
                Form Data:
                {form_data}
                
                Provide a detailed analysis determining if the form data shows compliance with the requirement.
                Consider direct evidence in the data, as well as any indirect indicators of compliance or non-compliance.
                
                {format_instructions}
                """
            )
            
            # Extract requirement text
            requirement_text = requirement_context.get("text", f"Unknown requirement: {requirement_context.get('id', 'unknown')}")
            requirement_id = requirement_context.get("id", "unknown")
            
            # Create form data string representation
            form_data_str = json.dumps(form_data.get("extracted_data", {}), indent=2)
            
            # Run the LLM chain
            chain = LLMChain(llm=self.llm, prompt=prompt_template)
            
            response = chain.run(
                form_data=form_data_str,
                requirement_text=requirement_text,
                requirement_id=requirement_id,
                format_instructions=self.findings_parser.get_format_instructions()
            )
            
            # Parse the response
            try:
                findings = self.findings_parser.parse(response)
                return findings
            except Exception as parse_error:
                logger.error(f"Error parsing LLM response: {str(parse_error)}")
                # Create a default findings object if parsing fails
                return ComplianceFindings(
                    is_compliant=False,
                    confidence_score=0.3,
                    requirement_id=requirement_id,
                    findings=["Error analyzing compliance"],
                    evidence=[],
                    suggested_actions=["Review form data manually"]
                )
                
        except Exception as e:
            logger.error(f"Error analyzing requirement compliance: {str(e)}")
            return ComplianceFindings(
                is_compliant=False,
                confidence_score=0.0,
                requirement_id=requirement_context.get("id", "unknown"),
                findings=[f"Error during analysis: {str(e)}"],
                evidence=[],
                suggested_actions=["Review form data manually"]
            )
            
    def _generate_summary(self, findings: List[ComplianceFindings], overall_compliance: bool) -> str:
        """
        Generate a summary of the compliance analysis.
        
        Args:
            findings: List of ComplianceFindings objects.
            overall_compliance: Whether the form is overall compliant.
            
        Returns:
            Summary string.
        """
        try:
            # Create a prompt for summary generation
            prompt_template = PromptTemplate(
                input_variables=["findings", "overall_compliance"],
                template="""
                You are an expert AI system analyzing CQI-9 compliance for thermal processing in the automotive industry.
                
                Generate a concise summary of the compliance analysis based on the following findings:
                
                Overall Compliance: {overall_compliance}
                
                Detailed Findings:
                {findings}
                
                Provide a clear, professional summary that highlights key aspects of compliance or non-compliance,
                major findings, and critical issues if any. Keep the summary focused and actionable.
                """
            )
            
            # Create findings string representation
            findings_str = "\n\n".join([
                f"Requirement {f.requirement_id}:\n" +
                f"Compliant: {f.is_compliant}\n" +
                f"Confidence: {f.confidence_score}\n" +
                f"Key Findings: {', '.join(f.findings)}"
                for f in findings
            ])
            
            # Run the LLM chain
            chain = LLMChain(llm=self.llm, prompt=prompt_template)
            
            summary = chain.run(
                findings=findings_str,
                overall_compliance=overall_compliance
            )
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            
            # Default summary in case of error
            if overall_compliance:
                return "The form appears to be compliant with relevant CQI-9 requirements. However, an error occurred during summary generation."
            else:
                return "The form appears to have compliance issues with one or more CQI-9 requirements. Detailed review is recommended. Note: An error occurred during summary generation."