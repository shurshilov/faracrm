import { useEffect, useState } from 'react';
import {
  Button,
  Container,
  Divider,
  Group,
  Select,
  Stack,
  TextInput,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import {
  useReadQuery,
  useSearchQuery,
  useUpdateMutation,
} from '@/services/api/crudApi';
import { selectCurrentSession } from '@/slices/authSlice';
import { PasswordChangeForm } from './PasswordChangeForm';

interface ProfileRecord {
  id: number;
  name: string;
  login: string;
  lang_id?: { id: number; name?: string } | null;
}

interface LanguageOption {
  id: number;
  code: string;
  name: string;
}

/**
 * Лёгкий профиль: имя, язык, пароль. Для пользователя без base_user
 * (портальный из маркетплейса): полная карточка /users/{id} тянет роли,
 * команды, контакты и «Рабочее место», которые ему закрыты, и не открывается
 * вовсе. Здесь только то, что разрешено правилом «свой профиль».
 */
export default function ProfilePage() {
  const { t } = useTranslation('users');
  const userId = useSelector(selectCurrentSession)?.user_id?.id;

  const { data } = useReadQuery(
    {
      model: 'users',
      id: userId ?? 0,
      fields: ['id', 'name', 'login', 'lang_id'],
    },
    { skip: !userId },
  );
  const { data: languagesData } = useSearchQuery({
    model: 'language',
    filter: [['active', '=', true]],
    fields: ['id', 'code', 'name'],
    sort: 'code',
    order: 'asc',
  });
  const [update, { isLoading }] = useUpdateMutation();

  const user = data?.data as ProfileRecord | undefined;
  const languages = (languagesData?.data as LanguageOption[] | undefined) ?? [];

  const [name, setName] = useState('');
  const [langId, setLangId] = useState<string | null>(null);
  useEffect(() => {
    setName(user?.name ?? '');
    setLangId(user?.lang_id?.id ? String(user.lang_id.id) : null);
  }, [user]);

  const save = async () => {
    if (!userId) return;
    await update({
      model: 'users',
      id: userId,
      values: {
        name: name.trim(),
        ...(langId ? { lang_id: Number(langId) } : {}),
      },
    }).unwrap();
    notifications.show({ message: t('profile.saved') });
  };

  return (
    <Container size="sm" py="md">
      <Title order={3} mb="md">
        {t('profile.title')}
      </Title>
      <Stack gap="sm">
        <TextInput label={t('fields.login')} value={user?.login ?? ''} disabled />
        <TextInput
          label={t('fields.name')}
          value={name}
          onChange={e => setName(e.currentTarget.value)}
        />
        <Select
          label={t('fields.lang')}
          data={languages.map(lang => ({
            value: String(lang.id),
            label: lang.name,
          }))}
          value={langId}
          onChange={setLangId}
          allowDeselect={false}
        />
        <Group justify="flex-end">
          <Button onClick={save} loading={isLoading} disabled={!name.trim()}>
            {t('profile.save')}
          </Button>
        </Group>
      </Stack>

      <Divider my="lg" />

      {userId && <PasswordChangeForm userId={userId} />}
    </Container>
  );
}
