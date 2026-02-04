import { useMemo } from 'react';
import {
  Modal,
  Button,
  Stack,
  Group,
  PasswordInput,
  Text,
  List,
  ThemeIcon,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconLock, IconCheck, IconX } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import { useChangePasswordMutation } from '@/services/api/users';
import { useSearchQuery } from '@/services/api/crudApi';

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

interface PasswordPolicy {
  min_length: number;
  require_uppercase: boolean;
  require_lowercase: boolean;
  require_digits: boolean;
  require_special: boolean;
}

const DEFAULT_POLICY: PasswordPolicy = {
  min_length: 5,
  require_uppercase: false,
  require_lowercase: false,
  require_digits: false,
  require_special: false,
};

function parsePolicyFromSettings(data: any): PasswordPolicy {
  try {
    const record = data?.data?.[0];
    if (!record?.value) return DEFAULT_POLICY;
    const raw = typeof record.value === 'string' ? JSON.parse(record.value) : record.value;
    const policy = raw?.value ?? raw;
    return {
      min_length: policy.min_length ?? DEFAULT_POLICY.min_length,
      require_uppercase: policy.require_uppercase ?? DEFAULT_POLICY.require_uppercase,
      require_lowercase: policy.require_lowercase ?? DEFAULT_POLICY.require_lowercase,
      require_digits: policy.require_digits ?? DEFAULT_POLICY.require_digits,
      require_special: policy.require_special ?? DEFAULT_POLICY.require_special,
    };
  } catch {
    return DEFAULT_POLICY;
  }
}

function validatePassword(
  password: string,
  policy: PasswordPolicy,
): { passed: boolean; checks: { key: string; ok: boolean }[] } {
  const checks = [
    { key: 'min_length', ok: password.length >= policy.min_length },
  ];

  if (policy.require_uppercase) {
    checks.push({ key: 'uppercase', ok: /[A-ZА-ЯЁ]/.test(password) });
  }
  if (policy.require_lowercase) {
    checks.push({ key: 'lowercase', ok: /[a-zа-яё]/.test(password) });
  }
  if (policy.require_digits) {
    checks.push({ key: 'digits', ok: /[0-9]/.test(password) });
  }
  if (policy.require_special) {
    checks.push({ key: 'special', ok: /[!@#$%^&*()_+\-=\[\]{}|;:'",.<>?/\\`~]/.test(password) });
  }

  return { passed: checks.every(c => c.ok), checks };
}

export function ChangePasswordModal({
  opened,
  onClose,
  userId,
  userName,
}: ChangePasswordModalProps) {
  const { t } = useTranslation('users');
  const [changePassword, { isLoading }] = useChangePasswordMutation();

  // Читаем парольную политику из system_settings через CRUD
  const { data: settingsData } = useSearchQuery(
    {
      model: 'system_settings',
      filter: [['key', '=', 'auth.password_policy']],
      fields: ['id', 'value'],
      limit: 1,
    },
    { skip: !opened },
  );

  const policy = useMemo(() => parsePolicyFromSettings(settingsData), [settingsData]);

  const checkLabel = (check: { key: string }) => {
    const labels: Record<string, string> = {
      min_length: t('changePassword.rule_min_length', { count: policy.min_length, defaultValue: `Минимум {{count}} символов` }),
      uppercase: t('changePassword.rule_uppercase', 'Заглавная буква (A-Z)'),
      lowercase: t('changePassword.rule_lowercase', 'Строчная буква (a-z)'),
      digits: t('changePassword.rule_digits', 'Цифра (0-9)'),
      special: t('changePassword.rule_special', 'Спецсимвол (!@#$%...)'),
    };
    return labels[check.key] || check.key;
  };

  const form = useForm<PasswordFormValues>({
    initialValues: {
      password: '',
      confirmPassword: '',
    },
    validate: {
      password: (value) => {
        if (!value) return t('changePassword.passwordRequired', 'Введите пароль');
        const { passed } = validatePassword(value, policy);
        if (!passed) return t('changePassword.policyNotMet', 'Пароль не соответствует требованиям');
        return null;
      },
      confirmPassword: (value, values) => {
        if (!value) return t('changePassword.confirmRequired', 'Подтвердите пароль');
        if (value !== values.password) return t('changePassword.passwordsMismatch', 'Пароли не совпадают');
        return null;
      },
    },
  });

  const currentPassword = form.getValues().password;
  const currentChecks = validatePassword(currentPassword || '', policy).checks;

  const handleSubmit = async (values: PasswordFormValues) => {
    try {
      await changePassword({
        userId,
        password: values.password,
      }).unwrap();

      notifications.show({
        title: t('changePassword.success', 'Готово'),
        message: t('changePassword.successMessage', 'Пароль успешно изменён'),
        color: 'green',
        icon: <IconCheck size={16} />,
      });

      form.reset();
      onClose();
    } catch (error: any) {
      const isPolicy = error?.data?.error === '#PASSWORD_POLICY';
      notifications.show({
        title: t('changePassword.error', 'Ошибка'),
        message: isPolicy
          ? t('changePassword.policyNotMet', 'Пароль не соответствует требованиям')
          : t('changePassword.errorMessage', 'Не удалось сменить пароль'),
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
          <Text fw={500}>{t('changePassword.title', 'Смена пароля')}</Text>
        </Group>
      }
      size="sm"
    >
      {userName && (
        <Text size="sm" c="dimmed" mb="md">
          {t('changePassword.forUser', 'Пользователь')}: <Text span fw={500}>{userName}</Text>
        </Text>
      )}

      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <PasswordInput
            label={t('changePassword.newPassword', 'Новый пароль')}
            placeholder={t('changePassword.enterNewPassword', 'Введите новый пароль')}
            required
            {...form.getInputProps('password')}
          />

          {currentPassword && (
            <List spacing={4} size="sm">
              {currentChecks.map(check => (
                <List.Item
                  key={check.key}
                  icon={
                    <ThemeIcon
                      color={check.ok ? 'teal' : 'red'}
                      size={18}
                      radius="xl"
                      variant="light"
                    >
                      {check.ok ? <IconCheck size={12} /> : <IconX size={12} />}
                    </ThemeIcon>
                  }
                  style={{ color: check.ok ? 'var(--mantine-color-teal-7)' : 'var(--mantine-color-red-7)' }}
                >
                  {checkLabel(check)}
                </List.Item>
              ))}
            </List>
          )}

          <PasswordInput
            label={t('changePassword.confirmPassword', 'Подтверждение пароля')}
            placeholder={t('changePassword.confirmNewPassword', 'Повторите новый пароль')}
            required
            {...form.getInputProps('confirmPassword')}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="light" onClick={handleClose} disabled={isLoading}>
              {t('common.cancel', 'Отмена')}
            </Button>
            <Button type="submit" loading={isLoading}>
              {t('changePassword.submit', 'Сменить пароль')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

export default ChangePasswordModal;
