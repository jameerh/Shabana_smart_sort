"""Bootstrap loader initializing directories, logging, and dependency container."""
import os
from pathlib import Path
import logging

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.infrastructure.logging_setup import setup_logging


def get_app_data_dir() -> Path:
    """Returns application data storage path under %APPDATA%/ShabanaSmartSort or ~/.shabana_smart_sort."""
    app_data = os.getenv("APPDATA")
    if app_data:
        data_dir = Path(app_data) / "ShabanaSmartSort"
    else:
        data_dir = Path.home() / ".shabana_smart_sort"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def bootstrap_application() -> DependencyContainer:
    """Bootstraps application logging, database, and dependency container."""
    data_dir = get_app_data_dir()
    log_dir = data_dir / "logs"

    logger = setup_logging(log_dir=log_dir)
    logger.info("Initializing Shabana Smart Sort system...")

    container = DependencyContainer(data_dir)

    # Run crash recovery reconciliation on startup
    reconciled = container.recovery_service.reconcile_interrupted_jobs()
    if reconciled:
        logger.warning(f"Reconciled jobs on startup: {reconciled}")

    logger.info("Bootstrap complete.")
    return container
