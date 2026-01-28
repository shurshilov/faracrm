import { useState } from 'react';
import {
  Modal,
  TextInput,
  Button,
  Stack,
  Group,
  Checkbox,
  Text,
  Divider,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconCopy, IconCheck } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import { useNavigate } from 'react-router-dom';
import { useCopyUserMutation } from '@/services/api/users';

interface CopyUserModalProps {
  opened: boolean;
  onClose: () => void;
  userId: number;
  userName?: string;
  userLogin?: string;
  isAdmin?: boolean;
}

interface CopyUserFormValues {
  name: string;
  login: string;
  copyPassword: boolean;
  copyRoles: boolean;
  copyFiles: boolean;
  copyLanguages: boolean;
  copyIsAdmin: boolean;
  copyContacts: boolean;
}

export function CopyUserModal({
  opened,
  onClose,
  userId,
  userName = '',
  userLogin = '',
  isAdmin = false,
}: CopyUserModalProps) {
  const { t } = useTranslation('users');
  const navigate = useNavigate();
  const [copyUser, { isLoading }] = useCopyUserMutation();

  const form = useForm<CopyUserFormValues>({
    initialValues: {
      name: userName ? `${userName} (копия)` : '',
      login: userLogin ? `${userLogin}_copy` : '',
      copyPassword: false,
      copyRoles: true,
      copyFiles: false,
      copyLanguages: true,
      copyIsAdmin: true,
      copyContacts: false,
    },
    validate: {
      name: value => {
        if (!value.trim()) return t('copyUser.nameRequired', 'Имя обязательно');
        return null;
      },
      login: value => {
        if (!value.trim())
          return t('copyUser.loginRequired', 'Логин обязателен');
        if (!/^[a-zA-Z0-9_]+$/.test(value)) {
          return t(
            'copyUser.loginInvalid',
            'Логин может содержать только латинские буквы, цифры и _',
          );
        }
        return null;
      },
    },
  });

  // Обновляем initialValues когда меняются props
  useState(() => {
    if (userName) {
      form.setFieldValue('name', `${userName} (копия)`);
    }
    if (userLogin) {
      form.setFieldValue('login', `${userLogin}_copy`);
    }
  });

  const handleSubmit = async (values: CopyUserFormValues) => {
    try {
      const result = await copyUser({
        source_user_id: userId,
        name: values.name,
        login: values.login,
        copy_password: values.copyPassword,
        copy_roles: values.copyRoles,
        copy_files: values.copyFiles,
        copy_languages: values.copyLanguages,
        copy_is_admin: values.copyIsAdmin,
        copy_contacts: values.copyContacts,
      }).unwrap();

      notifications.show({
        title: t('copyUser.success', 'Успешно'),
        message: t('copyUser.successMessage', 'Пользователь скопирован'),
        color: 'green',
        icon: <IconCheck size={16} />,
      });

      form.reset();
      onClose();

      // Переходим к новому пользователю
      navigate(`/users/${result.id}`);
    } catch (error: any) {
      const message =
        error?.data?.error ||
        t('copyUser.errorMessage', 'Не удалось скопировать пользователя');
      notifications.show({
        title: t('copyUser.error', 'Ошибка'),
        message,
        color: 'red',
      });
    }
  };

  const handleClose = () => {
    form.reset();
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={
        <Group gap="xs">
          <IconCopy size={20} />
          <Text fw={500}>{t('copyUser.title', 'Копировать пользователя')}</Text>
        </Group>
      }
      size="md">
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          {/* Основные данные */}
          <TextInput
            label={t('copyUser.name', 'Имя')}
            placeholder={t('copyUser.namePlaceholder', 'Введите имя')}
            required
            {...form.getInputProps('name')}
          />

          <TextInput
            label={t('copyUser.login', 'Логин')}
            placeholder={t('copyUser.loginPlaceholder', 'Введите логин')}
            required
            {...form.getInputProps('login')}
          />

          <Divider
            label={t('copyUser.copyOptions', 'Параметры копирования')}
            labelPosition="center"
          />

          {/* Чекбоксы */}
          <Stack gap="xs">
            <Checkbox
              label={t('copyUser.copyPassword', 'Копировать пароль')}
              description={t(
                'copyUser.copyPasswordDesc',
                'Новый пользователь сможет войти с тем же паролем',
              )}
              {...form.getInputProps('copyPassword', { type: 'checkbox' })}
            />

            <Checkbox
              label={t('copyUser.copyRoles', 'Копировать роли и права')}
              {...form.getInputProps('copyRoles', { type: 'checkbox' })}
            />

            {/* <Checkbox
              label={t('copyUser.copyLanguages', 'Копировать доступные языки')}
              {...form.getInputProps('copyLanguages', { type: 'checkbox' })}
            /> */}

            <Checkbox
              label={
                <Group gap="xs">
                  <span>{t('copyUser.copyIsAdmin', 'Суперпользователь')}</span>
                  {isAdmin && (
                    <Text size="xs" c="dimmed">
                      ({t('copyUser.currentlyEnabled', 'у исходного включено')})
                    </Text>
                  )}
                </Group>
              }
              description={t(
                'copyUser.copyIsAdminDesc',
                'Копировать статус суперпользователя',
              )}
              {...form.getInputProps('copyIsAdmin', { type: 'checkbox' })}
            />

            {/* <Checkbox
              label={t('copyUser.copyFiles', 'Копировать файлы')}
              description={t('copyUser.copyFilesDesc', 'Создать копии прикреплённых файлов')}
              {...form.getInputProps('copyFiles', { type: 'checkbox' })}
            /> */}

            <Checkbox
              label={t('copyUser.copyContacts', 'Копировать контакты')}
              description={t(
                'copyUser.copyContactsDesc',
                'Телефоны, email, мессенджеры',
              )}
              {...form.getInputProps('copyContacts', { type: 'checkbox' })}
            />
          </Stack>

          <Group justify="flex-end" mt="md">
            <Button variant="light" onClick={handleClose} disabled={isLoading}>
              {t('common.cancel', 'Отмена')}
            </Button>
            <Button
              type="submit"
              loading={isLoading}
              leftSection={<IconCopy size={16} />}>
              {t('copyUser.submit', 'Создать')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

export default CopyUserModal;
