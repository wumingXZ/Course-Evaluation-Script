from abc import ABC, abstractmethod


class BaseProvider(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat request to the LLM and return the response."""
        ...
