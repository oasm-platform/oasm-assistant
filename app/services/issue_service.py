from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage
from common.logger import logger
from llms import LLMManager
from llms.prompts.issue_prompts import IssuePrompts

from data.database import postgres_db
from data.database.models import LLMConfig

class IssueService:
    """Service for resolving security issues using LLM"""

    def __init__(self):
        # LLM Manager is now a static utility
        self.db = postgres_db

    async def resolve_issue(
        self, 
        question: str, 
        issue_type: int, 
        metadata: Dict[str, Any] = None,
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None
    ) -> str:
        """
        Resolve an issue based on its type using LLM.
        
        Args:
            question: The user's question about the issue
            issue_type: 0 for SSL_ISSUE, 1 for VULNERABILITY_ISSUE
            metadata: Additional context/metadata about the issue
            workspace_id: Workspace ID for LLM config lookup
            user_id: User ID for LLM config lookup
            
        Returns:
            str: The LLM generated solution/response
        """
        try:
            llm = LLMManager.get_llm(workspace_id=workspace_id, user_id=user_id)
            
            # Select prompt based on issue type
            # 0: SSL_ISSUE
            # 1: VULNERABILITY_ISSUE
            
            # issue_type mapping from assistant.proto:
            # ISSUE_TYPE_UNSPECIFIED = 0;
            # ISSUE_TYPE_SSL = 1;
            # ISSUE_TYPE_VULNERABILITY = 2;
            
            if issue_type == 1:
                prompt = IssuePrompts.get_ssl_issue_prompt(question, metadata)
            elif issue_type == 2:
                prompt = IssuePrompts.get_vulnerability_issue_prompt(question, metadata)
            else:
                # Use the default prompt for unspecified types (handles both specific and general cases)
                prompt = IssuePrompts.get_default_issue_prompt(question, metadata)

            # Invoke LLM
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            
            result = response.content.strip()
            
            return result

        except Exception as e:
            logger.error("Error resolving issue: {}", e)
            raise
