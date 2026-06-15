import logging
import threading
import json
import subprocess
import time
from collections.abc import Callable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import Settings, get_settings
from app.models.rag import ConversationMessage
from app.services.exceptions import LlmGenerationError

logger = logging.getLogger(__name__)
TRANSIENT_HTTP_STATUS_CODES = {429, 502, 503, 504}
OLLAMA_HTTP_MAX_ATTEMPTS = 3
OLLAMA_HTTP_RETRY_DELAYS_SECONDS = (2.0, 5.0)


JsonPost = Callable[[str, dict[str, Any], float, dict[str, str] | None], dict[str, Any]]


class BielikProviderProtocol(Protocol):
    """Protocol for Bielik text generation providers."""

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate one assistant response."""


class BielikLlmService:
    """Generate text with the configured Bielik provider."""

    def __init__(
        self,
        settings: Settings | None = None,
        ollama_post: JsonPost | None = None,
        provider: BielikProviderProtocol | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._provider = provider or create_bielik_provider(
            settings=self.settings,
            ollama_post=ollama_post,
        )

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate a single assistant response from chat messages."""
        return self._provider.generate(messages)


def create_bielik_provider(
    settings: Settings,
    ollama_post: JsonPost | None = None,
) -> BielikProviderProtocol:
    """Create the explicitly configured Bielik generation provider."""
    if settings.llm_provider == "ollama-http":
        return OllamaHttpBielikProvider(
            settings=settings,
            post_json=ollama_post or post_json,
        )

    raise LlmGenerationError(f"Unsupported LLM provider: {settings.llm_provider}")


class OllamaHttpBielikProvider:
    """Generate text with a Bielik model served by an Ollama-compatible HTTP API."""

    def __init__(self, settings: Settings, post_json: JsonPost) -> None:
        self.settings = settings
        self._post_json = post_json
        self._generation_lock = threading.Lock()

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate a single assistant response through Ollama HTTP."""
        with self._generation_lock:
            payload = {
                "model": self.settings.ollama_model,
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
                "stream": False,
                "options": {
                    "temperature": self.settings.llm_temperature,
                    "num_predict": self.settings.llm_max_new_tokens,
                },
            }
            url = _join_url(self.settings.ollama_base_url, "/api/chat")
            headers = self._auth_headers()
            prompt_chars = sum(len(message.content) for message in messages)
            logger.info(
                "Starting Bielik generation provider=ollama-http base_url=%s model=%s "
                "prompt_chars=%s",
                self.settings.ollama_base_url,
                self.settings.ollama_model,
                prompt_chars,
            )

            try:
                response = self._post_json(
                    url,
                    payload,
                    self.settings.ollama_timeout_seconds,
                    headers,
                )
            except LlmGenerationError:
                raise
            except Exception as exc:
                logger.exception(
                    "Bielik Ollama generation failed base_url=%s model=%s",
                    self.settings.ollama_base_url,
                    self.settings.ollama_model,
                )
                raise LlmGenerationError("Bielik Ollama generation failed.") from exc

            text = _extract_ollama_text(response)
            logger.info(
                "Bielik generation completed provider=ollama-http model=%s response_chars=%s",
                self.settings.ollama_model,
                len(text),
            )
            return text

    def _auth_headers(self) -> dict[str, str] | None:
        if self.settings.ollama_auth_mode == "none":
            return None
        if self.settings.ollama_auth_mode == "google-id-token":
            token = fetch_google_id_token(self.settings.ollama_base_url)
            return {"Authorization": f"Bearer {token}"}
        raise LlmGenerationError(f"Unsupported Ollama auth mode: {self.settings.ollama_auth_mode}")


def fetch_google_id_token(audience: str) -> str:
    """Fetch a Google identity token for private Cloud Run service-to-service calls."""
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token
    except ImportError as exc:
        raise LlmGenerationError(
            "google-auth is required when OLLAMA_AUTH_MODE=google-id-token."
        ) from exc

    try:
        auth_request = google.auth.transport.requests.Request()
        return str(google.oauth2.id_token.fetch_id_token(auth_request, audience))
    except Exception as exc:
        logger.warning(
            "Google metadata token fetch failed audience=%s error=%s; trying gcloud fallback.",
            audience,
            exc,
        )

    try:
        completed = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        raise LlmGenerationError("Could not fetch Google identity token.") from exc

    token = completed.stdout.strip()
    if not token:
        raise LlmGenerationError("Google identity token command returned an empty token.")
    return token


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """POST JSON to an HTTP endpoint and return the decoded JSON object."""
    body = _post_json_with_retries(url, payload, timeout_seconds, headers)

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.error("Ollama returned invalid JSON body=%s", body[:500])
        raise LlmGenerationError("Ollama returned invalid JSON.") from exc

    if not isinstance(decoded, dict):
        raise LlmGenerationError("Ollama returned an unexpected JSON root.")
    return decoded


def _post_json_with_retries(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    headers: dict[str, str] | None,
) -> str:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    last_error: Exception | None = None
    for attempt in range(1, OLLAMA_HTTP_MAX_ATTEMPTS + 1):
        request = Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = exc
            logger.error(
                "Ollama HTTP error status=%s attempt=%s/%s body=%s",
                exc.code,
                attempt,
                OLLAMA_HTTP_MAX_ATTEMPTS,
                detail[:500],
            )
            if exc.code not in TRANSIENT_HTTP_STATUS_CODES or attempt == OLLAMA_HTTP_MAX_ATTEMPTS:
                raise LlmGenerationError(
                    f"Ollama HTTP request failed with status {exc.code}."
                ) from exc
        except URLError as exc:
            last_error = exc
            logger.error(
                "Ollama HTTP connection failed url=%s attempt=%s/%s reason=%s",
                url,
                attempt,
                OLLAMA_HTTP_MAX_ATTEMPTS,
                exc.reason,
            )
            if attempt == OLLAMA_HTTP_MAX_ATTEMPTS:
                raise LlmGenerationError("Could not connect to Ollama HTTP server.") from exc
        except TimeoutError as exc:
            last_error = exc
            logger.error(
                "Ollama HTTP request timed out url=%s timeout=%s attempt=%s/%s",
                url,
                timeout_seconds,
                attempt,
                OLLAMA_HTTP_MAX_ATTEMPTS,
            )
            if attempt == OLLAMA_HTTP_MAX_ATTEMPTS:
                raise LlmGenerationError("Ollama HTTP request timed out.") from exc

        _sleep_before_retry(attempt, url)

    raise LlmGenerationError("Ollama HTTP request failed after retries.") from last_error


def _sleep_before_retry(attempt: int, url: str) -> None:
    delay = OLLAMA_HTTP_RETRY_DELAYS_SECONDS[min(attempt - 1, len(OLLAMA_HTTP_RETRY_DELAYS_SECONDS) - 1)]
    logger.info("Retrying Ollama HTTP request after %.1fs url=%s", delay, url)
    time.sleep(delay)


def _extract_ollama_text(result: dict[str, Any]) -> str:
    try:
        message = result["message"]
        if not isinstance(message, dict):
            raise TypeError
        text = message["content"]
        if not isinstance(text, str):
            raise TypeError
    except (KeyError, TypeError) as exc:
        logger.error("Ollama returned unexpected response shape: %s", result)
        raise LlmGenerationError("Ollama returned an unexpected response shape.") from exc

    return _strip_stop_markers(text.strip())


def _strip_stop_markers(text: str) -> str:
    for marker in ("<|im_end|>", "<|eot_id|>"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
