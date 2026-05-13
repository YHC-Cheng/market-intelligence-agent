from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    def summarize_article(self, article: dict) -> dict:
        pass

    @abstractmethod
    def rank_article(self, article: dict) -> dict:
        pass
