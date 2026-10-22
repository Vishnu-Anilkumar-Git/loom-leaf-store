from django.core.exceptions import ValidationError

MAX_IMAGE_SIZE = 6 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_image_upload(file):
    if not file:
        return
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError("Images must be smaller than 6 MB.")
    content_type = getattr(file, "content_type", "")
    if content_type and content_type not in ALLOWED_TYPES:
        raise ValidationError("Upload a JPEG, PNG or WebP image.")
    if hasattr(file, "image"):
        # Pillow opens the file to verify it really is an image.
        try:
            file.image.verify()
            file.seek(0)
        except Exception as exc:
            raise ValidationError("This file is not a valid image.") from exc
