# Shabana Smart Sort — Windows Folder Organizer

Production-ready, safe, rule-driven Windows desktop application built with **Python 3.11**, **PySide6 / Qt Widgets**, and **SQLite**.

Designed to intelligently organize any folder—starting with `Downloads`—without risking accidental file loss.

---

## 🌟 Key Features

1. **Safety-First Architecture**
   - **Dry-run by default**: View exactly what will happen before touching a single file.
   - **Never delete files automatically**: Sorting only moves or copies files.
   - **Atomic same-volume moves** via `os.replace`.
   - **Staged cross-volume transfers**: Safe temporary destination with SHA-256 verification before source unlink.
   - **Honest Undo**: Reverse individual operations or entire batches without overwriting newly created files.
   - **Crash Recovery & Reconciliation**: Detects and cleans interrupted jobs and leftover temporary files upon startup.

2. **6-Screen Modern Desktop UI (Windows 11 Dark Aesthetic)**
   - 📊 **Dashboard**: High-level metrics, active rules, total organized files, recent jobs, and 1-click Quick Scan.
   - 🔍 **Scan & Filter**: Non-recursive/recursive scanning, category presets, live filename search, and file details.
   - ⚡ **Rule Manager**: Prioritized rule builder (ALL/ANY logic), add/edit/clone/delete, priority up/down reordering, and versioned JSON import/export.
   - 👁 **Preview & Organize**: Side-by-side source & destination inspection, collision resolution policies, individual file selection, dry-run mode, and guarded live execution with progress tracking.
   - 📜 **History & Recovery**: Step-by-step audit journal, 1-click batch and single-file undo, and CSV/JSON export.
   - ⚙ **Settings**: Configurable default paths, collision policies, date filter fields, SHA-256 integrity verification, and directory traversal protections.

3. **Built-in Smart Rule Presets for Downloads**
   - Priority 10: **PDF Documents** (`.pdf`) ➔ `Organized/PDFs/{year}/{month}/`
   - Priority 20: **Images & Photos** (`.jpg`, `.png`, `.webp`, `.gif`, etc.) ➔ `Organized/Images/{year}/{month}/`
   - Priority 30: **Archives & Compressed** (`.zip`, `.rar`, `.7z`, etc.) ➔ `Organized/Archives/`
   - Priority 40: **Installers & Setups** (`.exe`, `.msi`, `.iso`, etc.) ➔ `Organized/Installers/`
   - Priority 50: **Office Documents** (`.docx`, `.xlsx`, `.pptx`, `.csv`, etc.) ➔ `Organized/Office/`
   - Priority 60: **Media (Audio & Video)** (`.mp4`, `.mp3`, `.wav`, etc.) ➔ `Organized/Media/{category}/`
   - Priority 70: **Code & Developer Files** (`.py`, `.js`, `.ts`, `.html`, etc.) ➔ `Organized/Code/`
   - Priority 100: **Unmatched** ➔ Stays safely in original location.

---

## 🏗 Architecture & Module Structure

```
shabana_smart_sort/
├── app/
│   ├── main.py                     # High-DPI Qt application bootstrap and launch
│   ├── bootstrap.py                # App directory creation, logging setup, and container initialization
│   └── dependency_container.py     # Central DI container wiring repositories, engines, workflows
├── ui/
│   ├── main_window.py              # Primary desktop window with sidebar and page switcher
│   ├── theme.py                    # Modern Windows 11 Dark Mode styling tokens
│   ├── widgets/
│   │   └── stat_card.py            # Reusable metric card widget
│   ├── dialogs/
│   │   └── rule_dialog.py          # Interactive visual rule editor dialog
│   └── pages/
│       ├── dashboard_page.py       # Metrics, quick scan, and recent jobs overview
│       ├── scan_page.py            # Folder discovery, search, and category filtering
│       ├── rules_page.py           # Priority list, rule management, and JSON exchange
│       ├── preview_page.py         # Plan review, collision detection, and dry-run execution
│       ├── history_page.py         # Operation audit journal, honest undo, and report export
│       └── settings_page.py        # Configurable paths, collision policies, and safety settings
├── domain/
│   ├── enums.py                    # File categories, operators, statuses, collision policies
│   ├── models.py                   # FileItem, ScanJob, PlannedOperation, SortJob entities
│   ├── rule_schema.py              # Pydantic schemas for Rules, Conditions, and Actions
│   └── operation_models.py         # JournalEntry audit entity
├── engines/
│   ├── discovery_engine.py         # os.scandir directory traversal with cancellation & loop protection
│   ├── metadata_engine.py          # System metadata, timestamps, and SHA-256 calculation
│   ├── rule_engine.py              # Priority-based rule evaluation with AND/OR logic & date ranges
│   ├── destination_engine.py       # Template variable expansion and directory traversal guard
│   └── duplicate_engine.py         # Tiered size and hash duplicate detection
├── services/
│   ├── safe_file_ops.py            # Atomic moves, staged cross-drive copy, and verification
│   ├── conflict_resolver.py        # Collision handling (Auto-rename (1), Skip, Overwrite)
│   ├── undo_service.py             # Honest undo with occupied destination protection
│   ├── recovery_service.py         # Interrupted job reconciliation and temp artifact cleanup
│   └── disk_space_service.py       # Available storage inspection and safety buffers
├── repositories/
│   ├── rule_repository.py          # SQLite persistence for rules and initial presets
│   ├── scan_repository.py          # Scan session persistence
│   └── operation_repository.py     # Sort jobs, planned operations, and audit journal
└── infrastructure/
    ├── database.py                 # SQLite WAL-mode connection manager & auto-migrations
    ├── logging_setup.py            # Structured console and rotating log file handlers
    ├── event_bus.py                # Typed pub/sub event bus
    ├── config_manager.py           # Versioned JSON user preferences manager
    └── worker_manager.py           # Thread-safe Qt background workers for responsive UI
```

---

## 🚀 Getting Started

### 1. Requirements
- Python 3.11+
- Windows 10 or Windows 11

### 2. Launch the Application
Run directly from the project directory:
```bash
python run.py
```
Or execute via the module:
```bash
python -m shabana_smart_sort.app.main
```

### 3. Run the Automated Test Suite
Run the 21 comprehensive test suites verifying safety, rules, undo, and integration:
```bash
python -m pytest tests
```

---

## 🔒 Safety Verification Contract
Every file movement adheres to a strict 9-step pipeline:
1. **Discover**: Extract full metadata without modifying the filesystem.
2. **Evaluate**: Deterministic matching with priority and date semantics.
3. **Plan**: Destination calculated in memory.
4. **Validate**: Preconditions re-verified (source exists, permissions, disk space, collision).
5. **Preview**: Displayed side-by-side with rule explanations.
6. **Confirm**: Explicit user approval required for live executions.
7. **Execute**: Atomic `os.replace` for same volume; staged copy + hash check + unlink for cross volume.
8. **Verify**: Ensure target exists and matches expected size.
9. **Journal**: Full audit entry recorded in SQLite to support guarded reversal.
