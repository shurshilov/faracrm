import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
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
  Loader,
  Divider,
} from '@mantine/core';
import { 
  IconDownload, 
  IconEye, 
  IconFolder, 
  IconLock, 
  IconWorld,
  IconMicrophone,
  IconFile,
  IconDatabase,
  IconLink,
} from '@tabler/icons-react';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { Attachment, SchemaAttachmentStorage } from '@/services/api/attachments';
import {
  FormRow,
  FormTabs,
  FormTab,
  FormSection,
} from '@/components/Form/Layout';
import { FileIcon } from '@/components/Attachment/FileIcon';
import { ImagePreviewModal } from '@/components/Attachment/ImagePreviewModal';
import { isImageMimetype, isAudioMimetype, isVideoMimetype, formatFileSize } from '@/components/Attachment/fileIcons';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { selectCurrentSession } from '@/slices/authSlice';
import classes from './Form.module.css';

// Компонент превью файла для формы
function AttachmentPreviewCard({ attachmentId }: { attachmentId?: number }) {
  const session = useSelector(selectCurrentSession);
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);

  // Загружаем данные attachment
  useEffect(() => {
    if (!attachmentId || !session?.token) return;

    fetch(`${API_BASE_URL}/attachments/${attachmentId}`, {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(res => res.json())
      .then(data => setAttachment(data))
      .catch(() => setAttachment(null));
  }, [attachmentId, session?.token]);

  // Загружаем превью для изображений
  useEffect(() => {
    if (!attachment || !isImageMimetype(attachment.mimetype) || !session?.token) return;

    setIsLoading(true);
    fetch(`${API_BASE_URL}/attachments/${attachment.id}/preview`, {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(res => res.ok ? res.blob() : Promise.reject())
      .then(blob => {
        const reader = new FileReader();
        reader.onload = () => setImageSrc(reader.result as string);
        reader.readAsDataURL(blob);
      })
      .catch(() => setImageSrc(null))
      .finally(() => setIsLoading(false));
  }, [attachment, session?.token]);

  const handleDownload = () => {
    if (!attachment?.id || !session?.token) return;

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

  if (!attachment) {
    return (
      <Paper className={classes.previewCard} withBorder p="xl" radius="md">
        <Stack align="center" gap="md">
          <Loader size="sm" />
          <Text size="sm" c="dimmed">Загрузка...</Text>
        </Stack>
      </Paper>
    );
  }

  const isImage = isImageMimetype(attachment.mimetype);
  const isAudio = isAudioMimetype(attachment.mimetype);
  const isVideo = isVideoMimetype(attachment.mimetype);

  return (
    <>
      <Paper className={classes.previewCard} withBorder p="md" radius="md">
        {/* Превью */}
        <Box className={classes.previewArea}>
          {isLoading ? (
            <Loader size="md" />
          ) : isImage && imageSrc ? (
            <Image
              src={imageSrc}
              alt={attachment.name || ''}
              fit="contain"
              mah={300}
              radius="md"
              style={{ cursor: 'pointer' }}
              onClick={() => setPreviewOpen(true)}
            />
          ) : (
            <Box className={classes.iconArea}>
              <FileIcon mimetype={attachment.mimetype} size={80} />
            </Box>
          )}
        </Box>

        <Divider my="md" />

        {/* Информация о файле */}
        <Stack gap="xs">
          <Group justify="space-between">
            <Text size="lg" fw={600} lineClamp={1}>
              {attachment.name || 'Без имени'}
            </Text>
            <Group gap="xs">
              {isImage && imageSrc && (
                <Tooltip label="Просмотр">
                  <ActionIcon variant="light" color="blue" onClick={() => setPreviewOpen(true)}>
                    <IconEye size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
              <Tooltip label="Скачать">
                <ActionIcon variant="light" color="gray" onClick={handleDownload}>
                  <IconDownload size={18} />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>

          <Group gap="xs">
            <Badge size="sm" variant="light" color="gray">
              {formatFileSize(attachment.size)}
            </Badge>
            
            {attachment.folder && (
              <Badge size="sm" color="yellow" leftSection={<IconFolder size={10} />}>
                Папка
              </Badge>
            )}
            
            {attachment.is_voice && (
              <Badge size="sm" color="pink" leftSection={<IconMicrophone size={10} />}>
                Голосовое
              </Badge>
            )}
            
            {isImage && (
              <Badge size="sm" color="teal">Изображение</Badge>
            )}
            
            {isVideo && (
              <Badge size="sm" color="violet">Видео</Badge>
            )}
            
            {isAudio && !attachment.is_voice && (
              <Badge size="sm" color="pink">Аудио</Badge>
            )}

            <Badge 
              size="sm" 
              variant="light" 
              color={attachment.public ? 'green' : 'gray'}
              leftSection={attachment.public ? <IconWorld size={10} /> : <IconLock size={10} />}
            >
              {attachment.public ? 'Публичный' : 'Приватный'}
            </Badge>
          </Group>

          {attachment.mimetype && (
            <Text size="xs" c="dimmed">
              MIME: {attachment.mimetype}
            </Text>
          )}
        </Stack>
      </Paper>

      {/* Модалка просмотра */}
      {isImage && imageSrc && (
        <ImagePreviewModal
          opened={previewOpen}
          onClose={() => setPreviewOpen(false)}
          src={imageSrc}
          filename={attachment.name || undefined}
          onDownload={handleDownload}
        />
      )}
    </>
  );
}

export function ViewFormAttachments(props: ViewFormProps) {
  const { id } = useParams<{ id: string }>();
  const attachmentId = id ? parseInt(id, 10) : undefined;

  return (
    <Form<Attachment> model="attachments" {...props}>
      {/* Превью карточка */}
      {attachmentId && (
        <AttachmentPreviewCard attachmentId={attachmentId} />
      )}

      {/* Вкладки с информацией */}
      <FormTabs defaultTab="info">
        <FormTab name="info" label="Основная информация" icon={<IconFile size={16} />}>
          <FormSection title="Файл">
            <FormRow cols={2}>
              <Field name="id" label="ID" />
              <Field name="name" label="Название" />
            </FormRow>
            <FormRow cols={3}>
              <Field name="size" label="Размер (байт)" />
              <Field name="mimetype" label="MIME тип" />
              <Field name="checksum" label="Контрольная сумма" />
            </FormRow>
            <FormRow cols={3}>
              <Field name="public" label="Публичный" />
              <Field name="folder" label="Папка" />
              <Field name="is_voice" label="Голосовое сообщение" />
            </FormRow>
          </FormSection>

          <FormSection title="Доступ">
            <Field name="access_token" label="Токен доступа" />
          </FormSection>
        </FormTab>

        <FormTab name="resource" label="Привязка к ресурсу" icon={<IconDatabase size={16} />}>
          <FormSection title="Связанный ресурс">
            <FormRow cols={3}>
              <Field name="res_model" label="Модель" />
              <Field name="res_field" label="Поле" />
              <Field name="res_id" label="ID записи" />
            </FormRow>
          </FormSection>
        </FormTab>

        <FormTab name="storage" label="Хранилище" icon={<IconLink size={16} />}>
          <FormSection title="Настройки хранилища">
            <Field name="storage_id" label="Хранилище" />
            <FormRow cols={2}>
              <Field name="storage_file_id" label="ID файла в хранилище" />
              <Field name="storage_file_url" label="URL файла" />
            </FormRow>
            <FormRow cols={2}>
              <Field name="storage_parent_id" label="ID родительской папки" />
              <Field name="storage_parent_name" label="Имя родительской папки" />
            </FormRow>
          </FormSection>
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export function ViewFormAttachmentsStorage(props: ViewFormProps) {
  return (
    <Form<SchemaAttachmentStorage> model="attachments_storage" {...props}>
      <FormSection title="Настройки хранилища">
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="type" label="Тип" />
        </FormRow>
      </FormSection>
    </Form>
  );
}
