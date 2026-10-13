"""Safe file operation service guaranteeing data safety, verification, and auditability."""
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Optional
import logging

from shabana_smart_sort.domain.enums import (
    ActionType,
    OperationStatus,
    VerificationLevel,
)
from shabana_smart_sort.domain.models import PlannedOperation
from shabana_smart_sort.domain.operation_models import JournalEntry
from shabana_smart_sort.engines.metadata_engine import MetadataEngine

logger = logging.getLogger("ShabanaSmartSort.SafeFileOps")


class FileOperationError(Exception):
    """Raised when a safe file operation fails validation or execution."""
    pass


class SafeFileOperationService:
    """
    Executes file moves and copies with atomic same-volume operations,
    staged cross-volume transfers, verification, and journal recording.
    """

    def __init__(self, verification_level: VerificationLevel = VerificationLevel.SIZE_ONLY):
        self.verification_level = verification_level

    @staticmethod
    def is_same_volume(source: Path, destination: Path) -> bool:
        """Determines if source and destination share the same drive volume."""
        try:
            src_drive = os.path.splitdrive(str(source.resolve()))[0].lower()
            dst_drive = os.path.splitdrive(str(destination.resolve()))[0].lower()
            return src_drive == dst_drive and bool(src_drive)
        except Exception:
            return False

    def validate_preconditions(self, op: PlannedOperation) -> Tuple[bool, Optional[str]]:
        """Revalidates source and destination immediately prior to execution."""
        src = Path(op.source_path)
        dst = Path(op.destination_path)

        # 1. Check source existence
        if not src.exists():
            return False, f"Source file no longer exists at: {src}"

        if not src.is_file():
            return False, f"Source is not a regular file: {src}"

        # 2. Prevent moving file into itself or its descendant
        try:
            if src.resolve() == dst.resolve():
                return False, "Source and destination are identical file paths"
            if dst.resolve().is_relative_to(src.resolve()):
                return False, "Destination is located inside source path"
        except (ValueError, AttributeError):
            pass

        # 3. Check source read accessibility
        try:
            with open(src, "rb") as f:
                f.read(1)
        except (PermissionError, OSError) as e:
            return False, f"Source file cannot be read (possibly locked or inaccessible): {e}"

        # If it's a MOVE operation, verify file is not locked exclusively by another program
        if op.action == ActionType.MOVE:
            try:
                with open(src, "r+b"):
                    pass
            except PermissionError:
                return False, f"File '{src.name}' is currently in use or open in another program (e.g. PDF reader, Word, browser). Please close it first."
            except OSError:
                pass

        # 4. Check destination parent directory writeability
        dst_parent = dst.parent
        try:
            dst_parent.mkdir(parents=True, exist_ok=True)
            # Test write access with a dummy probe file
            probe_path = dst_parent / f".probe_{uuid.uuid4().hex}.tmp"
            with open(probe_path, "w") as f:
                f.write("test")
            probe_path.unlink()
        except (PermissionError, OSError) as e:
            return False, f"Destination directory is not writeable: {e}"

        return True, None

    def execute_operation(self, op: PlannedOperation) -> JournalEntry:
        """
        Executes a planned operation through the guarded pipeline.
        Returns the finalized JournalEntry recording the outcome.
        """
        src = Path(op.source_path)
        dst = Path(op.destination_path)
        same_volume = self.is_same_volume(src, dst)
        op.is_cross_volume = not same_volume

        journal = JournalEntry(
            id=str(uuid.uuid4()),
            operation_id=op.id,
            sort_job_id=op.sort_job_id,
            source_path=str(src),
            destination_path=str(dst),
            action=op.action,
            status=OperationStatus.RUNNING,
            file_size=op.file_size,
            is_cross_volume=op.is_cross_volume,
            created_at=datetime.now(timezone.utc),
        )

        # Step 1: Precondition check
        valid, err_msg = self.validate_preconditions(op)
        if not valid:
            journal.mark_failed(err_msg or "Precondition validation failed")
            return journal

        # Step 2: Checksum calculation if required
        expected_size = src.stat().st_size
        journal.file_size = expected_size
        sha_before = None
        if self.verification_level == VerificationLevel.SHA256_HASH:
            sha_before = MetadataEngine.compute_sha256(src)
            journal.sha256_before = sha_before

        try:
            if op.action == ActionType.COPY:
                self._execute_copy(src, dst, expected_size, sha_before, journal)
            else:
                # MOVE
                if same_volume:
                    self._execute_same_volume_move(src, dst, expected_size, sha_before, journal)
                else:
                    self._execute_cross_volume_move(src, dst, expected_size, sha_before, journal)

            journal.mark_succeeded()
            return journal

        except Exception as e:
            err = f"Execution error: {str(e)}"
            logger.error(err, exc_info=True)
            journal.mark_failed(err)
            return journal

    def _execute_same_volume_move(
        self,
        src: Path,
        dst: Path,
        expected_size: int,
        sha_before: Optional[str],
        journal: JournalEntry,
    ) -> None:
        """Atomic same-volume relocation using os.replace."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)

        # Verification
        if not dst.exists():
            raise FileOperationError("Destination file does not exist after atomic move")
        actual_size = dst.stat().st_size
        if actual_size != expected_size:
            raise FileOperationError(f"Size mismatch: expected {expected_size}, got {actual_size}")

        if sha_before:
            sha_after = MetadataEngine.compute_sha256(dst)
            journal.sha256_after = sha_after
            if sha_after != sha_before:
                raise FileOperationError("SHA256 checksum mismatch after atomic move")

    def _execute_cross_volume_move(
        self,
        src: Path,
        dst: Path,
        expected_size: int,
        sha_before: Optional[str],
        journal: JournalEntry,
    ) -> None:
        """Multi-stage verified cross-volume move."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        temp_name = f".smart_sort_temp_{uuid.uuid4().hex}_{dst.name}"
        temp_path = dst.parent / temp_name
        journal.temp_path = str(temp_path)

        try:
            # 1. Copy to temp
            with open(src, "rb") as fsrc, open(temp_path, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst, length=1024 * 1024)
                fdst.flush()
                os.fsync(fdst.fileno())

            # 2. Copy metadata/permissions
            shutil.copystat(src, temp_path)

            # 3. Verify copied file
            if not temp_path.exists():
                raise FileOperationError("Staged temp file was not created successfully")
            temp_size = temp_path.stat().st_size
            if temp_size != expected_size:
                raise FileOperationError(f"Staged file size mismatch: {temp_size} vs {expected_size}")

            if sha_before:
                temp_sha = MetadataEngine.compute_sha256(temp_path)
                if temp_sha != sha_before:
                    raise FileOperationError("Staged file SHA256 checksum mismatch")
                journal.sha256_after = temp_sha

            # 4. Atomically rename temp file to final destination
            os.replace(temp_path, dst)
            journal.temp_path = None

            # 5. Revalidate source before removing
            if not src.exists():
                raise FileOperationError("Source file disappeared before final unlink")

            # 6. Remove source
            try:
                os.unlink(src)
            except Exception as unlink_err:
                # If we cannot remove the source (e.g. WinError 32: file open in Acrobat/Browser),
                # remove the destination file so no ghost copy or duplicate remains!
                if dst.exists():
                    try:
                        dst.unlink()
                    except Exception:
                        pass
                raise FileOperationError(
                    f"File '{src.name}' is currently in use or locked by another program (WinError 32). "
                    "Please close any application viewing it and retry."
                ) from unlink_err

        except Exception as e:
            # Cleanup temp file on failure, preserve source!
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise e

    def _execute_copy(
        self,
        src: Path,
        dst: Path,
        expected_size: int,
        sha_before: Optional[str],
        journal: JournalEntry,
    ) -> None:
        """Staged copy operation preserving original source."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        temp_name = f".smart_sort_temp_{uuid.uuid4().hex}_{dst.name}"
        temp_path = dst.parent / temp_name
        journal.temp_path = str(temp_path)

        try:
            with open(src, "rb") as fsrc, open(temp_path, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst, length=1024 * 1024)
                fdst.flush()
                os.fsync(fdst.fileno())

            shutil.copystat(src, temp_path)

            if temp_path.stat().st_size != expected_size:
                raise FileOperationError("Copied file size mismatch")

            if sha_before:
                temp_sha = MetadataEngine.compute_sha256(temp_path)
                if temp_sha != sha_before:
                    raise FileOperationError("Copied file SHA256 checksum mismatch")
                journal.sha256_after = temp_sha

            os.replace(temp_path, dst)
            journal.temp_path = None

        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise e
