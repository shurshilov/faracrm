import { useRef, useState, useEffect, DragEvent, ChangeEvent } from 'react';
import { Box, Text, Group, Stack, useMantineTheme } from '@mantine/core';
import { IconUpload, IconFile } from '@tabler/icons-react';
import { useParams } from 'react-router-dom';
import { useFormContext } from '../FormContext';
import { useGetAttachmentQuery } from '@/services/api/crudApi';
import { FaraRecord } from '@/services/api/crudTypes';
import {
  AttachmentPreview,
  isImageMimetype,
  formatFileSize,
} from '@/components/Attachment';
import classes from './FieldPolymorphicMany2one.module.css';

interface FieldPolymorphicMany2oneProps {
  name: string;
  model?: string;
  label?: string;
  accept?: string;
  maxSize?: number; // в байтах
}

export const FieldPolymorphicMany2one = <RecordType extends FaraRecord>({
  name,
  model,
  label,
  accept,
  maxSize = 10 * 1024 * 1024, // 10MB по умолчанию
  ...props
}: FieldPolymorphicMany2oneProps) => {
  const form = useFormContext();
  const { id } = useParams<{ id: string }>();
  const theme = useMantineTheme();
  const inputRef = useRef<HTMLInputElement>(null);

  // Состояния
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [previewData, setPreviewData] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Текущее значение из формы
  const currentValue = form.getValues()?.[name];
  const hasExistingFile =
    currentValue?.id && typeof currentValue.id === 'number';
  const hasNewFile = currentValue?.content;
  const hasFile = hasExistingFile || hasNewFile;

  // Запрос на скачивание файла
  const [shouldFetch, setShouldFetch] = useState(false);
  useGetAttachmentQuery(
    { id: hasExistingFile ? Number(currentValue.id) : 0 },
    { skip: !shouldFetch },
  );

  useEffect(() => {
    if (shouldFetch) {
      setShouldFetch(false);
    }
  }, [shouldFetch]);

  // Чтение файла в base64
  const readFileAsBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Ошибка чтения файла'));
      reader.onabort = () => reject(new Error('Чтение прервано'));
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]); // Убираем data:...;base64,
      };
      reader.readAsDataURL(file);
    });
  };

  // Обработка файла
  const processFile = async (file: File) => {
    setError(null);

    // Проверка размера
    if (file.size > maxSize) {
      setError(`Файл слишком большой. Максимум: ${formatFileSize(maxSize)}`);
      return;
    }

    setIsUploading(true);

    try {
      const content = await readFileAsBase64(file);

      // Создаём превью для изображений
      if (isImageMimetype(file.type)) {
        setPreviewData(`data:${file.type};base64,${content}`);
      } else {
        setPreviewData(null);
      }

      // Сохраняем в форму
      const fileData = {
        name: file.name,
        mimetype: file.type,
        size: file.size,
        res_model: model,
        res_id: id ? Number(id) : null,
        content: content,
      };

      form.setValues({ [name]: fileData });
    } catch (err) {
      console.error('Ошибка загрузки файла:', err);
      setError('Ошибка загрузки файла');
    } finally {
      setIsUploading(false);
    }
  };

  // Обработка выбора файла через input
  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
    // Сбрасываем input для возможности повторной загрузки того же файла
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
      processFile(files[0]);
    }
  };

  // Клик по зоне загрузки
  const handleZoneClick = () => {
    inputRef.current?.click();
  };

  // Удаление файла
  const handleDelete = () => {
    form.setValues({ [name]: null });
    setPreviewData(null);
    setError(null);
  };

  // Замена файла
  const handleReplace = () => {
    inputRef.current?.click();
  };

  // Скачивание файла
  const handleDownload = () => {
    if (hasExistingFile) {
      setShouldFetch(true);
    } else if (hasNewFile && currentValue.content) {
      // Скачивание нового файла из base64
      const link = document.createElement('a');
      link.href = `data:${currentValue.mimetype};base64,${currentValue.content}`;
      link.download = currentValue.name || 'file';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <Stack gap="xs">
      {label && (
        <Text size="sm" fw={500}>
          {label || name}
        </Text>
      )}

      {/* Скрытый input */}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />

      {/* Отображение загруженного файла */}
      {hasFile && !isUploading && (
        <AttachmentPreview
          attachment={{
            id: currentValue.id,
            name: currentValue.name,
            mimetype: currentValue.mimetype,
            size: currentValue.size,
            content: currentValue.content,
            storage_file_url: previewData || undefined,
          }}
          onDelete={handleDelete}
          onReplace={handleReplace}
          onDownload={handleDownload}
          showPreview={currentValue.show_preview !== false}
          showActions={true}
        />
      )}

      {/* Зона загрузки */}
      {(!hasFile || isUploading) && (
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
                  : 'Перетащите файл сюда или нажмите для выбора'}
              </Text>
              <Text size="xs" c="dimmed" inline mt={7}>
                Максимальный размер: {formatFileSize(maxSize)}
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
    </Stack>
  );
};
