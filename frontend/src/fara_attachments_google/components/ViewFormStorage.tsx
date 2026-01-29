import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FieldBoolean } from '@/components/Form/Fields/FieldBoolean';
import { FieldFile } from '@/components/Form/Fields/FieldFile';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import {
  Button,
  Group,
  Badge,
  Text,
  Alert,
  Anchor,
  Stack,
  Box,
} from '@mantine/core';
import {
  IconBrandGoogleDrive,
  IconLink,
  IconAlertCircle,
  IconArrowRight,
  IconInfoCircle,
  IconExternalLink,
} from '@tabler/icons-react';

/**
 * Расширение формы хранилища для Google Drive.
 * Добавляется в таб "connection" (по аналогии с chat_telegram).
 */
export function ViewFormStorageGoogle() {
  const form = useFormContext();
  const storageType = form.values?.type;

  // Показываем только для типа google
  if (storageType !== 'google') {
    return null;
  }

  const authState = form.values?.google_auth_state;
  const isAuthorized = authState === 'authorized';
  const isPending = authState === 'pending';
  const isFailed = authState === 'failed';

  return (
    <FormSection
      title="Google Drive"
      icon={<IconBrandGoogleDrive size={18} />}
      collapsible>
      {/* Статус авторизации */}
      <Group mb="md" justify="space-between">
        <Group gap="sm">
          <Text size="sm" fw={500}>
            Статус авторизации:
          </Text>
          <Badge
            color={
              isAuthorized
                ? 'green'
                : isFailed
                  ? 'red'
                  : isPending
                    ? 'yellow'
                    : 'gray'
            }
            variant="filled"
            size="lg">
            {isAuthorized && 'Авторизован'}
            {isPending && 'Ожидает авторизации'}
            {isFailed && 'Ошибка авторизации'}
            {(!authState || authState === 'none') && 'Не настроен'}
          </Badge>
        </Group>

        <Group gap="sm">
          {!isAuthorized && (
            <Button
              leftSection={<IconLink size={16} />}
              color="blue"
              variant="outline"
              disabled={!form.values?.id}>
              Авторизовать в Google
            </Button>
          )}
        </Group>
      </Group>

      {!form.values?.id && (
        <Alert icon={<IconAlertCircle size={16} />} color="blue" mb="md">
          Сначала сохраните хранилище, чтобы настроить авторизацию Google Drive.
        </Alert>
      )}

      {/* Инструкции по настройке */}
      {!isAuthorized && (
        <Alert
          icon={<IconBrandGoogleDrive size={20} />}
          title="Настройка Google Drive"
          color="blue"
          mb="md">
          <Text size="sm">Для настройки хранилища Google Drive:</Text>
          <ol style={{ margin: '8px 0', paddingLeft: '20px' }}>
            <li>Создайте проект в Google Cloud Console</li>
            <li>Включите Google Drive API</li>
            <li>Создайте OAuth 2.0 credentials</li>
            <li>Скачайте credentials.json и загрузите его ниже</li>
            <li>Сохраните хранилище и нажмите "Авторизовать"</li>
          </ol>

          {/* Ссылки на Google Cloud Console */}
          <Stack gap="xs" mt="sm">
            <Anchor
              href="https://console.cloud.google.com/apis/dashboard"
              target="_blank"
              size="sm">
              <Group gap={6}>
                <IconArrowRight size={14} />
                <Text span>1. Enable Google Drive API</Text>
                <IconExternalLink size={12} />
              </Group>
            </Anchor>
            <Anchor
              href="https://console.cloud.google.com/apis/credentials"
              target="_blank"
              size="sm">
              <Group gap={6}>
                <IconArrowRight size={14} />
                <Text span>2. Create Web App credentials</Text>
                <IconExternalLink size={12} />
              </Group>
            </Anchor>
          </Stack>
        </Alert>
      )}

      {/* Credentials файл */}
      <FormRow cols={1}>
        <FieldFile
          name="google_json_credentials"
          label="Файл credentials.json"
          accept=".json"
          description="Загрузите файл credentials.json из Google Cloud Console"
        />
      </FormRow>

      {/* Настройки папки */}
      <FormRow cols={2}>
        <FieldChar
          name="google_folder_id"
          label="ID корневой папки"
          placeholder="1ABC...xyz"
          description="ID папки в Google Drive для хранения файлов"
        />
        <FieldSelection
          name="google_auth_state"
          label="Статус авторизации"
          readonly
        />
      </FormRow>

      {/* Shared Drive настройки */}
      <FormRow cols={2}>
        <FieldBoolean
          name="google_team_enabled"
          label="Использовать Shared Drive"
          description="Включите для хранения файлов в общем диске команды"
        />
        <FieldChar
          name="google_team_id"
          label="ID Shared Drive"
          placeholder="0ABC...xyz"
          disabled={!form.values?.google_team_enabled}
          description="ID общего диска (Team Drive)"
        />
      </FormRow>

      {/* Напоминание про production mode - всегда видно, но ненавязчиво */}
      <Box
        mt="md"
        pt="sm"
        style={{
          borderTop: '1px solid var(--mantine-color-gray-2)',
        }}>
        <Group gap={6} c="dimmed">
          <IconInfoCircle size={14} style={{ flexShrink: 0 }} />
          <Text size="xs" c="dimmed">
            Не забудьте переключить приложение в{' '}
            <Anchor
              href="https://console.cloud.google.com/auth/audience"
              target="_blank"
              size="xs"
              c="dimmed"
              td="underline">
              production mode
            </Anchor>
            . Иначе интеграция перестанет работать через 7 дней (только для
            external).
          </Text>
        </Group>
      </Box>
    </FormSection>
  );
}

// Регистрируем расширение для модели attachments_storage
// Добавляется в таб "connection" (по аналогии с chat_telegram)
registerExtension(
  'attachments_storage',
  ViewFormStorageGoogle,
  'after:FormTab:connection',
  [
    'google_json_credentials',
    'google_credentials',
    'google_refresh_token',
    'google_auth_state',
    'google_verify_code',
    'google_folder_id',
    'google_team_enabled',
    'google_team_id',
  ],
);

export default ViewFormStorageGoogle;
