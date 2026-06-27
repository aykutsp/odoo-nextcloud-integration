from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.nextcloud_utils import (
    ensure_filename_extension,
    sanitize_filename,
    slugify,
)


@tagged("post_install", "-at_install")
class TestNextcloudPathBuilder(TransactionCase):
    def test_project_path_contains_project_id(self):
        project = self.env["project.project"].create({"name": "Çatı / Bakım Projesi"})
        self.assertEqual(
            project.get_nextcloud_folder_path(),
            f"odoo/project/{project.id}",
        )

    def test_task_path_under_project(self):
        project = self.env["project.project"].create({"name": "Müşteri Projesi"})
        task = self.env["project.task"].create({"name": "İlk Görev", "project_id": project.id})
        self.assertIn(
            (
                f"odoo/projects/{project.id}-musteri-projesi/"
                f"tasks/{task.id}-ilk-gorev"
            ),
            task.get_nextcloud_folder_path(),
        )

    def test_lead_path_without_project(self):
        lead = self.env["crm.lead"].create({"name": "Yeni Lead / İstanbul"})
        self.assertEqual(
            lead.get_nextcloud_folder_path(),
            f"odoo/crm/{lead.id}",
        )

    def test_lead_path_under_project(self):
        lead = self.env["crm.lead"].create({"name": "Yeni Fırsat"})
        self.assertEqual(lead.get_nextcloud_folder_path(), f"odoo/crm/{lead.id}")

    def test_task_path_without_project(self):
        task = self.env["project.task"].create({"name": "Bağımsız İş"})
        self.assertEqual(
            task.get_nextcloud_folder_path(),
            f"odoo/tasks/{task.id}-bagimsiz-is",
        )

    def test_task_photo_path_under_project(self):
        project = self.env["project.project"].create({"name": "Şantiye"})
        task = self.env["project.task"].create({
            "name": "Elektrik İş Emri",
            "project_id": project.id,
        })
        self.assertEqual(
            task.get_nextcloud_photo_folder_path(),
            (
                f"odoo/projects/{project.id}-santiye/"
                f"tasks/{task.id}-elektrik-is-emri/photos"
            ),
        )

    def test_task_photo_path_without_project(self):
        task = self.env["project.task"].create({"name": "Saha Fotoğrafı"})
        self.assertEqual(
            task.get_nextcloud_photo_folder_path(),
            f"odoo/tasks/{task.id}-saha-fotografi/photos",
        )

    def test_slugify_turkish_and_unsafe_characters(self):
        self.assertEqual(
            slugify('Çığ / Şube: "Özel" | Ürün?'),
            "cig-sube-ozel-urun",
        )

    def test_sanitize_filename_preserves_extension(self):
        self.assertEqual(
            sanitize_filename("../Teklif / İstanbul.PDF"),
            "istanbul.pdf",
        )

    def test_ensure_filename_extension_appends_missing_extension(self):
        self.assertEqual(
            ensure_filename_extension("Saha Fotoğrafı", "png"),
            "saha-fotografi.png",
        )
        self.assertEqual(
            ensure_filename_extension("program.zip", "pdf"),
            "program.zip",
        )
