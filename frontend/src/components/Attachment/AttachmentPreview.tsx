import { useState, useEffect } from 'react';
import {
  Box,
  Image,
  Text,
  ActionIcon,
  Group,
  Tooltip,
  Paper,
  Stack,
  Loader,
} from '@mantine/core';
import {
  IconTrash,
  IconDownload,
  IconRefresh,
  IconX,
} from '@tabler/icons-react';
import { useSelector } from 'react-redux';
import { FileIcon } from './FileIcon';
import { ImagePreviewModal } from './ImagePreviewModal';
import { AudioPlayer } from './AudioPlayer';
import { isImageMimetype, isAudioMimetype, formatFileSize } from './fileIcons';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { selectCurrentSession } from '@/slices/authSlice';
import classes from './AttachmentPreview.module.css';

export interface AttachmentData {
  id?: number | string;
  name?: string | null;
  mimetype?: string | null;
  size?: number | null;
  content?: string | null; // base64 для новых файлов
  storage_file_url?: string | null; // URL для существующих файлов
  is_voice?: boolean; // Голосовое сообщение
}

interface AttachmentPreviewProps {
  attachment: AttachmentData;
  onDelete?: () => void;
  onReplace?: () => void;
  onDownload?: () => void;
  onClick?: () => void; // для открытия галереи
  isLoading?: boolean;
  showActions?: boolean;
  showPreview?: boolean; // загружать ли превью изображений (по умолчанию true)
  previewSize?: number;
  /** Компактный режим - только превью с крестиком удаления */
  compact?: boolean;
}

