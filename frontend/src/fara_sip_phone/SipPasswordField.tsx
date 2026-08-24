// Copyright 2025 FARA CRM
// Пароль SIP-регистрации линии.
//
// Поле private=True — в API-схему модели оно не попадает, значит и в generic-
// форму не приедет. Пишется отдельной ручкой; прочитать его обратно нельзя ни
// здесь, ни через список номеров — только владелец получает его при регистрации.

import { useState } from 'react';
import { Button, Group, PasswordInput, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import { useSetSipPasswordMutation } from '@/services/api/telephony';
import { useFormContext } from '@/components/Form/FormContext';

export function SipPasswordField() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [password, setPassword] = useState('');
  const [save, { isLoading }] = useSetSipPasswordMutation();

  // На форме создания записи ещё нет — пароль задаётся после сохранения.
  const phoneNumberId = Number(form.values?.id) || undefined;
  if (!phoneNumberId) return null;

  const handleSave = async () => {
    try {
      await save({ phoneNumberId, password }).unwrap();
      setPassword('');
      notifications.show({
        message: t('phoneNumber.sipPasswordSaved', 'Пароль сохранён'),
        color: 'green',
      });
    } catch {
      notifications.show({
        message: t(
          'phoneNumber.sipPasswordFailed',
          'Не удалось сохранить пароль',
        ),
        color: 'red',
      });
    }
  };

  return (
    <>
      <Group align="flex-end" gap="xs">
        <PasswordInput
          flex={1}
          value={password}
          onChange={e => setPassword(e.currentTarget.value)}
          label={t('phoneNumber.fields.sipPassword', 'Пароль SIP')}
          placeholder="••••••••"
        />
        <Button
          variant="light"
          loading={isLoading}
          disabled={!password}
          onClick={handleSave}>
          {t('common.save', 'Сохранить')}
        </Button>
      </Group>
      <Text size="xs" c="dimmed" mt={4}>
        {t(
          'phoneNumber.hints.sipPassword',
          'Нужен, чтобы сотрудник мог звонить из браузера. Обратно не читается: ' +
            'приходит только владельцу линии при регистрации звонилки.',
        )}
      </Text>
    </>
  );
}
