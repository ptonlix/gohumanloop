from typing import Any
from pydantic import BaseModel, Field, field_validator, SecretStr


class GoHumanLoopConfig(BaseModel):
    """GoHumanLoop Configuration Model"""

    api_key: SecretStr = Field(..., description="GoHumanLoop API Key")
    api_base_url: str = Field(
        default="https://www.gohumanloop.com", description="GoHumanLoop API Base URL"
    )

    @field_validator("api_key")
    def validate_api_key(cls, v: SecretStr) -> Any:
        """Validate that API Key is not empty"""
        if not v:
            raise ValueError("GoHumanLoop API Key cannot be None or empty")
        return v

    @field_validator("api_base_url")
    def validate_api_base_url(cls, v: str) -> Any:
        """Validate API Base URL"""
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                "GoHumanLoop API Base URL must start with http:// or https://"
            )
        return v.rstrip("/")
