from io import BytesIO
from pathlib import Path
import warnings
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16000000
FORMATS = {"PNG": ({".png"}, "image/png"), "JPEG": ({".jpg", ".jpeg"}, "image/jpeg"), "WEBP": ({".webp"}, "image/webp"), "GIF": ({".gif"}, "image/gif")}


def normalize_image(upload):
    if upload.size > MAX_IMAGE_BYTES:
        raise ValidationError({"images": "An image must not exceed 10 MB."})
    data = upload.read(MAX_IMAGE_BYTES + 1)
    upload.seek(0)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError({"images": "An image must not exceed 10 MB."})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                if image_format not in FORMATS:
                    raise ValueError
                extensions, mime = FORMATS[image_format]
                if Path(upload.name).suffix.lower() not in extensions or upload.content_type != mime:
                    raise ValueError
                if image.width * image.height > MAX_IMAGE_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise ValueError
                image.verify()
            with Image.open(BytesIO(data)) as image:
                normalized = ImageOps.exif_transpose(image).convert("RGB" if image_format == "JPEG" else "RGBA")
                # Rebuild pixel data so EXIF, comments and ancillary chunks disappear.
                clean = Image.frombytes(normalized.mode, normalized.size, normalized.tobytes())
                stream = BytesIO()
                clean.save(stream, format=image_format)
                encoded = stream.getvalue()
                if len(encoded) > MAX_IMAGE_BYTES:
                    raise ValueError
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError({"images": "Upload a valid still PNG, JPEG, WebP or GIF, at most 16 megapixels."})
    return ContentFile(encoded, name=Path(upload.name).name)


def store_question_images(question, uploads):
    from django.db import transaction
    from django.db.models import Sum, Max
    from learning.models import ImageStorageLock, QuestionImage

    if not uploads or len(uploads) > 10:
        raise ValidationError({"images": "Upload between 1 and 10 images."})
    files = [normalize_image(upload) for upload in uploads]
    created, written = [], []
    try:
        with transaction.atomic():
            ImageStorageLock.objects.select_for_update().get(pk=1)
            if question.images.count() + len(files) > 20:
                raise ValidationError({"images": "At most 20 images per question are allowed."})
            total = sum(file.size for file in files)
            owner = question.topic.subject.owner_id
            used = QuestionImage.objects.filter(question__topic__subject__owner_id=owner).aggregate(total=Sum("size_bytes"))["total"] or 0
            global_used = QuestionImage.objects.aggregate(total=Sum("size_bytes"))["total"] or 0
            if total > 30 * 1024 * 1024 or used + total > 500 * 1024 * 1024 or global_used + total > 2 * 1024 * 1024 * 1024:
                raise ValidationError({"images": "Image storage quota exceeded."})
            next_order = (question.images.aggregate(value=Max("order"))["value"] or 0) + 1
            for offset, file in enumerate(files):
                image = QuestionImage(question=question, original_name=file.name[:255], size_bytes=file.size, order=next_order + offset)
                image.image.save(file.name, file, save=False)
                written.append((image.image.storage, image.image.name))
                image.full_clean()
                image.save()
                created.append(image)
    except Exception:
        for storage, name in written:
            storage.delete(name)
        raise
    return created
