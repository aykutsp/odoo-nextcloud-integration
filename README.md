# Odoo Nextcloud Integration

Professional Nextcloud document management for Odoo 18. This repository
contains a production-oriented Odoo add-on suite that stores business
documents in Nextcloud through WebDAV while keeping access control, metadata,
preview, download approval, and record-level visibility inside Odoo.

## Modules

| Module | Purpose |
| --- | --- |
| `odoo_nextcloud_document_hub` | Core integration for CRM Leads, Projects, Tasks, Deliveries, and Expenses. |
| `odoo_nextcloud_document_hub_mrp` | Optional extension for Manufacturing Work Orders. |

## Highlights

- Upload files from Odoo records directly to Nextcloud over WebDAV.
- Keep Odoo as the business-facing document hub while Nextcloud remains the
  file storage backend.
- Preview browser-supported files through authenticated Odoo routes.
- Download files directly for authorized users or through a manager approval
  workflow for viewer-only users.
- Organize documents with configurable folder categories and nested category
  trees.
- Restrict folder categories by Odoo user groups, including inherited parent
  category restrictions.
- Generate safe, predictable folder paths per CRM, project, task, delivery,
  expense, and work order.
- Prevent accidental overwrites by automatically suffixing duplicate filenames.
- Add manual and automatic tags in Odoo and synchronize them to Nextcloud
  System Tags.
- Hide standard chatter attachment controls for non-admin users so document
  flows stay governed through the integration.
- Optionally keep a copy in `ir.attachment` for environments that require local
  Odoo attachment retention.

## Supported Records

- CRM Leads
- Projects
- Project Tasks
- Stock Pickings / Deliveries
- HR Expenses
- MRP Work Orders through the optional MRP module

## Requirements

- Odoo 18.0
- Python package: `requests`
- A reachable Nextcloud instance
- A Nextcloud user with WebDAV access
- A Nextcloud App Password is strongly recommended

## Installation

1. Copy this repository into a directory included in your Odoo `addons_path`.
2. Restart the Odoo service.
3. Update the Apps list.
4. Install **Nextcloud Document Hub**.
5. If Manufacturing support is needed, install **Nextcloud Document Hub - MRP
   Work Orders** after the core module.

Command-line example:

```bash
./odoo-bin -d DATABASE \
  --addons-path=/path/to/odoo/addons,/path/to/odoo-nextcloud-integration \
  -i odoo_nextcloud_document_hub \
  --stop-after-init
```

To install the MRP extension:

```bash
./odoo-bin -d DATABASE \
  --addons-path=/path/to/odoo/addons,/path/to/odoo-nextcloud-integration \
  -i odoo_nextcloud_document_hub_mrp \
  --stop-after-init
```

## Configuration

Open **Settings > Nextcloud Settings** in Odoo and configure:

| Setting | Description |
| --- | --- |
| Base URL | Root URL of the Nextcloud instance, for example `https://cloud.example.com`. |
| Username | Nextcloud username used by the integration. |
| App Password | Nextcloud app password or password for WebDAV authentication. |
| Root Folder | Top-level folder under the user's Nextcloud files, for example `odoo`. |
| WebDAV Path | Defaults to `/remote.php/dav/files/{username}`. |
| Max Upload Size | Upload limit in MB. The default is `500 MB`. |
| Keep Odoo Attachment | Optional local `ir.attachment` copy after upload. |

Use **Test Connection** after saving the settings.

## Permissions

The module separates access into dedicated Odoo security groups:

| Group | Capability |
| --- | --- |
| Nextcloud Document Viewer | View visible document records and preview supported files. |
| Nextcloud Document Downloader | Download files directly. |
| Nextcloud Document Uploader | Upload files and photos from supported records. |
| Nextcloud Document Manager | Manage document records, rename files in Odoo, and approve download requests. |

System administrators can configure the Nextcloud connection. Every preview,
download, and open action also checks access to the related Odoo record.

## Folder Strategy

The integration builds deterministic Nextcloud paths using safe slugs. Examples:

| Record | Folder pattern |
| --- | --- |
| CRM Lead | `odoo/crm/{odoo-id}/{selected-category}` |
| Project | `odoo/project/{odoo-id}/{main-category}/{sub-category}` |
| Project Task | `odoo/projects/{project-id}-{slug}/tasks/{id}-{slug}` |
| Standalone Task | `odoo/tasks/{id}-{slug}` |
| Task Photo | `odoo/projects/{project-id}-{slug}/tasks/{id}-{slug}/photos` |
| Delivery | `odoo/deliveries/{id}-{slug}` |
| Expense | `odoo/expenses/{id}-{slug}` |
| Work Order | `odoo/workorders/{id}-{slug}` |
| Project Work Order | `odoo/projects/{project-id}-{slug}/workorders/{id}-{slug}` |

Project and CRM uploads use selectable folder categories. Categories can be
managed from **Project > Configuration > Nextcloud Folder Categories** and can
be nested into parent and child folders.

When a parent category contains children, users select the final child category
as the upload destination. Parent group restrictions are inherited by children.

## Document Workspace

The **Cloud** application in Odoo provides:

- **All Files**: a searchable document workspace filtered by record access and
  category permissions.
- **My Download Requests**: the current user's pending, approved, rejected, and
  expired requests.
- **Request Approvals**: manager and administrator approval screen for download
  requests.

Document rows expose actions for preview, download, download request, rename,
opening the related Odoo record, and opening the file in Nextcloud.

## Download Approval Flow

Users in the Downloader group can download directly. Viewer-only users can
request access instead. Managers and administrators receive Odoo activities for
new requests and can approve or reject them.

Approved requests are time-limited. The approval validity period can be changed
in the Nextcloud settings.

## Security Model

- Nextcloud credentials are stored server-side and are never sent to the
  browser.
- Preview and download routes use Odoo `auth=user` protection.
- Related Odoo record access is checked before document access is granted.
- Category group restrictions are applied to upload lists, document lists,
  preview, and download actions.
- App passwords are not written to logs.
- Deleting an Odoo document record does not delete the file from Nextcloud.
- Failed uploads are kept as error records with the error message for audit and
  troubleshooting.

## File Type Behavior

Browser-previewable files include common image, text, audio, video, PDF, JSON,
and XML content types. Unsupported file types remain downloadable according to
the user's permissions or approval state.

Task photo uploads accept:

- JPEG
- PNG
- WebP
- HEIC
- HEIF

## Testing

Run Odoo tests with an Odoo 18 test database:

```bash
./odoo-bin -d TEST_DATABASE \
  --addons-path=/path/to/odoo/addons,/path/to/odoo-nextcloud-integration \
  -i odoo_nextcloud_document_hub \
  --test-enable \
  --stop-after-init
```

This repository contains module tests, but a complete Odoo 18 environment and a
database are required to execute them.

## Repository Layout

```text
.
|-- odoo_nextcloud_document_hub/
|   |-- controllers/
|   |-- data/
|   |-- models/
|   |-- security/
|   |-- static/
|   |-- tests/
|   |-- views/
|   `-- wizards/
`-- odoo_nextcloud_document_hub_mrp/
    |-- models/
    |-- tests/
    `-- views/
```

## License

This project is licensed under LGPL-3, matching the license declared in the
Odoo module manifests.
