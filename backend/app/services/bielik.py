import logging
import os
import platform
import threading
from collections.abc import Callable
from pathlib import Path
from site import getusersitepackages
from typing import Any, Protocol

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


class BielikLlmService:
    """Generate text with a local Bielik GGUF model through llama.cpp."""

    def __init__(
        self,
        settings: Settings | None = None,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._model_factory = model_factory or create_llama_cpp_model
        self._model: LlamaModelProtocol | None = None
        self._generation_lock = threading.Lock()

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate a single assistant response from chat messages."""
        with self._generation_lock:
            model = self._get_model()
            prompt = format_chatml(messages)
            logger.info(
                "Starting Bielik generation model_path=%s prompt_chars=%s",
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
                logger.exception("Bielik generation failed.")
                raise LlmGenerationError("Bielik generation failed.") from exc

            text = _extract_text(result)
            logger.info("Bielik generation completed response_chars=%s", len(text))
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


def _extract_text(result: dict[str, Any]) -> str:
    try:
        text = str(result["choices"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmGenerationError("Bielik returned an unexpected response shape.") from exc

    for marker in ("<|im_end|>", "<|eot_id|>"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()
