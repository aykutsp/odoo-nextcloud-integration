from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class NextcloudDownloadRequest(models.Model):
    _name = "nextcloud.download.request"
    _description = "Dosya Talebi"
    _order = "request_date desc, id desc"

    document_id = fields.Many2one(
        "nextcloud.document",
        required=True,
        ondelete="cascade",
        index=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    request_date = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    reason = fields.Text()
    state = fields.Selection(
        [
            ("pending", "Bekliyor"),
            ("approved", "Onaylandı"),
            ("rejected", "Reddedildi"),
            ("expired", "Süresi Doldu"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    approver_id = fields.Many2one("res.users", readonly=True)
    decision_date = fields.Datetime(readonly=True)
    expires_at = fields.Datetime(readonly=True, index=True)
    decision_note = fields.Text()
    document_name = fields.Char(related="document_id.name", store=True)
    related_record_name = fields.Char(
        related="document_id.res_name",
        store=True,
    )

    def _manager_activity_users(self):
        manager_group = self.env.ref(
            "odoo_nextcloud_document_hub.group_nextcloud_document_manager",
            raise_if_not_found=False,
        )
        system_group = self.env.ref("base.group_system", raise_if_not_found=False)
        users = self.env["res.users"]
        if manager_group:
            users |= manager_group.users
        if system_group:
            users |= system_group.users
        return users.filtered(lambda user: user.active and not user.share)

    def _download_request_activity_type(self):
        return (
            self.env.ref(
                "odoo_nextcloud_document_hub."
                "mail_activity_type_nextcloud_download_request",
                raise_if_not_found=False,
            )
            or self.env.ref("mail.mail_activity_data_todo")
        )

    def _create_manager_activities(self):
        Activity = self.env["mail.activity"].sudo()
        activity_type = self._download_request_activity_type()
        model_id = self.env["ir.model"].sudo()._get_id(self._name)
        managers = self._manager_activity_users()
        today = fields.Date.context_today(self)
        for request in self:
            if request.state != "pending":
                continue
            existing = Activity.search([
                ("res_model_id", "=", model_id),
                ("res_id", "=", request.id),
                ("activity_type_id", "=", activity_type.id),
            ])
            existing_users = existing.mapped("user_id")
            for manager in managers - existing_users:
                Activity.create({
                    "activity_type_id": activity_type.id,
                    "summary": _("Dosya Talepleri"),
                    "note": _(
                        "%(requester)s kullanıcısı %(document)s dosyası için "
                        "indirme talebi gönderdi."
                    ) % {
                        "requester": request.requester_id.display_name,
                        "document": request.document_name
                        or request.document_id.display_name
                        or _("Dosya"),
                    },
                    "res_model_id": model_id,
                    "res_id": request.id,
                    "user_id": manager.id,
                    "date_deadline": today,
                })

    def _clear_manager_activities(self):
        if not self:
            return
        activity_type = self._download_request_activity_type()
        model_id = self.env["ir.model"].sudo()._get_id(self._name)
        self.env["mail.activity"].sudo().search([
            ("res_model_id", "=", model_id),
            ("res_id", "in", self.ids),
            ("activity_type_id", "=", activity_type.id),
        ]).unlink()

    @api.model
    def _approval_hours(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "nextcloud_document_hub.download_approval_hours",
            "1",
        )
        try:
            return max(float(value or 1), 0.25)
        except (TypeError, ValueError):
            return 1.0

    def _check_manager(self):
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "odoo_nextcloud_document_hub."
                "group_nextcloud_document_manager"
            )
        ):
            raise AccessError(_("İndirme taleplerini yönetme yetkiniz yok."))

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "odoo_nextcloud_document_hub."
                "group_nextcloud_document_viewer"
            )
        ):
            raise AccessError(_("İndirme talebi oluşturma yetkiniz yok."))
        for values in vals_list:
            document = self.env["nextcloud.document"].browse(
                values.get("document_id")
            ).exists()
            if not document:
                raise UserError(_("Geçerli bir belge gereklidir."))
            document._check_related_record_access("read")
            document._check_category_access()
            values["requester_id"] = self.env.user.id
            values["state"] = "pending"
            values.pop("approver_id", None)
            values.pop("expires_at", None)
        requests = super().create(vals_list)
        requests._create_manager_activities()
        return requests

    def write(self, values):
        is_manager = (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "odoo_nextcloud_document_hub."
                "group_nextcloud_document_manager"
            )
        )
        if not is_manager:
            if set(values) - {"reason"}:
                raise AccessError(_("Yalnızca talep açıklamasını değiştirebilirsiniz."))
            for request in self:
                if (
                    request.requester_id != self.env.user
                    or request.state != "pending"
                ):
                    raise AccessError(_("Bu talebi değiştiremezsiniz."))
        previous_pending = self.filtered(lambda request: request.state == "pending")
        result = super().write(values)
        if "state" in values:
            previous_pending.filtered(
                lambda request: request.state != "pending"
            )._clear_manager_activities()
        return result

    def action_approve(self):
        self._check_manager()
        if any(request.state != "pending" for request in self):
            raise UserError(_("Yalnızca bekleyen talepler onaylanabilir."))
        now = fields.Datetime.now()
        for request in self:
            request.write({
                "state": "approved",
                "approver_id": self.env.user.id,
                "decision_date": now,
                "expires_at": now
                + relativedelta(hours=self._approval_hours()),
            })

    def action_reject(self):
        self._check_manager()
        if any(request.state != "pending" for request in self):
            raise UserError(_("Yalnızca bekleyen talepler reddedilebilir."))
        self.write({
            "state": "rejected",
            "approver_id": self.env.user.id,
            "decision_date": fields.Datetime.now(),
            "expires_at": False,
        })

    def action_open_document(self):
        self.ensure_one()
        self.document_id._check_related_record_access("read")
        self.document_id._check_category_access()
        return {
            "type": "ir.actions.act_window",
            "res_model": "nextcloud.document",
            "res_id": self.document_id.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _cron_expire_approvals(self):
        expired = self.sudo().search([
            ("state", "=", "approved"),
            ("expires_at", "<=", fields.Datetime.now()),
        ])
        expired.write({"state": "expired"})

    def unlink(self):
        self._clear_manager_activities()
        return super().unlink()

    @api.model
    def create_request(self, document, reason=None):
        existing = self.search([
            ("document_id", "=", document.id),
            ("requester_id", "=", self.env.user.id),
            ("state", "=", "pending"),
        ], limit=1)
        if existing:
            raise UserError(_("Bu dosya için bekleyen talebiniz zaten var."))
        return self.create({
            "document_id": document.id,
            "requester_id": self.env.user.id,
            "reason": reason,
        })
