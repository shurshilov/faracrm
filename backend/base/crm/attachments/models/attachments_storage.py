from backend.base.system.dotorm.dotorm.fields import Char, Integer, Selection
from backend.base.system.dotorm.dotorm.model import DotModel


class AttachmentStorage(DotModel):
    __table__ = "attachments_storage"

    id: int = Integer(primary_key=True)
    name: str = Char()
    type: str = Selection(
        options=[
            ("file", "File"),
            ("ftp", "FTP/SFTP"),
            ("google", "Google gdrive"),
            ("microsoft", "Microsoft onedrive"),
            ("yandex", "Yandex cloud"),
            ("next", "Next cloud"),
            ("url", "URL"),
        ],
        default="file",
        string="Storage",
    )
