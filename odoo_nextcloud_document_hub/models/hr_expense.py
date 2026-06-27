from odoo import _, models
from odoo.exceptions import AccessError

from .nextcloud_utils import record_segment


class HrExpense(models.Model):
    _name = "hr.expense"
    _inherit = ["hr.expense", "nextcloud.document.mixin"]

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        return [
            self._get_nextcloud_root_folder(),
            "expenses",
            record_segment(self),
        ]

    def _nextcloud_automatic_tag_names(self):
        self.ensure_one()
        return [self.display_name, f"EXPENSE-{self.id}"]

    def _check_nextcloud_upload_access(self):
        is_system = self.env.user.has_group("base.group_system")
        is_uploader = self.env.user.has_group(
            "odoo_nextcloud_document_hub.group_nextcloud_document_uploader"
        )
        if not is_system and not is_uploader:
            raise AccessError(_("Nextcloud dosyası yükleme yetkiniz yok."))
        self.check_access("read")
