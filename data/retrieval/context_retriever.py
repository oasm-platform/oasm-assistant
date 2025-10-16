"""
Context-aware retrieval with multiple context modes
"""
from typing import List, Tuple, Dict, Any, Optional
from data.retrieval.similarity_searcher import SimilaritySearcher
from data.retrieval.hybrid_retriever import HybridRetriever, Ranker
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from common.logger import logger
from data.database import postgres_db as db
from sqlalchemy import text
import datetime
from enum import Enum


class ContextMode(Enum):
    """
    Different modes for context retrieval:
    """
    WINDOW = "window"           
    FULL_CHAT = "full_chat"     
    FULL_CONVERSATION = "full_conversation"  


class ContextRetriever:
    """
    Context-aware retrieval that considers conversation history and metadata
    to improve the relevance of search results with multiple context modes.
    """
    
    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None,
        embedding_model: Optional[Any] = None,
        similarity_searcher: Optional[SimilaritySearcher] = None,
        hybrid_retriever: Optional[HybridRetriever] = None,
        context_window_size: int = 5,
        conversation_weight: float = 0.3,
        metadata_weight: float = 0.2,
        context_mode: ContextMode = ContextMode.WINDOW,
        ranker: Optional[Ranker] = None
    ):
        """
        Initialize the context retriever.
        
        Args:
            vector_store: PgVectorStore instance for database operations
            embedding_model: Embedding model for generating query vectors
            similarity_searcher: Pre-configured SimilaritySearcher instance
            hybrid_retriever: Pre-configured HybridRetriever instance
            context_window_size: Number of previous messages to consider as context
            conversation_weight: Weight for conversation context (0-1)
            metadata_weight: Weight for metadata matching (0-1)
            context_mode: Mode of context retrieval (window, full_chat, full_conversation)
            ranker: Ranker to use for final result ranking
        """
        self.vector_store = vector_store or PgVectorStore()
        self.embedding_model = embedding_model or Embeddings.create_embedding('sentence_transformer')
        self.similarity_searcher = similarity_searcher or SimilaritySearcher(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model
        )
        self.hybrid_retriever = hybrid_retriever or HybridRetriever(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model,
            ranker=ranker 
        )
        self.context_window_size = context_window_size
        self.conversation_weight = conversation_weight
        self.metadata_weight = metadata_weight  # Reserved for future metadata-based scoring
        self.context_mode = context_mode
    
    def _get_conversation_context(
        self,
        conversation_id: Optional[str],
        current_query: str,
        context_mode: Optional[ContextMode] = None,
        window_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history to provide context based on the specified mode.
        
        Args:
            conversation_id: ID of the current conversation
            current_query: Current query from the user
            context_mode: Mode of context retrieval (defaults to self.context_mode)
            window_size: Number of messages to retrieve (for window mode, defaults to self.context_window_size)
            
        Returns:
            List of messages in the conversation based on the context mode
        """
        if not conversation_id:
            return []
        
        mode = context_mode or self.context_mode
        window = window_size or self.context_window_size
        
        try:
            with db.get_session() as session:
                if mode == ContextMode.WINDOW:
                    query = text("""
                        SELECT question, answer, created_at, id
                        FROM messages
                        WHERE conversation_id = :conversation_id
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """)
                    
                    result = session.execute(
                        query,
                        {"conversation_id": conversation_id, "limit": window}
                    )
                    
                    context_messages = []
                    for row in result:
                        context_messages.append({
                            'id': row.id,
                            'question': row.question,
                            'answer': row.answer,
                            'timestamp': row.created_at
                        })
                    
                    return list(reversed(context_messages))
                
                elif mode == ContextMode.FULL_CHAT:
                    query = text("""
                        SELECT question, answer, created_at, id
                        FROM messages
                        WHERE conversation_id = :conversation_id
                        AND created_at > :time_threshold
                        ORDER BY created_at ASC
                    """)

                    time_threshold = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
                    
                    result = session.execute(
                        query,
                        {"conversation_id": conversation_id, "time_threshold": time_threshold}
                    )
                    
                    context_messages = []
                    for row in result:
                        context_messages.append({
                            'id': row.id,
                            'question': row.question,
                            'answer': row.answer,
                            'timestamp': row.created_at
                        })
                    
                    return context_messages
                
                elif mode == ContextMode.FULL_CONVERSATION:
                    query = text("""
                        SELECT question, answer, created_at, id
                        FROM messages
                        WHERE conversation_id = :conversation_id
                        ORDER BY created_at ASC
                    """)
                    
                    result = session.execute(
                        query,
                        {"conversation_id": conversation_id}
                    )
                    
                    context_messages = []
                    for row in result:
                        context_messages.append({
                            'id': row.id,
                            'question': row.question,
                            'answer': row.answer,
                            'timestamp': row.created_at
                        })
                    
                    return context_messages
                else:
                    query = text("""
                        SELECT question, answer, created_at, id
                        FROM messages
                        WHERE conversation_id = :conversation_id
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """)
                    
                    result = session.execute(
                        query,
                        {"conversation_id": conversation_id, "limit": window}
                    )
                    
                    context_messages = []
                    for row in result:
                        context_messages.append({
                            'id': row.id,
                            'question': row.question,
                            'answer': row.answer,
                            'timestamp': row.created_at
                        })
                    
                    return list(reversed(context_messages))
                    
        except Exception as e:
            logger.error(f"Error retrieving conversation context: {e}")
            return []
    
    def _expand_query_with_context(
        self,
        query: str,
        context_messages: List[Dict[str, Any]],
        context_mode: ContextMode = ContextMode.WINDOW
    ) -> str:
        """
        Expand the query with relevant context from conversation history based on context mode.
        
        Args:
            query: Original query from the user
            context_messages: Messages in the conversation
            context_mode: Mode of context retrieval
            
        Returns:
            Expanded query string with context
        """
        if not context_messages:
            return query
        
        # Build context string from messages based on context mode
        if context_mode == ContextMode.WINDOW:
            # Use only last few messages as context (similar to original behavior)
            recent_messages = context_messages[-3:] if len(context_messages) > 3 else context_messages
            context_str = "Previous conversation context:\n"
            for msg in recent_messages:
                if msg.get('question'):
                    context_str += f"Q: {msg['question']}\n"
                if msg.get('answer'):
                    context_str += f"A: {msg['answer']}\n"
        else:
            # For full chat or full conversation, we might want to summarize or sample
            if len(context_messages) > 10:  
                sampled_messages = context_messages[-5:] 
                context_str = "Recent conversation context:\n"
                for msg in sampled_messages:
                    if msg.get('question'):
                        context_str += f"Q: {msg['question']}\n"
                    if msg.get('answer'):
                        context_str += f"A: {msg['answer']}\n"
            else:
                context_str = "Conversation context:\n"
                for msg in context_messages:
                    if msg.get('question'):
                        context_str += f"Q: {msg['question']}\n"
                    if msg.get('answer'):
                        context_str += f"A: {msg['answer']}\n"
        
        expanded_query = f"{context_str}\nCurrent query: {query}"
        return expanded_query
    
    def retrieve_with_context(
        self,
        table_name: str,
        query: str,
        conversation_id: Optional[str] = None,
        k: int = 10,
        text_column: str = "text",
        embedding_column: str = "embedding",
        metadata_filters: Optional[Dict[str, Any]] = None,
        context_mode: Optional[ContextMode] = None,
        window_size: Optional[int] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Retrieve results considering both conversation context and metadata filters.
        
        Args:
            table_name: Name of the table to search in
            query: User query to search for
            conversation_id: ID of the current conversation (for context)
            k: Number of results to return
            text_column: Name of the text column to search in (default: "text")
            embedding_column: Name of the embedding column (default: "embedding")
            metadata_filters: Optional filters to apply to metadata
            context_mode: Mode of context retrieval (defaults to self.context_mode)
            window_size: Number of messages to retrieve (for window mode, defaults to self.context_window_size)
            
        Returns:
            List of (score, metadata) tuples with context-aware scoring
        """
        try:
            # Get conversation context based on specified mode
            mode = context_mode or self.context_mode
            context_messages = self._get_conversation_context(
                conversation_id, query, mode, window_size
            )
            
            # Expand query with context based on mode
            expanded_query = self._expand_query_with_context(query, context_messages, mode)
            
            # Perform hybrid search with expanded query
            results = self.hybrid_retriever.hybrid_search(
                table_name=table_name,
                query_text=expanded_query,
                k=k * 2,  # Get more results to account for context filtering
                text_column=text_column,
                embedding_column=embedding_column
            )
            
            # Apply metadata filters if provided
            if metadata_filters:
                filtered_results = []
                for score, metadata in results:
                    include_result = True
                    for filter_key, filter_value in metadata_filters.items():
                        if metadata.get(filter_key) != filter_value:
                            include_result = False
                            break
                    if include_result:
                        filtered_results.append((score, metadata))
                results = filtered_results
            
            # Adjust scores based on context relevance
            adjusted_results = []
            for score, metadata in results:
                # Calculate context relevance score if we have conversation context
                context_relevance = 0.0
                if context_messages and 'text' in metadata:
                    # Simple keyword matching between context and result text
                    context_text = " ".join([
                        msg.get('question', '') + " " + msg.get('answer', '')
                        for msg in context_messages
                    ]).lower()
                    result_text = metadata.get('text', '').lower()
                    
                    # Count matching words as context relevance
                    context_words = set(context_text.split())
                    result_words = set(result_text.split())
                    matching_words = context_words.intersection(result_words)
                    if context_words:
                        context_relevance = len(matching_words) / len(context_words)
                
                # Calculate adjusted score with context weight
                adjusted_score = (
                    score * (1 - self.conversation_weight) +
                    context_relevance * self.conversation_weight
                )
                
                adjusted_results.append((adjusted_score, metadata))
            
            # Sort by adjusted score and return top k
            adjusted_results.sort(key=lambda x: x[0], reverse=True)
            return adjusted_results[:k]
            
        except Exception as e:
            logger.error(f"Error in context-aware retrieval: {e}")
            return []
    
    def retrieve_conversation_aware(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        k: int = 5,
        knowledge_table: str = "text_vectors",
        message_table: str = "messages",
        window_size: Optional[int] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Retrieve results considering both knowledge base and conversation history.
        
        Args:
            query: User query to search for
            conversation_id: ID of the current conversation
            k: Number of results to return
            knowledge_table: Name of the knowledge base table (default: "text_vectors")
            message_table: Name of the message history table (default: "messages")
            window_size: Number of messages to retrieve for context (defaults to self.context_window_size)
            
        Returns:
            List of (score, metadata) tuples combining knowledge and conversation context
        """
        try:
            # Get conversation context using WINDOW mode (as specified in requirements)
            context_messages = self._get_conversation_context(
                conversation_id, query, ContextMode.WINDOW, window_size
            )
            
            # Search in knowledge base with context using WINDOW mode
            knowledge_results = self.retrieve_with_context(
                table_name=knowledge_table,
                query=query,
                conversation_id=conversation_id,
                k=k,
                metadata_filters=None,
                context_mode=ContextMode.WINDOW,
                window_size=window_size
            )
            
            # If we have conversation context, also search in message history
            message_results = []
            if conversation_id and context_messages:
                message_results = self.hybrid_retriever.hybrid_search(
                    table_name=message_table,
                    query_text=query,
                    k=min(k//2, 3),  # Limit message history results
                    text_column="question"  # Search in questions
                )
                
                # Add a source indicator to message results
                for i in range(len(message_results)):
                    score, metadata = message_results[i]
                    metadata['source'] = 'conversation_history'
                    message_results[i] = (score, metadata)
            
            # Combine knowledge and message results
            all_results = knowledge_results + message_results
            
            # Sort by score and return top k
            all_results.sort(key=lambda x: x[0], reverse=True)
            return all_results[:k]
            
        except Exception as e:
            logger.error(f"Error in conversation-aware retrieval: {e}")
            return []
    
    def search_with_query_understanding(
        self,
        table_name: str,
        query: str,
        conversation_id: Optional[str] = None,
        k: int = 10,
        text_column: str = "text",
        embedding_column: str = "embedding",
        window_size: Optional[int] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Perform context-aware search with query understanding and expansion.
        
        Args:
            table_name: Name of the table to search in
            query: User query to search for
            conversation_id: ID of the current conversation
            k: Number of results to return
            text_column: Name of the text column to search in (default: "text")
            embedding_column: Name of the embedding column (default: "embedding")
            window_size: Number of messages to retrieve for context (defaults to self.context_window_size)
            
        Returns:
            List of (score, metadata) tuples with enhanced query understanding
        """
        try:
            # Get conversation context using WINDOW mode (as specified in requirements)
            context_messages = self._get_conversation_context(
                conversation_id, query, ContextMode.WINDOW, window_size
            )
            
            # Identify query type and expand accordingly with context mode
            expanded_query = self._expand_query_by_type(query, context_messages, ContextMode.WINDOW)
            
            # Perform context-aware retrieval using WINDOW mode
            results = self.retrieve_with_context(
                table_name=table_name,
                query=expanded_query,
                conversation_id=conversation_id,
                k=k,
                text_column=text_column,
                embedding_column=embedding_column,
                context_mode=ContextMode.WINDOW,
                window_size=window_size
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in query understanding retrieval: {e}")
            return []
    
    def _expand_query_by_type(
        self,
        query: str,
        context_messages: List[Dict[str, Any]],
        context_mode: ContextMode = ContextMode.WINDOW
    ) -> str:
        """
        Expand query based on its type and conversation context.
        
        Args:
            query: Original query
            context_messages: Context messages from conversation
            context_mode: Mode of context retrieval
            
        Returns:
            Expanded query string
        """
        # Simple query type detection
        query_lower = query.lower()
        
        # Check if query refers to previous conversation
        if any(word in query_lower for word in ["that", "it", "the above", "previous", "earlier", "mentioned"]):
            # If query refers to previous content, include more context
            if context_messages:
                if context_mode == ContextMode.WINDOW:
                    # Use last 2 exchanges for window mode
                    relevant_messages = context_messages[-2:] if len(context_messages) >= 2 else context_messages
                else:
                    # For full modes, use first and last few messages to summarize
                    relevant_messages = context_messages[:1] + context_messages[-2:] if len(context_messages) > 3 else context_messages
                
                context_str = " ".join([
                    msg.get('question', '') + " " + msg.get('answer', '')
                    for msg in relevant_messages
                ])
                return f"Based on this context: {context_str}. Query: {query}"
        
        # For follow-up questions, expand with context
        if any(word in query_lower for word in ["how", "why", "what", "when", "where", "who", "which"]):
            if context_messages:
                # Add context from last message based on mode
                if context_mode == ContextMode.WINDOW:
                    last_msg = context_messages[-1] if context_messages else {}
                else:
                    # For full modes, consider the most recent message
                    last_msg = context_messages[-1] if context_messages else {}
                    
                last_question = last_msg.get('question', '')
                if last_question:
                    return f"Regarding: {last_question}. Follow-up: {query}"
        
        # Default: return original query with context
        if context_messages:
            if context_mode == ContextMode.WINDOW:
                # Use last exchange only for window mode
                last_exchange = context_messages[-1:] if context_messages else []
            else:
                # For full modes, use first and last to summarize
                last_exchange = context_messages[:1] + context_messages[-1:] if len(context_messages) > 1 else context_messages[:1]
                
            context_str = " ".join([
                msg.get('question', '') + " " + msg.get('answer', '')
                for msg in last_exchange
            ])
            if context_str:
                return f"Context: {context_str}. Query: {query}"
        
        return query

    def retrieve_with_window_context(
        self,
        table_name: str,
        query: str,
        conversation_id: Optional[str],
        k: int = 10,
        text_column: str = "text",
        embedding_column: str = "embedding",
        window_size: Optional[int] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Retrieve results using only the WINDOW context mode (k most recent messages).
        This is the primary method as per requirements.
        
        Args:
            table_name: Name of the table to search in
            query: User query to search for
            conversation_id: ID of the current conversation
            k: Number of results to return
            text_column: Name of the text column to search in (default: "text")
            embedding_column: Name of the embedding column (default: "embedding")
            window_size: Number of recent messages to use as context (defaults to self.context_window_size)
            
        Returns:
            List of (score, metadata) tuples with window-based context
        """
        return self.retrieve_with_context(
            table_name=table_name,
            query=query,
            conversation_id=conversation_id,
            k=k,
            text_column=text_column,
            embedding_column=embedding_column,
            metadata_filters=None,
            context_mode=ContextMode.WINDOW,
            window_size=window_size
        )

    def retrieve_with_full_chat_context(
        self,
        table_name: str,
        query: str,
        conversation_id: Optional[str],
        k: int = 10,
        text_column: str = "text",
        embedding_column: str = "embedding"
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Retrieve results using FULL_CHAT context mode (all messages in current chat session).
        Currently implemented as messages from the last hour as a proxy for "current chat session".
        
        Args:
            table_name: Name of the table to search in
            query: User query to search for
            conversation_id: ID of the current conversation
            k: Number of results to return
            text_column: Name of the text column to search in (default: "text")
            embedding_column: Name of the embedding column (default: "embedding")
            
        Returns:
            List of (score, metadata) tuples with full chat context
        """
        return self.retrieve_with_context(
            table_name=table_name,
            query=query,
            conversation_id=conversation_id,
            k=k,
            text_column=text_column,
            embedding_column=embedding_column,
            metadata_filters=None,
            context_mode=ContextMode.FULL_CHAT
        )

    def retrieve_with_full_conversation_context(
        self,
        table_name: str,
        query: str,
        conversation_id: Optional[str],
        k: int = 10,
        text_column: str = "text",
        embedding_column: str = "embedding"
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Retrieve results using FULL_CONVERSATION context mode (all messages in the conversation).
        
        Args:
            table_name: Name of the table to search in
            query: User query to search for
            conversation_id: ID of the current conversation
            k: Number of results to return
            text_column: Name of the text column to search in (default: "text")
            embedding_column: Name of the embedding column (default: "embedding")
            
        Returns:
            List of (score, metadata) tuples with full conversation context
        """
        return self.retrieve_with_context(
            table_name=table_name,
            query=query,
            conversation_id=conversation_id,
            k=k,
            text_column=text_column,
            embedding_column=embedding_column,
            metadata_filters=None,
            context_mode=ContextMode.FULL_CONVERSATION
        )
