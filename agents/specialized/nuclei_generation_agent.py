import re
import uuid
import yaml
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts.nuclei_generation_prompts import NucleiGenerationPrompts
from llms.prompts.security_agent_prompts import SecurityAgentPrompts


@dataclass
class NucleiTemplate:
    id: str
    name: str
    severity: str
    description: str
    tags: List[str]
    yaml_content: str
    confidence: float
    cve_id: Optional[str] = None
    created_at: datetime = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class NucleiGenerationAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="NucleiGenerationAgent",
            role=AgentRole.SECURITY_RESEARCHER,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="nuclei_template_generation",
                    description="Generate Nuclei YAML templates for vulnerability detection",
                    tools=["yaml_validator", "template_analyzer", "cve_lookup"]
                ),
                AgentCapability(
                    name="vulnerability_research",
                    description="Research vulnerabilities and create detection templates",
                    tools=["cve_database", "exploit_db", "security_advisories"]
                ),
                AgentCapability(
                    name="template_validation",
                    description="Validate and optimize Nuclei templates",
                    tools=["nuclei_validator", "syntax_checker", "performance_analyzer"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        return [
            "yaml_parser",
            "template_validator",
            "cve_analyzer",
            "nuclei_engine",
            "template_optimizer"
        ]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_nuclei_generation_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "vulnerability_data": observation.get("vulnerability_data", {}),
            "target_info": observation.get("target_info", {}),
            "template_requirements": observation.get("template_requirements", {}),
            "processed": True
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "generate_template")

            if action == "generate_template":
                return self._generate_nuclei_template(task)
            elif action == "validate_template":
                return self._validate_template(task)
            elif action == "enhance_template":
                return self._enhance_template(task)
            elif action == "generate_bulk_templates":
                return self._generate_bulk_templates(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Nuclei generation task failed: {e}")
            return {"success": False, "error": str(e)}

    def _generate_nuclei_template(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            vulnerability_data = task.get("vulnerability_data", {})

            if vulnerability_data.get("cve_id"):
                return self._generate_cve_template(vulnerability_data)
            elif vulnerability_data.get("vulnerability_type"):
                return self._generate_vuln_type_template(vulnerability_data)
            else:
                return self._generate_generic_template(task)

        except Exception as e:
            logger.error(f"Template generation failed: {e}")
            return {
                "success": False,
                "error": f"Template generation failed: {e}",
                "agent": self.name
            }

    def _generate_cve_template(self, vulnerability_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            cve_id = vulnerability_data.get("cve_id")
            description = vulnerability_data.get("description", "")

            prompt = NucleiGenerationPrompts.get_cve_template_prompt(cve_id, description)

            llm_response = self.query_llm(prompt, {
                "cve_id": cve_id,
                "description": description,
                "severity": vulnerability_data.get("severity", "medium")
            })

            template = self._parse_template_response(llm_response, cve_id)

            if template:
                logger.info(f"Generated Nuclei template for {cve_id}")
                return {
                    "success": True,
                    "template": template,
                    "generation_type": "cve_based",
                    "agent": self.name
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to parse generated template",
                    "agent": self.name
                }

        except Exception as e:
            logger.error(f"CVE template generation failed: {e}")
            return {
                "success": False,
                "error": f"CVE template generation failed: {e}",
                "agent": self.name
            }

    def _generate_vuln_type_template(self, vulnerability_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            vuln_type = vulnerability_data.get("vulnerability_type")
            severity = vulnerability_data.get("severity", "medium")

            prompt = NucleiGenerationPrompts.get_vulnerability_type_prompt(vuln_type)

            llm_response = self.query_llm(prompt, {
                "vulnerability_type": vuln_type,
                "severity": severity,
                "description": vulnerability_data.get("description", "")
            })

            template_id = f"{vuln_type.lower().replace(' ', '-')}-detection"
            template = self._parse_template_response(llm_response, template_id)

            if template:
                logger.info(f"Generated Nuclei template for {vuln_type}")
                return {
                    "success": True,
                    "template": template,
                    "generation_type": "vulnerability_type",
                    "agent": self.name
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to parse generated template",
                    "agent": self.name
                }

        except Exception as e:
            logger.error(f"Vulnerability type template generation failed: {e}")
            return {
                "success": False,
                "error": f"Vulnerability type template generation failed: {e}",
                "agent": self.name
            }

    def _generate_generic_template(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            question = task.get("question", "")
            target = task.get("target", "")

            prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt()
            prompt += f"\n\nGenerate a template based on this request: {question}"
            if target:
                prompt += f"\nTarget: {target}"

            llm_response = self.query_llm(prompt)

            template_id = f"custom-{str(uuid.uuid4())[:8]}"
            template = self._parse_template_response(llm_response, template_id)

            if template:
                logger.info(f"Generated generic Nuclei template: {template_id}")
                return {
                    "success": True,
                    "template": template,
                    "generation_type": "generic",
                    "agent": self.name
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to parse generated template",
                    "agent": self.name
                }

        except Exception as e:
            logger.error(f"Generic template generation failed: {e}")
            return {
                "success": False,
                "error": f"Generic template generation failed: {e}",
                "agent": self.name
            }

    def _parse_template_response(self, llm_response: str, template_id: str) -> Optional[NucleiTemplate]:
        try:
            yaml_content = self._extract_yaml_from_response(llm_response)
            if not yaml_content:
                # If no YAML found, create a basic template with the response as description
                return self._create_fallback_template(llm_response, template_id)

            try:
                parsed_yaml = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                logger.error(f"Invalid YAML generated: {e}")
                logger.info("Creating fallback template due to YAML parsing error")
                return self._create_fallback_template(llm_response, template_id)

            if not isinstance(parsed_yaml, dict):
                logger.error("Parsed YAML is not a dictionary")
                return self._create_fallback_template(llm_response, template_id)

            info = parsed_yaml.get("info", {})
            template_name = info.get("name", template_id)
            severity = info.get("severity", "medium")
            description = info.get("description", "Generated Nuclei template")
            tags = info.get("tags", "").split(",") if info.get("tags") else []

            template = NucleiTemplate(
                id=parsed_yaml.get("id", template_id),
                name=template_name,
                severity=severity,
                description=description,
                tags=[tag.strip() for tag in tags],
                yaml_content=yaml_content,
                confidence=0.8,
                cve_id=info.get("classification", {}).get("cve-id") if isinstance(info.get("classification"), dict) else None,
                metadata={
                    "generated_by": self.name,
                    "yaml_valid": True,
                    "template_type": "nuclei"
                }
            )

            return template

        except Exception as e:
            logger.error(f"Template parsing failed: {e}")
            return self._create_fallback_template(llm_response, template_id)

    def _create_fallback_template(self, llm_response: str, template_id: str) -> NucleiTemplate:
        """Create a fallback template when YAML parsing fails"""
        return NucleiTemplate(
            id=template_id,
            name=f"Generated Template - {template_id}",
            severity="medium",
            description=f"Template generation attempted but YAML parsing failed. Raw response available in metadata.",
            tags=["generated", "fallback"],
            yaml_content=f"# Failed to parse YAML from LLM response\n# Template ID: {template_id}\n# Raw response in metadata",
            confidence=0.3,  # Lower confidence for fallback
            metadata={
                "generated_by": self.name,
                "yaml_valid": False,
                "template_type": "nuclei",
                "fallback": True,
                "raw_llm_response": llm_response[:1000]  # Truncate to avoid too much data
            }
        )

    def _extract_yaml_from_response(self, response: str) -> Optional[str]:
        try:
            # First try to extract from code blocks
            yaml_pattern = r'```ya?ml\s*\n(.*?)\n```'
            match = re.search(yaml_pattern, response, re.DOTALL | re.IGNORECASE)

            if match:
                yaml_content = match.group(1).strip()
                return self._clean_yaml_content(yaml_content)

            # Try to find YAML structure without code blocks
            lines = response.split('\n')
            yaml_lines = []
            in_yaml = False
            base_indent = 0
            inside_list_context = False  # Track if we're inside a list context where '-' is valid

            for line in lines:
                stripped_line = line.strip()
                
                if stripped_line.startswith('id:') and not in_yaml:
                    # Start of YAML content
                    in_yaml = True
                    yaml_lines.append(line)
                    base_indent = len(line) - len(line.lstrip())
                elif in_yaml:
                    current_indent = len(line) - len(line.lstrip()) if line.strip() else 0
                    
                    if not line.strip():
                        # Empty line - keep it as part of the structure
                        yaml_lines.append(line)
                        continue
                    
                    # Check if this line is at the base level (same indentation as 'id:')
                    if current_indent == base_indent:
                        # If it's a new top-level key (contains ':' but doesn't start with '-'),
                        # it might be the start of a new YAML block or non-YAML content
                        if ':' in stripped_line and not stripped_line.startswith('-'):
                            # This is a new top-level key, so we continue with YAML
                            yaml_lines.append(line)
                        elif stripped_line.startswith('-'):
                            # This is a list item at the base level, which shouldn't happen in valid Nuclei templates
                            # This likely means we've reached content that's not part of the template
                            break
                        else:
                            # This doesn't look like valid YAML, so we stop
                            break
                    elif current_indent > base_indent:
                        # Indented content - part of the YAML structure
                        yaml_lines.append(line)
                        
                        # Check if this line introduces a list context
                        if ':' in stripped_line and stripped_line.endswith(':') and not stripped_line.startswith('-'):
                            # This is a key that ends with ':', which might introduce a list on following lines
                            # Check if the content after the colon is a list marker
                            line_content_after_colon = stripped_line.split(':', 1)[1].strip()
                            if line_content_after_colon == '-':  # like "paths: -"
                                inside_list_context = True
                    else:
                        # Less indented than base - this shouldn't happen in valid YAML, so we stop
                        break

            if yaml_lines:
                yaml_content = '\n'.join(yaml_lines)
                return self._clean_yaml_content(yaml_content)

            return None

        except Exception as e:
            logger.error(f"YAML extraction failed: {e}")
            return None

    def _clean_yaml_content(self, yaml_content: str) -> str:
        """Clean and fix common YAML issues"""
        try:
            # Remove any trailing commas in YAML
            yaml_content = re.sub(r',(\s*\n)', r'\1', yaml_content)

            # Fix common quote escaping issues
            yaml_content = re.sub(r'\\([\'"])', r'\1', yaml_content)

            # Fix malformed YAML lists - properly quote problematic entries
            lines = yaml_content.split('\n')
            cleaned_lines = []
            skip_next_lines = 0

            for i, line in enumerate(lines):
                if skip_next_lines > 0:
                    skip_next_lines -= 1
                    continue

                # Skip empty lines or comments only
                if not line.strip() or line.strip().startswith('#'):
                    cleaned_lines.append(line)
                    continue

                # Look for SQL injection patterns and properly quote them
                if re.search(r"(?i)(' OR '1'='1|' UNION|' OR 1=1|SLEEP\(|WAITFOR|EXEC\(|SELECT.*FROM|UNION.*SELECT)", line):
                    # This looks like a SQL injection payload, need to properly quote it
                    if ':' in line and not (line.strip().endswith(':') or line.strip().startswith('-')):
                        # Handle key-value pairs
                        key, value = line.split(':', 1)
                        value = value.strip()
                        # Add quotes around the value if not already quoted
                        if value and not (value.startswith('"') and value.endswith('"')) and not (value.startswith("'") and value.endswith("'")):
                            # Properly escape quotes within the value to avoid double quotes issues
                            value = value.replace('"', '\\"')
                            value = f'"{value}"'
                        line = f"{key.strip()}: {value}"
                    elif line.strip().startswith('-'):
                        # Handle list items that start with '-'
                        # Extract the content after the '-'
                        content = line.strip()[1:].strip()
                        # Add quotes around the content if it contains problematic characters
                        if content and not (content.startswith('"') and content.endswith('"')) and not (content.startswith("'") and content.endswith("'")):
                            # Properly escape quotes within the content to avoid double quotes issues
                            content = content.replace('"', '\\"')
                            content = f'"{content}"'
                        line = f"- {content}"
                
                # Check for problematic YAML patterns and fix them instead of skipping
                if re.search(r'["\'][^"\']*["\'][^"\']*["\']', line):
                    # Line has multiple quotes, likely malformed - try to fix it
                    # Instead of skipping, try to properly quote the content
                    if ':' in line and not line.strip().endswith(':'):
                        # It's a key-value pair, try to fix the value part
                        key, value = line.split(':', 1)
                        value = value.strip()
                        # If the value contains problematic quote patterns, wrap it in quotes
                        if value and not (value.startswith('"') and value.endswith('"')) and not (value.startswith("'") and value.endswith("'")):
                            # Escape quotes properly before wrapping
                            value = value.replace('"', '\\"')
                            value = f'"{value}"'
                        line = f"{key.strip()}: {value}"
                    elif line.strip().startswith('-') and ':' not in line:
                        # Handle list items that start with '-' but don't have a colon
                        # Extract the content after the '-'
                        prefix = line.split('-', 1)[0]  # Preserve any indentation
                        content = line.split('-', 1)[1].strip()
                        # Add quotes around the content if it contains problematic characters
                        if content and not (content.startswith('"') and content.endswith('"')) and not (content.startswith("'") and content.endswith("'")):
                            # Properly escape quotes within the content to avoid double quotes issues
                            content = content.replace('"', '\\"')
                            content = f'"{content}"'
                        line = f"{prefix}- {content}"
                    else:
                        # For other lines with multiple quotes, wrap the entire content in quotes
                        content = line.strip()
                        if content and not (content.startswith('"') and content.endswith('"')) and not (content.startswith("'") and content.endswith("'")):
                            # Escape quotes properly before wrapping
                            content = content.replace('"', '\\"')
                            content = f'"{content}"'
                        line = content

                # Check for unclosed quotes
                quote_count = line.count('"') + line.count("'")
                if quote_count % 2 != 0:
                    # Odd number of quotes, likely unclosed - try to fix or skip
                    if line.strip().startswith('-') and ':' not in line:
                        # Handle list item with unclosed quote
                        prefix = line.split('-', 1)[0]  # Preserve any indentation
                        content = line.split('-', 1)[1].strip()
                        if '"' in content and not content.endswith('"'):
                            # First ensure any quotes in the content are properly escaped
                            content = content.replace('"', '\\"')
                            # Add a closing quote
                            content += '"'
                        elif "'" in content and not content.endswith("'"):
                            # First ensure any single quotes in the content are properly escaped
                            content = content.replace("'", "\\'")
                            # Add a closing quote
                            content += "'"
                        line = f"{prefix}- {content}"
                    elif ':' in line and not line.strip().endswith(':'):
                        # Handle key-value pair with unclosed quote
                        key, value = line.split(':', 1)
                        value = value.strip()
                        if '"' in value and not value.endswith('"'):
                            # First ensure any quotes in the value are properly escaped
                            value = value.replace('"', '\\"')
                            # Add a closing quote
                            value += '"'
                        elif "'" in value and not value.endswith("'"):
                            # First ensure any single quotes in the value are properly escaped
                            value = value.replace("'", "\\'")
                            # Add a closing quote
                            value += "'"
                        line = f"{key.strip()}: {value}"

                cleaned_lines.append(line)

            return '\n'.join(cleaned_lines)

        except Exception as e:
            logger.error(f"YAML cleaning failed: {e}")
            return yaml_content

    def _validate_template(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            template_content = task.get("template_content", "")

            validation_prompt = NucleiGenerationPrompts.get_template_validation_prompt()
            validation_prompt += f"\n\nTemplate to validate:\n{template_content}"

            validation_result = self.query_llm(validation_prompt)

            return {
                "success": True,
                "validation_result": validation_result,
                "agent": self.name
            }

        except Exception as e:
            logger.error(f"Template validation failed: {e}")
            return {
                "success": False,
                "error": f"Template validation failed: {e}",
                "agent": self.name
            }

    def _enhance_template(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            template_content = task.get("template_content", "")

            enhancement_prompt = NucleiGenerationPrompts.get_template_enhancement_prompt()
            enhancement_prompt += f"\n\nTemplate to enhance:\n{template_content}"

            enhanced_result = self.query_llm(enhancement_prompt)

            return {
                "success": True,
                "enhanced_template": enhanced_result,
                "agent": self.name
            }

        except Exception as e:
            logger.error(f"Template enhancement failed: {e}")
            return {
                "success": False,
                "error": f"Template enhancement failed: {e}",
                "agent": self.name
            }

    def _generate_bulk_templates(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            target_list = task.get("target_list", [])

            if not target_list:
                return {
                    "success": False,
                    "error": "No targets provided for bulk generation",
                    "agent": self.name
                }

            bulk_prompt = NucleiGenerationPrompts.get_bulk_template_generation_prompt(target_list)
            bulk_result = self.query_llm(bulk_prompt)

            return {
                "success": True,
                "bulk_templates": bulk_result,
                "template_count": len(target_list),
                "agent": self.name
            }

        except Exception as e:
            logger.error(f"Bulk template generation failed: {e}")
            return {
                "success": False,
                "error": f"Bulk template generation failed: {e}",
                "agent": self.name
            }