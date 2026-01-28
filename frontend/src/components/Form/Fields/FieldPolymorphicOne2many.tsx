import {
  useRef,
  useState,
  useContext,
  useEffect,
  DragEvent,
  ChangeEvent,
} from 'react';
import {
  Box,
  Text,
  Group,
  Stack,
  SimpleGrid,
  useMantineTheme,
} from '@mantine/core';
import { IconUpload, IconFile, IconPlus } from '@tabler/icons-react';
import { useParams } from 'react-router-dom';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { useGetAttachmentQuery } from '@/services/api/crudApi';
import { FaraRecord } from '@/services/api/crudTypes';
import {
  AttachmentPreview,
  ImageGalleryModal,
  isImageMimetype,
  formatFileSize,
} from '@/components/Attachment';
import type { GalleryItem, AttachmentData } from '@/components/Attachment';
import classes from './FieldPolymorphicOne2many.module.css';

interface AttachmentFile {
  id?: number;
  name: string;
  mimetype: string;
  size: number;
  content?: string; // base64 для новых файлов
  res_model?: string;
  res_id?: number | null;
  _isNew?: boolean; // маркер нового файла
  _localId?: string; // локальный id для ключей
}

interface FieldPolymorphicOne2manyProps {
  name: string;
  model?: string;
  label?: string;
  accept?: string;
  maxSize?: number; // максимальный размер одного файла в байтах
  maxFiles?: number; // максимальное количество файлов
  showPreview?: boolean; // загружать ли превью изображений (по умолчанию true)
  previewSize?: number;
  columns?: number; // количество колонок в сетке
}

