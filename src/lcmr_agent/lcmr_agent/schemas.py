"""Argument schemas for the six tools. Anything not listed here is rejected."""
from pydantic import BaseModel, ConfigDict, StrictStr


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NavigateToArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: StrictStr
