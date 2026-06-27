from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class NextcloudDocumentCategory(models.Model):
    _name = "nextcloud.document.category"
    _description = "Nextcloud Document Category"
    _parent_store = True
    _parent_name = "parent_id"
    _rec_name = "complete_name"
    _order = "model_name, parent_path, sequence, id"

    name = fields.Char(required=True, translate=True)
    folder_name = fields.Char(required=True)
    complete_name = fields.Char(
        compute="_compute_complete_name",
        recursive=True,
        store=True,
    )
    parent_id = fields.Many2one(
        "nextcloud.document.category",
        index=True,
        ondelete="cascade",
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        "nextcloud.document.category",
        "parent_id",
    )
    allowed_group_ids = fields.Many2many(
        "res.groups",
        "nextcloud_category_res_groups_rel",
        "category_id",
        "group_id",
        string="İzinli Kullanıcı Grupları",
        help=(
            "Boş bırakılırsa klasör, diğer Nextcloud yetkileri kapsamında "
            "tüm kullanıcılara açıktır. Grup seçilirse kullanıcı bu "
            "gruplardan en az birine üye olmalıdır."
        ),
    )
    model_name = fields.Selection(
        [
            ("crm.lead", "CRM Lead"),
            ("project.project", "Project"),
            ("project.task", "Task / Project Work Order"),
            ("mrp.workorder", "MRP Work Order"),
        ],
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "folder_model_unique",
            "unique(model_name, parent_id, folder_name)",
            "Aynı üst klasör altında klasör adı benzersiz olmalıdır.",
        ),
    ]

    @api.constrains("folder_name", "model_name", "parent_id")
    def _check_folder_name(self):
        for category in self:
            if "/" in category.folder_name or "\\" in category.folder_name:
                raise ValidationError(
                    "Klasör adı slash veya backslash içeremez."
                )
            duplicate = self.search_count([
                ("id", "!=", category.id),
                ("model_name", "=", category.model_name),
                ("parent_id", "=", category.parent_id.id or False),
                ("folder_name", "=", category.folder_name),
            ])
            if duplicate:
                raise ValidationError(
                    "Aynı üst klasör altında klasör adı benzersiz olmalıdır."
                )

    @api.depends("folder_name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for category in self:
            names = []
            if category.parent_id:
                names.append(category.parent_id.complete_name)
            if category.folder_name:
                names.append(category.folder_name)
            category.complete_name = " / ".join(names)

    @api.constrains("parent_id", "model_name")
    def _check_parent(self):
        if not self._check_recursion():
            raise ValidationError("Klasör kategorilerinde döngü oluşturulamaz.")
        for category in self:
            if (
                category.parent_id
                and category.parent_id.model_name != category.model_name
            ):
                raise ValidationError(
                    "Üst ve alt klasör aynı Odoo modeline ait olmalıdır."
                )

    def get_folder_path(self):
        self.ensure_one()
        segments = []
        category = self
        while category:
            if category.folder_name:
                segments.insert(0, category.folder_name)
            category = category.parent_id
        return "/".join(segments)

    @api.model
    def _access_filter_enabled(self):
        return not (
            self.env.is_superuser()
            or self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "odoo_nextcloud_document_hub."
                "group_nextcloud_document_manager"
            )
        )

    def _is_accessible_by_user(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if (
            user.id == SUPERUSER_ID
            or user.has_group("base.group_system")
            or user.has_group(
                "odoo_nextcloud_document_hub."
                "group_nextcloud_document_manager"
            )
        ):
            return True
        user_group_ids = set(user.groups_id.ids)
        category = self.sudo()
        while category:
            allowed_group_ids = set(category.allowed_group_ids.ids)
            if allowed_group_ids and not user_group_ids.intersection(
                allowed_group_ids
            ):
                return False
            category = category.parent_id
        return True

    def _check_user_access(self):
        for category in self:
            if not category._is_accessible_by_user():
                raise AccessError(
                    _("Bu Nextcloud klasör kategorisine erişim yetkiniz yok.")
                )
        return True

    def _search(self, domain, offset=0, limit=None, order=None):
        if not self._access_filter_enabled():
            return super()._search(
                domain,
                offset=offset,
                limit=limit,
                order=order,
            )
        candidate_query = super()._search(domain, order=order)
        candidate_ids = [
            row[0] for row in self.env.execute_query(candidate_query.select())
        ]
        allowed_ids = [
            category.id
            for category in self.sudo().browse(candidate_ids)
            if category._is_accessible_by_user(self.env.user)
        ]
        return super()._search(
            [("id", "in", allowed_ids)],
            offset=offset,
            limit=limit,
            order=order,
        )

    def read(self, fields=None, load="_classic_read"):
        self._check_user_access()
        return super().read(fields=fields, load=load)

    @api.model
    def _migrate_default_hierarchy(self):
        engineering = self.env.ref(
            "odoo_nextcloud_document_hub.category_project_02_engineering",
            raise_if_not_found=False,
        )
        software = self.env.ref(
            "odoo_nextcloud_document_hub.category_project_08_software",
            raise_if_not_found=False,
        )
        if (
            engineering
            and software
            and not software.parent_id
            and software.folder_name == "08 - Yazılım"
        ):
            software.write({
                "folder_name": "07 - Yazılım",
                "parent_id": engineering.id,
                "sequence": 70,
            })
        return True
