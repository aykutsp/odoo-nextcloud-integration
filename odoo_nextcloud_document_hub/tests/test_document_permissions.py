from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDocumentPermissions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({
            "name": "Viewer Test",
            "privacy_visibility": "employees",
        })
        cls.viewer_group = cls.env.ref(
            "odoo_nextcloud_document_hub.group_nextcloud_document_viewer"
        )
        cls.downloader_group = cls.env.ref(
            "odoo_nextcloud_document_hub.group_nextcloud_document_downloader"
        )
        cls.restricted_group = cls.env["res.groups"].create({
            "name": "Restricted Nextcloud Folder",
        })
        cls.viewer = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Nextcloud Viewer",
            "login": "nextcloud-viewer",
            "groups_id": [
                (6, 0, [
                    cls.env.ref("base.group_user").id,
                    cls.env.ref("project.group_project_user").id,
                    cls.viewer_group.id,
                ])
            ],
        })
        cls.document = cls.env["nextcloud.document"].sudo().create({
            "name": "test.pdf",
            "res_model": cls.project._name,
            "res_id": cls.project.id,
            "res_name": cls.project.display_name,
            "nextcloud_path": "odoo/projects/test.pdf",
            "mime_type": "application/pdf",
            "state": "uploaded",
        })
        cls.private_project = cls.env["project.project"].create({
            "name": "Private Viewer Test",
            "privacy_visibility": "followers",
        })
        cls.private_document = cls.env[
            "nextcloud.document"
        ].sudo().create({
            "name": "private.pdf",
            "res_model": cls.private_project._name,
            "res_id": cls.private_project.id,
            "res_name": cls.private_project.display_name,
            "nextcloud_path": "odoo/projects/private.pdf",
            "mime_type": "application/pdf",
            "state": "uploaded",
        })
        cls.restricted_category = cls.env[
            "nextcloud.document.category"
        ].create({
            "name": "Restricted Software",
            "folder_name": "99 - Restricted Software",
            "model_name": "project.project",
            "allowed_group_ids": [(6, 0, [cls.restricted_group.id])],
        })
        cls.restricted_document = cls.env[
            "nextcloud.document"
        ].sudo().create({
            "name": "restricted.zip",
            "res_model": cls.project._name,
            "res_id": cls.project.id,
            "res_name": cls.project.display_name,
            "nextcloud_path": "odoo/project/restricted.zip",
            "mime_type": "application/zip",
            "category_id": cls.restricted_category.id,
            "state": "uploaded",
        })

    def test_viewer_can_preview_but_not_download(self):
        document = self.document.with_user(self.viewer)
        self.assertTrue(document._check_user_can("preview"))
        with self.assertRaises(AccessError):
            document._check_user_can("download")

    def test_downloader_can_download(self):
        self.viewer.write({
            "groups_id": [(4, self.downloader_group.id)],
        })
        self.assertTrue(
            self.document.with_user(self.viewer)._check_user_can("download")
        )

    def test_search_hides_documents_of_inaccessible_records(self):
        documents = self.env["nextcloud.document"].with_user(
            self.viewer
        ).search([
            ("id", "in", [self.document.id, self.private_document.id]),
        ])

        self.assertEqual(documents, self.document)

    def test_approved_request_temporarily_allows_download(self):
        request = self.env["nextcloud.download.request"].with_user(
            self.viewer
        ).create_request(self.document.with_user(self.viewer))
        request.with_user(self.env.user).action_approve()

        self.assertTrue(
            self.document.with_user(self.viewer)._check_user_can("download")
        )

    def test_restricted_category_and_document_are_hidden(self):
        categories = self.env[
            "nextcloud.document.category"
        ].with_user(self.viewer).search([
            ("id", "=", self.restricted_category.id),
        ])
        documents = self.env["nextcloud.document"].with_user(
            self.viewer
        ).search([
            ("id", "=", self.restricted_document.id),
        ])

        self.assertFalse(categories)
        self.assertFalse(documents)
        with self.assertRaises(AccessError):
            self.restricted_document.with_user(
                self.viewer
            )._check_user_can("preview")

    def test_category_access_is_granted_by_any_selected_group(self):
        self.viewer.write({
            "groups_id": [(4, self.restricted_group.id)],
        })

        self.assertEqual(
            self.env["nextcloud.document.category"].with_user(
                self.viewer
            ).search([("id", "=", self.restricted_category.id)]),
            self.restricted_category,
        )
        self.assertEqual(
            self.env["nextcloud.document"].with_user(
                self.viewer
            ).search([("id", "=", self.restricted_document.id)]),
            self.restricted_document,
        )

    def test_parent_category_restriction_is_inherited(self):
        child = self.env["nextcloud.document.category"].create({
            "name": "Inherited Restriction",
            "folder_name": "01 - Inherited Restriction",
            "model_name": "project.project",
            "parent_id": self.restricted_category.id,
        })

        self.assertFalse(
            self.env["nextcloud.document.category"].with_user(
                self.viewer
            ).search([("id", "=", child.id)])
        )

    def test_manager_can_open_rename_wizard(self):
        manager = self.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Nextcloud Manager",
            "login": "nextcloud-manager",
            "groups_id": [
                (6, 0, [
                    self.env.ref("base.group_user").id,
                    self.env.ref("project.group_project_user").id,
                    self.env.ref(
                        "odoo_nextcloud_document_hub."
                        "group_nextcloud_document_manager"
                    ).id,
                ])
            ],
        })

        action = self.document.with_user(manager).action_rename_wizard()

        self.assertEqual(action["res_model"], "nextcloud.rename.wizard")

    def test_viewer_cannot_open_rename_wizard(self):
        with self.assertRaises(AccessError):
            self.document.with_user(self.viewer).action_rename_wizard()

    def test_related_info_for_project_document(self):
        self.document._compute_related_info()

        self.assertEqual(self.document.project_code, str(self.project.id))
        self.assertEqual(self.document.project_name, self.project.display_name)
        self.assertFalse(self.document.task_code)
        self.assertFalse(self.document.crm_code)

    def test_related_info_for_task_document(self):
        task = self.env["project.task"].create({
            "name": "Panel Test Task",
            "project_id": self.project.id,
        })
        document = self.env["nextcloud.document"].sudo().create({
            "name": "task.pdf",
            "res_model": task._name,
            "res_id": task.id,
            "res_name": task.display_name,
            "nextcloud_path": "odoo/task.pdf",
            "mime_type": "application/pdf",
            "state": "uploaded",
        })

        document._compute_related_info()

        self.assertEqual(document.project_code, str(self.project.id))
        self.assertEqual(document.project_name, self.project.display_name)
        self.assertEqual(document.task_code, str(task.id))
        self.assertEqual(document.task_name, task.display_name)

    def test_related_info_for_crm_document(self):
        lead = self.env["crm.lead"].create({"name": "New CRM Lead"})
        document = self.env["nextcloud.document"].sudo().create({
            "name": "crm.pdf",
            "res_model": lead._name,
            "res_id": lead.id,
            "res_name": lead.display_name,
            "nextcloud_path": "odoo/crm.pdf",
            "mime_type": "application/pdf",
            "state": "uploaded",
        })

        document._compute_related_info()

        self.assertEqual(document.crm_code, str(lead.id))
        self.assertEqual(document.crm_name, lead.display_name)
        self.assertFalse(document.project_code)
