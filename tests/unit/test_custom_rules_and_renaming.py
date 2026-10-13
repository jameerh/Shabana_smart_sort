"""Tests for Satbara land records, Farmer ID 27_ series, WhatsApp images, and sequential renaming."""
from pathlib import Path
from datetime import datetime

from shabana_smart_sort.domain.enums import FileCategory, CollisionPolicy
from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.engines.metadata_engine import MetadataEngine


def test_satbara_and_farmer_id_and_whatsapp_rules(container, temp_dir):
    # Retrieve all rules
    rules = container.rule_workflow.get_all_rules(enabled_only=True)
    rule_names = [r.name for r in rules]

    assert "Satbara Land Records (7/12)" in rule_names
    assert "Farmer IDs (27_ Series)" in rule_names
    assert "WhatsApp Images & Photos" in rule_names

    satbara_rule = next(r for r in rules if r.name == "Satbara Land Records (7/12)")
    farmer_rule = next(r for r in rules if r.name == "Farmer IDs (27_ Series)")
    whatsapp_rule = next(r for r in rules if r.name == "WhatsApp Images & Photos")

    now = datetime(2026, 10, 15)

    # 1. Test Satbara Land Record files (both English and Marathi Devanagari prefix)
    satbara_items = [
        FileItem(
            path=Path("C:/Downloads/satbara_590_2.pdf"),
            name="satbara_590_2.pdf",
            stem="satbara_590_2",
            extension=".pdf",
            size_bytes=2048,
            category=FileCategory.DOCUMENT,
            created_at=now,
            modified_at=now,
            accessed_at=now,
        ),
        FileItem(
            path=Path("C:/Downloads/देवनाळ_75#1_Satbara.pdf"),
            name="देवनाळ_75#1_Satbara.pdf",
            stem="देवनाळ_75#1_Satbara",
            extension=".pdf",
            size_bytes=4096,
            category=FileCategory.DOCUMENT,
            created_at=now,
            modified_at=now,
            accessed_at=now,
        ),
    ]

    for item in satbara_items:
        match_res = container.rule_engine.evaluate_file(item)
        assert match_res.is_matched is True
        assert match_res.rule.name == "Satbara Land Records (7/12)"

    # 2. Test Farmer ID (27_ series)
    farmer_item = FileItem(
        path=Path("C:/Downloads/27_480_4286_567330_008189.pdf"),
        name="27_480_4286_567330_008189.pdf",
        stem="27_480_4286_567330_008189",
        extension=".pdf",
        size_bytes=1024,
        category=FileCategory.DOCUMENT,
        created_at=now,
        modified_at=now,
        accessed_at=now,
    )
    farmer_match = container.rule_engine.evaluate_file(farmer_item)
    assert farmer_match.is_matched is True
    assert farmer_match.rule.name == "Farmer IDs (27_ Series)"

    # 3. Test WhatsApp Images
    whatsapp_item = FileItem(
        path=Path("C:/Downloads/WhatsApp Image 2026-07-19 at 12.55.59 (1).jpeg"),
        name="WhatsApp Image 2026-07-19 at 12.55.59 (1).jpeg",
        stem="WhatsApp Image 2026-07-19 at 12.55.59 (1)",
        extension=".jpeg",
        size_bytes=30000,
        category=FileCategory.IMAGE,
        created_at=now,
        modified_at=now,
        accessed_at=now,
    )
    wa_match = container.rule_engine.evaluate_file(whatsapp_item)
    assert wa_match.is_matched is True
    assert wa_match.rule.name == "WhatsApp Images & Photos"


def test_sequential_batch_renaming(container, temp_dir):
    now = datetime(2026, 10, 15)
    target_root = temp_dir / "Organized"

    # Create 3 WhatsApp items
    items = [
        FileItem(
            path=Path(f"C:/Downloads/WhatsApp Image {i}.jpeg"),
            name=f"WhatsApp Image {i}.jpeg",
            stem=f"WhatsApp Image {i}",
            extension=".jpeg",
            size_bytes=1000 + i,
            category=FileCategory.IMAGE,
            created_at=now,
            modified_at=now,
            accessed_at=now,
        )
        for i in [3, 1, 2]
    ]

    report = container.preview_workflow.generate_preview(
        files=items,
        rules=container.rule_workflow.get_all_rules(enabled_only=True),
        target_root=target_root,
    )

    ops = report.operations
    assert len(ops) == 3

    # Apply sequential rename with prefix 'xyz' starting from 1
    count = container.preview_workflow.apply_sequential_rename(
        operations=ops,
        prefix="xyz",
        start_counter=1,
        selected_only=False,
    )
    assert count == 3

    # Should be named xyz_1.jpeg, xyz_2.jpeg, xyz_3.jpeg
    dest_names = [Path(op.destination_path).name for op in ops]
    assert "xyz_1.jpeg" in dest_names
    assert "xyz_2.jpeg" in dest_names
    assert "xyz_3.jpeg" in dest_names

    # Test revert to original names
    container.preview_workflow.reset_renames(ops)
    reverted_names = [Path(op.destination_path).name for op in ops]
    assert "WhatsApp Image 1.jpeg" in reverted_names
    assert "WhatsApp Image 2.jpeg" in reverted_names
    assert "WhatsApp Image 3.jpeg" in reverted_names


def test_custom_output_folder_override(container, temp_dir):
    now = datetime(2026, 10, 15)
    item = FileItem(
        path=Path("C:/Downloads/satbara_590_2.pdf"),
        name="satbara_590_2.pdf",
        stem="satbara_590_2",
        extension=".pdf",
        size_bytes=2048,
        category=FileCategory.DOCUMENT,
        created_at=now,
        modified_at=now,
        accessed_at=now,
    )

    report = container.preview_workflow.generate_preview(
        files=[item],
        rules=container.rule_workflow.get_all_rules(enabled_only=True),
        target_root=temp_dir / "Default_Organized",
    )

    custom_dest = temp_dir / "My_Special_Satbara_Folder"
    container.preview_workflow.override_output_directory(
        operations=report.operations,
        new_dir=custom_dest,
        selected_only=False,
    )

    assert str(custom_dest) in report.operations[0].destination_path
    assert report.operations[0].destination_path.endswith("satbara_590_2.pdf")
