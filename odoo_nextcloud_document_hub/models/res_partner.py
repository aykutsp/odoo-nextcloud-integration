from odoo import _, models
from odoo.exceptions import AccessError
from odoo.osv import expression

from .nextcloud_utils import record_segment


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "nextcloud.document.mixin"]

    def _purchase_document_domain(self):
        self.ensure_one()
        if not self.id:
            return [("id", "=", 0)]
        partner = self.commercial_partner_id or self
        child_partners = self.env["res.partner"].search([
            ("id", "child_of", partner.id),
        ])
        purchase_orders = self.env["purchase.order"].search([
            ("partner_id", "child_of", partner.id),
        ])
        partner_ids = list(set(child_partners.ids + [self.id, partner.id]))
        return expression.OR([
            [
                ("res_model", "=", "res.partner"),
                ("res_id", "in", partner_ids),
            ],
            [
                ("res_model", "=", "purchase.order"),
                ("res_id", "in", purchase_orders.ids),
            ],
        ])

    def _compute_nextcloud_document_ids(self):
        Document = self.env["nextcloud.document"]
        for partner in self:
            docs = Document.search(partner._purchase_document_domain())
            partner.nextcloud_document_ids = docs
            partner.nextcloud_document_count = len(docs)

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        partner = self.commercial_partner_id or self
        return [
            self._get_nextcloud_root_folder(),
            "partners",
            record_segment(partner),
        ]

    def _nextcloud_automatic_tag_names(self):
        self.ensure_one()
        partner = self.commercial_partner_id or self
        return [partner.display_name, f"PARTNER-{partner.id}"]

    def _check_nextcloud_upload_access(self):
        is_system = self.env.user.has_group("base.group_system")
        is_uploader = self.env.user.has_group(
            "odoo_nextcloud_document_hub.group_nextcloud_document_uploader"
        )
        if not is_system and not is_uploader:
            raise AccessError(_("Nextcloud dosyası yükleme yetkiniz yok."))
        self.check_access("read")

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
            "domain": self._purchase_document_domain(),
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }
