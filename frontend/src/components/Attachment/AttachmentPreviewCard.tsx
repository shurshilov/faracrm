/**
 * AttachmentPreviewCard — превью карточка вложения для использования в Form.
 *
 * Поддерживает:
 *   - Превью существующих файлов через attachmentPreviewUrl(id) (без fetch)
 *   - Превью новых файлов из base64 (после загрузки)
 *   - Drag & drop для загрузки/замены файла
 *   - Клик по зоне для выбора файла
 *
 * Данные берёт из useFormContext() — никаких fetch.
 *
 * Использование:
 *   <Form model="attachments">
 *     <AttachmentPreviewCard />
 *     ...
 *   </Form>
 */
import { useState, useRef, ChangeEvent, DragEvent } from 'react';
import { useParams } from 'react-router-dom';
import {
  Paper,
  Group,
  Stack,
  Text,
  Badge,
  ActionIcon,
  Tooltip,
  Box,
  Image,
  Divider,
  Loader,
} from '@mantine/core';
import {
  IconDownload,
  IconEye,
  IconFolder,
  IconLock,
  IconWorld,
  IconMicrophone,
  IconUpload,
  IconRefresh,
  IconX,
} from '@tabler/icons-react';
import { useFormContext } from '@/components/Form/FormContext';
import { FileIcon } from './FileIcon';
import { ImagePreviewModal } from './ImagePreviewModal';
import {
  isImageMimetype,
  isAudioMimetype,
  isVideoMimetype,
  formatFileSize,
} from './fileIcons';
import {
  attachmentPreviewUrl,
  attachmentContentUrl,
} from '@/utils/attachmentUrls';
import classes from './AttachmentPreviewCard.module.css';

const DEFAULT_MAX_SIZE = 100 * 1024 * 1024; // 100 MB

interface AttachmentPreviewCardProps {
  /** Максимальный размер файла в байтах. По умолчанию 100 MB. */
  maxSize?: number;
}

