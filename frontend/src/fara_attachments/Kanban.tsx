import { useCallback, useState, useEffect, useMemo } from 'react';
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
  Switch,
  Paper,
} from '@mantine/core';
import {
  IconDownload,
  IconEye,
  IconFolder,
  IconLock,
  IconWorld,
  IconMicrophone,
  IconCloud,
  IconPhoto,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
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
import {
  attachmentPreviewUrl,
  attachmentContentUrl,
} from '@/utils/attachmentUrls';
import { useTranslation } from 'react-i18next';
import classes from './Kanban.module.css';

// ==================== CLOUD PLACEHOLDER ====================

interface CloudPlaceholderProps {
  mimetype?: string | null;
  onLoadPreview: () => void;
  isLoading: boolean;
}

function CloudPlaceholder({
  mimetype,
  onLoadPreview,
  isLoading,
}: CloudPlaceholderProps) {
  const { t } = useTranslation('attachments');
  const isImage = isImageMimetype(mimetype);

  return (
    <Box className={classes.cloudPlaceholder}>
      {isLoading ? (
        <Loader size="sm" />
      ) : (
        <>
          <IconCloud size={32} className={classes.cloudIcon} />
          {isImage && (
            <Tooltip label={t('load_preview', 'Загрузить превью')}>
              <ActionIcon
                variant="light"
                color="blue"
                size="sm"
                className={classes.loadPreviewBtn}
                onClick={e => {
                  e.stopPropagation();
                  onLoadPreview();
                }}>
                <IconEye size={14} />
              </ActionIcon>
            </Tooltip>
          )}
        </>
      )}
    </Box>
  );
}

// ==================== ATTACHMENT CARD ====================

interface AttachmentCardProps {
  attachment: Attachment;
  onClick: () => void;
  onOpenGallery: () => void;
  showAllPreviews: boolean;
}

function AttachmentCard({
  attachment,
  onClick,
  onOpenGallery,
  showAllPreviews,
}: AttachmentCardProps) {
  const [thumbSrc, setThumbSrc] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [manuallyLoaded, setManuallyLoaded] = useState(false);

  const isImage = isImageMimetype(attachment.mimetype);
  const isAudio = isAudioMimetype(attachment.mimetype);
  const isVideo = isVideoMimetype(attachment.mimetype);

  // Определяем, является ли хранилище облачным (type != 'file')
  const isCloudStorage = useMemo(() => {
    const storageType = attachment.storage_id?.type;
    return storageType && storageType !== 'file';
  }, [attachment.storage_id?.type]);

  // Определяем, нужно ли показывать превью
  const shouldShowPreview = useMemo(() => {
    // Если show_preview явно установлено в true - показываем
    if (attachment.show_preview === true) return true;
    // Если show_preview явно установлено в false и нет ручной загрузки - не показываем
    if (
      attachment.show_preview === false &&
      !manuallyLoaded &&
      !showAllPreviews
    )
      return false;
    // Если глобальная галочка включена - показываем
    if (showAllPreviews) return true;
    // Если файл был загружен вручную - показываем
    if (manuallyLoaded) return true;
    // Для локального хранилища - показываем по умолчанию
    if (!isCloudStorage) return true;
    // Для облачного хранилища без явного show_preview - не показываем
    return false;
  }, [
    attachment.show_preview,
    isCloudStorage,
    manuallyLoaded,
    showAllPreviews,
  ]);

  // Загрузка превью для карточки
  useEffect(() => {
    if (!isImage || !attachment.id) return;
    if (!shouldShowPreview) {
      setThumbSrc(null);
      return;
    }

    setIsLoading(true);
    setThumbSrc(
      attachmentPreviewUrl(attachment.id, 200, 200, attachment.checksum),
    );
    setIsLoading(false);
  }, [attachment.id, isImage, shouldShowPreview]);

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!attachment.id) return;

    // Скачивание через cookie auth — прямая ссылка
    const a = document.createElement('a');
    a.href = attachmentContentUrl(attachment.id);
    a.download = attachment.name || 'file';
    a.click();
  };

  const handlePreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isImage) {
      onOpenGallery();
    }
  };

  const handleLoadCloudPreview = () => {
    setManuallyLoaded(true);
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

  // Рендер области превью
  const renderPreviewArea = () => {
    // Показываем плейсхолдер для облачных файлов без превью
    if (isCloudStorage && !shouldShowPreview && isImage) {
      return (
        <CloudPlaceholder
          mimetype={attachment.mimetype}
          onLoadPreview={handleLoadCloudPreview}
          isLoading={isLoading}
        />
      );
    }

    // Показываем загрузку
    if (isLoading) {
      return <Loader size="sm" />;
    }

    // Показываем изображение
    if (isImage && thumbSrc) {
      return (
        <Image
          src={thumbSrc}
          alt={attachment.name || ''}
          fit="cover"
          h="100%"
          w="100%"
        />
      );
    }

    // Показываем иконку файла
    return (
      <Box className={classes.iconArea}>
        <FileIcon mimetype={attachment.mimetype} size={48} />
      </Box>
    );
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
        <Box className={classes.previewArea}>{renderPreviewArea()}</Box>

        {/* Бейджи сверху справа */}
        <Box className={classes.topBadges}>
          {/* Бейдж облачного хранилища */}
          {isCloudStorage && (
            <Tooltip
              label={`${attachment.storage_id?.type || 'Cloud'} storage`}>
              <ActionIcon
                size="xs"
                variant="filled"
                color="blue"
                radius="xl"
                mr={4}>
                <IconCloud size={12} />
              </ActionIcon>
            </Tooltip>
          )}

          {/* Бейдж публичности */}
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
  const { t } = useTranslation('attachments');
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [galleryIndex, setGalleryIndex] = useState(0);
  const [showAllPreviews, setShowAllPreviews] = useState(false);

  const { data } = useSearchQuery({
    model: 'attachments',
    fields: [
      'id',
      'name',
      'mimetype',
      'size',
      'checksum',
      'public',
      'folder',
      'is_voice',
      'show_preview',
      'res_model',
      'res_id',
      'storage_id',
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

  // Проверяем, есть ли облачные файлы
  const hasCloudFiles = useMemo(() => {
    return attachments.some(att => {
      const storageType = att.storage_id?.type;
      return storageType && storageType !== 'file';
    });
  }, [attachments]);

  return (
    <>
      {/* Панель управления превью */}
      {hasCloudFiles && (
        <Paper p="sm" mb="md" withBorder>
          <Group justify="space-between">
            <Group gap="xs">
              <IconPhoto size={18} />
              <Text size="sm">{t('preview_settings', 'Настройки превью')}</Text>
            </Group>
            <Switch
              label={t('show_all_previews', 'Показать все превью')}
              checked={showAllPreviews}
              onChange={e => setShowAllPreviews(e.currentTarget.checked)}
              size="sm"
            />
          </Group>
        </Paper>
      )}

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
            showAllPreviews={showAllPreviews}
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
