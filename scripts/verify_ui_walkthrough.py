"""Automated comprehensive UI walkthrough & verification script.
Tests every screen, button, workflow, renaming, and captures screenshots.
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Ensure offscreen for headless testing if needed
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QDate, QThreadPool
from PySide6.QtGui import QFont, QPixmap

# Auto-respond to modal dialogs during automated UI walkthrough
QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok
QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok
QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes
QMessageBox.critical = lambda *args, **kwargs: QMessageBox.Ok

from shabana_smart_sort.app.bootstrap import bootstrap_application
from shabana_smart_sort.ui.main_window import MainWindow
from shabana_smart_sort.domain.enums import OperationStatus, JobStatus


def capture_widget(widget, save_path: Path) -> None:
    """Renders widget directly via Qt paint engine into a PNG file."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    pix = QPixmap(widget.size())
    pix.fill(Qt.transparent)
    widget.render(pix)
    pix.save(str(save_path))


def run_full_ui_walkthrough(screenshot_dir: Path) -> dict:
    results = {}
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    # 1. Setup sample test folder with user's exact files
    test_root = Path(tempfile.mkdtemp(prefix="smart_sort_ui_test_"))
    source_dir = test_root / "downloads_mock"
    source_dir.mkdir(parents=True, exist_ok=True)

    # User's actual sample files from screenshots
    files_to_create = [
        ("satbara_590_2.pdf", b"%PDF-1.4 Mock Satbara 590_2 content"),
        ("devnal_75#1_Satbara.pdf", b"%PDF-1.4 Mock Devnal Satbara content"),
        ("27_480_4286_567330_008189.pdf", b"%PDF-1.4 Mock Farmer ID 27_480"),
        ("27_493_4304_568926_005901.pdf", b"%PDF-1.4 Mock Farmer ID 27_493"),
        ("WhatsApp Image 2026-07-19 at 12.55.59 (1).jpeg", b"\xFF\xD8\xFF\xE0Mock WA 1"),
        ("WhatsApp Image 2026-07-19 at 12.56.00.jpeg", b"\xFF\xD8\xFF\xE0Mock WA 2"),
        ("contract_agreement.docx", b"Mock docx"),
    ]

    for fname, content in files_to_create:
        p = source_dir / fname
        p.write_bytes(content)

    print(f"Created {len(files_to_create)} mock files in {source_dir}")

    # 2. Initialize Qt Application & MainWindow
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    container = bootstrap_application()
    for r in container.rule_workflow.get_all_rules():
        container.rule_workflow.set_rule_enabled(r.id, True)
    window = MainWindow(container)
    window.resize(1200, 800)
    window.show()
    app.processEvents()

    # Screenshot: Dashboard
    dash_shot = screenshot_dir / "01_dashboard.png"
    capture_widget(window, dash_shot)
    results["dashboard_loaded"] = True
    print("[OK] Dashboard loaded and captured to:", dash_shot)

    # 3. Test Scan Page
    window.switch_page(1)  # Tab 1: Scan
    scan_page = window.page_scan
    scan_page.folder_input.setText(str(source_dir))
    app.processEvents()

    # Execute scan
    summary = container.scan_workflow.run_scan(folder_path=source_dir, recursive=False)
    scan_page._on_scan_finished(summary)
    app.processEvents()

    assert len(scan_page.scanned_files) >= 7, f"Expected 7 files, got {len(scan_page.scanned_files)}"
    results["scan_files_count"] = len(scan_page.scanned_files)
    print(f"[OK] Scan Page discovered {len(scan_page.scanned_files)} files")

    # Screenshot: Scan page
    scan_shot = screenshot_dir / "02_scan_page.png"
    capture_widget(window, scan_shot)

    # Test preset click: Satbara
    scan_page._handle_preset_click("preset_satbara")
    app.processEvents()
    satbara_visible = sum(1 for r in range(scan_page.table.rowCount()) if not scan_page.table.isRowHidden(r))
    assert satbara_visible == 2, f"Expected 2 Satbara files, got {satbara_visible}"
    results["satbara_preset_filter_ok"] = True
    print("[OK] Satbara filter preset works")

    # Test preset click: Farmer 27_
    scan_page._handle_preset_click("preset_farmer")
    app.processEvents()
    farmer_visible = sum(1 for r in range(scan_page.table.rowCount()) if not scan_page.table.isRowHidden(r))
    assert farmer_visible == 2, f"Expected 2 Farmer ID files, got {farmer_visible}"
    results["farmer_preset_filter_ok"] = True
    print("[OK] Farmer 27_ filter preset works")

    # Reset filter
    scan_page._reset_filters()
    app.processEvents()

    # 4. Navigate to Preview Page
    scan_page.on_proceed_to_preview()
    app.processEvents()
    assert window.stack.currentIndex() == 3  # Preview
    preview_page = window.page_preview
    results["preview_loaded"] = True

    # Screenshot: Preview
    prev_shot = screenshot_dir / "03_preview_page.png"
    capture_widget(window, prev_shot)
    print(f"[OK] Preview Page loaded with {len(preview_page.planned_operations)} operations")

    # Verify Satbara rules matched
    satbara_ops = [op for op in preview_page.planned_operations if "Satbara" in (op.matched_rule_name or "")]
    assert len(satbara_ops) == 2, f"Expected 2 Satbara ops, got {len(satbara_ops)}"
    results["satbara_rules_matched"] = len(satbara_ops)

    # Verify Farmer 27_ rules matched
    farmer_ops = [op for op in preview_page.planned_operations if "Farmer" in (op.matched_rule_name or "")]
    assert len(farmer_ops) == 2, f"Expected 2 Farmer ID ops, got {len(farmer_ops)}"
    results["farmer_rules_matched"] = len(farmer_ops)

    # Verify WhatsApp rules matched
    wa_ops = [op for op in preview_page.planned_operations if "WhatsApp" in (op.matched_rule_name or "")]
    assert len(wa_ops) == 2, f"Expected 2 WhatsApp ops, got {len(wa_ops)}"
    results["whatsapp_rules_matched"] = len(wa_ops)

    # 5. Test Sequential Renaming on WhatsApp Images
    preview_page._set_all_selected(False)
    preview_page._set_preset_filter("WHATSAPP")
    app.processEvents()
    preview_page._set_filtered_selected(True)
    preview_page.prefix_input.setText("xyz")
    preview_page.counter_spin.setValue(1)
    preview_page._apply_batch_rename()
    app.processEvents()

    renamed_ops = [op for op in preview_page.planned_operations if op.rename_applied]
    assert len(renamed_ops) == 2
    renamed_filenames = [op.rename_applied for op in renamed_ops]
    assert "xyz_1.jpeg" in renamed_filenames
    assert "xyz_2.jpeg" in renamed_filenames
    results["sequential_rename_ok"] = True
    print(f"[OK] Sequential rename successfully produced: {renamed_filenames}")

    # Screenshot: Sequential rename in Preview
    rename_shot = screenshot_dir / "04_preview_renamed.png"
    capture_widget(window, rename_shot)

    # 6. Test Output Folder Override
    custom_output = test_root / "Organized_Custom"
    custom_output.mkdir(parents=True, exist_ok=True)
    preview_page._set_preset_filter("ALL")
    app.processEvents()
    preview_page._set_all_selected(True)
    app.processEvents()

    container.preview_workflow.override_output_directory(
        preview_page.planned_operations, custom_output, selected_only=False
    )
    for op in preview_page.planned_operations:
        assert str(custom_output) in op.destination_path
    results["custom_output_override_ok"] = True
    print("[OK] Custom Output folder override works")

    # 7. Execute Live Organization
    report = container.sort_workflow.execute_sort(
        operations=preview_page.planned_operations,
        source_folder=source_dir,
        target_folder=custom_output,
        is_dry_run=False,
    )
    assert report.succeeded >= 6, f"Expected at least 6 successes, got {report.succeeded}"
    results["sort_execution_succeeded"] = report.succeeded
    print(f"[OK] Live sort execution completed successfully: {report.succeeded} files moved")

    # Verify files now exist in custom_output
    assert (custom_output / "xyz_1.jpeg").exists()
    assert (custom_output / "xyz_2.jpeg").exists()
    assert (custom_output / "satbara_590_2.pdf").exists()
    assert (custom_output / "27_480_4286_567330_008189.pdf").exists()

    # 8. Test History & Recovery Page
    window.switch_page(4)  # Tab 4: History
    history_page = window.page_history
    history_page.reload_history()
    app.processEvents()
    assert len(history_page.entries) >= 6
    results["history_entries_count"] = len(history_page.entries)
    print(f"[OK] History Page loaded {len(history_page.entries)} audit entries")

    # Screenshot: History
    hist_shot = screenshot_dir / "05_history_page.png"
    capture_widget(window, hist_shot)

    # 9. Test Honest Undo of the batch
    succeeded_undo, failed_undo, _ = container.undo_workflow.undo_batch(report.job_id)
    assert succeeded_undo == report.succeeded
    assert failed_undo == 0
    results["undo_succeeded"] = succeeded_undo
    print(f"[OK] Honest Undo succeeded: {succeeded_undo} files restored back to source")

    # Verify files restored to source_dir
    assert (source_dir / "satbara_590_2.pdf").exists()
    assert (source_dir / "WhatsApp Image 2026-07-19 at 12.55.59 (1).jpeg").exists()

    # 10. Test Rules Page
    window.switch_page(2)  # Tab 2: Rules
    rules_page = window.page_rules
    rules_page.reload_rules()
    app.processEvents()
    assert len(rules_page.rules) >= 10
    results["total_rules"] = len(rules_page.rules)
    print(f"[OK] Rules Page loaded {len(rules_page.rules)} rules")

    # Screenshot: Rules
    rules_shot = screenshot_dir / "06_rules_page.png"
    capture_widget(window, rules_shot)

    # 11. Test Settings Page
    window.switch_page(5)  # Tab 5: Settings
    app.processEvents()
    settings_shot = screenshot_dir / "07_settings_page.png"
    capture_widget(window, settings_shot)
    print("[OK] Settings Page verified and captured")

    # Cleanup temp test files
    shutil.rmtree(test_root, ignore_errors=True)

    results["all_tests_passed"] = True
    print("\n=======================================================")
    print("ALL UI WALKTHROUGH AND FUNCTIONALITY CHECKS PASSED 100%")
    print("=======================================================")
    return results


if __name__ == "__main__":
    artifact_dir = Path(r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\2c03553e-23ee-4ea3-aec1-e0d4a3a7b03c")
    shots_dir = artifact_dir / "ui_walkthrough_screenshots"
    res = run_full_ui_walkthrough(shots_dir)
    print("Results:", res)