export function AttachmentPreview({
  attachment,
  onDelete,
  onReplace,
  onDownload,
  onClick,
  isLoading = false,
  showActions = true,
  showPreview = true,
  previewSize = 120,
  compact = false,
}: AttachmentPreviewProps) {
  const [imageModalOpened, setImageModalOpened] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [loadedImageSrc, setLoadedImageSrc] = useState<string | null>(null);
  const [isLoadingImage, setIsLoadingImage] = useState(false);

  const session = useSelector(selectCurrentSession);
  const isImage = isImageMimetype(attachment.mimetype);
  const isAudio = isAudioMimetype(attachment.mimetype);

  // Загрузка изображения через fetch с авторизацией
  useEffect(() => {
    // Сбрасываем состояние при смене attachment
    setLoadedImageSrc(null);
    setImageError(false);

    // Если превью отключено или это аудио — не загружаем картинку
    if (!showPreview || isAudio) return;

    // Если есть base64 контент — не нужно загружать
    if (attachment.content) {
      setLoadedImageSrc(
        `data:${attachment.mimetype};base64,${attachment.content}`,
      );
      return;
    }

    // Если есть storage_file_url как data URL
    if (attachment.storage_file_url?.startsWith('data:')) {
      setLoadedImageSrc(attachment.storage_file_url);
      return;
    }

    // Если есть id и это изображение — загружаем через API
    // Пропускаем временные отрицательные ID (используются при оптимистичном обновлении)
    if (
      isImage &&
      attachment.id &&
      typeof attachment.id === 'number' &&
      attachment.id > 0 &&
      session?.token
    ) {
      setIsLoadingImage(true);

      fetch(`${API_BASE_URL}/attachments/${attachment.id}/preview`, {
        headers: {
          Authorization: `Bearer ${session.token}`,
        },
      })
        .then(response => {
          if (!response.ok) throw new Error('Failed to load image');
          return response.blob();
        })
        .then(blob => {
          const reader = new FileReader();
          reader.onload = () => {
            setLoadedImageSrc(reader.result as string);
          };
          reader.readAsDataURL(blob);
        })
        .catch(() => {
          setImageError(true);
        })
        .finally(() => {
          setIsLoadingImage(false);
        });
    }
  }, [
    attachment.id,
    attachment.content,
    attachment.storage_file_url,
    attachment.mimetype,
    isImage,
    session?.token,
    showPreview,
  ]);

  const imageSrc = loadedImageSrc;

  const handleClick = () => {
    // Если передан onClick — используем его (для галереи)
    if (onClick) {
      onClick();
      return;
    }
    // Иначе открываем встроенную модалку для одиночного изображения
    if (isImage && imageSrc && !imageError) {
      setImageModalOpened(true);
    } else if (onDownload) {
      onDownload();
    }
  };

  const handleImageError = () => {
    setImageError(true);
  };

  // Компактный режим - только превью с крестиком удаления (для ChatInput)
  if (compact) {
    return (
      <Box
        className={classes.compactContainer}
        style={{ width: previewSize, height: previewSize }}>
        {isAudio ? (
          <Box className={classes.compactAudio}>
            <FileIcon mimetype={attachment.mimetype} size={previewSize * 0.4} />
            <Text size="xs" lineClamp={1} className={classes.compactName}>
              {attachment.name}
            </Text>
          </Box>
        ) : isImage && imageSrc && !imageError ? (
          <Image
            src={imageSrc}
            alt={attachment.name || 'Preview'}
            fit="cover"
            radius="sm"
            w={previewSize}
            h={previewSize}
            onError={handleImageError}
            onClick={onClick}
            style={{ cursor: onClick ? 'pointer' : undefined }}
          />
        ) : (
          <Box className={classes.compactFile}>
            <FileIcon mimetype={attachment.mimetype} size={previewSize * 0.4} />
            <Text size="xs" lineClamp={1} className={classes.compactName}>
              {attachment.name}
            </Text>
          </Box>
        )}
        {onDelete && (
          <ActionIcon
            className={classes.compactDeleteBtn}
            variant="filled"
            color="dark"
            size="xs"
            radius="xl"
            onClick={e => {
              e.stopPropagation();
              onDelete();
            }}>
            <IconX size={12} />
          </ActionIcon>
        )}
      </Box>
    );
  }

  return (
    <>
      {/* Аудио файлы отображаем с плеером */}
      {isAudio ? (
        <Paper
          className={classes.audioContainer}
          withBorder={!attachment.is_voice}
          p="xs"
          radius="md">
          <Stack gap={4}>
            <AudioPlayer
              attachmentId={
                typeof attachment.id === 'number' ? attachment.id : undefined
              }
              content={attachment.content || undefined}
              mimetype={attachment.mimetype || 'audio/webm'}
              isVoice={attachment.is_voice || false}
              compact
            />
            {/* Показываем имя файла только для не-голосовых */}
            {!attachment.is_voice && (
              <Text size="xs" c="dimmed" lineClamp={1}>
                {attachment.name || 'Audio'}
              </Text>
            )}
          </Stack>
        </Paper>
      ) : (
        <Paper className={classes.container} withBorder p="xs" radius="md">
          {isLoading || isLoadingImage ? (
            <Box
              className={classes.preview}
              style={{ width: previewSize, height: previewSize }}>
              <Loader size="sm" />
            </Box>
          ) : (
            <Box
              className={classes.preview}
              style={{ width: previewSize, height: previewSize }}
              onClick={handleClick}>
              {isImage && imageSrc && !imageError && showPreview ? (
                <Image
                  src={imageSrc}
                  alt={attachment.name || 'Preview'}
                  fit="cover"
                  radius="md"
                  w={previewSize}
                  h={previewSize}
                  onError={handleImageError}
                  className={classes.image}
                />
              ) : (
                <Box className={classes.iconWrapper}>
                  <FileIcon
                    mimetype={attachment.mimetype}
                    size={previewSize * 0.5}
                  />
                </Box>
              )}
            </Box>
          )}

          <Stack gap={4} className={classes.info}>
            <Tooltip label={attachment.name} disabled={!attachment.name}>
              <Text
                size="sm"
                fw={500}
                lineClamp={1}
                className={classes.filename}>
                {attachment.name || 'Без имени'}
              </Text>
            </Tooltip>

            <Text size="xs" c="dimmed">
              {formatFileSize(attachment.size)}
            </Text>

            {showActions && (
              <Group gap="xs" mt={4}>
                {onDownload && (
                  <Tooltip label="Скачать">
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      color="blue"
                      onClick={e => {
                        e.stopPropagation();
                        onDownload();
                      }}>
                      <IconDownload size={16} />
                    </ActionIcon>
                  </Tooltip>
                )}
                {onReplace && (
                  <Tooltip label="Заменить">
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      color="gray"
                      onClick={e => {
                        e.stopPropagation();
                        onReplace();
                      }}>
                      <IconRefresh size={16} />
                    </ActionIcon>
                  </Tooltip>
                )}
                {onDelete && (
                  <Tooltip label="Удалить">
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      color="red"
                      onClick={e => {
                        e.stopPropagation();
                        onDelete();
                      }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </Group>
            )}
          </Stack>
        </Paper>
      )}

      {/* Модальное окно для просмотра изображения */}
      {isImage && imageSrc && (
        <ImagePreviewModal
          opened={imageModalOpened}
          onClose={() => setImageModalOpened(false)}
          src={imageSrc}
          filename={attachment.name || undefined}
          onDownload={onDownload}
        />
      )}
    </>
  );
}
