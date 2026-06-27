from odoo import models

class ProjectProject(models.Model):
    _name = "project.project"
    _inherit = ["project.project", "nextcloud.document.mixin"]

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        return [self._get_nextcloud_root_folder(), "project", str(self.id)]

    def _nextcloud_automatic_tag_names(self):
        self.ensure_one()
        return [self.display_name, f"PROJECT-{self.id}"]