export function AttachmentPreviewCard({
  maxSize = DEFAULT_MAX_SIZE,
}: AttachmentPreviewCardProps = {}) {
  const form = useFormContext();
  const params = useParams<{ id: string }>();
  const inputRef = useRef<HTMLInputElement>(null);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const values = form.getValues() || {};

  // ID берём из URL (для существующих) или из values (если есть)
  const idFromUrl = params.id ? parseInt(params.id, 10) : null;
  const id = idFromUrl || values.id;

  // Метаданные из формы
  const mimetype = values.mimetype as string | undefined;
  const name = (values.name as string) || '';
  const size = values.size as number | undefined;
  const checksum = values.checksum as string | undefined;
  const isPublic = values.public as boolean | undefined;
  const isVoice = values.is_voice as boolean | undefined;
  const showPreview = values.show_preview !== false;
  const folder = values.folder;
  const newFileContent = values.content as string | undefined;

  const isImage = mimetype ? isImageMimetype(mimetype) : false;
  const isAudio = mimetype ? isAudioMimetype(mimetype) : false;
  const isVideo = mimetype ? isVideoMimetype(mimetype) : false;

  const hasFile = !!(id || newFileContent);

  // URL изображения по приоритету
  let imageSrc: string | null = null;
  if (isImage && showPreview) {
    if (newFileContent) {
      imageSrc = `data:${mimetype};base64,${newFileContent}`;
    } else if (id) {
      imageSrc = attachmentPreviewUrl(id, undefined, undefined, checksum);
    }
  }

  // ─── File handling ───

  const readFileAsBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Ошибка чтения файла'));
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]); // убираем data:...;base64,
      };
      reader.readAsDataURL(file);
    });

  const processFile = async (file: File) => {
    setError(null);

    if (file.size > maxSize) {
      setError(`Файл слишком большой. Максимум: ${formatFileSize(maxSize)}`);
      return;
    }

    setIsUploading(true);
    try {
      const content = await readFileAsBase64(file);

      // Записываем поля в form values — модель Attachment имеет
      // эти поля на верхнем уровне (не вложенные)
      form.setValues({
        name: file.name,
        mimetype: file.type,
        size: file.size,
        content,
      });
    } catch (err) {
      console.error('Ошибка загрузки файла:', err);
      setError('Ошибка загрузки файла');
    } finally {
      setIsUploading(false);
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
  };

  const handleZoneClick = () => {
    inputRef.current?.click();
  };

  const handleReplace = (e: React.MouseEvent) => {
    e.stopPropagation();
    inputRef.current?.click();
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    form.setValues({
      name: '',
      mimetype: '',
      size: 0,
      content: null,
    });
    setError(null);
  };

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (id) {
      const a = document.createElement('a');
      a.href = attachmentContentUrl(id);
      a.download = name || 'file';
      a.click();
    } else if (newFileContent && mimetype) {
      const a = document.createElement('a');
      a.href = `data:${mimetype};base64,${newFileContent}`;
      a.download = name || 'file';
      a.click();
    }
  };

  // ─── Render ───

  // Hidden file input — общий для всех режимов
  const fileInput = (
    <input
      ref={inputRef}
      type="file"
      style={{ display: 'none' }}
      onChange={handleInputChange}
    />
  );

  // Empty state — нет файла, показываем зону загрузки
  if (!hasFile) {
    return (
      <>
        <Paper
          className={classes.previewCard}
          withBorder
          p="md"
          radius="md"
          data-drag-over={isDragOver || undefined}
          onClick={handleZoneClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          style={{
            cursor: 'pointer',
            borderStyle: 'dashed',
            borderColor: isDragOver
              ? 'var(--mantine-color-blue-6)'
              : undefined,
          }}>
          <Stack align="center" gap="sm" py="xl">
            {isUploading ? (
              <Loader size="md" />
            ) : (
              <IconUpload
                size={48}
                stroke={1.5}
                color="var(--mantine-color-gray-6)"
              />
            )}
            <Text size="md" fw={500}>
              {isUploading
                ? 'Загрузка...'
                : isDragOver
                  ? 'Отпустите файл'
                  : 'Перетащите файл или нажмите'}
            </Text>
            <Text size="xs" c="dimmed">
              Максимум: {formatFileSize(maxSize)}
            </Text>
            {error && (
              <Text size="sm" c="red">
                {error}
              </Text>
            )}
          </Stack>
        </Paper>
        {fileInput}
      </>
    );
  }

  // File state — есть файл, показываем превью
  return (
    <>
      <Paper
        className={classes.previewCard}
        withBorder
        p="md"
        radius="md"
        data-drag-over={isDragOver || undefined}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          borderColor: isDragOver
            ? 'var(--mantine-color-blue-6)'
            : undefined,
          borderStyle: isDragOver ? 'dashed' : undefined,
        }}>
        {/* Превью */}
        <Box className={classes.previewArea} onClick={handleZoneClick}>
          {isUploading ? (
            <Loader size="md" />
          ) : imageSrc ? (
            <Image
              src={imageSrc}
              alt={name}
              fit="contain"
              mah={300}
              radius="md"
              style={{ cursor: 'pointer' }}
              onClick={e => {
                e.stopPropagation();
                setPreviewOpen(true);
              }}
            />
          ) : (
            <Box
              className={classes.iconArea}
              style={{ cursor: 'pointer' }}>
              <FileIcon
                mimetype={mimetype || 'application/octet-stream'}
                size={80}
              />
              <Text size="xs" c="dimmed" mt="xs">
                Нажмите чтобы заменить
              </Text>
            </Box>
          )}
        </Box>

        <Divider my="md" />

        {/* Информация о файле */}
        <Stack gap="xs">
          <Group justify="space-between">
            <Text size="lg" fw={600} lineClamp={1}>
              {name || 'Без имени'}
            </Text>
            <Group gap="xs">
              {imageSrc && (
                <Tooltip label="Просмотр">
                  <ActionIcon
                    variant="light"
                    color="blue"
                    onClick={e => {
                      e.stopPropagation();
                      setPreviewOpen(true);
                    }}>
                    <IconEye size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
              <Tooltip label="Заменить файл">
                <ActionIcon
                  variant="light"
                  color="gray"
                  onClick={handleReplace}>
                  <IconRefresh size={18} />
                </ActionIcon>
              </Tooltip>
              {(id || newFileContent) && (
                <Tooltip label="Скачать">
                  <ActionIcon
                    variant="light"
                    color="gray"
                    onClick={handleDownload}>
                    <IconDownload size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
              {newFileContent && !id && (
                <Tooltip label="Очистить">
                  <ActionIcon
                    variant="light"
                    color="red"
                    onClick={handleClear}>
                    <IconX size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
            </Group>
          </Group>

          <Group gap="xs">
            {size != null && size > 0 && (
              <Badge size="sm" variant="light" color="gray">
                {formatFileSize(size)}
              </Badge>
            )}

            {folder && (
              <Badge
                size="sm"
                color="yellow"
                leftSection={<IconFolder size={10} />}>
                Папка
              </Badge>
            )}

            {isVoice && (
              <Badge
                size="sm"
                color="pink"
                leftSection={<IconMicrophone size={10} />}>
                Голосовое
              </Badge>
            )}

            {isImage && (
              <Badge size="sm" color="teal">
                Изображение
              </Badge>
            )}

            {isVideo && (
              <Badge size="sm" color="violet">
                Видео
              </Badge>
            )}

            {isAudio && !isVoice && (
              <Badge size="sm" color="pink">
                Аудио
              </Badge>
            )}

            {isPublic !== undefined && (
              <Badge
                size="sm"
                variant="light"
                color={isPublic ? 'green' : 'gray'}
                leftSection={
                  isPublic ? <IconWorld size={10} /> : <IconLock size={10} />
                }>
                {isPublic ? 'Публичный' : 'Приватный'}
              </Badge>
            )}
          </Group>

          {error && (
            <Text size="sm" c="red">
              {error}
            </Text>
          )}
        </Stack>
      </Paper>

      {imageSrc && (
        <ImagePreviewModal
          opened={previewOpen}
          onClose={() => setPreviewOpen(false)}
          src={imageSrc}
          alt={name}
        />
      )}

      {fileInput}
    </>
  );
}

AttachmentPreviewCard.displayName = 'AttachmentPreviewCard';
