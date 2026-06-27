from odoo import models


class CrmLead(models.Model):
    _name = "crm.lead"
    _inherit = ["crm.lead", "nextcloud.document.mixin"]

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        return [self._get_nextcloud_root_folder(), "crm", str(self.id)]

    def _nextcloud_automatic_tag_names(self):
        self.ensure_one()
        return [self.display_name, f"CRM-{self.id}"]