export const FieldPolymorphicOne2many = <RecordType extends FaraRecord>({
  name,
  model,
  label,
  accept,
  maxSize = 10 * 1024 * 1024, // 10MB по умолчанию
  maxFiles = 50,
  showPreview = true,
  previewSize = 100,
  columns = 4,
}: FieldPolymorphicOne2manyProps) => {
  const form = useFormContext();
  const { id } = useParams<{ id: string }>();
  const theme = useMantineTheme();
  const inputRef = useRef<HTMLInputElement>(null);
  const { fields: fieldsServer } = useContext(FormFieldsContext);

  // Состояния
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Галерея
  const [galleryOpened, setGalleryOpened] = useState(false);
  const [galleryInitialIndex, setGalleryInitialIndex] = useState(0);

  // Для скачивания файлов
  const [downloadFileId, setDownloadFileId] = useState(0);
  const [shouldFetch, setShouldFetch] = useState(false);

  useGetAttachmentQuery({ id: downloadFileId }, { skip: !shouldFetch });

  useEffect(() => {
    setShouldFetch(false);
  }, [shouldFetch]);

  // Получить все файлы (существующие + новые)
  const getExistingFiles = (): AttachmentFile[] => {
    const fieldValue = form.getValues()?.[name];
    if (fieldValue?.data && Array.isArray(fieldValue.data)) {
      return fieldValue.data.map((f: any) => ({ ...f, _isNew: false }));
    }
    return [];
  };

  const getNewFiles = (): AttachmentFile[] => {
    const fieldValue = form.getValues()?.['_' + name];
    if (fieldValue?.created && Array.isArray(fieldValue.created)) {
      return fieldValue.created.map((f: any) => ({ ...f, _isNew: true }));
    }
    return [];
  };

  const getDeletedIds = (): number[] => {
    const fieldValue = form.getValues()?.['_' + name];
    if (fieldValue?.deleted && Array.isArray(fieldValue.deleted)) {
      return fieldValue.deleted;
    }
    return [];
  };

  const existingFiles = getExistingFiles();
  const newFiles = getNewFiles();
  const deletedIds = getDeletedIds();

  // Фильтруем удалённые из существующих
  const visibleExistingFiles = existingFiles.filter(
    f => f.id && !deletedIds.includes(f.id),
  );
  const allFiles = [...visibleExistingFiles, ...newFiles];

  // Чтение файла в base64
  const readFileAsBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Ошибка чтения файла'));
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]);
      };
      reader.readAsDataURL(file);
    });
  };

  // Обработка файлов
  const processFiles = async (files: FileList | File[]) => {
    setError(null);
    const fileArray = Array.from(files);

    // Проверка количества
    if (allFiles.length + fileArray.length > maxFiles) {
      setError(`Максимум ${maxFiles} файлов`);
      return;
    }

    // Проверка размеров
    const oversizedFiles = fileArray.filter(f => f.size > maxSize);
    if (oversizedFiles.length > 0) {
      setError(`Некоторые файлы превышают ${formatFileSize(maxSize)}`);
      return;
    }

    setIsUploading(true);

    try {
      const newFilesData: AttachmentFile[] = [];

      for (const file of fileArray) {
        const content = await readFileAsBase64(file);
        newFilesData.push({
          name: file.name,
          mimetype: file.type,
          size: file.size,
          res_model: model,
          res_id: id ? Number(id) : null,
          content: content,
          _isNew: true,
          _localId: `new_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        });
      }

      // Добавляем к существующим новым файлам
      const currentNew = getNewFiles();
      form.setValues({
        ['_' + name]: {
          deleted: deletedIds,
          created: [...currentNew, ...newFilesData],
          fieldsServer: fieldsServer,
        },
      });
    } catch (err) {
      console.error('Ошибка загрузки файлов:', err);
      setError('Ошибка загрузки файлов');
    } finally {
      setIsUploading(false);
    }
  };

  // Обработка выбора файлов через input
  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      processFiles(files);
    }
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  // Drag & Drop handlers
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
      processFiles(files);
    }
  };

  // Клик по зоне загрузки
  const handleZoneClick = () => {
    inputRef.current?.click();
  };

  // Удаление файла
  const handleDelete = (file: AttachmentFile, index: number) => {
    if (file._isNew) {
      // Удаляем из новых
      const currentNew = getNewFiles();
      const newIndex = index - visibleExistingFiles.length;
      const newCreated = currentNew.filter((_, i) => i !== newIndex);
      form.setValues({
        ['_' + name]: {
          deleted: deletedIds,
          created: newCreated,
          fieldsServer: fieldsServer,
        },
      });
    } else if (file.id) {
      // Добавляем в deleted
      form.setValues({
        ['_' + name]: {
          deleted: [...deletedIds, file.id],
          created: getNewFiles(),
          fieldsServer: fieldsServer,
        },
      });
    }
  };

  // Скачивание файла
  const handleDownload = (file: AttachmentFile) => {
    if (file.id && !file._isNew) {
      setDownloadFileId(file.id);
      setShouldFetch(true);
    } else if (file.content) {
      const link = document.createElement('a');
      link.href = `data:${file.mimetype};base64,${file.content}`;
      link.download = file.name || 'file';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  // Открытие галереи
  const handleOpenGallery = (index: number) => {
    // Находим индекс среди изображений
    const imageFiles = allFiles.filter(f => isImageMimetype(f.mimetype));
    const file = allFiles[index];
    const imageIndex = imageFiles.findIndex(
      f =>
        (f.id && f.id === file.id) ||
        (f._localId && f._localId === file._localId),
    );

    if (imageIndex >= 0) {
      setGalleryInitialIndex(imageIndex);
      setGalleryOpened(true);
    }
  };

  // Подготовка элементов галереи
  const galleryItems: GalleryItem[] = allFiles
    .filter(f => isImageMimetype(f.mimetype))
    .map(f => ({
      id: f.id,
      name: f.name,
      mimetype: f.mimetype,
      content: f.content,
    }));

  const canAddMore = allFiles.length < maxFiles;

  return (
    <Stack gap="xs">
      {label && (
        <Text size="sm" fw={500}>
          {label}
        </Text>
      )}

      {/* Скрытый input */}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />

      {/* Сетка файлов */}
      {allFiles.length > 0 && (
        <SimpleGrid cols={columns} spacing="xs">
          {allFiles.map((file, index) => (
            <AttachmentPreview
              key={file.id || file._localId || index}
              attachment={{
                id: file.id,
                name: file.name,
                mimetype: file.mimetype,
                size: file.size,
                content: file.content,
              }}
              onDelete={() => handleDelete(file, index)}
              onDownload={() => handleDownload(file)}
              onClick={
                isImageMimetype(file.mimetype)
                  ? () => handleOpenGallery(index)
                  : undefined
              }
              showPreview={showPreview}
              previewSize={previewSize}
              showActions={true}
            />
          ))}

          {/* Кнопка добавления */}
          {canAddMore && (
            <Box
              className={classes.addButton}
              style={{ width: previewSize, height: previewSize }}
              onClick={handleZoneClick}>
              <IconPlus size={32} stroke={1.5} color={theme.colors.gray[5]} />
            </Box>
          )}
        </SimpleGrid>
      )}

      {/* Зона загрузки (если нет файлов) */}
      {allFiles.length === 0 && (
        <Box
          className={classes.dropzone}
          data-drag-over={isDragOver || undefined}
          data-loading={isUploading || undefined}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleZoneClick}>
          <Group justify="center" gap="xl" mih={120}>
            {isDragOver ? (
              <IconUpload size={50} stroke={1.5} color={theme.colors.blue[6]} />
            ) : (
              <IconFile size={50} stroke={1.5} color={theme.colors.gray[5]} />
            )}

            <div>
              <Text size="sm" inline>
                {isUploading
                  ? 'Загрузка...'
                  : 'Перетащите файлы сюда или нажмите для выбора'}
              </Text>
              <Text size="xs" c="dimmed" inline mt={7}>
                Максимум {maxFiles} файлов, до {formatFileSize(maxSize)} каждый
              </Text>
            </div>
          </Group>
        </Box>
      )}

      {/* Ошибка */}
      {error && (
        <Text size="xs" c="red">
          {error}
        </Text>
      )}

      {/* Галерея */}
      <ImageGalleryModal
        opened={galleryOpened}
        onClose={() => setGalleryOpened(false)}
        items={galleryItems}
        initialIndex={galleryInitialIndex}
        onDownload={item => {
          const file = allFiles.find(
            f =>
              (f.id && f.id === item.id) ||
              (f.content && f.content === item.content),
          );
          if (file) handleDownload(file);
        }}
      />
    </Stack>
  );
};
