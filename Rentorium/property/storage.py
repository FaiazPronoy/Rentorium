"""
Storage for the ownership papers.

These used to sit under MEDIA_ROOT next to the photos. The page that showed
them checked who was asking, but the file itself was at a guessable
/media/property_documents/<name>, so the check did nothing.

Files saved here go outside MEDIA_ROOT, so no URL maps to them. The only way
in is property.views.property_document_file, which checks first.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('location', str(settings.PRIVATE_MEDIA_ROOT))
        kwargs.setdefault('base_url', None)
        super().__init__(*args, **kwargs)

    def url(self, name):
        raise ValueError('These files have no public URL. Use the document view.')


private_storage = PrivateStorage()
