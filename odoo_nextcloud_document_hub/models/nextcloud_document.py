from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class NextcloudDocument(models.Model):
    _name = "nextcloud.document"
    _description = "Nextcloud Document"
    _order = "upload_date desc, id desc"

    name = fields.Char(required=True)
    description = fields.Text()
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    res_name = fields.Char()
    uploaded_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    upload_date = fields.Datetime(readonly=True)
    nextcloud_path = fields.Char(readonly=True)
    nextcloud_url = fields.Char(readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("uploaded", "Uploaded"), ("error", "Error")],
        default="draft",
        required=True,
        index=True,
    )
    error_message = fields.Text(readonly=True)
    file_size = fields.Integer(readonly=True)
    mime_type = fields.Char(readonly=True)
    category_id = fields.Many2one(
        "nextcloud.document.category",
        readonly=True,
        index=True,
    )
    tag_ids = fields.Many2many(
        "nextcloud.document.tag",
        string="Etiketler",
        readonly=True,
    )
    tag_sync_error = fields.Text(readonly=True)
    upload_kind = fields.Selection(
        [("document", "Document"), ("photo", "Photo")],
        default="document",
        required=True,
        readonly=True,
        index=True,
    )
    is_image = fields.Boolean(compute="_compute_file_properties", store=True)
    is_previewable = fields.Boolean(
        compute="_compute_file_properties",
        store=True,
    )
    viewer_url = fields.Char(compute="_compute_route_urls")
    download_url = fields.Char(compute="_compute_route_urls")
    can_download = fields.Boolean(compute="_compute_download_access")
    can_request_download = fields.Boolean(
        compute="_compute_download_access"
    )
    has_pending_download_request = fields.Boolean(
        compute="_compute_download_access"
    )
    project_code = fields.Char(
        string="Proje No",
        compute="_compute_related_info",
        search="_search_project_code",
    )
    project_name = fields.Char(
        string="Proje Adı",
        compute="_compute_related_info",
    )
    task_code = fields.Char(
        string="Task No",
        compute="_compute_related_info",
    )
    task_name = fields.Char(
        string="Task Adı",
        compute="_compute_related_info",
    )
    crm_code = fields.Char(
        string="CRM No",
        compute="_compute_related_info",
    )
    crm_name = fields.Char(
        string="CRM Adı",
        compute="_compute_related_info",
    )
    attachment_id = fields.Many2one(
        "ir.attachment",
        readonly=True,
        ondelete="set null",
        groups="base.group_system",
    )

    @api.depends("mime_type")
    def _compute_file_properties(self):
        previewable_types = {
            "application/pdf",
            "application/json",
            "application/xml",
        }
        previewable_prefixes = ("image/", "text/", "audio/", "video/")
        for document in self:
            mime_type = document.mime_type or ""
            document.is_image = mime_type.startswith("image/")
            document.is_previewable = (
                mime_type in previewable_types
                or mime_type.startswith(previewable_prefixes)
            )

    def _compute_route_urls(self):
        for document in self:
            if document.id:
                document.viewer_url = (
                    f"/nextcloud_document/preview/{document.id}"
                )
                document.download_url = (
                    f"/nextcloud_document/download/{document.id}"
                )
            else:
                document.viewer_url = False
                document.download_url = False

    def _compute_download_access(self):
        Request = self.env["nextcloud.download.request"]
        now = fields.Datetime.now()
        is_direct_downloader = (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "odoo_nextcloud_document_hub."
                "group_nextcloud_document_downloader"
            )
        )
        for document in self:
            approved = Request.search_count([
                ("document_id", "=", document.id),
                ("requester_id", "=", self.env.user.id),
                ("state", "=", "approved"),
                ("expires_at", ">", now),
            ], limit=1)
            pending = Request.search_count([
                ("document_id", "=", document.id),
                ("requester_id", "=", self.env.user.id),
                ("state", "=", "pending"),
            ], limit=1)
            document.can_download = bool(
                document.state == "uploaded"
                and (is_direct_downloader or approved)
            )
            document.has_pending_download_request = bool(pending)
            document.can_request_download = bool(
                document.state == "uploaded"
                and not document.can_download
                and not pending
            )

    def _record_display_code(self, record):
        if (
            record._name == "project.project"
            and "x_project_code" in record._fields
        ):
            return record.x_project_code or str(record.id)
        return str(record.id)

    def _set_project_info(self, document, project):
        document.project_code = self._record_display_code(project)
        document.project_name = project.display_name

    def _set_task_info(self, document, task):
        document.task_code = str(task.id)
        document.task_name = task.display_name
        if task.project_id:
            self._set_project_info(document, task.project_id)

    def _compute_related_info(self):
        for document in self:
            document.project_code = False
            document.project_name = False
            document.task_code = False
            document.task_name = False
            document.crm_code = False
            document.crm_name = False
            if document.res_model not in self.env or not document.res_id:
                continue
            record = self.env[document.res_model].browse(
                document.res_id
            ).exists()
            if not record:
                continue
            if record._name == "project.project":
                self._set_project_info(document, record)
            elif record._name == "project.task":
                self._set_task_info(document, record)
            elif record._name == "crm.lead":
                document.crm_code = str(record.id)
                document.crm_name = record.display_name
            elif record._name == "mrp.workorder":
                document.task_code = str(record.id)
                document.task_name = record.display_name
                production = getattr(record, "production_id", False)
                project = getattr(production, "project_id", False)
                if project:
                    self._set_project_info(document, project)

    def _search_project_code(self, operator, value):
        Project = self.env["project.project"]
        if "x_project_code" not in Project._fields:
            return [("res_model", "=", "__none__")]
        projects = Project.search([("x_project_code", operator, value)])
        task_ids = self.env["project.task"].search([
            ("project_id", "in", projects.ids),
        ]).ids
        return [
            "|",
            "&",
            ("res_model", "=", "project.project"),
            ("res_id", "in", projects.ids),
            "&",
            ("res_model", "=", "project.task"),
            ("res_id", "in", task_ids),
        ]

    def _has_valid_download_approval(self):
        self.ensure_one()
        return bool(self.env["nextcloud.download.request"].search_count([
            ("document_id", "=", self.id),
            ("requester_id", "=", self.env.user.id),
            ("state", "=", "approved"),
            ("expires_at", ">", fields.Datetime.now()),
        ], limit=1))

    def _check_related_record_access(self, operation="read"):
        if self.env.is_superuser():
            return
        for document in self.sudo():
            if document.res_model not in self.env:
                raise AccessError(_("İlişkili model artık mevcut değil."))
            related = self.env[document.res_model].browse(document.res_id).exists()
            if not related:
                raise AccessError(_("İlişkili Odoo kaydı artık mevcut değil."))
            related.check_access(operation)

    def _check_category_access(self):
        if self.env.is_superuser():
            return
        for document in self.sudo():
            if (
                document.category_id
                and not document.category_id._is_accessible_by_user(
                    self.env.user
                )
            ):
                raise AccessError(
                    _("Bu dosyanın klasör kategorisine erişim yetkiniz yok.")
                )

    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.is_superuser():
            return super()._search(
                domain,
                offset=offset,
                limit=limit,
                order=order,
            )

        candidate_query = super()._search(domain, order=order)
        candidate_ids = [
            row[0] for row in self.env.execute_query(candidate_query.select())
        ]
        allowed_ids = []
        for document in self.sudo().browse(candidate_ids):
            if (
                document.category_id
                and not document.category_id._is_accessible_by_user(
                    self.env.user
                )
            ):
                continue
            if document.res_model not in self.env:
                continue
            related = self.env[document.res_model].browse(
                document.res_id
            ).exists()
            if not related:
                continue
            try:
                related.check_access("read")
            except AccessError:
                continue
            allowed_ids.append(document.id)

        return super()._search(
            [("id", "in", allowed_ids)],
            offset=offset,
            limit=limit,
            order=order,
        )

    def _check_user_can(self, action):
        self.ensure_one()
        group_by_action = {
            "preview": "group_nextcloud_document_viewer",
            "open": "group_nextcloud_document_viewer",
            "download": "group_nextcloud_document_downloader",
            "manage": "group_nextcloud_document_manager",
        }
        group = group_by_action.get(action)
        is_system = self.env.user.has_group("base.group_system")
        has_action_group = group and self.env.user.has_group(
            f"odoo_nextcloud_document_hub.{group}"
        )
        if (
            action == "download"
            and not is_system
            and not has_action_group
            and self._has_valid_download_approval()
        ):
            has_action_group = True
        if group and not is_system and not has_action_group:
            raise AccessError(_("Bu dosya işlemi için yetkiniz yok."))
        self._check_related_record_access(
            "write" if action == "manage" else "read"
        )
        self._check_category_access()
        if action in ("preview", "download", "open"):
            if self.state != "uploaded" or not self.nextcloud_path:
                raise UserError(_("Dosya henüz başarıyla yüklenmemiş."))
        if action == "preview" and not self.is_previewable:
            raise UserError(
                _("Bu dosya türü tarayıcıda önizlenemiyor. İndir aksiyonunu kullanın.")
            )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            model_name = values.get("res_model")
            record_id = values.get("res_id")
            if model_name not in self.env or not record_id:
                raise UserError(_("Geçerli bir ilişkili Odoo kaydı gereklidir."))
            self.env[model_name].browse(record_id).check_access("read")
        return super().create(vals_list)

    def read(self, fields=None, load="_classic_read"):
        self._check_related_record_access("read")
        self._check_category_access()
        return super().read(fields=fields, load=load)

    def write(self, values):
        if not self.env.is_superuser():
            self._check_user_can("manage")
        return super().write(values)

    def unlink(self):
        self._check_user_can("manage")
        return super().unlink()

    def action_open_nextcloud(self):
        self.ensure_one()
        self._check_user_can("open")
        if not self.nextcloud_url:
            raise UserError(_("Bu doküman için Nextcloud URL'si yok."))
        return {
            "type": "ir.actions.act_url",
            "url": self.nextcloud_url,
            "target": "new",
        }

    def action_preview(self):
        self.ensure_one()
        self._check_user_can("preview")
        return {
            "type": "ir.actions.act_url",
            "url": self.viewer_url,
            "target": "new",
        }

    def action_download(self):
        self.ensure_one()
        self._check_user_can("download")
        return {
            "type": "ir.actions.act_url",
            "url": self.download_url,
            "target": "self",
        }

    def action_request_download(self):
        self.ensure_one()
        self._check_user_can("open")
        if self.can_download:
            raise UserError(_("Bu dosyayı zaten indirebilirsiniz."))
        request = self.env["nextcloud.download.request"].create_request(self)
        return {
            "type": "ir.actions.act_window",
            "name": _("İndirme Talebi"),
            "res_model": "nextcloud.download.request",
            "res_id": request.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_rename_wizard(self):
        self.ensure_one()
        self._check_user_can("manage")
        return {
            "type": "ir.actions.act_window",
            "name": _("Dosya Adını Değiştir"),
            "res_model": "nextcloud.rename.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_document_id": self.id,
                "default_name": self.name,
            },
        }

    def action_open_related_record(self):
        self.ensure_one()
        self._check_related_record_access("read")
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            raise UserError(_("İlişkili Odoo kaydı bulunamadı."))
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
