from odoo import _, fields, models
from odoo.exceptions import AccessError

from .nextcloud_utils import join_segments, record_segment, slugify


class NextcloudDocumentMixin(models.AbstractModel):
    _name = "nextcloud.document.mixin"
    _description = "Nextcloud Document Mixin"

    nextcloud_document_ids = fields.Many2many(
        "nextcloud.document",
        compute="_compute_nextcloud_document_ids",
        string="Nextcloud Documents",
    )
    nextcloud_document_count = fields.Integer(compute="_compute_nextcloud_document_ids")

    def _compute_nextcloud_document_ids(self):
        Document = self.env["nextcloud.document"]
        for record in self:
            docs = Document.search([("res_model", "=", record._name), ("res_id", "=", record.id)])
            record.nextcloud_document_ids = docs
            record.nextcloud_document_count = len(docs)

    def _get_nextcloud_root_folder(self):
        configured_root = self.env["ir.config_parameter"].sudo().get_param(
            "nextcloud_document_hub.root_folder", "odoo"
        )
        return slugify(configured_root, fallback="odoo")

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        return [
            self._get_nextcloud_root_folder(),
            self._name.replace(".", "_"),
            record_segment(self),
        ]

    def get_nextcloud_folder_path(self):
        self.ensure_one()
        return join_segments(self._nextcloud_folder_segments())

    def _nextcloud_automatic_tag_names(self):
        self.ensure_one()
        return [self.display_name]

    def action_nextcloud_upload_wizard(self):
        self.ensure_one()
        self._check_nextcloud_upload_access()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nextcloud Dosya Yükle"),
            "res_model": "nextcloud.upload.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
                "default_res_name": self.display_name,
                "default_upload_kind": "document",
            },
        }

    def action_nextcloud_photo_upload_wizard(self):
        self.ensure_one()
        self._check_nextcloud_upload_access()
        if self._name != "project.task":
            raise AccessError(_("Fotoğraf yükleme yalnızca görevlerde kullanılabilir."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Nextcloud Fotoğraf Yükle"),
            "res_model": "nextcloud.upload.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
                "default_res_name": self.display_name,
                "default_upload_kind": "photo",
            },
        }

    def _check_nextcloud_upload_access(self):
        is_system = self.env.user.has_group("base.group_system")
        is_uploader = self.env.user.has_group(
            "odoo_nextcloud_document_hub.group_nextcloud_document_uploader"
        )
        if not is_system and not is_uploader:
            raise AccessError(_("Nextcloud dosyası yükleme yetkiniz yok."))
        self.check_access("write")

    def action_nextcloud_documents(self):
        self.ensure_one()
        is_system = self.env.user.has_group("base.group_system")
        is_viewer = self.env.user.has_group(
            "odoo_nextcloud_document_hub.group_nextcloud_document_viewer"
        )
        if not is_system and not is_viewer:
            raise AccessError(_("Nextcloud dosyalarını görüntüleme yetkiniz yok."))
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": _("Nextcloud Dosyaları"),
            "res_model": "nextcloud.document",
            "view_mode": "list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }
