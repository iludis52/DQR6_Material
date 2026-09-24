from __future__ import annotations

import json
import re
import time
from typing import Protocol, Any

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - only relevant before project dependencies are installed
    OpenAI = None
from pydantic import ValidationError

from .lekt_config import LMStudioConfig
from .lekt_schema import AnalysisResponse, EditProposal, InvalidEdit


_DENKEN = re.compile(r"<think>.*?</think>", re.S)
_ZAUN = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def inline_refs(schema: dict) -> dict:
    """`$ref`/`$defs` auflösen. Nicht jeder Anbieter wertet Verweise im
    Strict-Schema aus; das aufgelöste Schema ist gleichbedeutend."""
    defs = schema.get("$defs", {})

    def aufloesen(knoten):
        if isinstance(knoten, dict):
            if "$ref" in knoten and knoten["$ref"].startswith("#/$defs/"):
                return aufloesen(defs[knoten["$ref"].rsplit("/", 1)[-1]])
            return {k: aufloesen(v) for k, v in knoten.items() if k != "$defs"}
        if isinstance(knoten, list):
            return [aufloesen(x) for x in knoten]
        return knoten

    return aufloesen(schema)


def json_inhalt(content: str) -> str:
    """Denkspuren und Markdown-Zäune entfernen, falls ein Modell sie trotz
    Structured Output mitschickt."""
    text = _DENKEN.sub("", content).strip()
    zaun = _ZAUN.match(text)
    return zaun.group(1) if zaun else text


class LMStudioError(RuntimeError):
    pass


class ModelUnavailableError(LMStudioError):
    pass


class LLMClient(Protocol):
    def preflight(self) -> None: ...
    def analyze(self, messages: list[dict[str, str]]) -> AnalysisResponse: ...



def _is_retriable_engine_error(exc: Exception) -> bool:
    """Classify transient LM Studio inference-engine failures.

    LM Studio can surface model/worker crashes through the OpenAI-compatible
    endpoint as HTTP 400 responses. These are transport/engine failures rather
    than malformed user requests, so retrying the exact uncommitted chunk is safe.
    """
    text = str(exc).lower()
    needles = (
        "engine protocol predict request failed",
        "channel error",
        "model has crashed",
        "model has unloaded or crashed",
        "fetch failed",
    )
    return any(n in text for n in needles)


class LMStudioOpenAIClient:
    def __init__(self, config: LMStudioConfig, *, client: Any | None = None, retry_count: int = 0):
        self.config = config
        self.retry_count = retry_count
        if client is not None:
            self.client = client
        else:
            if OpenAI is None:
                raise LMStudioError("The openai Python package is required for the real LM Studio adapter")
            key = config.api_key.get_secret_value() if config.api_key else "lm-studio"
            self.client = OpenAI(base_url=config.base_url, api_key=key, timeout=config.timeout)
        self.extra_body = dict(config.extra_body)

    def preflight(self) -> None:
        try:
            models = self.client.models.list()
        except Exception as exc:
            raise LMStudioError(f"LM Studio endpoint not reachable: {exc}") from exc
        ids = [m.id for m in getattr(models, "data", [])]
        if not ids:
            raise ModelUnavailableError("LM Studio returned no models")
        if self.config.model not in ids:
            raise ModelUnavailableError(
                f"Configured model {self.config.model!r} not available at {self.config.base_url}. "
                f"Available: {ids[:25]}{' …' if len(ids) > 25 else ''}"
            )

    def analyze(self, messages: list[dict[str, str]]) -> AnalysisResponse:
        schema = inline_refs(AnalysisResponse.model_json_schema())
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "markdown_lektorat_response",
                "strict": True,
                "schema": schema,
            },
        }
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_output_tokens,
                    response_format=response_format,
                    extra_body=self.extra_body or None,
                )
                choice = response.choices[0]
                finish_reason = getattr(choice, "finish_reason", None)
                content = choice.message.content
                if finish_reason == "length":
                    head = (content or "")[:240].replace("\n", "\\n")
                    tail = (content or "")[-240:].replace("\n", "\\n")
                    raise LMStudioError(
                        "LM Studio truncated the structured response at max_output_tokens. "
                        "The current chunk remains uncommitted. This usually indicates either "
                        "too much requested output or a repetition loop in constrained decoding. "
                        f"Raw response start={head!r}; end={tail!r}"
                    )
                if not content:
                    raise LMStudioError("LM Studio returned an empty response")
                try:
                    data = json.loads(json_inhalt(content))
                    if not isinstance(data, dict) or set(data) != {"edits"} or not isinstance(data.get("edits"), list):
                        raise LMStudioError(
                            "LM Studio returned a JSON envelope that violates the response protocol. "
                            "Expected exactly {\"edits\": [...]}. The current chunk was not committed."
                        )

                    valid_edits = []
                    invalid_edits = []
                    for index, raw_edit in enumerate(data["edits"]):
                        if not isinstance(raw_edit, dict):
                            invalid_edits.append(InvalidEdit(index, {"value": raw_edit}, "edit must be a JSON object"))
                            continue
                        try:
                            valid_edits.append(EditProposal.model_validate(raw_edit))
                        except ValidationError as exc:
                            first = exc.errors()[0] if exc.errors() else {}
                            loc = ".".join(str(x) for x in first.get("loc", ()))
                            msg = first.get("msg", str(exc))
                            detail = f"{loc}: {msg}" if loc else str(msg)
                            invalid_edits.append(InvalidEdit(index, raw_edit, detail))

                    result = AnalysisResponse(edits=valid_edits)
                    result._invalid_edits = invalid_edits
                    return result
                except json.JSONDecodeError as exc:
                    # A malformed/truncated structured answer is expensive to regenerate locally.
                    # Do not auto-retry it: checkpoint/resume lets the user retry this exact chunk.
                    raise LMStudioError(
                        f"LM Studio returned invalid/truncated JSON ({exc}). "
                        "The current chunk was not committed and can be resumed safely."
                    ) from exc
                except ValidationError as exc:
                    raise LMStudioError(
                        f"LM Studio returned JSON that violates the response schema ({exc}). "
                        "The current chunk was not committed and can be resumed safely."
                    ) from exc
            except LMStudioError:
                # Structured-output failures are deterministic enough that automatic repetition
                # can waste many minutes on a local model. Fail fast and resume explicitly.
                raise
            except Exception as exc:
                # Retry transport/server failures and LM Studio engine/channel crashes.
                # Schema/JSON errors above still fail fast and are never retried.
                last_error = exc
                if (exc.__class__.__name__ == "BadRequestError" and self.extra_body
                        and "reason" in str(exc).lower()):
                    # Modell kennt den Reasoning-Schalter nicht: ohne ihn erneut.
                    self.extra_body = {}
                    continue
                if not _is_retriable_engine_error(exc) and exc.__class__.__name__ == "BadRequestError":
                    # A genuine HTTP 400 is normally a caller/configuration error.
                    # LM Studio's transient engine failures are the explicit exception.
                    raise LMStudioError(f"LM Studio rejected the request: {exc}") from exc
                if attempt >= self.retry_count:
                    break
                time.sleep(min(30, 2 ** (attempt + 1)))     # 429/Netz: kurz warten
        raise LMStudioError(f"LLM transport failed after retries: {last_error}") from last_error
