import logging
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests

from odoo import _, models
from odoo.exceptions import UserError

from .nextcloud_utils import quote_path, sanitize_filename, slugify

_logger = logging.getLogger(__name__)


class NextcloudWebdavClient(models.AbstractModel):
    _name = "nextcloud.webdav.client"
    _description = "Nextcloud WebDAV Client"
    _known_folders = set()

    def _get_config(self):
        params = self.env["ir.config_parameter"].sudo()
        base_url = params.get_param(
            "nextcloud_document_hub.base_url",
            "https://cloud.example.com",
        )
        username = params.get_param("nextcloud_document_hub.username")
        password = params.get_param("nextcloud_document_hub.app_password")
        webdav_path = params.get_param(
            "nextcloud_document_hub.webdav_path", "/remote.php/dav/files/{username}"
        )
        root_folder = params.get_param("nextcloud_document_hub.root_folder", "odoo")
        settings_max_upload_mb = 500
        if not username or not password:
            settings = self.env["nextcloud.config.settings"].sudo().search(
                [],
                order="id",
                limit=1,
            )
            if settings:
                base_url = settings.nextcloud_base_url or base_url
                username = settings.nextcloud_username or username
                password = settings.nextcloud_app_password or password
                webdav_path = settings.nextcloud_webdav_path or webdav_path
                root_folder = settings.nextcloud_root_folder or root_folder
                settings_max_upload_mb = (
                    settings.nextcloud_max_upload_mb or 500
                )
        try:
            max_upload_mb = int(
                params.get_param(
                    "nextcloud_document_hub.max_upload_mb",
                    str(settings_max_upload_mb),
                )
                or settings_max_upload_mb
            )
        except (TypeError, ValueError):
            max_upload_mb = 500
        try:
            webdav_path = webdav_path.format(username=username)
        except (KeyError, ValueError) as exc:
            raise UserError(
                _("WebDAV yolu yalnızca {username} değişkenini içerebilir.")
            ) from exc
        if not base_url or not username or not password:
            raise UserError(
                _(
                    "Nextcloud bağlantı ayarları eksik. Lütfen Ayarlar > "
                    "Nextcloud bölümünü doldurun."
                )
            )
        return {
            "base_url": base_url.rstrip("/") + "/",
            "username": username,
            "password": password,
            "webdav_path": webdav_path.strip("/"),
            "root_folder": slugify(root_folder, fallback="odoo"),
            "max_upload_mb": max(max_upload_mb, 1),
        }

    def _build_url(self, path=""):
        cfg = self._get_config()
        webdav_base = urljoin(
            cfg["base_url"],
            quote_path(cfg["webdav_path"].strip("/")) + "/",
        )
        return urljoin(webdav_base, quote_path(path.strip("/")))

    def _request(self, method, path="", **kwargs):
        cfg = self._get_config()
        url = self._build_url(path)
        timeout = kwargs.pop("timeout", 30)
        try:
            response = requests.request(
                method,
                url,
                auth=(cfg["username"], cfg["password"]),
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            _logger.exception("Nextcloud WebDAV network error")
            raise UserError(
                _("Nextcloud sunucusuna bağlanılamadı. Ağ adresini ve servisi kontrol edin.")
            ) from exc
        if response.status_code in (401, 403):
            raise UserError(
                _(
                    "Nextcloud yetki hatası. Kullanıcı adı veya app password "
                    "bilgisini kontrol edin."
                )
            )
        if response.status_code == 413:
            raise UserError(_("Nextcloud dosyayı çok büyük olduğu için reddetti (HTTP 413)."))
        if (
            response.status_code >= 400
            and response.status_code not in (404, 405, 409, 412)
        ):
            raise UserError(_("Nextcloud WebDAV hatası: HTTP %s") % response.status_code)
        return response

    def _dav_request(self, method, dav_path, **kwargs):
        cfg = self._get_config()
        url = urljoin(
            cfg["base_url"],
            "remote.php/dav/" + quote_path(dav_path.strip("/")),
        )
        timeout = kwargs.pop("timeout", 8)
        try:
            return requests.request(
                method,
                url,
                auth=(cfg["username"], cfg["password"]),
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise UserError(
                _("Nextcloud etiket servisine bağlanılamadı.")
            ) from exc

    def test_connection(self):
        response = self._request("PROPFIND", "", headers={"Depth": "0"})
        if response.status_code not in (200, 207):
            if response.status_code == 404:
                raise UserError(
                    _("WebDAV adresi bulunamadı. Endpoint şablonunu kontrol edin.")
                )
            raise UserError(
                _("Nextcloud bağlantı testi başarısız: HTTP %s") % response.status_code
            )
        return True

    def ensure_folder(self, folder_path):
        """Create folder_path recursively using MKCOL. Ignores already-existing folders."""
        parts = [part for part in folder_path.strip("/").split("/") if part]
        current = []
        cfg = self._get_config()
        for part in parts:
            current.append(part)
            folder = "/".join(current)
            cache_key = (
                cfg["base_url"],
                cfg["webdav_path"],
                cfg["username"],
                folder,
            )
            if cache_key in self._known_folders:
                continue
            response = self._request("MKCOL", folder)
            if response.status_code not in (201, 405):
                if response.status_code == 409:
                    raise UserError(
                        _(
                            "Nextcloud klasörü oluşturulamadı (%s). WebDAV "
                            "endpoint ve üst klasör yolunu kontrol edin."
                        )
                        % folder
                    )
                raise UserError(
                    _("Nextcloud klasörü oluşturulamadı: %s (HTTP %s)")
                    % (folder, response.status_code)
                )
            self._known_folders.add(cache_key)

    def exists(self, path):
        response = self._request("PROPFIND", path, headers={"Depth": "0"})
        return response.status_code in (200, 207)

    def unique_file_path(self, folder_path, filename):
        if not self.exists(f"{folder_path}/{filename}"):
            return f"{folder_path}/{filename}"
        if "." in filename:
            stem, ext = filename.rsplit(".", 1)
            ext = "." + ext
        else:
            stem, ext = filename, ""
        counter = 2
        while True:
            candidate = f"{folder_path}/{stem}-{counter}{ext}"
            if not self.exists(candidate):
                return candidate
            counter += 1

    def upload_bytes(
        self,
        folder_path,
        filename,
        data,
        content_type=None,
        check_existing=True,
    ):
        cfg = self._get_config()
        max_bytes = cfg["max_upload_mb"] * 1024 * 1024
        if len(data) > max_bytes:
            raise UserError(_("Dosya boyutu limiti aşıldı. Limit: %s MB") % cfg["max_upload_mb"])
        filename = sanitize_filename(filename)
        self.ensure_folder(folder_path)
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        if check_existing:
            full_path = self.unique_file_path(folder_path, filename)
        else:
            full_path = f"{folder_path}/{filename}"
            headers["If-None-Match"] = "*"
        response = self._request(
            "PUT",
            full_path,
            data=data,
            headers=headers,
            timeout=120,
        )
        if response.status_code == 412:
            headers.pop("If-None-Match", None)
            full_path = self.unique_file_path(folder_path, filename)
            response = self._request(
                "PUT",
                full_path,
                data=data,
                headers=headers,
                timeout=120,
            )
        if response.status_code not in (200, 201, 204):
            raise UserError(_("Dosya Nextcloud'a yüklenemedi: HTTP %s") % response.status_code)
        return full_path

    def download_bytes(self, path):
        response = self._request("GET", path, timeout=120)
        if response.status_code == 404:
            raise UserError(_("Nextcloud dosyası bulunamadı."))
        if response.status_code != 200:
            raise UserError(
                _("Dosya Nextcloud'dan indirilemedi: HTTP %s")
                % response.status_code
            )
        return response.content, response.headers.get("Content-Type")

    def _get_file_id(self, path):
        body = """<?xml version="1.0"?>
            <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
                <d:prop><oc:fileid/></d:prop>
            </d:propfind>
        """
        response = self._request(
            "PROPFIND",
            path,
            headers={
                "Depth": "0",
                "Content-Type": "application/xml",
            },
            data=body.encode(),
            timeout=8,
        )
        if response.status_code != 207:
            raise UserError(_("Nextcloud file ID alınamadı."))
        root = ElementTree.fromstring(response.content)
        file_id = root.find(".//{http://owncloud.org/ns}fileid")
        if file_id is None or not file_id.text:
            raise UserError(_("Nextcloud file ID yanıtı boş."))
        return file_id.text

    def _system_tags(self):
        body = """<?xml version="1.0"?>
            <d:propfind xmlns:d="DAV:">
                <d:prop><d:displayname/></d:prop>
            </d:propfind>
        """
        response = self._dav_request(
            "PROPFIND",
            "systemtags",
            headers={
                "Depth": "1",
                "Content-Type": "application/xml",
            },
            data=body.encode(),
            timeout=8,
        )
        if response.status_code != 207:
            raise UserError(
                _("Nextcloud sistem etiketleri okunamadı: HTTP %s")
                % response.status_code
            )
        tags = {}
        root = ElementTree.fromstring(response.content)
        for item in root.findall(".//{DAV:}response"):
            href = item.find("{DAV:}href")
            name = item.find(".//{DAV:}displayname")
            if href is None or name is None or not name.text:
                continue
            tag_id = href.text.rstrip("/").rsplit("/", 1)[-1]
            if tag_id.isdigit():
                tags[name.text.casefold()] = tag_id
        return tags

    def _create_system_tag(self, name):
        response = self._dav_request(
            "POST",
            "systemtags",
            headers={"Content-Type": "application/json"},
            json={
                "name": name,
                "userVisible": True,
                "userAssignable": True,
            },
            timeout=8,
        )
        if response.status_code not in (200, 201):
            raise UserError(
                _("Nextcloud etiketi oluşturulamadı: %s") % name
            )
        location = response.headers.get("Location", "")
        tag_id = location.rstrip("/").rsplit("/", 1)[-1]
        if not tag_id:
            tag_id = self._system_tags().get(name.casefold())
        return tag_id

    def sync_system_tags(self, path, tag_names):
        tag_names = [name.strip() for name in tag_names if name.strip()]
        if not tag_names:
            return True
        file_id = self._get_file_id(path)
        existing_tags = self._system_tags()
        for name in tag_names:
            tag_id = existing_tags.get(name.casefold())
            if not tag_id:
                tag_id = self._create_system_tag(name)
                existing_tags[name.casefold()] = tag_id
            response = self._dav_request(
                "PUT",
                f"systemtags-relations/files/{file_id}/{tag_id}",
                timeout=8,
            )
            if response.status_code not in (200, 201, 204):
                raise UserError(
                    _("Nextcloud etiketi dosyaya bağlanamadı: %s") % name
                )
        return True

    def make_files_url(self, folder_path, filename=None):
        cfg = self._get_config()
        # Nextcloud UI direct file browser URL. It still requires Nextcloud authentication.
        url = urljoin(cfg["base_url"], "apps/files/files")
        if filename:
            return f"{url}?dir=/{quote_path(folder_path)}&openfile={quote_path(filename)}"
        return f"{url}?dir=/{quote_path(folder_path)}"
