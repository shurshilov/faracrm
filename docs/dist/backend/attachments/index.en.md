# Attachments — overview

The `attachments` module manages files across all of FARA. Supports multiple storage providers (local disk, Google Drive, Yandex.Disk) through the Strategy pattern. Only one storage can be active — it accepts new files.

## Architecture

Four related entities:

```mermaid
graph TB
    A[Attachment<br/>file with metadata]
    S[AttachmentStorage<br/>configured storage]
    R[AttachmentRoute<br/>placement rule]
    C[AttachmentCache<br/>cloud folder ID cache]
    ST[Strategy<br/>provider]

    A -->|storage_id| S
    A -->|res_model + res_id| Record[Any CRM record]
    S -->|type| ST
    R -->|storage_id| S
    R -->|model| Record
    C -->|storage_id + route_id| S

    style A fill:#dde7ff,stroke:#5170c4
    style ST fill:#d1f7c4,stroke:#2c6c1c
```

| Class | Stores | Example |
|-------|--------|---------|
| `Attachment` | File + polymorphic link | `name="contract.pdf", res_model="sale", res_id=42` |
| `AttachmentStorage` | Provider configuration | "Office's Google Drive" — type=google, active=true |
| `AttachmentRoute` | Folder template | "sale → Sales Orders/SO-{id}-{name}" |
| `AttachmentCache` | Cloud folder IDs | "storage=2 + sale#42 → folder_id=abc123" |
| `Strategy` | Provider work logic | `FileStoreStrategy`, `GoogleDriveStrategy`, `YandexDiskStrategy` |

## Strategy pattern

`StorageStrategyBase` (in `attachments/strategies/strategy.py`) is the base class. Each provider implements its own subclass:

```python
class StorageStrategyBase(ABC):
    strategy_type: str = ""

    @abstractmethod
    async def create_file(self, storage, attachment, content, filename, ...): ...

    @abstractmethod
    async def read_file(self, storage, attachment) -> bytes | None: ...

    @abstractmethod
    async def update_file(self, storage, attachment, content=None, ...): ...

    @abstractmethod
    async def delete_file(self, storage, attachment) -> bool: ...

    # Optional — for cloud storage
    async def create_folder(self, storage, folder_name, parent_id=None): ...
    async def get_folder_path(self, storage, res_model, res_id): ...
    async def get_credentials(self, storage): ...
    async def validate_connection(self, storage) -> bool: ...
```

Registration:

```python
from backend.base.crm.attachments.strategies import register_strategy

class GoogleDriveStrategy(StorageStrategyBase):
    strategy_type = "google"
    ...

register_strategy(GoogleDriveStrategy)
```

After registration, `AttachmentStorage(type="google")` will automatically work through this strategy.

## Polymorphic link

Like `Activity`, `Attachment` links to any record via `res_model` + `res_id`:

```python
# Attach a file to a lead
await Attachment.create_file(
    res_model="lead",
    res_id=lead.id,
    name="Contract.pdf",
    content=file_bytes,
    mimetype="application/pdf",
)

# Get all files of a lead
attachments = await Attachment.search(
    filter=[("res_model", "=", "lead"), ("res_id", "=", lead.id)],
)
```

This is cheaper than having an FK on each table. Downside — no cascade on deletion (see below).

## What's next

- [Local storage](filestore.md) — `FileStoreStrategy`, simple disk write
- [Google Drive](google.md) — OAuth, Shared Drives, API specifics
- [Yandex.Disk](yandex.md) — REST API, redirect quirks
