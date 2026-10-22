"""
Member photo handling.

Uploads are decoded with Pillow, checked by their actual content (not the file
name or the browser's content type), then re-encoded as a fresh JPEG. Only the
re-encoded bytes are stored, so metadata (including GPS location) and anything
appended to the original file are dropped.

Files are never served from a public media URL. Clients get short-lived signed
URLs (see signed_photo_url) that apps.profiles.views.PhotoFileView verifies.
"""
import io
import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.signing import BadSignature, Signer
from django.urls import reverse
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Refuse decompression bombs well before Pillow's own limit.
MAX_PIXELS = 40_000_000
# Longest side of the stored image.
MAX_DIMENSION = 1600
MIN_DIMENSION = 200


class PhotoRejected(ValueError):
    """The upload isn't an acceptable photo; the message is safe to show the member."""


def process_upload(upload) -> tuple[ContentFile, int, int]:
    """Validate an uploaded file and return (jpeg_file, width, height)."""
    if upload.size > settings.PROFILE_PHOTO_MAX_BYTES:
        limit_mb = settings.PROFILE_PHOTO_MAX_BYTES // (1024 * 1024)
        raise PhotoRejected(f"The photo is larger than {limit_mb} MB. Please choose a smaller file.")

    try:
        upload.seek(0)
        with Image.open(upload) as probe:
            image_format = probe.format
            width, height = probe.size
            if image_format not in ALLOWED_FORMATS:
                raise PhotoRejected("Upload a JPEG, PNG or WebP photo.")
            if width * height > MAX_PIXELS:
                raise PhotoRejected("The photo's dimensions are too large.")
            probe.verify()  # structural check; the image must be reopened afterwards

        upload.seek(0)
        with Image.open(upload) as image:
            image = ImageOps.exif_transpose(image)  # honour camera rotation before metadata is dropped
            if min(image.size) < MIN_DIMENSION:
                raise PhotoRejected(f"The photo is too small. Use one at least {MIN_DIMENSION} pixels on each side.")
            image = image.convert("RGB")
            image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
            return ContentFile(output.getvalue(), name="photo.jpg"), image.width, image.height
    except PhotoRejected:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise PhotoRejected("This file isn't a photo we can read. Upload a JPEG, PNG or WebP image.") from exc


_signer = Signer(salt="apps.profiles.photo-url")


def signed_photo_url(photo, request=None) -> str:
    """A URL for the photo file that works until PHOTO_URL_TTL_SECONDS from now."""
    expires = int(time.time()) + settings.PHOTO_URL_TTL_SECONDS
    token = _signer.sign(f"{photo.public_id.hex}:{expires}")
    path = reverse("profiles:photo-file", kwargs={"token": token})
    if settings.API_PUBLIC_URL:
        return f"{settings.API_PUBLIC_URL.rstrip('/')}{path}"
    return request.build_absolute_uri(path) if request else path


def photo_id_from_token(token: str) -> str | None:
    """The photo's public id (hex) if the token is genuine and unexpired, else None."""
    try:
        value = _signer.unsign(token)
        photo_hex, expires = value.split(":")
        if int(expires) < time.time():
            return None
        return photo_hex
    except (BadSignature, ValueError):
        return None
