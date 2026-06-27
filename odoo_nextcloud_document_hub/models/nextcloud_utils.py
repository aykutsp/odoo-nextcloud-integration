import re
import unicodedata
from urllib.parse import quote

TURKISH_TRANSLATION = str.maketrans({
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
})


def slugify(value, fallback="record", max_length=80):
    """Return a filesystem/WebDAV-safe slug for record and folder names."""
    value = (value or "").translate(TURKISH_TRANSLATION)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"[^a-z0-9._ -]+", "-", value)
    value = re.sub(r"[\s_-]+", "-", value).strip("-.")
    if not value:
        value = fallback
    return value[:max_length].strip("-") or fallback


def sanitize_filename(filename, fallback="file"):
    """Return a safe filename while preserving a normalized extension."""
    filename = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if "." in filename and not filename.startswith("."):
        stem, extension = filename.rsplit(".", 1)
        extension = slugify(extension, fallback="", max_length=16)
    else:
        stem, extension = filename, ""
    safe_stem = slugify(stem, fallback=fallback, max_length=120)
    return f"{safe_stem}.{extension}" if extension else safe_stem


def ensure_filename_extension(filename, extension):
    """Append extension when filename has no extension."""
    filename = sanitize_filename(filename)
    extension = (extension or "").strip().lstrip(".")
    if not extension or "." in filename.rsplit("/", 1)[-1]:
        return filename
    safe_extension = slugify(extension, fallback="", max_length=16)
    return f"{filename}.{safe_extension}" if safe_extension else filename


def record_segment(record, label=None):
    name = label or getattr(record, "display_name", None) or getattr(record, "name", None) or "record"
    return f"{record.id}-{slugify(name)}"


def quote_path(path):
    """Quote each path segment without losing slashes."""
    return "/".join(quote(segment) for segment in path.split("/"))


def join_segments(*segments):
    clean = []
    for segment in segments:
        if not segment:
            continue
        if isinstance(segment, (list, tuple)):
            clean.extend(str(item).strip("/") for item in segment if item)
        else:
            clean.append(str(segment).strip("/"))
    return "/".join(item for item in clean if item)
