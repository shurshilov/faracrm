import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import {
  Button,
  Group,
  Badge,
  Text,
  Alert,
  Anchor,
  Stack,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';
import {
  IconBrandYandex,
  IconLink,
  IconAlertCircle,
  IconArrowRight,
  IconExternalLink,
} from '@tabler/icons-react';
import { useParams } from 'react-router-dom';

/**
 * Расширение формы хранилища для Яндекс.Диска.
 * Добавляется в таб "connection" (по аналогии с attachments_google).
 */
export function ViewFormStorageYandex() {
  const form = useFormContext();
  const { id } = useParams<{ id: string }>();
  const storageType = form.values?.type;
  const [isLoading, setIsLoading] = useState(false);

  // Показываем только для типа yandex
  if (storageType !== 'yandex') {
    return null;
  }

  const authState = form.values?.yandex_auth_state;
  const isAuthorized = authState === 'authorized';
  const isPending = authState === 'pending';
  const isFailed = authState === 'failed';

  const hasCredentials =
    !!form.values?.yandex_client_id && !!form.values?.yandex_client_secret;

  // Обработчик авторизации
  const handleAuthorize = async () => {
    if (!id) return;

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/yandex/auth/${id}`);
      const data = await response.json();

      if (data.authorization_url) {
        // Открываем Yandex OAuth в новом окне
        window.open(data.authorization_url, '_blank', 'width=600,height=700');
      } else if (data.error) {
        notifications.show({
          title: 'Ошибка',
          message: data.error,
          color: 'red',
        });
      }
    } catch (error) {
      notifications.show({
        title: 'Ошибка',
        message: 'Не удалось начать авторизацию',
        color: 'red',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <FormSection
      title="Yandex Disk"
      icon={<IconBrandYandex size={18} />}
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
              onClick={handleAuthorize}
              loading={isLoading}
              leftSection={<IconLink size={16} />}
              color="red"
              variant="outline"
              disabled={!id || !hasCredentials}>
              Авторизовать в Яндексе
            </Button>
          )}
        </Group>
      </Group>

      {!id && (
        <Alert icon={<IconAlertCircle size={16} />} color="blue" mb="md">
          Сначала сохраните хранилище, чтобы настроить авторизацию Яндекс.Диска.
        </Alert>
      )}

      {id && !hasCredentials && !isAuthorized && (
        <Alert icon={<IconAlertCircle size={16} />} color="orange" mb="md">
          Заполните Client ID и Client Secret для авторизации в Яндекс.Диске.
        </Alert>
      )}

      {/* Инструкции по настройке */}
      {!isAuthorized && (
        <Alert
          icon={<IconBrandYandex size={20} />}
          title="Настройка Яндекс.Диска"
          color="red"
          mb="md">
          <Text size="sm">Для настройки хранилища Яндекс.Диск:</Text>
          <ol style={{ margin: '8px 0', paddingLeft: '20px' }}>
            <li>Создайте OAuth-приложение на oauth.yandex.ru</li>
            <li>
              Добавьте права: <code>cloud_api:disk.read</code> и{' '}
              <code>cloud_api:disk.write</code>
            </li>
            <li>
              В качестве Redirect URI укажите{' '}
              <code>{`{ваш_домен}/yandex/callback`}</code>
            </li>
            <li>Скопируйте Client ID и Client Secret в поля ниже</li>
            <li>Сохраните хранилище и нажмите "Авторизовать"</li>
          </ol>

          <Stack gap="xs" mt="sm">
            <Anchor
              href="https://oauth.yandex.ru/client/new"
              target="_blank"
              size="sm">
              <Group gap={6}>
                <IconArrowRight size={14} />
                <Text span>1. Зарегистрировать приложение Yandex OAuth</Text>
                <IconExternalLink size={12} />
              </Group>
            </Anchor>
            <Anchor
              href="https://yandex.ru/dev/disk-api/doc/ru/concepts/quickstart"
              target="_blank"
              size="sm">
              <Group gap={6}>
                <IconArrowRight size={14} />
                <Text span>2. Документация Яндекс.Диск REST API</Text>
                <IconExternalLink size={12} />
              </Group>
            </Anchor>
          </Stack>
        </Alert>
      )}

      {/* Учётные данные приложения */}
      <FormRow cols={2}>
        <FieldChar
          name="yandex_client_id"
          label="Client ID"
          placeholder="abcdef..."
          description="Client ID из настроек OAuth-приложения"
        />
        <FieldChar
          name="yandex_client_secret"
          label="Client Secret"
          placeholder="••••••••"
          description="Client Secret из настроек OAuth-приложения"
        />
      </FormRow>

      {/* Папка */}
      <FormRow cols={1}>
        <FieldChar
          name="yandex_folder_path"
          label="Путь к корневой папке"
          placeholder="/CRM"
          description="Путь на Яндекс.Диске для хранения файлов (по умолчанию — корень)"
        />
      </FormRow>
    </FormSection>
  );
}

// Регистрируем расширение для модели attachments_storage
// Добавляется в таб "connection" (по аналогии с attachments_google)
registerExtension(
  'attachments_storage',
  ViewFormStorageYandex,
  'after:FormTab:connection',
  [
    'yandex_client_id',
    'yandex_client_secret',
    'yandex_access_token',
    'yandex_refresh_token',
    'yandex_token_expires_at',
    'yandex_auth_state',
    'yandex_verify_code',
    'yandex_folder_path',
  ],
);

export default ViewFormStorageYandex;
