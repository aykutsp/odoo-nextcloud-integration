from odoo import models

from .nextcloud_utils import record_segment


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "nextcloud.document.mixin"]

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id or self.partner_id
        return [
            self._get_nextcloud_root_folder(),
            "purchase",
            record_segment(partner) if partner else "vendors",
            record_segment(self),
        ]

    def _nextcloud_automatic_tag_names(self):
        self.ensure_one()
        tags = [self.display_name, f"PURCHASE-{self.id}"]
        if self.partner_id:
            tags.append(self.partner_id.display_name)
        return tags
