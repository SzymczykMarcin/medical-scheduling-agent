import logging
import os
import platform
import threading
import json
from collections.abc import Callable
from pathlib import Path
from site import getusersitepackages
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import Settings, get_settings
from app.models.rag import ConversationMessage
from app.services.exceptions import LlmGenerationError

logger = logging.getLogger(__name__)
_DLL_HANDLES: list[Any] = []


class LlamaModelProtocol(Protocol):
    """Protocol for llama-cpp compatible model instances."""

    def __call__(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Generate text from a prompt."""


ModelFactory = Callable[[Path, Settings], LlamaModelProtocol]
JsonPost = Callable[[str, dict[str, Any], float], dict[str, Any]]


class BielikProviderProtocol(Protocol):
    """Protocol for Bielik text generation providers."""

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate one assistant response."""


class BielikLlmService:
    """Generate text with the configured Bielik provider."""

    def __init__(
        self,
        settings: Settings | None = None,
        model_factory: ModelFactory | None = None,
        ollama_post: JsonPost | None = None,
        provider: BielikProviderProtocol | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._provider = provider or create_bielik_provider(
            settings=self.settings,
            model_factory=model_factory,
            ollama_post=ollama_post,
        )

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate a single assistant response from chat messages."""
        return self._provider.generate(messages)


def create_bielik_provider(
    settings: Settings,
    model_factory: ModelFactory | None = None,
    ollama_post: JsonPost | None = None,
) -> BielikProviderProtocol:
    """Create the explicitly configured Bielik generation provider."""
    if settings.llm_provider == "llama-cpp":
        return LlamaCppBielikProvider(
            settings=settings,
            model_factory=model_factory or create_llama_cpp_model,
        )
    if settings.llm_provider == "ollama-http":
        return OllamaHttpBielikProvider(
            settings=settings,
            post_json=ollama_post or post_json,
        )

    raise LlmGenerationError(f"Unsupported LLM provider: {settings.llm_provider}")


class LlamaCppBielikProvider:
    """Generate text with a local Bielik GGUF model through llama.cpp."""

    def __init__(self, settings: Settings, model_factory: ModelFactory) -> None:
        self.settings = settings
        self._model_factory = model_factory
        self._model: LlamaModelProtocol | None = None
        self._generation_lock = threading.Lock()

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate a single assistant response through llama.cpp."""
        with self._generation_lock:
            model = self._get_model()
            prompt = format_chatml(messages)
            logger.info(
                "Starting Bielik generation provider=llama-cpp model_path=%s prompt_chars=%s",
                self.settings.bielik_gguf_path,
                len(prompt),
            )

            try:
                result = model(
                    prompt,
                    max_tokens=self.settings.llm_max_new_tokens,
                    temperature=self.settings.llm_temperature,
                    stop=["<|im_end|>", "<|eot_id|>"],
                    echo=False,
                )
            except Exception as exc:
                logger.exception("Bielik llama.cpp generation failed.")
                raise LlmGenerationError("Bielik llama.cpp generation failed.") from exc

            text = _extract_llama_cpp_text(result)
            logger.info(
                "Bielik generation completed provider=llama-cpp response_chars=%s",
                len(text),
            )
            return text

    def _get_model(self) -> LlamaModelProtocol:
        if self._model is None:
            model_path = Path(self.settings.bielik_gguf_path)
            if not model_path.exists():
                raise LlmGenerationError(f"Bielik GGUF model file does not exist: {model_path}")

            logger.info(
                "Loading Bielik model path=%s n_ctx=%s n_gpu_layers=%s",
                model_path,
                self.settings.llm_context_tokens,
                self.settings.llm_gpu_layers,
            )
            self._model = self._model_factory(model_path, self.settings)
            logger.info("Bielik model loaded successfully.")

        return self._model


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
            prompt_chars = sum(len(message.content) for message in messages)
            logger.info(
                "Starting Bielik generation provider=ollama-http base_url=%s model=%s "
                "prompt_chars=%s",
                self.settings.ollama_base_url,
                self.settings.ollama_model,
                prompt_chars,
            )

            try:
                response = self._post_json(url, payload, self.settings.ollama_timeout_seconds)
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


def create_llama_cpp_model(model_path: Path, settings: Settings) -> LlamaModelProtocol:
    """Create a llama-cpp-python model instance with GPU offload."""
    if settings.llm_provider != "llama-cpp":
        raise LlmGenerationError(f"Unsupported LLM provider: {settings.llm_provider}")

    _prepare_windows_llama_dlls()

    try:
        from llama_cpp import Llama
        from llama_cpp import llama_cpp as llama_cpp_lib
    except ImportError as exc:
        raise LlmGenerationError("llama-cpp-python is not installed.") from exc

    supports_gpu_offload = bool(llama_cpp_lib.llama_supports_gpu_offload())
    gpu_layers = settings.llm_gpu_layers if supports_gpu_offload else 0
    if not supports_gpu_offload and settings.llm_gpu_layers != 0:
        logger.warning("llama.cpp runtime does not support GPU offload; using CPU layers only.")

    return Llama(
        model_path=str(model_path),
        n_ctx=settings.llm_context_tokens,
        n_threads=settings.llm_threads or max(1, min(16, os.cpu_count() or 1)),
        n_gpu_layers=gpu_layers,
        verbose=False,
    )


def post_json(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    """POST JSON to an HTTP endpoint and return the decoded JSON object."""
    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("Ollama HTTP error status=%s body=%s", exc.code, detail[:500])
        raise LlmGenerationError(f"Ollama HTTP request failed with status {exc.code}.") from exc
    except URLError as exc:
        logger.error("Ollama HTTP connection failed url=%s reason=%s", url, exc.reason)
        raise LlmGenerationError("Could not connect to Ollama HTTP server.") from exc
    except TimeoutError as exc:
        logger.error("Ollama HTTP request timed out url=%s timeout=%s", url, timeout_seconds)
        raise LlmGenerationError("Ollama HTTP request timed out.") from exc

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.error("Ollama returned invalid JSON body=%s", body[:500])
        raise LlmGenerationError("Ollama returned invalid JSON.") from exc

    if not isinstance(decoded, dict):
        raise LlmGenerationError("Ollama returned an unexpected JSON root.")
    return decoded


def _prepare_windows_llama_dlls() -> None:
    """Preload llama.cpp CUDA DLL dependencies on Windows."""
    if platform.system() != "Windows" or _DLL_HANDLES:
        return

    import ctypes

    site_packages = Path(getusersitepackages())
    llama_lib_dir = site_packages / "llama_cpp" / "lib"
    torch_lib_dir = site_packages / "torch" / "lib"

    for dll_dir in (llama_lib_dir, torch_lib_dir):
        if dll_dir.exists():
            logger.debug("Adding DLL directory for llama.cpp: %s", dll_dir)
            _DLL_HANDLES.append(os.add_dll_directory(str(dll_dir)))

    for dll_name in (
        "ggml-base.dll",
        "ggml.dll",
        "ggml-cpu.dll",
        "ggml-cuda.dll",
        "llama.dll",
    ):
        dll_path = llama_lib_dir / dll_name
        if not dll_path.exists():
            continue
        try:
            _DLL_HANDLES.append(ctypes.CDLL(str(dll_path)))
        except OSError as exc:
            logger.debug("Could not preload optional llama.cpp DLL %s: %s", dll_path, exc)


def format_chatml(messages: list[ConversationMessage]) -> str:
    """Render messages as a ChatML-style prompt accepted by Bielik GGUF builds."""
    prompt_parts = ["<s>"]
    for message in messages:
        prompt_parts.append(f"<|im_start|>{message.role}\n{message.content}<|im_end|>\n")
    prompt_parts.append("<|im_start|>assistant\n")
    return "".join(prompt_parts)


def _extract_llama_cpp_text(result: dict[str, Any]) -> str:
    try:
        text = str(result["choices"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmGenerationError("Bielik returned an unexpected response shape.") from exc

    return _strip_stop_markers(text)


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
