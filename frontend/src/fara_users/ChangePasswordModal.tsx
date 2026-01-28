import { useState } from 'react';
import {
  Modal,
  TextInput,
  Button,
  Stack,
  Group,
  PasswordInput,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconLock, IconCheck } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import { useChangePasswordMutation } from '@/services/api/users';

interface ChangePasswordModalProps {
  opened: boolean;
  onClose: () => void;
  userId: number;
  userName?: string;
}

interface PasswordFormValues {
  password: string;
  confirmPassword: string;
}

export function ChangePasswordModal({
  opened,
  onClose,
  userId,
  userName,
}: ChangePasswordModalProps) {
  const { t } = useTranslation('users');
  const [changePassword, { isLoading }] = useChangePasswordMutation();

  const form = useForm<PasswordFormValues>({
    initialValues: {
      password: '',
      confirmPassword: '',
    },
    validate: {
      password: (value) => {
        if (!value) return t('changePassword.passwordRequired', 'Password is required');
        if (value.length < 8) return t('changePassword.passwordTooShort', 'Password must be at least 8 characters');
        return null;
      },
      confirmPassword: (value, values) => {
        if (!value) return t('changePassword.confirmRequired', 'Please confirm password');
        if (value !== values.password) return t('changePassword.passwordsMismatch', 'Passwords do not match');
        return null;
      },
    },
  });

  const handleSubmit = async (values: PasswordFormValues) => {
    try {
      await changePassword({
        userId,
        password: values.password,
      }).unwrap();

      notifications.show({
        title: t('changePassword.success', 'Success'),
        message: t('changePassword.successMessage', 'Password changed successfully'),
        color: 'green',
        icon: <IconCheck size={16} />,
      });

      form.reset();
      onClose();
    } catch (error) {
      notifications.show({
        title: t('changePassword.error', 'Error'),
        message: t('changePassword.errorMessage', 'Failed to change password'),
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
          <IconLock size={20} />
          <Text fw={500}>{t('changePassword.title', 'Change Password')}</Text>
        </Group>
      }
      size="sm"
    >
      {userName && (
        <Text size="sm" c="dimmed" mb="md">
          {t('changePassword.forUser', 'For user')}: <Text span fw={500}>{userName}</Text>
        </Text>
      )}

      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <PasswordInput
            label={t('changePassword.newPassword', 'New Password')}
            placeholder={t('changePassword.enterNewPassword', 'Enter new password')}
            required
            {...form.getInputProps('password')}
          />

          <PasswordInput
            label={t('changePassword.confirmPassword', 'Confirm Password')}
            placeholder={t('changePassword.confirmNewPassword', 'Confirm new password')}
            required
            {...form.getInputProps('confirmPassword')}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="light" onClick={handleClose} disabled={isLoading}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button type="submit" loading={isLoading}>
              {t('changePassword.submit', 'Change Password')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

export default ChangePasswordModal;
