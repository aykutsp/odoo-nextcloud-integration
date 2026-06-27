from odoo import _, api, fields, models
from odoo.exceptions import UserError


class NextcloudConfigSettings(models.Model):
    _name = "nextcloud.config.settings"
    _description = "Nextcloud Configuration Settings"

    name = fields.Char(
        default="Nextcloud",
        required=True,
        readonly=True,
    )
    nextcloud_base_url = fields.Char(
        string="Nextcloud Base URL",
        required=True,
        default="https://cloud.example.com",
    )
    nextcloud_username = fields.Char(
        string="Nextcloud Username",
        required=True,
    )
    nextcloud_app_password = fields.Char(
        string="Nextcloud App Password",
        required=True,
    )
    nextcloud_root_folder = fields.Char(
        string="Root Folder",
        required=True,
        default="odoo",
    )
    nextcloud_webdav_path = fields.Char(
        string="WebDAV Path Template",
        required=True,
        default="/remote.php/dav/files/{username}",
    )
    nextcloud_max_upload_mb = fields.Integer(
        string="Max Upload Size MB",
        required=True,
        default=500,
    )
    nextcloud_keep_ir_attachment = fields.Boolean(
        string="Keep Odoo Attachment Copy",
        default=False,
    )
    nextcloud_download_approval_hours = fields.Float(
        string="İndirme Onay Süresi (Saat)",
        required=True,
        default=1.0,
    )

    @api.model
    def _parameter_values(self):
        params = self.env["ir.config_parameter"].sudo()
        try:
            max_upload_mb = int(
                params.get_param(
                    "nextcloud_document_hub.max_upload_mb",
                    "500",
                )
                or 500
            )
        except (TypeError, ValueError):
            max_upload_mb = 500
        keep_attachment = params.get_param(
            "nextcloud_document_hub.keep_ir_attachment",
            "False",
        )
        try:
            approval_hours = float(
                params.get_param(
                    "nextcloud_document_hub.download_approval_hours",
                    "1",
                )
                or 1
            )
        except (TypeError, ValueError):
            approval_hours = 1.0
        return {
            "name": "Nextcloud",
            "nextcloud_base_url": params.get_param(
                "nextcloud_document_hub.base_url",
                "https://cloud.example.com",
            ),
            "nextcloud_username": params.get_param(
                "nextcloud_document_hub.username",
                "",
            ),
            "nextcloud_app_password": params.get_param(
                "nextcloud_document_hub.app_password",
                "",
            ),
            "nextcloud_root_folder": params.get_param(
                "nextcloud_document_hub.root_folder",
                "odoo",
            ),
            "nextcloud_webdav_path": params.get_param(
                "nextcloud_document_hub.webdav_path",
                "/remote.php/dav/files/{username}",
            ),
            "nextcloud_max_upload_mb": max(max_upload_mb, 1),
            "nextcloud_keep_ir_attachment": (
                str(keep_attachment).lower() in ("1", "true", "yes")
            ),
            "nextcloud_download_approval_hours": max(
                approval_hours,
                0.25,
            ),
        }

    @api.model
    def get_singleton(self):
        settings = self.sudo().search([], limit=1)
        parameter_values = self._parameter_values()
        if settings:
            empty_credentials = (
                not settings.nextcloud_username
                and not settings.nextcloud_app_password
            )
            if empty_credentials and parameter_values["nextcloud_username"]:
                settings.sudo().write(parameter_values)
            return settings
        return self.sudo().create(parameter_values)

    @api.model
    def action_open_settings(self):
        settings = self.get_singleton()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nextcloud Ayarları"),
            "res_model": self._name,
            "res_id": settings.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "odoo_nextcloud_document_hub."
                        "view_nextcloud_config_settings_form"
                    ).id,
                    "form",
                )
            ],
            "target": "current",
        }

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.is_superuser():
            existing = self.sudo().search([], limit=1)
            if existing:
                raise UserError(_("Yalnızca bir Nextcloud ayar kaydı olabilir."))
        return super().create(vals_list)

    def _save_parameters(self):
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(
            "nextcloud_document_hub.base_url",
            (self.nextcloud_base_url or "").strip(),
        )
        params.set_param(
            "nextcloud_document_hub.username",
            (self.nextcloud_username or "").strip(),
        )
        params.set_param(
            "nextcloud_document_hub.app_password",
            self.nextcloud_app_password or "",
        )
        params.set_param(
            "nextcloud_document_hub.root_folder",
            (self.nextcloud_root_folder or "odoo").strip(),
        )
        params.set_param(
            "nextcloud_document_hub.webdav_path",
            (self.nextcloud_webdav_path or "").strip(),
        )
        params.set_param(
            "nextcloud_document_hub.max_upload_mb",
            max(self.nextcloud_max_upload_mb, 1),
        )
        params.set_param(
            "nextcloud_document_hub.keep_ir_attachment",
            self.nextcloud_keep_ir_attachment,
        )
        params.set_param(
            "nextcloud_document_hub.download_approval_hours",
            max(self.nextcloud_download_approval_hours, 0.25),
        )

    def write(self, values):
        result = super().write(values)
        for settings in self:
            settings._save_parameters()
        return result

    def unlink(self):
        raise UserError(_("Nextcloud ayar kaydı silinemez."))

    def action_save(self):
        self._save_parameters()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Nextcloud"),
                "message": _("Ayarlar kaydedildi."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_test_nextcloud_connection(self):
        self._save_parameters()
        self.env["nextcloud.webdav.client"].test_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Nextcloud"),
                "message": _("Bağlantı testi başarılı."),
                "type": "success",
                "sticky": False,
            },
        }
