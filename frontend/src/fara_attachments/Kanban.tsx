import { useCallback, useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Stack,
  Box,
  Tooltip,
  ActionIcon,
  SimpleGrid,
  Image,
  Loader,
} from '@mantine/core';
import {
  IconDownload,
  IconEye,
  IconFolder,
  IconLock,
  IconWorld,
  IconMicrophone,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useSearchQuery } from '@/services/api/crudApi';
import { GetListParams, GetListResult } from '@/services/api/crudTypes';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import {
  Attachment,
  SchemaAttachmentStorage,
} from '@/services/api/attachments';
import { Kanban } from '@/components/Kanban';
import { FileIcon } from '@/components/Attachment/FileIcon';
import {
  ImageGalleryModal,
  GalleryItem,
} from '@/components/Attachment/ImageGalleryModal';
import {
  isImageMimetype,
  isAudioMimetype,
  isVideoMimetype,
  formatFileSize,
} from '@/components/Attachment/fileIcons';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { selectCurrentSession } from '@/slices/authSlice';
import classes from './Kanban.module.css';

// ==================== ATTACHMENT CARD ====================

interface AttachmentCardProps {
  attachment: Attachment;
  onClick: () => void;
  onOpenGallery: () => void;
}

function AttachmentCard({
  attachment,
  onClick,
  onOpenGallery,
}: AttachmentCardProps) {
  const session = useSelector(selectCurrentSession);
  const [thumbSrc, setThumbSrc] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const isImage = isImageMimetype(attachment.mimetype);
  const isAudio = isAudioMimetype(attachment.mimetype);
  const isVideo = isVideoMimetype(attachment.mimetype);

  // Загрузка превью для карточки
  useEffect(() => {
    if (!isImage || !attachment.id || !session?.token) return;

    setIsLoading(true);
    fetch(`${API_BASE_URL}/attachments/${attachment.id}/preview?w=200&h=200`, {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(res => (res.ok ? res.blob() : Promise.reject()))
      .then(blob => {
        const reader = new FileReader();
        reader.onload = () => setThumbSrc(reader.result as string);
        reader.readAsDataURL(blob);
      })
      .catch(() => setThumbSrc(null))
      .finally(() => setIsLoading(false));
  }, [attachment.id, isImage, session?.token]);

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!attachment.id || !session?.token) return;

    fetch(`${API_BASE_URL}/attachments/${attachment.id}/download`, {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(res => res.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = attachment.name || 'file';
        a.click();
        URL.revokeObjectURL(url);
      });
  };

  const handlePreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isImage) {
      onOpenGallery();
    }
  };

  // Определяем тип бейджа
  const getTypeBadge = () => {
    if (attachment.folder) {
      return (
        <Badge size="xs" color="yellow" leftSection={<IconFolder size={10} />}>
          Папка
        </Badge>
      );
    }
    if (attachment.is_voice) {
      return (
        <Badge
          size="xs"
          color="pink"
          leftSection={<IconMicrophone size={10} />}>
          Голос
        </Badge>
      );
    }
    if (isImage) {
      return (
        <Badge size="xs" color="teal">
          Изображение
        </Badge>
      );
    }
    if (isVideo) {
      return (
        <Badge size="xs" color="violet">
          Видео
        </Badge>
      );
    }
    if (isAudio) {
      return (
        <Badge size="xs" color="pink">
          Аудио
        </Badge>
      );
    }
    // Показываем расширение из mimetype
    const ext = attachment.mimetype?.split('/')[1]?.toUpperCase();
    if (ext) {
      return (
        <Badge size="xs" color="gray" variant="light">
          {ext}
        </Badge>
      );
    }
    return null;
  };

  return (
    <>
      <Card
        className={classes.card}
        shadow="sm"
        padding={0}
        radius="md"
        withBorder
        onClick={onClick}>
        {/* Превью область */}
        <Box className={classes.previewArea}>
          {isLoading ? (
            <Loader size="sm" />
          ) : isImage && thumbSrc ? (
            <Image
              src={thumbSrc}
              alt={attachment.name || ''}
              fit="cover"
              h="100%"
              w="100%"
            />
          ) : (
            <Box className={classes.iconArea}>
              <FileIcon mimetype={attachment.mimetype} size={48} />
            </Box>
          )}

          {/* Бейдж публичности */}
          <Box className={classes.accessBadge}>
            <Tooltip label={attachment.public ? 'Публичный' : 'Приватный'}>
              <ActionIcon
                size="xs"
                variant="filled"
                color={attachment.public ? 'green' : 'gray'}
                radius="xl">
                {attachment.public ? (
                  <IconWorld size={12} />
                ) : (
                  <IconLock size={12} />
                )}
              </ActionIcon>
            </Tooltip>
          </Box>
        </Box>

        {/* Информация */}
        <Stack gap={6} p="sm">
          <Tooltip label={attachment.name} disabled={!attachment.name}>
            <Text size="sm" fw={500} lineClamp={1}>
              {attachment.name || 'Без имени'}
            </Text>
          </Tooltip>

          <Group justify="space-between" gap={4}>
            <Text size="xs" c="dimmed">
              {formatFileSize(attachment.size)}
            </Text>
            {getTypeBadge()}
          </Group>

          {attachment.res_model && (
            <Text size="xs" c="dimmed" lineClamp={1}>
              {attachment.res_model} #{attachment.res_id}
            </Text>
          )}

          {/* Кнопки действий */}
          <Group gap={4} mt={4}>
            {isImage && (
              <Tooltip label="Просмотр">
                <ActionIcon
                  size="sm"
                  variant="light"
                  color="blue"
                  onClick={handlePreview}>
                  <IconEye size={14} />
                </ActionIcon>
              </Tooltip>
            )}
            <Tooltip label="Скачать">
              <ActionIcon
                size="sm"
                variant="light"
                color="gray"
                onClick={handleDownload}>
                <IconDownload size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Stack>
      </Card>
    </>
  );
}

