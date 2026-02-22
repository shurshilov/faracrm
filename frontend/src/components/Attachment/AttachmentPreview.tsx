import { useState, useEffect, useCallback, useRef } from 'react';
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
  IconPhotoOff,
} from '@tabler/icons-react';
import { FileIcon } from './FileIcon';
import { ImagePreviewModal } from './ImagePreviewModal';
import { AudioPlayer } from './AudioPlayer';
import { isImageMimetype, isAudioMimetype, formatFileSize } from './fileIcons';
import { attachmentPreviewUrl } from '@/utils/attachmentUrls';
import classes from './AttachmentPreview.module.css';

export interface AttachmentData {
  id?: number | string;
  name?: string | null;
  mimetype?: string | null;
  size?: number | null;
  checksum?: string | null;
  content?: string | null;
  storage_file_url?: string | null;
  is_voice?: boolean;
}

interface AttachmentPreviewProps {
  attachment: AttachmentData;
  onDelete?: () => void;
  onReplace?: () => void;
  onDownload?: () => void;
  onClick?: () => void;
  isLoading?: boolean;
  showActions?: boolean;
  showPreview?: boolean;
  previewSize?: number;
  compact?: boolean;
}

/** Прямой URL для превью — через cookie auth, без fetch+blob */
function getPreviewUrl(
  attach: AttachmentData,
  width?: number,
  height?: number,
): string {
  return attachmentPreviewUrl(attach.id!, width, height, attach.checksum);
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
  // Превью (маленькая картинка в карточке)
  const [thumbnailSrc, setThumbnailSrc] = useState<string | null>(null);
  const [thumbnailError, setThumbnailError] = useState(false);
  const [isLoadingThumbnail, setIsLoadingThumbnail] = useState(false);

  // Оригинал (для модального окна)
  const [originalSrc, setOriginalSrc] = useState<string | null>(null);
  const [isLoadingOriginal, setIsLoadingOriginal] = useState(false);

  const [imageModalOpened, setImageModalOpened] = useState(false);

  // Трекаем id чтобы не сбрасывать при ререндерах с тем же id
  const loadedForIdRef = useRef<number | string | null>(null);
  const errorForIdRef = useRef<number | string | null>(null);

  const isImage = isImageMimetype(attachment.mimetype);
  const isAudio = isAudioMimetype(attachment.mimetype);

  const canFetchFromApi =
    isImage &&
    attachment.id &&
    typeof attachment.id === 'number' &&
    attachment.id > 0;

  // --- Загрузка thumbnail при showPreview=true ---
  useEffect(() => {
    const attachId = attachment.id;

    // Id сменился — сбрасываем
    if (loadedForIdRef.current !== attachId) {
      loadedForIdRef.current = null;
      setThumbnailSrc(null);
      setOriginalSrc(null);
    }
    if (errorForIdRef.current !== attachId) {
      errorForIdRef.current = null;
      setThumbnailError(false);
    }

    if (!isImage || isAudio) return;

    // base64 из формы (новый файл)
    if (attachment.content) {
      const src = `data:${attachment.mimetype};base64,${attachment.content}`;
      setThumbnailSrc(src);
      setOriginalSrc(src); // для нового файла оригинал = то же самое
      loadedForIdRef.current = attachId ?? null;
      return;
    }

    // data URL из storage
    if (attachment.storage_file_url?.startsWith('data:')) {
      setThumbnailSrc(attachment.storage_file_url);
      loadedForIdRef.current = attachId ?? null;
      return;
    }

    // Уже загружено / ошибка для этого id — ничего не делаем
    if (loadedForIdRef.current === attachId) return;
    if (errorForIdRef.current === attachId) return;

    // showPreview=false → НЕ грузим, покажем иконку
    if (!showPreview) return;

    // showPreview=true → ставим прямой URL (cookie auth, браузер грузит сам)
    if (canFetchFromApi && typeof attachment.id === 'number') {
      const size = previewSize * 2;
      setThumbnailSrc(getPreviewUrl(attachment, size, size));
      loadedForIdRef.current = attachId ?? null;
    }
  }, [
    attachment.id,
    attachment.content,
    attachment.checksum,
    attachment.storage_file_url,
    attachment.mimetype,
    isImage,
    isAudio,
    showPreview,
    canFetchFromApi,
    previewSize,
  ]);

  // Показывать ли картинку inline
  const showImageInline = isImage && !!thumbnailSrc && !thumbnailError;

  // <Image> onError — файл битый / формат не поддерживается
  const handleImageError = useCallback(() => {
    setThumbnailError(true);
    setThumbnailSrc(null);
    errorForIdRef.current = attachment.id ?? null;
  }, [attachment.id]);

  // --- Клик: загружаем оригинал и открываем модалку ---
  const handleClick = useCallback(() => {
    // onClick от родителя (галерея) — приоритет
    if (onClick) {
      onClick();
      return;
    }

    if (!isImage) {
      onDownload?.();
      return;
    }

    // Уже была ошибка — не пытаемся снова
    if (thumbnailError) return;

    // Оригинал уже загружен
    if (originalSrc) {
      setImageModalOpened(true);
      return;
    }

    // Есть thumbnail (из base64/content) — он и есть оригинал
    if (thumbnailSrc && attachment.content) {
      setOriginalSrc(thumbnailSrc);
      setImageModalOpened(true);
      return;
    }

    // Нужно загрузить оригинал с сервера
    if (canFetchFromApi && typeof attachment.id === 'number') {
      // Прямой URL без размеров → оригинал
      const src = getPreviewUrl(attachment);
      setOriginalSrc(src);
      if (!thumbnailSrc) {
        setThumbnailSrc(src);
        loadedForIdRef.current = attachment.id ?? null;
      }
      setImageModalOpened(true);
    }
  }, [
    onClick,
    isImage,
    thumbnailError,
    originalSrc,
    thumbnailSrc,
    attachment.id,
    attachment.content,
    canFetchFromApi,
    onDownload,
  ]);

  const isLoadingAny = isLoadingThumbnail || isLoadingOriginal;

  // --- Compact mode ---
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
        ) : showImageInline ? (
          <Image
            src={thumbnailSrc}
            alt={attachment.name || 'Preview'}
            fit="cover"
            radius="sm"
            w={previewSize}
            h={previewSize}
            onError={handleImageError}
            onClick={handleClick}
            style={{ cursor: 'pointer' }}
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

  // --- Main render ---
  return (
    <>
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
            {!attachment.is_voice && (
              <Text size="xs" c="dimmed" lineClamp={1}>
                {attachment.name || 'Audio'}
              </Text>
            )}
          </Stack>
        </Paper>
      ) : (
        <Paper className={classes.container} withBorder p="xs" radius="md">
          <Box
            className={classes.preview}
            style={{
              width: previewSize,
              height: previewSize,
              cursor: isImage || onClick || onDownload ? 'pointer' : undefined,
            }}
            onClick={handleClick}>
            {isLoading || isLoadingAny ? (
              <Loader size="sm" />
            ) : showImageInline ? (
              <Image
                src={thumbnailSrc}
                alt={attachment.name || 'Preview'}
                fit="cover"
                radius="md"
                w={previewSize}
                h={previewSize}
                onError={handleImageError}
                className={classes.image}
              />
            ) : isImage && thumbnailError ? (
              <Box className={classes.iconWrapper}>
                <Stack align="center" gap={4}>
                  <IconPhotoOff
                    size={previewSize * 0.35}
                    stroke={1.2}
                    color="var(--mantine-color-gray-5)"
                  />
                  <Text size="xs" c="dimmed">
                    Превью недоступно
                  </Text>
                </Stack>
              </Box>
            ) : (
              <Box className={classes.iconWrapper}>
                <FileIcon
                  mimetype={attachment.mimetype}
                  size={previewSize * 0.5}
                />
              </Box>
            )}
          </Box>

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

      {/* Модальное окно — оригинал */}
      {isImage && (
        <ImagePreviewModal
          opened={imageModalOpened && !!originalSrc}
          onClose={() => setImageModalOpened(false)}
          src={originalSrc || ''}
          filename={attachment.name || undefined}
          onDownload={onDownload}
        />
      )}
    </>
  );
}
