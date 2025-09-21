"""
Base provider interface for embedding and generation
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """
    Abstract base class for embedding and generation providers
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration

        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.name = self.__class__.__name__
        logger.info(f"Initializing {self.name} provider")

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            List of float values representing the embedding
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of input texts

        Returns:
            List of embeddings
        """
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text response

        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and configured

        Returns:
            True if provider is ready to use
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get provider information

        Returns:
            Dictionary with provider details
        """
        pass

    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this provider

        Returns:
            Embedding vector dimension
        """
        pass

    @property
    @abstractmethod
    def max_text_length(self) -> int:
        """
        Get maximum text length supported by the provider

        Returns:
            Maximum character count
        """
        pass

    def validate_text(self, text: str) -> str:
        """
        Validate and truncate text if needed

        Args:
            text: Input text

        Returns:
            Validated/truncated text
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        if len(text) > self.max_text_length:
            logger.warning(f"Text exceeds maximum length, truncating to {self.max_text_length} characters")
            return text[:self.max_text_length]

        return text