import { useEffect, useState } from 'react';
import { Button, Container, Text, TextInput, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { useReadQuery, useUpdateMutation } from '@/services/api/crudApi';
import { selectCurrentSession } from '@/slices/authSlice';

/**
 * Счёт для выплат поставщику — поле payout_account на самом пользователе
 * (расширение User из модуля marketplace). Своя страница вместо формы
 * пользователя: портальной роли остальные поля профиля не нужны.
 */
export default function VendorSettings() {
  const { t } = useTranslation('marketplace');
  const userId = useSelector(selectCurrentSession)?.user_id?.id;
  const { data } = useReadQuery(
    { model: 'users', id: userId ?? 0, fields: ['id', 'payout_account'] },
    { skip: !userId },
  );
  const [update, { isLoading }] = useUpdateMutation();
  const [value, setValue] = useState('');

  useEffect(() => {
    setValue((data?.data as { payout_account?: string })?.payout_account || '');
  }, [data]);

  const save = async () => {
    if (!userId) return;
    await update({
      model: 'users',
      id: userId,
      values: { payout_account: value.trim() },
    }).unwrap();
    notifications.show({ message: t('vendor.saved') });
  };

  return (
    <Container size="sm" py="md">
      <Title order={3}>{t('vendor.title')}</Title>
      <Text c="dimmed" size="sm" mb="md">
        {t('vendor.hint')}
      </Text>
      <TextInput
        label={t('vendor.payoutAccount')}
        placeholder="ShopCode"
        value={value}
        onChange={e => setValue(e.currentTarget.value)}
      />
      <Button mt="md" onClick={save} loading={isLoading}>
        {t('vendor.save')}
      </Button>
    </Container>
  );
}
