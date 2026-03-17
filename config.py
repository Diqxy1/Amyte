from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Discord
    TOKEN: str
    PREFIX: str = "!"

    # Valorant API
    VAL_API_BASE: str = "https://valorant-api.com/v1"
    VP_CURRENCY_ID: str = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"

    # Regiões suportadas e seus endpoints PD
    REGIONS: dict = {
        "na":    "https://pd.na.a.pvp.net",
        "eu":    "https://pd.eu.a.pvp.net",
        "ap":    "https://pd.ap.a.pvp.net",
        "kr":    "https://pd.kr.a.pvp.net",
        "br":    "https://pd.na.a.pvp.net",   # BR usa servidor NA
        "latam": "https://pd.na.a.pvp.net",
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()