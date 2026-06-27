import base64
import logging
import mimetypes

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.nextcloud_utils import ensure_filename_extension, sanitize_filename

_logger = logging.getLogger(__name__)

PHOTO_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
PHOTO_EXTENSION_MIME_TYPES = {
    ".heic": "image/heic",
    ".heif": "image/heif",
}
MIMETYPE_EXTENSIONS = {
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
    "text/plain": "txt",
}


def detect_document_mimetype(data):
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"PK\x03\x04"):
        return "application/zip"
    return False


def detect_photo_mimetype(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12].lower()
        if brand in {b"heic", b"heix", b"hevc", b"hevx"}:
            return "image/heic"
        if brand in {b"mif1", b"msf1", b"heif"}:
            return "image/heif"
    return False


class NextcloudUploadWizard(models.TransientModel):
    _name = "nextcloud.upload.wizard"
    _description = "Nextcloud Upload Wizard"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    res_name = fields.Char(readonly=True)
    category_model = fields.Char(compute="_compute_category_context")
    category_required = fields.Boolean(compute="_compute_category_context")
    file_data = fields.Binary(string="File", required=True, attachment=False)
    filename = fields.Char(required=True)
    description = fields.Text()
    category_id = fields.Many2one(
        "nextcloud.document.category",
        string="Dosya Türü / Klasör",
        domain="[('model_name', '=', category_model), ('active', '=', True)]",
    )
    tag_ids = fields.Many2many(
        "nextcloud.document.tag",
        string="Etiketler",
    )
    upload_kind = fields.Selection(
        [("document", "Dosya"), ("photo", "Fotoğraf")],
        default="document",
        required=True,
        readonly=True,
    )

    @api.depends("res_model", "res_id", "upload_kind")
    def _compute_category_context(self):
        for wizard in self:
            category_record = wizard._get_category_record()
            wizard.category_model = (
                category_record._name if category_record else False
            )
            wizard.category_required = bool(
                category_record and wizard.upload_kind == "document"
            )

    def _get_category_record(self):
        self.ensure_one()
        if self.upload_kind == "photo":
            return self.env["project.project"]
        if self.res_model not in self.env or not self.res_id:
            return self.env["project.project"]
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            return self.env["project.project"]
        if record._name in ("crm.lead", "project.project"):
            return record
        if record._name == "project.task" and record.project_id:
            return record.project_id
        return self.env["project.project"]

    def action_upload(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Lütfen dosya seçin."))
        is_system = self.env.user.has_group("base.group_system")
        is_uploader = self.env.user.has_group(
            "odoo_nextcloud_document_hub.group_nextcloud_document_uploader"
        )
        if not is_system and not is_uploader:
            raise UserError(_("Nextcloud dosyası yükleme yetkiniz yok."))
        if self.res_model not in self.env:
            raise UserError(_("Geçersiz Odoo modeli."))
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            raise UserError(_("İlişkili Odoo kaydı bulunamadı."))
        if not hasattr(record, "get_nextcloud_folder_path"):
            raise UserError(_("Bu model Nextcloud yüklemeyi desteklemiyor: %s") % self.res_model)
        record.check_access("write")
        category_record = self._get_category_record()
        if category_record and self.upload_kind == "document":
            if not self.category_id:
                raise UserError(_("Lütfen dosya türü / klasör seçin."))
            if self.category_id.model_name != category_record._name:
                raise UserError(_("Seçilen klasör bu kayıt türüne ait değil."))
            self.category_id._check_user_access()

        try:
            raw = base64.b64decode(self.file_data, validate=True)
        except (ValueError, TypeError) as exc:
            raise UserError(_("Dosya verisi okunamadı.")) from exc
        safe_filename = sanitize_filename(self.filename)
        extension = (
            "." + safe_filename.rsplit(".", 1)[-1].lower()
            if "." in safe_filename
            else ""
        )
        mimetype = PHOTO_EXTENSION_MIME_TYPES.get(extension)
        mimetype = (
            mimetype
            or mimetypes.guess_type(safe_filename)[0]
            or "application/octet-stream"
        )
        if mimetype == "application/octet-stream":
            mimetype = detect_document_mimetype(raw) or mimetype
        if self.upload_kind == "photo":
            if record._name != "project.task":
                raise UserError(_("Fotoğraf yükleme yalnızca görevlerde kullanılabilir."))
            detected_mimetype = detect_photo_mimetype(raw)
            if (
                mimetype not in PHOTO_MIME_TYPES
                or detected_mimetype not in PHOTO_MIME_TYPES
            ):
                raise UserError(
                    _("Fotoğraf olarak yalnızca JPEG, PNG, WebP, HEIC veya HEIF yüklenebilir.")
                )
            mimetype = detected_mimetype
            safe_filename = ensure_filename_extension(
                safe_filename,
                MIMETYPE_EXTENSIONS.get(mimetype),
            )
            folder_path = record.get_nextcloud_photo_folder_path()
        else:
            safe_filename = ensure_filename_extension(
                safe_filename,
                MIMETYPE_EXTENSIONS.get(mimetype),
            )
            base_folder = (
                category_record.get_nextcloud_folder_path()
                if category_record
                else record.get_nextcloud_folder_path()
            )
            client = self.env["nextcloud.webdav.client"]
            if category_record:
                categories = self.env[
                    "nextcloud.document.category"
                ].search([
                    ("model_name", "=", category_record._name),
                    ("active", "=", True),
                ])
                client.ensure_folder(base_folder)
                if category_record == record:
                    for category in categories:
                        client.ensure_folder(
                            f"{base_folder}/{category.get_folder_path()}"
                        )
                    try:
                        client.sync_system_tags(
                            base_folder,
                            category_record._nextcloud_automatic_tag_names(),
                        )
                    except Exception:
                        _logger.exception(
                            "Nextcloud record-folder tag sync failed"
                        )
                folder_path = (
                    f"{base_folder}/{self.category_id.get_folder_path()}"
                )
            else:
                folder_path = base_folder
        automatic_tag_names = record._nextcloud_automatic_tag_names()
        if category_record and category_record != record:
            automatic_tag_names += (
                category_record._nextcloud_automatic_tag_names()
            )
        automatic_tags = self.env["nextcloud.document.tag"]
        for tag_name in dict.fromkeys(automatic_tag_names):
            tag = self.env["nextcloud.document.tag"].search([
                ("name", "=", tag_name),
            ], limit=1)
            if not tag:
                tag = self.env["nextcloud.document.tag"].create({
                    "name": tag_name,
                })
            automatic_tags |= tag
        selected_tags = self.tag_ids | automatic_tags
        Document = self.env["nextcloud.document"].sudo()
        doc = Document.create({
            "name": safe_filename,
            "description": self.description,
            "res_model": record._name,
            "res_id": record.id,
            "res_name": record.display_name,
            "uploaded_by": self.env.user.id,
            "file_size": len(raw),
            "mime_type": mimetype,
            "upload_kind": self.upload_kind,
            "category_id": self.category_id.id,
            "tag_ids": [(6, 0, selected_tags.ids)],
            "state": "draft",
        })
        try:
            client = self.env["nextcloud.webdav.client"]
            full_path = client.upload_bytes(
                folder_path,
                safe_filename,
                raw,
                mimetype,
                check_existing=self.upload_kind != "photo",
            )
            uploaded_filename = full_path.rsplit("/", 1)[-1]
            values = {
                "name": uploaded_filename,
                "nextcloud_path": full_path,
                "nextcloud_url": client.make_files_url(folder_path, uploaded_filename),
                "state": "uploaded",
                "upload_date": fields.Datetime.now(),
                "error_message": False,
            }
            if self.upload_kind != "photo":
                try:
                    client.sync_system_tags(
                        full_path,
                        selected_tags.mapped("name"),
                    )
                except Exception as tag_exc:
                    _logger.exception("Nextcloud tag sync failed")
                    values["tag_sync_error"] = str(tag_exc)
            keep_attachment = self.env["ir.config_parameter"].sudo().get_param(
                "nextcloud_document_hub.keep_ir_attachment", "False"
            )
            if str(keep_attachment).lower() in ("1", "true", "yes"):
                attachment = self.env["ir.attachment"].sudo().create({
                    "name": uploaded_filename,
                    "datas": self.file_data,
                    "mimetype": mimetype,
                    "res_model": record._name,
                    "res_id": record.id,
                    "description": self.description,
                })
                values["attachment_id"] = attachment.id
            doc.write(values)
        except Exception as exc:
            if isinstance(exc, UserError):
                message = exc.args[0] if exc.args else str(exc)
            else:
                _logger.exception(
                    "Unexpected Nextcloud upload error for %s,%s",
                    record._name,
                    record.id,
                )
                message = _(
                    "Beklenmeyen yükleme hatası oluştu. Odoo sunucu logunu "
                    "kontrol edin: %s"
                ) % str(exc)
            doc.write({
                "state": "error",
                "upload_date": fields.Datetime.now(),
                "error_message": message,
            })
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Nextcloud yükleme başarısız"),
                    "message": message,
                    "type": "danger",
                    "sticky": True,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Nextcloud"),
                "message": _("Dosya başarıyla yüklendi."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
