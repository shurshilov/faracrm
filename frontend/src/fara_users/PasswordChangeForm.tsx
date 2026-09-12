import { useState } from 'react';
import {
  Button,
  Group,
  List,
  PasswordInput,
  Stack,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import { useChangePasswordMutation } from '@/services/api/users';

interface PasswordChangeFormProps {
  userId: number;
}

/**
 * Смена своего пароля без чтения парольной политики: ChangePasswordModal
 * берёт её из system_settings, а эта таблица открыта не всем (портальному
 * пользователю — нет). Политику проверяет бэк и возвращает коды нарушений
 * (`#PASSWORD_POLICY` + details) — их и показываем.
 */
export function PasswordChangeForm({ userId }: PasswordChangeFormProps) {
  const { t } = useTranslation('users');
  const [changePassword, { isLoading }] = useChangePasswordMutation();
  const [policyErrors, setPolicyErrors] = useState<string[]>([]);

  const form = useForm({
    initialValues: { password: '', confirmPassword: '' },
    validate: {
      password: value =>
        value ? null : t('changePassword.passwordRequired'),
      confirmPassword: (value, values) =>
        value === values.password
          ? null
          : t('changePassword.passwordsMismatch'),
    },
  });

  // Код с бэка: too_short:8, no_uppercase, no_lowercase, no_digit, no_special.
  const policyLabel = (code: string) => {
    const [key, arg] = code.split(':');
    return t(`profile.policy.${key}`, { count: Number(arg) || 0 });
  };

  const submit = async (values: typeof form.values) => {
    setPolicyErrors([]);
    try {
      await changePassword({ userId, password: values.password }).unwrap();
      notifications.show({
        message: t('changePassword.successMessage'),
        color: 'green',
      });
      form.reset();
    } catch (error: any) {
      if (error?.data?.error === '#PASSWORD_POLICY') {
        setPolicyErrors(error.data.details ?? []);
        return;
      }
      notifications.show({
        message: t('changePassword.errorMessage'),
        color: 'red',
      });
    }
  };

  return (
    <form onSubmit={form.onSubmit(submit)}>
      <Stack gap="sm">
        <Text fw={500}>{t('changePassword.title')}</Text>
        <PasswordInput
          label={t('changePassword.newPassword')}
          {...form.getInputProps('password')}
        />
        <PasswordInput
          label={t('changePassword.confirmPassword')}
          {...form.getInputProps('confirmPassword')}
        />
        {policyErrors.length > 0 && (
          <List size="sm" c="red">
            {policyErrors.map(code => (
              <List.Item key={code}>{policyLabel(code)}</List.Item>
            ))}
          </List>
        )}
        <Group justify="flex-end">
          <Button type="submit" loading={isLoading}>
            {t('changePassword.submit')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
