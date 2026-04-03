import os
from dotenv import load_dotenv


load_dotenv()


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() == "true"


class Settings:
    def __init__(self) -> None:
        self.OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
        self.OPENROUTER_BASE_URL: str = os.getenv(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        )

        self.APP_ENV: str = os.getenv("APP_ENV", "dev")
        self.DISABLE_TRACING: bool = _to_bool(
            os.getenv("DISABLE_TRACING", "true"),
            default=True,
        )

        self.RESEARCH_MODEL: str = os.getenv("RESEARCH_MODEL", "gpt-4.1-mini")
        self.VALUE_TRADER_MODEL: str = os.getenv("VALUE_TRADER_MODEL", "gpt-4.1-mini")
        self.VALIDATOR_MODEL: str = os.getenv("VALIDATOR_MODEL", "gpt-4.1-mini")

        self.MACRO_TRADER_MODEL: str = os.getenv("MACRO_TRADER_MODEL", "gpt-4.1-mini")
        self.GROWTH_TRADER_MODEL: str = os.getenv("GROWTH_TRADER_MODEL", "gpt-4.1-mini")
        self.EVENT_TRADER_MODEL: str = os.getenv("EVENT_TRADER_MODEL", "gpt-4.1-mini")

        self.FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
        self.BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
        self.POLYGON_API_KEY: str = os.getenv("POLYGON_API_KEY", "")
        self.SEC_USER_AGENT: str = os.getenv(
            "SEC_USER_AGENT",
            "slimzhu invest-agent-system slimzhu@gmail.com",
        )

        self.RESEARCH_SOURCE_ENABLE_FINNHUB: bool = _to_bool(
            os.getenv("RESEARCH_SOURCE_ENABLE_FINNHUB", "true"),
            default=True,
        )
        self.RESEARCH_SOURCE_ENABLE_BRAVE: bool = _to_bool(
            os.getenv("RESEARCH_SOURCE_ENABLE_BRAVE", "true"),
            default=True,
        )
        self.RESEARCH_SOURCE_ENABLE_POLYGON: bool = _to_bool(
            os.getenv("RESEARCH_SOURCE_ENABLE_POLYGON", "true"),
            default=False,
        )
        self.RESEARCH_SOURCE_ENABLE_SEC: bool = _to_bool(
            os.getenv("RESEARCH_SOURCE_ENABLE_SEC", "true"),
            default=True,
        )
        self.RESEARCH_SOURCE_ENABLE_RESEARCH_FEED: bool = _to_bool(
            os.getenv("RESEARCH_SOURCE_ENABLE_RESEARCH_FEED", "false"),
            default=False,
        )


settings = Settings()