from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import content_disposition, request


class NextcloudFileController(http.Controller):
    """Authenticated proxy for controlled Nextcloud preview and download."""

    def _get_document(self, document_id, action):
        document = (
            request.env["nextcloud.document"].sudo().browse(document_id).exists()
        )
        if not document:
            raise NotFound()
        document.with_user(request.env.user)._check_user_can(action)
        return document

    def _file_response(self, document, download):
        data, content_type = (
            request.env["nextcloud.webdav.client"]
            .sudo()
            .download_bytes(document.nextcloud_path)
        )
        disposition = content_disposition(
            document.name or "file",
            "attachment" if download else "inline",
        )
        return request.make_response(
            data,
            headers=[
                (
                    "Content-Type",
                    document.mime_type
                    or content_type
                    or "application/octet-stream",
                ),
                ("Content-Disposition", disposition),
                ("X-Content-Type-Options", "nosniff"),
                ("Cache-Control", "private, no-store"),
            ],
        )

    @http.route(
        "/nextcloud_document/preview/<int:document_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def preview(self, document_id, **kwargs):
        document = self._get_document(document_id, "preview")
        return self._file_response(document, download=False)

    @http.route(
        "/nextcloud_document/download/<int:document_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def download(self, document_id, **kwargs):
        document = self._get_document(document_id, "download")
        return self._file_response(document, download=True)
