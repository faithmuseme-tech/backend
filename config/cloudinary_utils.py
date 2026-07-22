import re
import cloudinary.uploader


def _public_id_from_url(url: str, resource_type: str = 'image') -> str | None:
    """
    Extract the Cloudinary public_id from a secure_url.
    e.g. https://res.cloudinary.com/<cloud>/image/upload/v123/chat_attachments/file.webm
    → chat_attachments/file  (no extension)
    """
    if not url:
        return None
    # Match everything after /upload/v<digits>/ or /upload/
    match = re.search(r'/upload/(?:v\d+/)?(.+)$', url)
    if not match:
        return None
    path = match.group(1)
    # Strip file extension
    public_id = re.sub(r'\.[^.]+$', '', path)
    return public_id


def delete_cloudinary_file(url: str, resource_type: str = 'image') -> None:
    """
    Delete a file from Cloudinary by its URL.
    Silently ignores errors so a failed delete never breaks the main operation.
    resource_type: 'image', 'video' (also covers audio), or 'raw'
    """
    public_id = _public_id_from_url(url, resource_type)
    if not public_id:
        return
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    except Exception:
        pass


# Map file_type stored in ChatMessage → Cloudinary resource_type
CHAT_FILE_RESOURCE_TYPE = {
    'image': 'image',
    'video': 'video',
    'audio': 'video',   # Cloudinary stores audio under resource_type=video
    'doc':   'raw',
}


def delete_chat_file(file_url: str, file_type: str) -> None:
    """Delete a chat attachment from Cloudinary."""
    resource_type = CHAT_FILE_RESOURCE_TYPE.get(file_type, 'image')
    delete_cloudinary_file(file_url, resource_type)
