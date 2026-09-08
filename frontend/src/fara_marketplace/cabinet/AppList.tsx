import type { FaraRecord } from '@/services/api/crudTypes';
import { useCallback, useState } from 'react';
import { Button } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconBrandGithub } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewListProps } from '@/route/type';
import { selectCurrentSession } from '@/slices/authSlice';
import { useSearchQuery } from '@/services/api/crudApi';
import { useSyncGitAppsMutation } from '../api';

/** «Импорт из GitHub» (суперпользователь): без git-хранилища ведёт его
 *  создавать, с ним — добавляет в каталог модули репозитория
 *  (неопубликованными, архив — вложение в git-хранилище). */
function GitSyncButton({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation('marketplace');
  const navigate = useNavigate();
  const { data: storages } = useSearchQuery({
    model: 'attachments_storage',
    fields: ['id'],
    filter: [['type', '=', 'git']],
    limit: 1,
  });
  const [sync, { isLoading }] = useSyncGitAppsMutation();

  const handleClick = async () => {
    if (!storages?.data?.length) {
      navigate('/attachments_storage/create');
      return;
    }
    const result = await sync().unwrap();
    notifications.show({
      message: t('git.synced', { count: result.data.created }),
    });
    onDone();
  };

  return (
    <Button
      variant="light"
      size="compact-sm"
      leftSection={<IconBrandGithub size={16} />}
      loading={isLoading}
      onClick={handleClick}>
      {t('git.sync')}
    </Button>
  );
}

// «Мои приложения» — кабинет поставщика: только свои записи. Чужие
// опубликованные приложения тоже читаемы (правило каталога), но здесь
// они не нужны — за ними на публичную страницу /market.
export function ViewListMarketplaceApp(props: ViewListProps) {
  const { t } = useTranslation('marketplace');
  const user = useSelector(selectCurrentSession)?.user_id;
  const [refetchFn, setRefetchFn] = useState<(() => void) | null>(null);
  const handleRefetch = useCallback((refetch: () => void) => {
    setRefetchFn(() => refetch);
  }, []);

  return (
    <List<FaraRecord>
      model="marketplace_app"
      sort="id"
      order="desc"
      {...props}
      filter={[...(props.filter ?? []), ['create_user_id', '=', user?.id]]}
      toolbarActions={
        user?.is_admin ? (
          <GitSyncButton onDone={() => refetchFn?.()} />
        ) : undefined
      }
      onRefetch={handleRefetch}>
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="code" label={t('fields.code')} />
      <Field name="category" label={t('fields.category')} />
      <Field name="version" label={t('fields.version')} />
      <Field name="price" label={t('fields.price')} />
      <Field name="published" label={t('fields.published')} />
      <Field name="verified" label={t('fields.verified')} />
      <Field name="downloads" label={t('fields.downloads')} />
    </List>
  );
}

export default ViewListMarketplaceApp;
