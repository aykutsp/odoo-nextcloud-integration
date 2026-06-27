from unittest.mock import Mock, patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestNextcloudClient(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("nextcloud_document_hub.base_url", "https://cloud.example.test")
        params.set_param("nextcloud_document_hub.username", "odoo-user")
        params.set_param("nextcloud_document_hub.app_password", "secret")
        params.set_param(
            "nextcloud_document_hub.webdav_path",
            "/remote.php/dav/files/{username}",
        )

    @patch(
        "odoo.addons.odoo_nextcloud_document_hub.models.nextcloud_client.requests.request"
    )
    def test_connection_uses_propfind(self, request_mock):
        request_mock.return_value = Mock(status_code=207)

        self.env["nextcloud.webdav.client"].test_connection()

        self.assertEqual(request_mock.call_args.args[0], "PROPFIND")
        self.assertEqual(request_mock.call_args.kwargs["headers"]["Depth"], "0")

    @patch(
        "odoo.addons.odoo_nextcloud_document_hub.models.nextcloud_client.requests.request"
    )
    def test_duplicate_filename_gets_suffix(self, request_mock):
        request_mock.side_effect = [
            Mock(status_code=207),
            Mock(status_code=404),
        ]

        path = self.env["nextcloud.webdav.client"].unique_file_path(
            "odoo/projects/1-test",
            "teklif.pdf",
        )

        self.assertEqual(path, "odoo/projects/1-test/teklif-2.pdf")

    @patch(
        "odoo.addons.odoo_nextcloud_document_hub.models.nextcloud_client.requests.request"
    )
    def test_download_returns_content_and_mime_type(self, request_mock):
        request_mock.return_value = Mock(
            status_code=200,
            content=b"pdf-data",
            headers={"Content-Type": "application/pdf"},
        )

        data, mime_type = self.env[
            "nextcloud.webdav.client"
        ].download_bytes("odoo/test.pdf")

        self.assertEqual(data, b"pdf-data")
        self.assertEqual(mime_type, "application/pdf")
        self.assertEqual(request_mock.call_args.args[0], "GET")

    @patch(
        "odoo.addons.odoo_nextcloud_document_hub.models.nextcloud_client.requests.request"
    )
    def test_fast_upload_skips_preflight_exists_check(self, request_mock):
        request_mock.side_effect = [
            Mock(status_code=201),
            Mock(status_code=201),
            Mock(status_code=201),
            Mock(status_code=201),
            Mock(status_code=201),
        ]

        path = self.env["nextcloud.webdav.client"].upload_bytes(
            "fast-cache-test/tasks/1/photos",
            "saha.png",
            b"png-data",
            "image/png",
            check_existing=False,
        )

        methods = [call.args[0] for call in request_mock.call_args_list]
        self.assertEqual(methods, ["MKCOL", "MKCOL", "MKCOL", "MKCOL", "PUT"])
        self.assertEqual(path, "fast-cache-test/tasks/1/photos/saha.png")
        self.assertEqual(
            request_mock.call_args.kwargs["headers"]["If-None-Match"],
            "*",
        )
