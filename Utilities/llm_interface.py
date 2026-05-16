import asyncio
import json
import os
import time
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GeneralClient:
    """
    Simple class for other clients to inherit from
    """

    def __init__(
        self,
        model: str,
        rate_limit_between_calls: int = 0,
        api_key: str = "OPENROUTER_API_KEY",
        base_url: str = "https://openrouter.ai/api/v1",
        measure_performance: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        self.model_name = model
        self.rate_limit_between_calls = rate_limit_between_calls
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.measure_performance = measure_performance
        self._last_called_at = 0.0

    def _call_model(self, message: str, override_model: Optional[str] = None) -> str:
        raise NotImplementedError("Must be implemented by child class")  # noqa: EM101

    def _wait_for_rate_limit(self) -> None:
        if self.rate_limit_between_calls <= 0 or self._last_called_at == 0:
            return

        elapsed = time.perf_counter() - self._last_called_at
        remaining = self.rate_limit_between_calls - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def call_model(self, message: str, override_model: Optional[str] = None) -> str:
        self._wait_for_rate_limit()
        start_time = time.perf_counter()
        result = self._call_model(message, override_model=override_model)
        latency = time.perf_counter() - start_time
        self._last_called_at = time.perf_counter()
        if self.measure_performance:
            print(f"[{self.model_name}] API call took {latency:.2f} seconds")
        return result

    async def call_model_async(self, message: str, model: Optional[str] = None) -> str:
        """
        Async model call - by default runs sync version in thread pool,
        but subclasses should implement native async if available.
        Logs the latency of the API call.
        """
        return await asyncio.to_thread(self.call_model, message, model)

    def test(self, model: Optional[str] = None) -> None:
        """
        Test whether a given API integration is working for a given model
        """
        reply = self.call_model(
            "What is the more delicious food, Jollof Rice or Pepperoni Pizza? "
            "Answer with only and exactly one of these two options.",
            model,
        )
        print(model or self.model_name, "\t", self.base_url, reply)


class OpenRouterClient(GeneralClient):
    """
    Thin wrapper around OpenRouter's OpenAI-compatible chat completions API.
    """

    def __init__(
        self,
        model: str,
        rate_limit_between_calls: int = 0,
        api_key: str = "OPENROUTER_API_KEY",
        base_url: str = "https://openrouter.ai/api/v1",
        measure_performance: bool = False,  # noqa: FBT001, FBT002
        timeout_seconds: int = 120,
        max_tokens: Optional[int] = None,
    ) -> None:
        super().__init__(
            model=model,
            rate_limit_between_calls=rate_limit_between_calls,
            api_key=api_key,
            base_url=base_url,
            measure_performance=measure_performance,
        )
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    def _build_headers(self) -> dict[str, str]:
        api_key = os.getenv(self.api_key)
        if not api_key:
            raise RuntimeError(f"Missing required environment variable: {self.api_key}")

        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _extract_text(self, response_payload: dict[str, Any]) -> str:
        choices = response_payload.get("choices")
        if not choices:
            raise ValueError(f"OpenRouter response did not include choices: {response_payload}")  # noqa: TRY003, EM102

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            return "".join(text_parts)
        return str(content)

    def _call_model(self, message: str, override_model: Optional[str] = None) -> str:
        model_to_use = override_model or self.model_name
        payload: dict[str, Any] = {
            "model": model_to_use,
            "messages": [{"role": "user", "content": message}],
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens

        request = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(),
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_payload = json.load(response)
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        return self._extract_text(response_payload)


def _default_model_names() -> list[str]:
    configured_models = os.getenv("OPENROUTER_MODELS")
    if configured_models:
        return [model.strip() for model in configured_models.split(",") if model.strip()]
    return [os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")]


def build_clients(models: Optional[list[str]] = None) -> list[OpenRouterClient]:
    model_names = models if models is not None else _default_model_names()
    return [OpenRouterClient(model_name) for model_name in model_names]


ALL_MODELS = build_clients()
OPENROUTER_DEFAULT = ALL_MODELS[0]


def test_clients() -> None:
    """
    Test out the integrations
    """
    for client in ALL_MODELS:
        client.test()


if __name__ == "__main__":
    test_clients()
