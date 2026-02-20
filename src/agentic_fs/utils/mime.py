import mimetypes

# Ensure common Office formats are registered
mimetypes.add_type(
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
)
mimetypes.add_type(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"
)
mimetypes.add_type(
    "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"
)


def guess_mime_type(filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def is_text_type(mime_type: str) -> bool:
    if mime_type.startswith("text/"):
        return True
    text_types = {
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-python",
        "application/x-yaml",
        "application/toml",
    }
    return mime_type in text_types


def is_binary_type(mime_type: str) -> bool:
    return not is_text_type(mime_type)


def needs_extraction(mime_type: str) -> bool:
    extractable = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/msword",
        "application/vnd.ms-excel",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/gif",
        "image/webp",
    }
    return mime_type in extractable
