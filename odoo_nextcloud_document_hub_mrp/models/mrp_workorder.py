from odoo import fields, models

from odoo.addons.odoo_nextcloud_document_hub.models.nextcloud_utils import record_segment


class MrpWorkorder(models.Model):
    _name = "mrp.workorder"
    _inherit = ["mrp.workorder", "nextcloud.document.mixin"]

    nextcloud_project_id = fields.Many2one(
        "project.project",
        string="Nextcloud Related Project",
        help="Optional project folder for this work order's Nextcloud files.",
    )

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        root = self._get_nextcloud_root_folder()
        if self.nextcloud_project_id:
            return [
                root,
                "projects",
                record_segment(self.nextcloud_project_id),
                "workorders",
                record_segment(self),
            ]
        return [root, "workorders", record_segment(self)]
