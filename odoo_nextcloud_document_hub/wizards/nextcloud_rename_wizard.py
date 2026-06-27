from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.nextcloud_utils import ensure_filename_extension


class NextcloudRenameWizard(models.TransientModel):
    _name = "nextcloud.rename.wizard"
    _description = "Nextcloud Rename Wizard"

    document_id = fields.Many2one(
        "nextcloud.document",
        required=True,
        readonly=True,
    )
    name = fields.Char(required=True)

    def action_rename(self):
        self.ensure_one()
        self.document_id._check_user_can("manage")
        extension = ""
        if self.document_id.name and "." in self.document_id.name:
            extension = self.document_id.name.rsplit(".", 1)[-1]
        name = ensure_filename_extension(self.name, extension)
        if not name:
            raise UserError(_("Geçerli bir dosya adı girin."))
        self.document_id.write({"name": name})
        return {"type": "ir.actions.act_window_close"}
