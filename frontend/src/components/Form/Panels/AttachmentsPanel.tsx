import { useRef, useState, useCallback } from 'react';
import { Stack, Text, Button, Loader } from '@mantine/core';
import { IconUpload } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import {
  useSearchQuery,
  useCreateMutation,
  useDeleteBulkMutation,
} from '@/services/api/crudApi';
import {
  AttachmentPreview,
  ImageGalleryModal,
  isImageMimetype,
} from '@/components/Attachment';
import type { GalleryItem } from '@/components/Attachment';
import { attachmentContentUrl } from '@/utils/attachmentUrls';

const PAGE_SIZE = 80;

interface AttachmentsPanelProps {
  resModel: string;
  resId: number;
}

export function AttachmentsPanel({ resModel, resId }: AttachmentsPanelProps) {
  const { t } = useTranslation(['common']);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [limit, setLimit] = useState(PAGE_SIZE);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [galleryIndex, setGalleryIndex] = useState(0);

  const { data: attachmentsData, isLoading } = useSearchQuery({
    model: 'attachments',
    fields: [
      'id',
      'name',
      'size',
      'mimetype',
      'storage_file_url',
      'storage_file_id',
      'is_voice',
      'show_preview',
    ],
    filter: [
      ['res_model', '=', resModel],
      ['res_id', '=', resId],
      ['folder', '=', false],
    ],
    sort: 'id',
    order: 'desc',
    limit,
  });

  const [createAttachment, { isLoading: isUploading }] = useCreateMutation();
  const [deleteAttachment] = useDeleteBulkMutation();

  const attachments = attachmentsData?.data || [];
  const total = attachmentsData?.total || 0;
  const hasMore = total > attachments.length;

  // Image gallery items
  const imageAttachments = attachments.filter((att: any) =>
    isImageMimetype(att.mimetype),
  );
  const galleryItems: GalleryItem[] = imageAttachments.map((att: any) => ({
    id: att.id,
    name: att.name || undefined,
    mimetype: att.mimetype || undefined,
    checksum: att.checksum || undefined,
  }));

  const handleOpenGallery = useCallback(
    (attachmentId: number) => {
      const index = imageAttachments.findIndex(
        (att: any) => att.id === attachmentId,
      );
      if (index !== -1) {
        setGalleryIndex(index);
        setGalleryOpen(true);
      }
    },
    [imageAttachments],
  );

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    for (const file of Array.from(files)) {
      const base64 = await fileToBase64(file);

      try {
        await createAttachment({
          model: 'attachments',
          values: {
            name: file.name,
            res_model: resModel,
            res_id: resId,
            mimetype: file.type || 'application/octet-stream',
            size: file.size,
            content: base64,
            folder: false,
            public: false,
          },
        }).unwrap();
      } catch (error) {
        console.error('Failed to upload attachment:', error);
      }
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteAttachment({
        model: 'attachments',
        ids: [id],
      }).unwrap();
    } catch (error) {
      console.error('Failed to delete attachment:', error);
    }
  };

  const handleDownload = (id: number) => {
    const a = document.createElement('a');
    a.href = attachmentContentUrl(id);
    a.download = attachments.find((att: any) => att.id === id)?.name || 'file';
    a.click();
  };

  const handleLoadMore = () => {
    setLimit(prev => prev + PAGE_SIZE);
  };

  if (isLoading && attachments.length === 0) {
    return (
      <Stack align="center" py="xl">
        <Loader size="sm" />
      </Stack>
    );
  }

  return (
    <Stack gap="sm">
      {/* Upload button */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={e => handleUpload(e.target.files)}
      />
      <Button
        variant="light"
        size="compact-sm"
        leftSection={<IconUpload size={14} />}
        onClick={() => fileInputRef.current?.click()}
        loading={isUploading}
        fullWidth>
        {t('common:upload', 'Загрузить файл')}
      </Button>

      {/* Attachment list with AttachmentPreview */}
      {attachments.length === 0 && (
        <Text size="sm" c="dimmed" ta="center" py="md">
          {t('common:noAttachments', 'Нет вложений')}
        </Text>
      )}

      {attachments.map((att: any) => (
        <AttachmentPreview
          key={att.id}
          attachment={{
            id: att.id,
            name: att.name,
            mimetype: att.mimetype,
            size: att.size,
            storage_file_url: att.storage_file_url,
            is_voice: att.is_voice,
          }}
          onDelete={() => handleDelete(att.id)}
          onDownload={() => handleDownload(att.id)}
          onClick={
            isImageMimetype(att.mimetype)
              ? () => handleOpenGallery(att.id)
              : undefined
          }
          showPreview={att.show_preview !== false}
          previewSize={80}
        />
      ))}

      {hasMore && (
        <Button
          variant="subtle"
          size="compact-sm"
          onClick={handleLoadMore}
          loading={isLoading}
          fullWidth>
          {t('common:loadMore', 'Загрузить ещё')} ({total - attachments.length})
        </Button>
      )}

      {/* Image gallery modal */}
      <ImageGalleryModal
        opened={galleryOpen}
        onClose={() => setGalleryOpen(false)}
        items={galleryItems}
        initialIndex={galleryIndex}
        onDownload={item => item.id && handleDownload(item.id)}
      />
    </Stack>
  );
}

// ─── Helpers ──────────────────────────────────────────────────

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
