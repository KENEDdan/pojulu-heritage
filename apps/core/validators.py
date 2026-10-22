from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.template.defaultfilters import filesizeformat

IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx']
AUDIO_EXTENSIONS = ['mp3', 'wav', 'm4a', 'ogg', 'aac']
VIDEO_EXTENSIONS = ['mp4', 'mov', 'webm', 'avi']
GENERAL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + DOCUMENT_EXTENSIONS + AUDIO_EXTENSIONS + VIDEO_EXTENSIONS
DOCUMENT_OR_IMAGE_EXTENSIONS = DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB, matches submissions/form.html copy


def validate_upload_size(value):
    if value.size > MAX_UPLOAD_SIZE:
        raise ValidationError(
            f'File too large ({filesizeformat(value.size)}). '
            f'Maximum allowed size is {filesizeformat(MAX_UPLOAD_SIZE)}.'
        )


validate_image_extension = FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)
validate_document_extension = FileExtensionValidator(allowed_extensions=DOCUMENT_EXTENSIONS)
validate_audio_extension = FileExtensionValidator(allowed_extensions=AUDIO_EXTENSIONS)
validate_video_extension = FileExtensionValidator(allowed_extensions=VIDEO_EXTENSIONS)
validate_document_or_image_extension = FileExtensionValidator(allowed_extensions=DOCUMENT_OR_IMAGE_EXTENSIONS)
validate_general_media_extension = FileExtensionValidator(allowed_extensions=GENERAL_MEDIA_EXTENSIONS)
