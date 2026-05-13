from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    def summarize_article(self, article: dict) -> dict:
        pass

    @abstractmethod
    def rank_article(self, article: dict) -> dict:
        pass

    @abstractmethod
    def generate_market_analysis_report(
        self,
        topic: str,
        market_brief: str,
        ranked_sources: str,
        references_text: str
    ) -> str:
        pass
