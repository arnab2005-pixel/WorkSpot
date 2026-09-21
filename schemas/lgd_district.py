"""
Local Government Directory (LGD) district data models for PM-AJAY Voice Assistant.

Standardizes spoken regional district/block names and colloquial variations into official LGD codes.
"""

from pydantic import BaseModel, ConfigDict, Field


class LgdDistrictRecord(BaseModel):
    """LGD District master reference document."""

    model_config = ConfigDict(populate_by_name=True)

    district_code: str = Field(
        ..., description="LGD district identifier (e.g. 'UP_VARANASI')"
    )
    state_code: str = Field(..., description="State code (e.g. 'UP', 'BR')")
    state_name: str = Field(..., description="State name (e.g. 'Uttar Pradesh')")
    district_name_en: str = Field(
        ..., description="Official English name (e.g. 'Varanasi')"
    )
    district_name_hi: str = Field(
        ..., description="Official Hindi name (e.g. 'वाराणसी')"
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Phonetic variations & nicknames e.g. ['बनारस', 'काशी']",
    )
    blocks: list[str] = Field(
        default_factory=list, description="List of administrative blocks / tehsils"
    )
    primary_dialects: list[str] = Field(
        default_factory=list, description="Spoken dialects e.g. ['bhojpuri', 'awa']"
    )
    dpiu_office_contact: dict[str, str] | None = Field(
        default=None, description="Local DPIU contact details"
    )
