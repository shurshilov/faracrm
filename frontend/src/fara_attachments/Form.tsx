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
  Alert,
  Code,
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
  IconRoute,
  IconInfoCircle,
  IconSettings,
  IconArrowUp,
} from '@tabler/icons-react';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import {
  Attachment,
  SchemaAttachmentStorage,
} from '@/services/api/attachments';
import {
  FormRow,
  FormTabs,
  FormTab,
  FormSection,
} from '@/components/Form/Layout';
import { FileIcon } from '@/components/Attachment/FileIcon';
import { ImagePreviewModal } from '@/components/Attachment/ImagePreviewModal';
import {
  isImageMimetype,
  isAudioMimetype,
  isVideoMimetype,
  formatFileSize,
} from '@/components/Attachment/fileIcons';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { selectCurrentSession } from '@/slices/authSlice';
import classes from './Form.module.css';
import { FieldOne2many } from '@/components/Form/Fields/FieldOne2many';

// Тип для маршрута (UPDATED: removed is_default, folder_id, folder_model_name; added priority)
interface AttachmentRoute {
  id: number;
  name: string;
  model: string | null;
  priority: number;
  pattern_root: string;
  pattern_record: string;
  flat: boolean;
  filter: string;
  need_sync_root_name: boolean;
  storage_id: number;
  active: boolean;
}

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
    if (!attachment || !isImageMimetype(attachment.mimetype) || !session?.token)
      return;

    setIsLoading(true);
    fetch(`${API_BASE_URL}/attachments/${attachment.id}/preview`, {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(res => (res.ok ? res.blob() : Promise.reject()))
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
          <Text size="sm" c="dimmed">
            Загрузка...
          </Text>
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
                  <ActionIcon
                    variant="light"
                    color="blue"
                    onClick={() => setPreviewOpen(true)}>
                    <IconEye size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
              <Tooltip label="Скачать">
                <ActionIcon
                  variant="light"
                  color="gray"
                  onClick={handleDownload}>
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
              <Badge
                size="sm"
                color="yellow"
                leftSection={<IconFolder size={10} />}>
                Папка
              </Badge>
            )}

            {attachment.is_voice && (
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

            {isAudio && !attachment.is_voice && (
              <Badge size="sm" color="pink">
                Аудио
              </Badge>
            )}

            <Badge
              size="sm"
              variant="light"
              color={attachment.public ? 'green' : 'gray'}
              leftSection={
                attachment.public ? (
                  <IconWorld size={10} />
                ) : (
                  <IconLock size={10} />
                )
              }>
              {attachment.public ? 'Публичный' : 'Приватный'}
            </Badge>
          </Group>
        </Stack>
      </Paper>

      {/* Модальное окно для просмотра изображений */}
      {imageSrc && (
        <ImagePreviewModal
          opened={previewOpen}
          onClose={() => setPreviewOpen(false)}
          src={imageSrc}
          alt={attachment.name || ''}
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
      {attachmentId && <AttachmentPreviewCard attachmentId={attachmentId} />}

      {/* Вкладки с информацией */}
      <FormTabs defaultTab="info">
        <FormTab
          name="info"
          label="Основная информация"
          icon={<IconFile size={16} />}>
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
            <FormRow cols={2}>
              <Field name="show_preview" label="Показывать превью" />
            </FormRow>
          </FormSection>

          <FormSection title="Доступ">
            <Field name="access_token" label="Токен доступа" />
          </FormSection>
        </FormTab>

        <FormTab
          name="resource"
          label="Привязка к ресурсу"
          icon={<IconDatabase size={16} />}>
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
            <FormRow cols={2}>
              <Field name="storage_id" label="Хранилище" />
              <Field name="route_id" label="Маршрут" />
            </FormRow>
            <FormRow cols={2}>
              <Field name="storage_file_id" label="ID файла в хранилище" />
              <Field name="storage_file_url" label="URL файла" />
            </FormRow>
            <FormRow cols={2}>
              <Field name="storage_parent_id" label="ID родительской папки" />
              <Field
                name="storage_parent_name"
                label="Имя родительской папки"
              />
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
      {/* Основная информация */}
      <FormSection title="Основные настройки">
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="type" label="Тип хранилища" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="active" label="Активное" />
          <Field name="id" />
        </FormRow>
      </FormSection>

      {/* Вкладки для расширений */}
      <FormTabs defaultTab="connection">
        {/* Подключение - контент добавляется через расширения */}
        <FormTab
          name="connection"
          label="Подключение"
          icon={<IconLink size={16} />}>
          {/* Контент добавляется через расширения (Google Drive, Microsoft, etc.) */}
        </FormTab>

        <FormTab name="routes" label="Маршруты" icon={<IconRoute size={16} />}>
          <FormSection title="Маршруты организации файлов">
            <Alert
              icon={<IconInfoCircle size={16} />}
              title="Приоритеты маршрутов"
              color="blue"
              mb="md">
              <Text size="sm">
                Маршруты проверяются в порядке приоритета (высший первым).
                Маршрут с <Code>model=null</Code> и <Code>priority=0</Code>{' '}
                используется как fallback для всех моделей.
              </Text>
            </Alert>

            <Field name="route_ids">
              <Field name="id" />
              <Field name="name" />
              <Field name="model" />
              <Field name="priority" />
              <Field name="storage_id" />
              <Field name="pattern_root" />
              <Field name="pattern_record" />
              <Field name="active" />
            </Field>
          </FormSection>
        </FormTab>

        <FormTab
          name="sync"
          label="Синхронизация"
          icon={<IconSettings size={16} />}>
          <FormSection title="Режимы синхронизации">
            <FormRow cols={2}>
              <Field name="enable_realtime" label="Real-time" />
              <Field name="enable_one_way_cron" label="Односторонняя (cron)" />
            </FormRow>
            <FormRow cols={2}>
              <Field name="enable_two_way_cron" label="Двусторонняя (cron)" />
              <Field name="enable_routes_cron" label="Маршруты (cron)" />
            </FormRow>
          </FormSection>

          <FormSection title="Действия при отсутствии файлов">
            <FormRow cols={2}>
              <Field name="file_missing_cloud" label="Нет в облаке" />
              <Field name="file_missing_local" label="Нет в FARA" />
            </FormRow>
          </FormSection>
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export function ViewFormAttachmentsRoute(props: ViewFormProps) {
  return (
    <Form<AttachmentRoute> model="attachments_route" {...props}>
      {/* Основная информация */}
      <FormSection title="Основные настройки">
        <FormRow cols={2}>
          <Field name="name" label="Название маршрута" />
          <Field name="priority" label="Приоритет" />
        </FormRow>
        <Alert
          icon={<IconArrowUp size={16} />}
          color="gray"
          mb="md"
          variant="light">
          <Text size="xs">
            Высший приоритет проверяется первым. Fallback маршрут (для всех
            моделей) должен иметь <Code>priority=0</Code> и{' '}
            <Code>model=пусто</Code>
          </Text>
        </Alert>
        <FormRow cols={2}>
          <Field name="model" label="Модель (пусто = все модели)" />
          <Field name="storage_id" label="Хранилище" />
        </FormRow>
        <Field name="active" label="Активен" />
      </FormSection>

      <FormTabs defaultTab="patterns">
        <FormTab
          name="patterns"
          label="Шаблоны папок"
          icon={<IconFolder size={16} />}>
          <Alert
            icon={<IconInfoCircle size={16} />}
            title="Доступные переменные"
            color="blue"
            mb="md">
            <Text size="sm">
              <strong>Для корневой папки:</strong> <Code>{'{model}'}</Code>,{' '}
              <Code>{'{table}'}</Code>
            </Text>
            <Text size="sm" mt="xs">
              <strong>Для папки записи:</strong> <Code>{'{id}'}</Code>,{' '}
              <Code>{'{zfill(id)}'}</Code> (с нулями), и любые поля записи:{' '}
              <Code>{'{name}'}</Code>, <Code>{'{code}'}</Code> и т.д.
            </Text>
          </Alert>

          <FormSection title="Шаблон корневой папки">
            <Field name="pattern_root" label="Шаблон имени корневой папки" />
            <Text size="xs" c="dimmed" mt="xs">
              Пример: "Sales Orders" или "{'{model}'}" → создаст папку с именем
              модели
            </Text>
          </FormSection>

          <FormSection title="Шаблон папки записи">
            <FormRow cols={2}>
              <Field name="pattern_record" label="Шаблон имени папки записи" />
              <Field name="flat" label="Плоская структура (без подпапок)" />
            </FormRow>
            <Text size="xs" c="dimmed" mt="xs">
              Пример: "{'{zfill(id)}'}-{'{name}'}" → "0000001-John Doe"
            </Text>
          </FormSection>
        </FormTab>

        <FormTab
          name="filter"
          label="Фильтрация"
          icon={<IconRoute size={16} />}>
          <FormSection title="Фильтр записей">
            <Field name="filter" label="JSON фильтр" />
            <Text size="xs" c="dimmed" mt="xs">
              Пример: [["active", "=", true], ["state", "=", "done"]]
            </Text>
          </FormSection>
        </FormTab>

        <FormTab
          name="status"
          label="Статус"
          icon={<IconInfoCircle size={16} />}>
          <FormSection title="Синхронизация">
            <Field
              name="need_sync_root_name"
              label="Требуется синхронизация имени"
            />
            <Text size="xs" c="dimmed" mt="xs">
              Кеш папок хранится в отдельной таблице attachments_cache
            </Text>
          </FormSection>
        </FormTab>
      </FormTabs>
    </Form>
  );
}
