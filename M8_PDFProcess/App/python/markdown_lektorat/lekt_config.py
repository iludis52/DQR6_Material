from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputConfig(StrictModel):
    document_path: Path
    encoding: str = "utf-8"


class LMStudioConfig(StrictModel):
    """OpenAI-kompatibler Endpunkt: LM Studio lokal oder ein Anbieter wie DeepInfra."""
    base_url: str = "http://localhost:1234/v1"
    model: str
    timeout: float = 300.0
    temperature: float = 0.0
    max_output_tokens: int = 4096
    # Nur für entfernte Anbieter; SecretStr, damit der Schlüssel in keiner
    # Ausgabe (Notebook-Repr, Logs) im Klartext erscheint.
    api_key: SecretStr | None = None
    # Zusätzliche Felder im Request, z. B. {"reasoning_effort": "none"}.
    extra_body: dict = Field(default_factory=dict)


class ProcessingConfig(StrictModel):
    context_strategy: str = "structural"
    max_context_tokens: int = Field(default=16000, ge=4096)
    context_reserve_tokens: int = Field(default=2500, ge=512)
    text_chunk_tokens: int = Field(default=2000, ge=256)
    table_chunk_tokens: int = Field(default=2500, ge=256)
    structure_chunk_tokens: int = Field(default=2500, ge=256)
    caption_chunk_tokens: int = Field(default=2000, ge=256)
    overlap_blocks: int = Field(default=2, ge=0)
    retry_count: int = Field(default=2, ge=0)
    resume: bool = True


class ThresholdPolicy(StrictModel):
    text_high_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    text_medium_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    structural_high_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    structural_medium_threshold: float = Field(default=0.80, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_order(self) -> "ThresholdPolicy":
        if self.text_medium_threshold > self.text_high_threshold:
            raise ValueError("text_medium_threshold must be <= text_high_threshold")
        if self.structural_medium_threshold > self.structural_high_threshold:
            raise ValueError("structural_medium_threshold must be <= structural_high_threshold")
        return self


class ConfidenceConfig(StrictModel):
    default: ThresholdPolicy = Field(default_factory=ThresholdPolicy)
    by_model: dict[str, ThresholdPolicy] = Field(default_factory=dict)

    def for_model(self, model_id: str) -> ThresholdPolicy:
        return self.by_model.get(model_id, self.default)


class OutputConfig(StrictModel):
    output_dir: Path | None = None
    overwrite: bool = False
    write_intermediate_artifacts: bool = True
    write_raw_responses: bool = False


class LoggingConfig(StrictModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class AppConfig(StrictModel):
    input: InputConfig
    lm: LMStudioConfig
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def read_source_text(config: InputConfig) -> str:
    # Strict decode: UnicodeDecodeError is intentionally allowed to propagate.
    return config.document_path.read_text(encoding=config.encoding, errors="strict")


def write_utf8_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="strict")
