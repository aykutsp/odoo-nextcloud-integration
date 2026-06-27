from odoo import models

from .nextcloud_utils import join_segments, record_segment


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "nextcloud.document.mixin"]

    def _nextcloud_folder_segments(self):
        self.ensure_one()
        root = self._get_nextcloud_root_folder()
        if self.project_id:
            return [
                root,
                "projects",
                record_segment(self.project_id),
                "tasks",
                record_segment(self),
            ]
        return [root, "tasks", record_segment(self)]

    def get_nextcloud_photo_folder_path(self):
        self.ensure_one()
        return join_segments(self._nextcloud_folder_segments(), "photos")
