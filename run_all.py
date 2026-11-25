import logging

import uvicorn

from backend.config import load_settings
from backend.database import initialize_database


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = load_settings()
    initialize_database(settings)
    logging.getLogger("anaaj_mitra").info(
        "Database initialised at %s. Hamlets: %s. Warehouses: %s.",
        settings.database_path,
        ", ".join(settings.hamlet_ids),
        ", ".join(settings.warehouse_ids),
    )
    uvicorn.run(
        "backend.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
