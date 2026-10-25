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
