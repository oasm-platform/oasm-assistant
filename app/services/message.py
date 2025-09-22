import asyncio
from typing import Dict, Any
from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Message, Conversation

# Import OASM security agent
from agents.security_assistant import create_security_agent


class MessageService(assistant_pb2_grpc.MessageServiceServicer):
    """Enhanced message service with OASM security agent integration"""

    def __init__(self):
        self.db = database_instance

        # Initialize OASM Security Agent
        try:
            self.security_agent = create_security_agent()
            logger.info("OASM Security Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OASM Security Agent: {e}")
            self.security_agent = None

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

                # Generate answer using OASM Security Agent
                answer = ""
                if self.security_agent:
                    try:
                        # Call the security agent directly (now synchronous)
                        result = self.security_agent.answer_security_question(question)

                        if result.get("success"):
                            answer = result.get("answer", "")
                            logger.info(f"Generated answer with confidence: {result.get('confidence', 0)}")
                        else:
                            answer = result.get("answer", "I apologize, but I couldn't process your security question at this time.")
                            logger.warning(f"Agent failed to generate answer: {result.get('metadata', {}).get('error', 'Unknown error')}")

                    except Exception as e:
                        logger.error(f"Error generating answer with security agent: {e}")
                        answer = "I apologize, but I'm experiencing technical difficulties. Please try again later or contact support for assistance with your security question."
                else:
                    # Fallback if security agent is not available
                    answer = f"Thank you for your question: '{question}'. I'm currently unable to provide detailed security analysis, but I recommend consulting with security professionals for specific security concerns."
                    logger.warning("Security agent not available, using fallback response")

                # Create and save message with both question and answer
                message = Message(
                    conversation_id=conversation_id,
                    question=question,
                    answer=answer
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

    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of the security agent"""
        if self.security_agent:
            return {
                "agent_available": True,
                "agent_name": self.security_agent.name,
                "agent_role": self.security_agent.role.value,
                "llm_available": self.security_agent.llm is not None,
                "llm_provider": self.security_agent.llm_provider,
                "capabilities": len(self.security_agent.capabilities),
                "performance": self.security_agent.get_performance_metrics()
            }
        else:
            return {
                "agent_available": False,
                "error": "Security agent not initialized"
            }