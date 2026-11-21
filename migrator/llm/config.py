from collections.abc import Mapping
from dataclasses import dataclass, field
import math
import os
from typing import Literal
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ModelConfig:
    model: str
    provider: Literal["openai", "openai_compatible"] = "openai"
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    timeout_seconds: float = 60

    def __post_init__(self) -> None:
        if self.provider not in ("openai", "openai_compatible"):
            raise ValueError("Unsupported model provider")
        if not isinstance(self.model, str) or not self.model or self.model != self.model.strip():
            raise ValueError("Model ID must be nonblank without surrounding whitespace")
        if self.api_key is not None:
            if not isinstance(self.api_key, str) or not self.api_key or self.api_key != self.api_key.strip():
                raise ValueError("API key must be nonblank text without surrounding whitespace")
        if self.provider != "openai_compatible":
            if not self.api_key:
                raise ValueError("The selected hosted provider requires its API key")
            if self.base_url is not None:
                raise ValueError("Custom endpoints require provider=openai_compatible")
        else:
            try:
                url = urlsplit(self.base_url or "")
                valid = (
                    url.scheme in ("http", "https") and bool(url.hostname)
                    and url.username is None and url.password is None
                    and "?" not in self.base_url and "#" not in self.base_url
                    and not any(c.isspace() or ord(c) < 32 for c in self.base_url)
                )
                _ = url.port
            except (TypeError, ValueError, AttributeError):
                valid = False
            if not valid:
                raise ValueError("Compatible endpoint must be an HTTP(S) URL without credentials, query, or fragment")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0
        ):
            raise ValueError("Model timeout must be a positive finite number")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ModelConfig":
        env = os.environ if environ is None else environ
        provider = env.get("MIGRATOR_MODEL_PROVIDER", "openai").strip().lower()
        key_name = {
            "openai": "OPENAI_API_KEY",
            "openai_compatible": "MIGRATOR_MODEL_API_KEY",
        }.get(provider)
        try:
            timeout = float(env.get("MIGRATOR_MODEL_TIMEOUT_SECONDS", "60"))
        except ValueError:
            raise ValueError("Model timeout must be a positive finite number") from None
        return cls(
            provider=provider, model=env.get("MIGRATOR_MODEL", "").strip(),
            api_key=(env.get(key_name, "").strip() or None) if key_name else None,
            base_url=env.get("MIGRATOR_MODEL_BASE_URL", "").strip() or None,
            timeout_seconds=timeout,
        )
