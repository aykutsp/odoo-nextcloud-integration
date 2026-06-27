{
    "name": "Nextcloud Document Hub - MRP Work Orders",
    "summary": "Upload MRP work order files to Nextcloud WebDAV",
    "version": "18.0.3.6.0",
    "category": "Manufacturing",
    "author": "Odoo Nextcloud Integration Contributors",
    "license": "LGPL-3",
    "depends": ["odoo_nextcloud_document_hub", "mrp"],
    "data": [
        "views/mrp_workorder_views.xml",
    ],
    "installable": True,
    "application": False,
}
