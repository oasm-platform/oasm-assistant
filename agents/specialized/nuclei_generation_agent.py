import re
import uuid
from typing import Dict, Any, List, Optional

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts.nuclei_generation_prompts import NucleiGenerationPrompts
from llms.prompts.security_agent_prompts import SecurityAgentPrompts




class NucleiGenerationAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="NucleiGenerationAgent",
            role=AgentRole.NUCLEI_GENERATION,
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

            template_string = self._parse_template_response(llm_response, cve_id)

            if template_string:
                logger.info(f"Generated Nuclei template for {cve_id}")
                return {
                    "success": True,
                    "template": template_string,
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
            template_string = self._parse_template_response(llm_response, template_id)

            if template_string:
                logger.info(f"Generated Nuclei template for {vuln_type}")
                return {
                    "success": True,
                    "template": template_string,
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
            template_string = self._parse_template_response(llm_response, template_id)

            if template_string:
                logger.info(f"Generated generic Nuclei template: {template_id}")
                return {
                    "success": True,
                    "template": template_string,
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

    def _parse_template_response(self, llm_response: str, template_id: str) -> Optional[str]:
        """Parse LLM response to extract Nuclei template without validation"""
        try:
            print("LLM Response: ", llm_response)
            # Extract YAML content without validation
            yaml_content = self._extract_yaml_from_response(llm_response)
            if not yaml_content:
                logger.warning("No YAML content found in response, creating fallback")
                return self._create_fallback_template(llm_response, template_id)

            logger.debug(f"Extracted YAML content length: {len(yaml_content)}")

            # Return the original LLM response with YAML marked properly
            output = f"{llm_response}\n\nExtracted YAML Content:\n```yaml\n{yaml_content}\n```\n"

            logger.info(f"Successfully returned LLM response with YAML content")
            return output

        except Exception as e:
            logger.error(f"Template extraction failed: {e}", exc_info=True)
            return self._create_fallback_template(llm_response, template_id)

    def _create_fallback_template(self, llm_response: str, template_id: str) -> str:
        """Create a fallback template when YAML parsing fails"""
        output = f"LLM Response:\n{llm_response}\n\n"
        output += f"Fallback YAML Content:\n```yaml\n# Failed to parse YAML from LLM response\n# Template ID: {template_id}\n# Raw response:\n{llm_response[:1000]}\n```\n"  # Truncate to avoid too much data

        return output

    def _extract_template_info_from_text(self, yaml_content: str, default_id: str) -> Dict[str, Any]:
        """Extract template information from YAML text without parsing"""
        try:
            # Initialize with defaults
            template_info = {
                "id": default_id,
                "name": f"Generated Template - {default_id}",
                "severity": "medium",
                "description": "Generated Nuclei template",
                "tags": ["generated"],
                "cve_id": None
            }

            lines = yaml_content.split('\n')

            for line in lines:
                line_stripped = line.strip()

                # Extract ID
                if line_stripped.startswith('id:'):
                    value = line_stripped[3:].strip()
                    if value:
                        template_info["id"] = value.strip('"').strip("'")

                # Extract name from info section
                elif 'name:' in line_stripped and not line_stripped.startswith('#'):
                    value = line_stripped.split('name:', 1)[1].strip()
                    if value:
                        template_info["name"] = value.strip('"').strip("'")

                # Extract severity
                elif 'severity:' in line_stripped and not line_stripped.startswith('#'):
                    value = line_stripped.split('severity:', 1)[1].strip()
                    if value:
                        template_info["severity"] = value.strip('"').strip("'")

                # Extract description
                elif 'description:' in line_stripped and not line_stripped.startswith('#'):
                    value = line_stripped.split('description:', 1)[1].strip()
                    if value:
                        template_info["description"] = value.strip('"').strip("'")

                # Extract tags
                elif 'tags:' in line_stripped and not line_stripped.startswith('#'):
                    value = line_stripped.split('tags:', 1)[1].strip()
                    if value:
                        # Handle both string and list format tags
                        tags_text = value.strip('"').strip("'").strip('[').strip(']')
                        if ',' in tags_text:
                            template_info["tags"] = [tag.strip().strip('"').strip("'") for tag in tags_text.split(',') if tag.strip()]
                        else:
                            template_info["tags"] = [tags_text] if tags_text else ["generated"]

                # Extract CVE ID
                elif 'cve-id:' in line_stripped and not line_stripped.startswith('#'):
                    value = line_stripped.split('cve-id:', 1)[1].strip()
                    if value:
                        template_info["cve_id"] = value.strip('"').strip("'")
                elif 'cve_id:' in line_stripped and not line_stripped.startswith('#'):
                    value = line_stripped.split('cve_id:', 1)[1].strip()
                    if value:
                        template_info["cve_id"] = value.strip('"').strip("'")

            logger.debug(f"Extracted template info: {template_info}")
            return template_info

        except Exception as e:
            logger.error(f"Failed to extract template info from text: {e}")
            return {
                "id": default_id,
                "name": f"Generated Template - {default_id}",
                "severity": "medium",
                "description": "Generated Nuclei template",
                "tags": ["generated"],
                "cve_id": None
            }

    def _extract_yaml_from_response(self, response: str) -> Optional[str]:
        """Extract YAML content from LLM response without validation"""
        try:
            # Strategy 1: Extract from code blocks (most reliable)
            yaml_patterns = [
                r'```ya?ml\s*\n(.*?)\n```',  # Standard YAML code block
                r'```\s*\n(id:.*?)\n```',   # Code block starting with id:
                r'```\s*\n(.*?)\n```'       # Any code block
            ]

            for pattern in yaml_patterns:
                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                if match:
                    yaml_content = match.group(1).strip()
                    logger.debug(f"Found YAML in code block")
                    if 'id:' in yaml_content:  # Basic check for Nuclei template
                        return yaml_content

            # Strategy 2: Look for YAML starting with 'id:'
            id_match = re.search(r'(id:\s*[^\n]+.*?)(?=\n\n|\n[^\s]|\Z)', response, re.DOTALL | re.IGNORECASE)
            if id_match:
                yaml_content = id_match.group(1).strip()
                logger.debug("Found YAML starting with 'id:'")
                return yaml_content

            # Strategy 3: Extract multi-line YAML-like structure
            lines = response.split('\n')
            yaml_lines = []
            in_yaml = False

            for line in lines:
                stripped = line.strip()

                # Start YAML detection
                if not in_yaml and (stripped.startswith('id:') or
                                   stripped.startswith('info:') or
                                   stripped.startswith('requests:')):
                    in_yaml = True
                    yaml_lines.append(line)
                    continue

                if in_yaml:
                    # Continue if line looks like YAML
                    if (not stripped or  # Empty line
                        stripped.startswith('#') or  # Comment
                        ':' in stripped or  # Key-value pair
                        stripped.startswith('-') or  # List item
                        line.startswith(' ') or line.startswith('\t')):  # Indented
                        yaml_lines.append(line)
                    else:
                        # Stop if line doesn't look like YAML
                        break

            if yaml_lines:
                yaml_content = '\n'.join(yaml_lines).strip()
                logger.debug(f"Extracted YAML with {len(yaml_lines)} lines")
                return yaml_content

            logger.warning("No YAML content found in response")
            return None

        except Exception as e:
            logger.error(f"YAML extraction failed: {e}")
            return None


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