// ==================== ATTACHMENTS KANBAN ====================

export function ViewKanbanAttachments() {
  const navigate = useNavigate();
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [galleryIndex, setGalleryIndex] = useState(0);

  const { data } = useSearchQuery({
    model: 'attachments',
    fields: [
      'id',
      'name',
      'mimetype',
      'size',
      'public',
      'folder',
      'is_voice',
      'res_model',
      'res_id',
    ],
    limit: 50,
    order: 'desc',
    sort: 'id',
  }) as TypedUseQueryHookResult<
    GetListResult<Attachment>,
    GetListParams,
    BaseQueryFn
  >;

  const handleClick = useCallback(
    (id: number) => navigate(`${id}`),
    [navigate],
  );
  const attachments = data?.data || [];

  // Фильтруем только изображения для галереи
  const imageAttachments = attachments.filter(att =>
    isImageMimetype(att.mimetype),
  );

  // Конвертируем в формат GalleryItem
  const galleryItems: GalleryItem[] = imageAttachments.map(att => ({
    id: att.id,
    name: att.name || undefined,
    mimetype: att.mimetype || undefined,
  }));

  const handleOpenGallery = useCallback(
    (attachmentId: number) => {
      const index = imageAttachments.findIndex(att => att.id === attachmentId);
      if (index !== -1) {
        setGalleryIndex(index);
        setGalleryOpen(true);
      }
    },
    [imageAttachments],
  );

  return (
    <>
      <SimpleGrid
        cols={{ base: 2, sm: 3, md: 4, lg: 5, xl: 6 }}
        spacing="md"
        p="md">
        {attachments.map(att => (
          <AttachmentCard
            key={att.id}
            attachment={att}
            onClick={() => handleClick(att.id)}
            onOpenGallery={() => handleOpenGallery(att.id)}
          />
        ))}
      </SimpleGrid>

      {/* Галерея изображений */}
      <ImageGalleryModal
        opened={galleryOpen}
        onClose={() => setGalleryOpen(false)}
        items={galleryItems}
        initialIndex={galleryIndex}
      />
    </>
  );
}

// ==================== STORAGE KANBAN ====================

export function ViewKanbanAttachmentsStorage() {
  return (
    <Kanban<SchemaAttachmentStorage>
      model="attachments_storage"
      fields={['id', 'name', 'type']}
    />
  );
}
