from typing import List, Optional
from langchain_core.embeddings import Embeddings
from common.logger import logger
from common.config import EmbeddingConfigs


class EmbeddingManager:
    """
    Embedding Manager using LangChain embeddings (Singleton)

    Supports:
    - OpenAI (via langchain-openai)
    - Google Gemini (via langchain-google-genai)
    - HuggingFace (via langchain-community)
    """

    _instance = None
    _initialized = False

    def __new__(cls, config: EmbeddingConfigs = None):
        """
        Singleton implementation - ensures only one instance exists

        Args:
            config: EmbeddingConfigs instance with provider configuration
        """
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: EmbeddingConfigs = None):
        """
        Initialize Embedding Manager with configurations
        Only initializes once due to Singleton pattern

        Args:
            config: EmbeddingConfigs instance with provider configuration
        """
        # Only initialize once
        if self._initialized:
            return

        if config is None:
            raise ValueError("Config must be provided on first initialization")

        self.config = config
        self.embedding_model: Optional[Embeddings] = None
        self._initialize_embedding()

        # Mark as initialized
        EmbeddingManager._initialized = True

    def _initialize_embedding(self):
        """Initialize embedding model based on configuration"""
        try:
            provider = (self.config.provider or "huggingface").lower().strip()

            # Normalize provider name
            if provider in ["sentence_transformer", "sentence_transformers"]:
                provider = "huggingface"

            if provider == "openai":
                self.embedding_model = self._create_openai_embedding()
            elif provider == "google":
                self.embedding_model = self._create_google_embedding()
            elif provider == "huggingface":
                self.embedding_model = self._create_huggingface_embedding()
            elif provider == "vllm":
                self.embedding_model = self._create_vllm_embedding()
            elif provider == "ollama":
                self.embedding_model = self._create_ollama_embedding()
            elif provider == "sglang":
                self.embedding_model = self._create_sglang_embedding()
            else:
                logger.warning(f"Unknown provider '{provider}', falling back to HuggingFace")
                self.embedding_model = self._create_huggingface_embedding()

            logger.info(f"[EmbeddingManager] Initialized {provider} embedding successfully")

        except Exception as e:
            logger.error(f"[EmbeddingManager] Failed to initialize embedding: {e}")
            raise

    def _create_openai_embedding(self) -> Embeddings:
        """Create OpenAI embedding using LangChain"""
        try:
            from langchain_openai import OpenAIEmbeddings

            if not self.config.api_key:
                raise ValueError("OpenAI API key is required")

            params = {
                "api_key": self.config.api_key,
                "model": self.config.model_name or "text-embedding-3-small",
            }

            # Add optional parameters
            if self.config.dimensions:
                params["dimensions"] = self.config.dimensions

            if self.config.base_url:
                params["base_url"] = self.config.base_url

            logger.info(f"[EmbeddingManager] Creating OpenAI embedding with model: {params['model']}")
            return OpenAIEmbeddings(**params)

        except ImportError:
            raise ImportError(
                "OpenAI embeddings not available. Install with: "
                "pip install langchain-openai"
            )
        except Exception as e:
            raise ValueError(f"Failed to create OpenAI embedding: {e}")

    def _create_google_embedding(self) -> Embeddings:
        """Create Google Gemini embedding using LangChain"""
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            if not self.config.api_key:
                raise ValueError("Google API key is required")

            params = {
                "google_api_key": self.config.api_key,
                "model": self.config.model_name or "models/embedding-001",
            }

            logger.info(f"[EmbeddingManager] Creating Google embedding with model: {params['model']}")
            return GoogleGenerativeAIEmbeddings(**params)

        except ImportError:
            raise ImportError(
                "Google embeddings not available. Install with: "
                "pip install langchain-google-genai"
            )
        except Exception as e:
            raise ValueError(f"Failed to create Google embedding: {e}")

    def _create_huggingface_embedding(self) -> Embeddings:
        """Create HuggingFace embedding using LangChain"""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            model_name = self.config.model_name or "sentence-transformers/all-MiniLM-L6-v2"

            params = {
                "model_name": model_name,
            }

            logger.info(f"[EmbeddingManager] Creating HuggingFace embedding with model: {model_name}")
            return HuggingFaceEmbeddings(**params)

        except ImportError:
            raise ImportError(
                "HuggingFace embeddings not available. Install with: "
                "pip install langchain-huggingface sentence-transformers"
            )
        except Exception as e:
            raise ValueError(f"Failed to create HuggingFace embedding: {e}")

    def _create_openai_compatible_embedding(self, default_base_url: str, default_model_name: str, provider_name: str) -> Embeddings:
        """Create an embedding model for an OpenAI-compatible API (vLLM, SGLang)"""
        try:
            from langchain_openai import OpenAIEmbeddings

            base_url = self.config.base_url or default_base_url
            model_name = self.config.model_name or default_model_name

            params = {
                "api_key": "EMPTY",  # OpenAI-compatible APIs don't require API key
                "base_url": base_url,
                "model": model_name,
            }

            # Add optional parameters
            if self.config.dimensions:
                params["dimensions"] = self.config.dimensions

            logger.info(f"[EmbeddingManager] Creating {provider_name} embedding with model: {model_name} at {base_url}")
            return OpenAIEmbeddings(**params)

        except ImportError:
            raise ImportError(
                "OpenAI embeddings not available. Install with: "
                "pip install langchain-openai"
            )
        except Exception as e:
            raise ValueError(f"Failed to create {provider_name} embedding: {e}")

    def _create_vllm_embedding(self) -> Embeddings:
        """Create vLLM embedding using OpenAI-compatible API"""
        return self._create_openai_compatible_embedding(
            default_base_url="http://localhost:8006/v1",
            default_model_name="BAAI/bge-small-en-v1.5",
            provider_name="vLLM"
        )

    def _create_ollama_embedding(self) -> Embeddings:
        """Create Ollama embedding using LangChain"""
        try:
            from langchain_ollama import OllamaEmbeddings

            base_url = self.config.base_url or "http://localhost:8005"
            model_name = self.config.model_name or "nomic-embed-text"

            params = {
                "model": model_name,
                "base_url": base_url,
            }

            logger.info(f"[EmbeddingManager] Creating Ollama embedding with model: {model_name} at {base_url}")
            return OllamaEmbeddings(**params)

        except ImportError:
            raise ImportError(
                "Ollama embeddings not available. Install with: "
                "pip install langchain-ollama"
            )
        except Exception as e:
            raise ValueError(f"Failed to create Ollama embedding: {e}")

    def _create_sglang_embedding(self) -> Embeddings:
        """Create SGLang embedding using OpenAI-compatible API"""
        return self._create_openai_compatible_embedding(
            default_base_url="http://localhost:8007/v1",
            default_model_name="BAAI/bge-small-en-v1.5",
            provider_name="SGLang"
        )

    def get_embedding(self) -> Embeddings:
        """
        Get the LangChain embedding model instance

        Returns:
            Embeddings: LangChain embedding model
        """
        if self.embedding_model is None:
            raise ValueError("Embedding model not initialized")
        return self.embedding_model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple documents using LangChain

        Args:
            texts: List of text strings to embed

        Returns:
            List[List[float]]: List of embedding vectors
        """
        if self.embedding_model is None:
            raise ValueError("Embedding model not initialized")

        try:
            return self.embedding_model.embed_documents(texts)
        except Exception as e:
            logger.error(f"[EmbeddingManager] Failed to embed documents: {e}")
            raise

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query using LangChain

        Args:
            text: Query text to embed

        Returns:
            List[float]: Embedding vector
        """
        if self.embedding_model is None:
            raise ValueError("Embedding model not initialized")

        try:
            return self.embedding_model.embed_query(text)
        except Exception as e:
            logger.error(f"[EmbeddingManager] Failed to embed query: {e}")
            raise

    def encode(self, docs: List[str] | str) -> List[List[float]] | List[float]:
        """
        Encode text(s) into embeddings (backward compatibility for sentence_transformers)

        Args:
            docs: Single string or list of strings to encode

        Returns:
            Single embedding vector or list of embedding vectors
        """
        is_single_string = isinstance(docs, str)

        if is_single_string:
            # Single text - return single embedding
            return self.embed_query(docs)
        else:
            # Multiple texts - return list of embeddings
            return self.embed_documents(docs)

    @property
    def dim(self) -> int:
        """
        Get embedding dimension

        Returns:
            int: Embedding dimension
        """
        if self.embedding_model is None:
            raise ValueError("Embedding model not initialized")

        # Try to get dimension from config first
        if self.config.dimensions:
            return self.config.dimensions

        # Otherwise, get from model by encoding a sample text
        try:
            sample_embedding = self.embedding_model.embed_query("test")
            return len(sample_embedding)
        except:
            # Fallback to common dimensions based on provider
            provider = (self.config.provider or "huggingface").lower()
            if provider == "openai":
                model_name = self.config.model_name or "text-embedding-3-small"
                if "large" in model_name:
                    return 3072
                elif "small" in model_name or "ada" in model_name:
                    return 1536
                return 1536
            elif provider == "google":
                return 768
            elif provider == "huggingface":
                return 384
            elif provider in ["vllm", "sglang"]:
                # Common vLLM/SGLang embedding models dimensions
                model_name = self.config.model_name or "BAAI/bge-small-en-v1.5"
                if "large" in model_name:
                    return 1024
                elif "base" in model_name:
                    return 768
                else:  # small
                    return 384
            return 384

    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return ["openai", "google", "huggingface", "vllm", "ollama", "sglang"]

    def get_provider_config(self) -> EmbeddingConfigs:
        """Get current configuration"""
        return self.config

    async def generate_message_embedding_async(self, question: str, answer: str) -> Optional[List[float]]:
        """
        Generate embedding asynchronously from question + answer concatenation for semantic search

        Args:
            question: User's question
            answer: Agent's answer

        Returns:
            Embedding vector or None if failed
        """
        try:
            # Concatenate question and answer for better semantic search
            text = f"Question: {question}\nAnswer: {answer}"

            # Check if embedding model supports async
            if hasattr(self.embedding_model, 'aembed_query'):
                # Use async method if available (OpenAI, Google support this)
                embedding = await self.embedding_model.aembed_query(text)
            else:
                # Fallback to sync method wrapped in asyncio
                import asyncio
                embedding = await asyncio.to_thread(self.embed_query, text)

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate message embedding async: {e}")
            return None
