import unittest
from unittest.mock import patch

from llm import gemini_provider


class FakeResponse:
    text = "{}"


class FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **request):
        self.calls.append(request)
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


class GeminiProviderRequestDelayTest(unittest.TestCase):
    def test_request_delay_zero_does_not_sleep(self):
        provider = object.__new__(gemini_provider.GeminiProvider)

        with patch.object(gemini_provider, "LLM_REQUEST_DELAY_SECONDS", 0):
            with patch.object(gemini_provider.time, "sleep") as sleep:
                provider._apply_request_delay()

        sleep.assert_not_called()

    def test_request_delay_positive_sleeps(self):
        provider = object.__new__(gemini_provider.GeminiProvider)

        with patch.object(gemini_provider, "LLM_REQUEST_DELAY_SECONDS", 2):
            with patch.object(gemini_provider.time, "sleep") as sleep:
                provider._apply_request_delay()

        sleep.assert_called_once_with(2.0)

    def test_generate_content_applies_delay_after_successful_request(self):
        provider = object.__new__(gemini_provider.GeminiProvider)
        provider.client = FakeClient()
        provider.last_model_used = ""

        with patch.object(gemini_provider, "LLM_REQUEST_DELAY_SECONDS", 1):
            with patch.object(gemini_provider.time, "sleep") as sleep:
                response_text = provider.generate_content_text("prompt", "title")

        self.assertEqual(response_text, "{}")
        self.assertEqual(len(provider.client.models.calls), 1)
        sleep.assert_called_once_with(1.0)


if __name__ == "__main__":
    unittest.main()
