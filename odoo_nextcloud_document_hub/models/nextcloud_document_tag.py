from odoo import fields, models


class NextcloudDocumentTag(models.Model):
    _name = "nextcloud.document.tag"
    _description = "Nextcloud Document Tag"
    _order = "name"

    name = fields.Char(required=True, index="trigram")
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_unique", "unique(name)", "Etiket adı benzersiz olmalıdır."),
    ]
