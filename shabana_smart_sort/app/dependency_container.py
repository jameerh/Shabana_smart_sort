"""Dependency injection container wiring all application layers."""
from pathlib import Path
from typing import Optional

from shabana_smart_sort.application.preview_workflow import PreviewWorkflow
from shabana_smart_sort.application.rule_workflow import RuleWorkflow
from shabana_smart_sort.application.scan_workflow import ScanWorkflow
from shabana_smart_sort.application.sort_workflow import SortWorkflow
from shabana_smart_sort.application.undo_workflow import UndoWorkflow
from shabana_smart_sort.domain.enums import VerificationLevel
from shabana_smart_sort.engines.content_engine import ContentEngine
from shabana_smart_sort.engines.discovery_engine import DiscoveryEngine
from shabana_smart_sort.engines.rule_engine import RuleEngine
from shabana_smart_sort.infrastructure.config_manager import ConfigManager
from shabana_smart_sort.infrastructure.database import DatabaseManager
from shabana_smart_sort.infrastructure.event_bus import EventBus
from shabana_smart_sort.repositories.operation_repository import OperationRepository
from shabana_smart_sort.repositories.rule_repository import RuleRepository
from shabana_smart_sort.repositories.scan_repository import ScanRepository
from shabana_smart_sort.services.recovery_service import RecoveryService
from shabana_smart_sort.services.safe_file_ops import SafeFileOperationService
from shabana_smart_sort.services.undo_service import UndoService


class DependencyContainer:
    """Central container managing singletons and service lifecycles."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = data_dir / "smart_sort.db"
        self.config_path = data_dir / "config.json"

        # Infrastructure
        self.event_bus = EventBus()
        self.config_mgr = ConfigManager(self.config_path)
        self.db_mgr = DatabaseManager(self.db_path)

        # Repositories
        self.rule_repo = RuleRepository(self.db_mgr)
        self.scan_repo = ScanRepository(self.db_mgr)
        self.op_repo = OperationRepository(self.db_mgr)

        # Engines
        verify_sha = self.config_mgr.get("verify_sha256", False)
        follow_links = self.config_mgr.get("follow_symlinks", False)
        self.discovery_engine = DiscoveryEngine(follow_symlinks=follow_links)
        self.content_engine = ContentEngine(self.db_mgr)
        self.rule_engine = RuleEngine(self.rule_repo.get_all(enabled_only=True))

        # Services
        ver_level = VerificationLevel.SHA256_HASH if verify_sha else VerificationLevel.SIZE_ONLY
        self.safe_ops = SafeFileOperationService(verification_level=ver_level)
        self.undo_service = UndoService(self.op_repo, self.safe_ops)
        self.recovery_service = RecoveryService(self.op_repo)

        # Workflows
        self.scan_workflow = ScanWorkflow(self.scan_repo, self.discovery_engine)
        self.preview_workflow = PreviewWorkflow(self.rule_engine, content_engine=self.content_engine)
        self.sort_workflow = SortWorkflow(self.op_repo, self.safe_ops)
        self.rule_workflow = RuleWorkflow(self.rule_repo, event_bus=self.event_bus)
        self.undo_workflow = UndoWorkflow(self.op_repo, self.undo_service)
