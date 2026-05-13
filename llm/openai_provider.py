from llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def summarize_article(self, article: dict) -> dict:
        raise NotImplementedError("OpenAI provider is not implemented yet.")

    def rank_article(self, article: dict) -> dict:
        raise NotImplementedError("OpenAI provider is not implemented yet.")
