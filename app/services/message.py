import asyncio
from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Message, Conversation
from agents.core import BaseAgent, AgentRole
from agents.workflows.langgraph_coordinator import LangGraphSecurityCoordinator


def create_security_agent():
    """Create a basic security agent for fallback"""

    class BasicSecurityAgent(BaseAgent):
        def setup_tools(self):
            return []

        def create_prompt_template(self):
            return "You are a security assistant."

        def process_observation(self, observation):
            return {"processed": True}

        def execute_task(self, task):
            return {"success": False, "message": "Basic agent - limited functionality"}

        def answer_security_question(self, question):
            """Synchronous method to answer security questions"""
            try:
                response = self.query_llm(f"Security question: {question}")

                return {
                    "success": True,
                    "answer": response,
                    "agent": self.name
                }
            except Exception as e:
                logger.error(f"Security agent error: {e}")
                return {
                    "success": False,
                    "answer": "I apologize, but I'm currently unable to process this security question.",
                    "error": str(e)
                }

    return BasicSecurityAgent(
        name="BasicSecurityAgent",
        role=AgentRole.THREAT_ANALYST
    )


class MessageService(assistant_pb2_grpc.MessageServiceServicer):
    """Enhanced message service with OASM security agent integration"""

    def __init__(self):
        self.db = database_instance
        self.security_agent = create_security_agent()

        # Initialize LangGraph coordination system
        try:
            self.coordination_agent = LangGraphSecurityCoordinator()
            logger.info("LangGraph multi-agent coordination system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph coordinator: {e}")
            self.coordination_agent = None

        logger.info("Message service initialized with LangGraph security coordination")

    def GetMessages(self, request, context):
        """Get all messages for a conversation"""
        try:
            conversation_id = request.conversation_id
            with self.db.get_session() as session:
                messages = session.query(Message).filter(
                    Message.conversation_id == conversation_id
                ).all()
                return assistant_pb2.GetMessagesResponse(messages=[message.to_dict() for message in messages])

        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetMessagesResponse(messages=[])

    def CreateMessage(self, request, context):
        """Enhanced CreateMessage with OASM security agent integration"""
        try:
            conversation_id = request.conversation_id
            question = request.question

            with self.db.get_session() as session:
                # Check if conversation exists
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()

                if not conversation:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Conversation not found")
                    return assistant_pb2.CreateMessageResponse()

                # Generate answer using OASM Multi-Agent System
                answer = ""

                # Try LangGraph multi-agent coordination first
                if self.coordination_agent:
                    try:
                        # Analyze question to determine task type
                        task_type = self._analyze_question_type(question)

                        # Create task for LangGraph coordinator
                        coordination_task = {
                            "type": task_type,
                            "question": question,
                            "target": self._extract_target_from_question(question),
                            "vulnerability_data": self._extract_vulnerability_data(question)
                        }

                        # Execute through LangGraph coordinator
                        result = self.coordination_agent.execute_security_task(coordination_task)

                        if result.get("success"):
                            # Format LangGraph results into readable answer
                            answer = self._format_langgraph_response(result, question)
                            logger.info(f"Generated LangGraph answer for task type: {task_type}")
                        else:
                            # Fall back to single security agent
                            answer = self._fallback_to_security_agent(question)

                    except Exception as e:
                        logger.error(f"Error with LangGraph coordination: {e}")
                        # Fall back to single security agent
                        answer = self._fallback_to_security_agent(question)

                else:
                    # Fall back to single security agent
                    answer = self._fallback_to_security_agent(question)

                # Create and save message with both question and answer
                message = Message(
                    conversation_id=conversation_id,
                    question=question,
                    answer=answer,
                    is_create_template=request.is_create_template if hasattr(request, 'is_create_template') else False
                )
                session.add(message)
                session.commit()
                session.refresh(message)

                logger.info(f"Created message with ID: {message.id}")
                return assistant_pb2.CreateMessageResponse(message=message.to_dict())

        except Exception as e:
            logger.error(f"Error creating message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.CreateMessageResponse()

    def UpdateMessage(self, request, context):
        """Enhanced UpdateMessage with potential re-generation of answers"""
        try:
            id = request.id
            question = request.question

            with self.db.get_session() as session:
                message = session.query(Message).filter(
                    Message.id == id
                ).first()

                if not message:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Message not found")
                    return assistant_pb2.UpdateMessageResponse()

                # Update question
                old_question = message.question
                message.question = question
                # Update is_create_template if provided in request
                if hasattr(request, 'is_create_template'):
                    message.is_create_template = request.is_create_template

                # If question changed significantly, regenerate answer
                if old_question != question and self.security_agent:
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        try:
                            result = loop.run_until_complete(
                                self.security_agent.answer_security_question(question)
                            )

                            if result.get("success"):
                                message.answer = result.get("answer", message.answer)
                                logger.info(f"Regenerated answer for updated question")

                        finally:
                            loop.close()

                    except Exception as e:
                        logger.error(f"Error regenerating answer: {e}")
                        # Keep the old answer if regeneration fails

                session.commit()
                session.refresh(message)
                return assistant_pb2.UpdateMessageResponse(message=message.to_dict())

        except Exception as e:
            logger.error(f"Error updating message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.UpdateMessageResponse()

    def DeleteMessage(self, request, context):
        """Delete a message"""
        try:
            id = request.id

            with self.db.get_session() as session:
                message = session.query(Message).filter(
                    Message.id == id
                ).first()

                if not message:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Message not found")
                    return assistant_pb2.DeleteMessageResponse(message="Message not found", success=False)

                session.delete(message)
                session.commit()
                return assistant_pb2.DeleteMessageResponse(message="Message deleted successfully", success=True)

        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteMessageResponse(message="Error deleting message", success=False)

    def _analyze_question_type(self, question: str) -> str:
        """Analyze question to determine appropriate multi-agent task type"""
        question_lower = question.lower()

        # Check for nuclei template generation
        if any(keyword in question_lower for keyword in ["nuclei", "template", "generate", "vulnerability", "cve"]):
            return "generate_nuclei_template"

        # Check for security analysis
        if any(keyword in question_lower for keyword in ["scan", "analyze", "security", "threat", "attack"]):
            return "coordinate_security_analysis"

        # Check for multi-tool scanning
        if any(keyword in question_lower for keyword in ["nmap", "subfinder", "httpx", "reconnaissance", "recon"]):
            return "multi_agent_scan"

        # Check for threat investigation
        if any(keyword in question_lower for keyword in ["investigate", "incident", "malware", "breach"]):
            return "threat_investigation"

        # Default to general security analysis
        return "coordinate_security_analysis"

    def _extract_target_from_question(self, question: str) -> str:
        """Extract target information from question"""
        # Simple regex patterns to extract domains, IPs, etc.
        import re

        # Look for domain patterns
        domain_pattern = r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
        domains = re.findall(domain_pattern, question)

        # Look for IP patterns
        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        ips = re.findall(ip_pattern, question)

        # Return first found target
        if domains:
            return domains[0]
        elif ips:
            return ips[0]

        return "unknown"

    def _extract_vulnerability_data(self, question: str) -> dict:
        """Extract vulnerability data from question"""
        import re

        vulnerability_data = {}

        # Extract CVE IDs
        cve_pattern = r'CVE-\d{4}-\d{4,7}'
        cves = re.findall(cve_pattern, question, re.IGNORECASE)
        if cves:
            vulnerability_data["cve_id"] = cves[0]

        # Extract severity keywords
        severity_keywords = ["critical", "high", "medium", "low"]
        for severity in severity_keywords:
            if severity in question.lower():
                vulnerability_data["severity"] = severity
                break

        # Extract vulnerability types
        vuln_types = ["xss", "sqli", "sql injection", "lfi", "rfi", "ssrf", "csrf", "rce"]
        for vuln_type in vuln_types:
            if vuln_type in question.lower():
                vulnerability_data["vulnerability_type"] = vuln_type
                break

        # Add question as description
        vulnerability_data["description"] = question

        return vulnerability_data

    def _format_langgraph_response(self, result: dict, question: str) -> str:
        """Format LangGraph coordination results into readable response"""
        try:
            task_type = result.get("task_type", "unknown")
            success = result.get("success", False)

            if not success:
                error_msg = result.get("error", "Unknown error")
                return f"I apologize, but I encountered difficulties processing your request: {error_msg}"

            # Get participating agents and results
            participating_agents = result.get("participating_agents", [])
            agent_results = result.get("agent_results", {})

            # Format response based on task type
            response = f"**LangGraph Security Analysis Complete**\n\n"
            response += f"**Task Type:** {task_type.replace('_', ' ').title()}\n"
            response += f"**Question:** {question}\n"
            response += f"**Participating Agents:** {len(participating_agents)}\n\n"

            if task_type == "generate_nuclei_template":
                return self._format_langgraph_nuclei_response(result, question)

            # Format results from each agent
            if agent_results:
                response += "**Agent Analysis Results:**\n"
                for agent_name, agent_result in agent_results.items():
                    if isinstance(agent_result, dict):
                        success_status = "✅ Success" if agent_result.get("success") else "❌ Failed"
                        response += f"\n**{agent_name.replace('_', ' ').title()}:** {success_status}\n"

                        if agent_result.get("success"):
                            # Add specific results based on agent type
                            if "analysis" in agent_result:
                                analysis = agent_result["analysis"]
                                if isinstance(analysis, dict):
                                    response += f"- Risk Assessment: {analysis.get('risk_assessment', 'N/A')}\n"
                                    response += f"- Confidence: {analysis.get('confidence', 0):.1%}\n"

                            if "scan_results" in agent_result:
                                response += f"- Scan completed successfully\n"
                        else:
                            error = agent_result.get("error", "Unknown error")
                            response += f"- Error: {error}\n"

            response += f"\n**Summary:**\nCompleted multi-agent security analysis using LangGraph workflow coordination. "
            response += f"Each agent contributed specialized expertise to provide comprehensive security insights."

            return response

        except Exception as e:
            logger.error(f"Error formatting LangGraph response: {e}")
            return f"LangGraph analysis completed, but I encountered an issue formatting the detailed response."

    def _format_langgraph_nuclei_response(self, result: dict, question: str) -> str:
        """Format LangGraph nuclei template generation response"""
        try:
            agent_results = result.get("agent_results", {})
            nuclei_result = agent_results.get("nuclei_generator", {})

            if nuclei_result.get("success"):
                template_info = nuclei_result.get("template")
                if template_info:
                    # Handle NucleiTemplate object
                    if hasattr(template_info, 'id'):
                        # It's a NucleiTemplate object
                        response = f"**Nuclei Template Generated Successfully**\n\n"
                        response += f"**Question:** {question}\n"
                        response += f"**Template Details:**\n"
                        response += f"- Template ID: {getattr(template_info, 'id', 'N/A')}\n"
                        response += f"- Name: {getattr(template_info, 'name', 'N/A')}\n"
                        response += f"- Severity: {getattr(template_info, 'severity', 'N/A')}\n"
                        response += f"- Description: {getattr(template_info, 'description', 'N/A')}\n"
                        response += f"- Tags: {', '.join(getattr(template_info, 'tags', []))}\n\n"
                        response += f"**Generation Metadata:**\n"
                        response += f"- Confidence: {getattr(template_info, 'confidence', 0):.1%}\n"
                        response += f"- Generated via LangGraph workflow\n\n"
                        response += f"The template is ready for use with nuclei scanning tools and follows nuclei best practices."
                        response += f"\n\n"
                        response += f"```yaml\n{template_info.yaml_content}\n```"
                        return response
                    elif isinstance(template_info, dict):
                        # It's a dictionary
                        response = f"**Nuclei Template Generated Successfully**\n\n"
                        response += f"**Question:** {question}\n"
                        response += f"**Template Details:**\n"
                        response += f"- Template ID: {template_info.get('id', 'N/A')}\n"
                        response += f"- Name: {template_info.get('name', 'N/A')}\n"
                        response += f"- Severity: {template_info.get('severity', 'N/A')}\n"
                        response += f"- Description: {template_info.get('description', 'N/A')}\n"
                        response += f"- Tags: {', '.join(template_info.get('tags', []))}\n\n"
                        response += f"**Generation Metadata:**\n"
                        response += f"- Confidence: {template_info.get('confidence', 0):.1%}\n"
                        response += f"- Generated via LangGraph workflow\n\n"
                        response += f"The template is ready for use with nuclei scanning tools and follows nuclei best practices."
                        return response
                    else:
                        # Unknown format
                        logger.error(f"Unknown template format: {type(template_info)}")
                        return "Nuclei template generation completed, but template format is not recognized."

            return "Nuclei template generation completed via LangGraph, but template details are not available."

        except Exception as e:
            logger.error(f"Error formatting LangGraph nuclei response: {e}")
            return "Nuclei template generation completed, but encountered formatting issues."

    def _format_nuclei_generation_response(self, result: dict, question: str) -> str:
        """Format nuclei template generation response"""
        try:
            if result.get("delegated_to") == "nuclei_generator":
                nuclei_result = result.get("result", {})
                if nuclei_result.get("success"):
                    template = nuclei_result.get("template")
                    if template:
                        return f"""I've successfully generated a nuclei template based on your request.

**Template Details:**
- Template ID: {template.id}
- Name: {template.name}
- Severity: {template.severity}
- Description: {template.description}
- Tags: {', '.join(template.tags)}

**Generation Metadata:**
- Confidence: {template.confidence:.2f}
- Generated at: {template.created_at}

The template is ready for use with nuclei scanning tools. It includes proper YAML structure, detection logic, and follows nuclei best practices."""
                    else:
                        return "Nuclei template generation completed, but template details are not available in the expected format."
                else:
                    error = nuclei_result.get("error", "Unknown error during template generation")
                    return f"I encountered an issue generating the nuclei template: {error}"
            else:
                return "Nuclei template generation was requested but not properly delegated to the specialized agent."

        except Exception as e:
            logger.error(f"Error formatting nuclei response: {e}")
            return "Nuclei template generation completed, but I encountered an issue formatting the detailed response."

    def _format_coordination_response(self, result: dict, question: str) -> str:
        """Format general coordination response"""
        try:
            participating_agents = result.get("participating_agents", [])
            results = result.get("results", {})

            response = f"I've coordinated a multi-agent analysis to address your security question.\n\n"
            response += f"**Analysis Overview:**\n"
            response += f"- Question: {question}\n"
            response += f"- Participating Agents: {len(participating_agents)}\n"
            response += f"- Task ID: {result.get('task_id', 'N/A')}\n\n"

            if results:
                response += "**Agent Results:**\n"
                for agent_name, agent_result in results.items():
                    if isinstance(agent_result, dict):
                        success = agent_result.get("success", False)
                        status = "✅ Completed" if success else "❌ Failed"
                        response += f"- {agent_name}: {status}\n"

                        if not success and agent_result.get("error"):
                            response += f"  Error: {agent_result['error']}\n"

            response += f"\n**Summary:**\nMulti-agent security analysis completed successfully. Each participating agent contributed specialized expertise to provide comprehensive insights for your security question."

            return response

        except Exception as e:
            logger.error(f"Error formatting coordination response: {e}")
            return "Multi-agent coordination completed, but I encountered an issue formatting the detailed response."

    def _fallback_to_security_agent(self, question: str) -> str:
        """Fallback to single security agent if multi-agent fails"""
        if self.security_agent:
            try:
                # Call the security agent directly (now synchronous)
                result = self.security_agent.answer_security_question(question)

                if result.get("success"):
                    return result.get("answer", "")
                else:
                    return result.get("answer", "I apologize, but I couldn't process your security question at this time.")

            except Exception as e:
                logger.error(f"Error with fallback security agent: {e}")
                return "I apologize, but I'm experiencing technical difficulties. Please try again later."
        else:
            return f"Thank you for your question: '{question}'. I'm currently unable to provide detailed security analysis, but I recommend consulting with security professionals for specific security concerns."
