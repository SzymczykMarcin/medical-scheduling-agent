from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_DURATIONS = (30, 60, 90, 120)


class MedicalRule(BaseModel):
    """One validated clinic scheduling rule prepared for RAG ingestion."""

    model_config = ConfigDict(extra="forbid")

    procedure_name: str = Field(min_length=2)
    specialty: str = Field(min_length=2)
    duration_minutes: int
    duration_rationale: str = Field(min_length=2)
    patient_preparation: str | None = None
    contraindications_for_auto_booking: list[str] = Field(default_factory=list)
    source: str | None = None

    @field_validator("procedure_name", "specialty", "duration_rationale", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> str:
        """Normalize required text fields."""
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("patient_preparation", "source", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> str | None:
        """Normalize optional text fields."""
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("duration_minutes", mode="before")
    @classmethod
    def normalize_duration(cls, value: object) -> int:
        """Normalize duration to one of the scheduler-supported values."""
        try:
            raw_duration = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("duration_minutes must be an integer number of minutes") from exc

        if raw_duration <= 0:
            raise ValueError("duration_minutes must be greater than zero")

        for allowed in ALLOWED_DURATIONS:
            if raw_duration <= allowed:
                return allowed

        raise ValueError("duration_minutes must not exceed 120 minutes")

    @field_validator("contraindications_for_auto_booking", mode="before")
    @classmethod
    def normalize_contraindications(cls, value: object) -> list[str]:
        """Normalize contraindications from list or semicolon-separated text."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(";") if item.strip()]
        raise ValueError("contraindications_for_auto_booking must be a list or semicolon text")

    def to_rag_text(self) -> str:
        """Render the rule as deterministic Polish-friendly RAG text."""
        contraindications = (
            "; ".join(self.contraindications_for_auto_booking)
            if self.contraindications_for_auto_booking
            else "brak"
        )
        preparation = self.patient_preparation or "brak szczególnych przygotowań"
        source = self.source or "clinic scheduling rule"
        return "\n".join(
            [
                f"Procedura: {self.procedure_name}",
                f"Specjalizacja: {self.specialty}",
                f"Czas trwania: {self.duration_minutes} minut",
                f"Uzasadnienie czasu: {self.duration_rationale}",
                f"Przygotowanie pacjenta: {preparation}",
                f"Przeciwwskazania do automatycznej rezerwacji: {contraindications}",
                f"Źródło: {source}",
            ]
        )
