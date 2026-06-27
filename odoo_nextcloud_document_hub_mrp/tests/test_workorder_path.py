from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestWorkorderPath(TransactionCase):
    def test_workorder_path_without_project(self):
        product = self.env["product.product"].create({"name": "Test Product"})
        production = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1,
            "product_uom_id": product.uom_id.id,
            "location_src_id": self.env.ref("stock.stock_location_stock").id,
            "location_dest_id": self.env.ref("stock.stock_location_stock").id,
        })
        workorder = self.env["mrp.workorder"].create({
            "name": "Kesim / İstanbul",
            "production_id": production.id,
            "workcenter_id": self.env["mrp.workcenter"].create({
                "name": "Test Workcenter",
            }).id,
        })

        self.assertEqual(
            workorder.get_nextcloud_folder_path(),
            f"odoo/workorders/{workorder.id}-kesim-istanbul",
        )
