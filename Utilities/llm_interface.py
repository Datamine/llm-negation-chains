import asyncio
import json
import os
import time
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PaymentRequiredError(RuntimeError):
    pass


class GeneralClient:
    """
    OpenRouter client.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        measure_performance: bool = False,  # noqa: FBT001, FBT002
        timeout_seconds: int = 120,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        reasoning: Optional[dict[str, Any]] = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not resolved_api_key:
            raise RuntimeError("Missing required environment variable: OPENROUTER_API_KEY")

        self.model_name = model
        self.api_key = resolved_api_key
        self.base_url = base_url.rstrip("/")
        self.measure_performance = measure_performance
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.reasoning = reasoning

    def call_model(self, message: str, override_model: Optional[str] = None) -> str:
        return self.call_model_details(message, override_model)["text"]

    def call_model_details(
        self,
        message: str,
        override_model: Optional[str] = None,
    ) -> dict[str, Any]:
        start_time = time.perf_counter()
        result = self._call_model(message, override_model=override_model)
        latency = time.perf_counter() - start_time
        if self.measure_performance:
            print(f"[{self.model_name}] API call took {latency:.2f} seconds")
        return result

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_result(self, response_payload: dict[str, Any]) -> dict[str, Any]:
        choices = response_payload.get("choices")
        if not choices:
            raise ValueError(f"OpenRouter response did not include choices: {response_payload}")  # noqa: TRY003, EM102

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            text = "".join(text_parts)

        return {
            "text": text,
            "finish_reason": choice.get("finish_reason"),
            "message": message,
            "usage": response_payload.get("usage"),
        }

    def _call_model(self, message: str, override_model: Optional[str] = None) -> dict[str, Any]:
        model_to_use = override_model or self.model_name
        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {
            "model": model_to_use,
            "messages": messages,
        }
        if self.max_tokens is not None:
            payload["max_completion_tokens"] = self.max_tokens
        if self.reasoning:
            payload["reasoning"] = self.reasoning

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
            if exc.code == 402:
                raise PaymentRequiredError(
                    f"OpenRouter request failed with HTTP {exc.code}: {error_body}",
                ) from exc
            raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        return self._extract_result(response_payload)

    async def call_model_async(self, message: str, model: Optional[str] = None) -> str:
        """
        Async model call - by default runs sync version in thread pool,
        but subclasses should implement native async if available.
        Logs the latency of the API call.
        """
        return await asyncio.to_thread(self.call_model, message, model)
