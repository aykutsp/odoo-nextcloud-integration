from odoo import models

from .nextcloud_utils import record_segment


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "nextcloud.document.mixin"]

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        return [
            self._get_nextcloud_root_folder(),
            "deliveries",
            record_segment(self),
        ]

    def _nextcloud_automatic_tag_names(self):
        self.ensure_one()
        return [self.display_name, f"PICKING-{self.id}"]
