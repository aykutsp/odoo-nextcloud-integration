import base64

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..wizards.nextcloud_upload_wizard import (
    detect_document_mimetype,
    detect_photo_mimetype,
)


@tagged("post_install", "-at_install")
class TestUploadWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({
            "groups_id": [
                (
                    4,
                    cls.env.ref(
                        "odoo_nextcloud_document_hub."
                        "group_nextcloud_document_uploader"
                    ).id,
                )
            ],
        })
        cls.task = cls.env["project.task"].create({"name": "Photo Test"})
        cls.project = cls.env["project.project"].create({
            "name": "Categorized Project",
        })
        cls.project_task = cls.env["project.task"].create({
            "name": "Software Task",
            "project_id": cls.project.id,
        })

    def test_photo_upload_rejects_non_image(self):
        wizard = self.env["nextcloud.upload.wizard"].create({
            "res_model": self.task._name,
            "res_id": self.task.id,
            "res_name": self.task.display_name,
            "file_data": base64.b64encode(b"not-an-image"),
            "filename": "notes.txt",
            "upload_kind": "photo",
        })

        with self.assertRaisesRegex(UserError, "JPEG"):
            wizard.action_upload()

    def test_photo_magic_detection(self):
        self.assertEqual(
            detect_photo_mimetype(b"\x89PNG\r\n\x1a\ncontent"),
            "image/png",
        )
        self.assertEqual(
            detect_photo_mimetype(b"\x00\x00\x00\x18ftypheiccontent"),
            "image/heic",
        )
        self.assertFalse(detect_photo_mimetype(b"plain text"))

    def test_document_magic_detection(self):
        self.assertEqual(detect_document_mimetype(b"%PDF-1.7"), "application/pdf")
        self.assertEqual(detect_document_mimetype(b"PK\x03\x04zip"), "application/zip")
        self.assertFalse(detect_document_mimetype(b"plain text"))

    def test_crm_and_project_categories_are_installed(self):
        Category = self.env["nextcloud.document.category"]
        self.assertEqual(
            Category.search_count([("model_name", "=", "crm.lead")]),
            7,
        )
        self.assertEqual(
            Category.search_count([
                ("model_name", "=", "project.project"),
                ("parent_id", "=", False),
            ]),
            7,
        )
        engineering = Category.search([
            ("model_name", "=", "project.project"),
            ("folder_name", "=", "02 - Mühendislik"),
            ("parent_id", "=", False),
        ], limit=1)
        self.assertTrue(engineering)
        self.assertTrue(Category.search([
            ("model_name", "=", "project.project"),
            ("folder_name", "=", "07 - Yazılım"),
            ("parent_id", "=", engineering.id),
        ], limit=1))

    def test_category_complete_name_handles_empty_new_row_values(self):
        category = self.env["nextcloud.document.category"].new({
            "model_name": "project.project",
        })

        category._compute_complete_name()

        self.assertFalse(category.complete_name)

    def test_project_task_uses_project_categories(self):
        wizard = self.env["nextcloud.upload.wizard"].create({
            "res_model": self.project_task._name,
            "res_id": self.project_task.id,
            "res_name": self.project_task.display_name,
            "file_data": base64.b64encode(b"software"),
            "filename": "program.zip",
            "upload_kind": "document",
        })

        self.assertTrue(wizard.category_required)
        self.assertEqual(wizard.category_model, "project.project")
        self.assertEqual(wizard._get_category_record(), self.project)

    def test_project_task_photo_does_not_use_project_categories(self):
        wizard = self.env["nextcloud.upload.wizard"].create({
            "res_model": self.project_task._name,
            "res_id": self.project_task.id,
            "res_name": self.project_task.display_name,
            "file_data": base64.b64encode(b"\x89PNG\r\n\x1a\ncontent"),
            "filename": "saha.png",
            "upload_kind": "photo",
        })

        self.assertFalse(wizard.category_required)
        self.assertFalse(wizard.category_model)
        self.assertFalse(wizard._get_category_record())

    def test_standalone_task_does_not_require_category(self):
        wizard = self.env["nextcloud.upload.wizard"].create({
            "res_model": self.task._name,
            "res_id": self.task.id,
            "res_name": self.task.display_name,
            "file_data": base64.b64encode(b"document"),
            "filename": "notes.txt",
            "upload_kind": "document",
        })

        self.assertFalse(wizard.category_required)
        self.assertFalse(wizard.category_model)
