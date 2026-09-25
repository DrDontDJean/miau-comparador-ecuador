"""Configuración local, sin credenciales en el código."""
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    mongo_uri: str = 'mongodb://127.0.0.1:27018'
    mongo_db: str = 'frecuento_catalogo'
    port: int = 5001
    sync_hour: int = 3
    sync_minute: int = 0
    timezone: str = 'America/Guayaquil'
    page_size: int = 500
    delay: float = 1.5

    @classmethod
    def cargar(cls):
        load_dotenv(ROOT / '.env')
        c = cls(os.getenv('MONGODB_URI', cls.mongo_uri), os.getenv('MONGODB_DB', cls.mongo_db),
                int(os.getenv('WEB_PORT', 5001)), int(os.getenv('SYNC_HOUR', 3)),
                int(os.getenv('SYNC_MINUTE', 0)), os.getenv('SYNC_TIMEZONE', cls.timezone),
                int(os.getenv('API_PAGE_SIZE', 500)), float(os.getenv('API_DELAY_SECONDS', 1.5)))
        ZoneInfo(c.timezone)
        if not (0 <= c.sync_hour <= 23 and 0 <= c.sync_minute <= 59 and
                1 <= c.page_size <= 500 and 1 <= c.delay <= 60 and 1024 <= c.port <= 65535):
            raise ValueError('Configuración de horario, puerto o paginación inválida.')
        if not c.mongo_db or any(x in c.mongo_db for x in '/\\. "$*<>:|?'):
            raise ValueError('Nombre de base inválido.')
        return c
