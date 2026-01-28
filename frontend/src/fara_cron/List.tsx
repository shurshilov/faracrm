/**
 * Список запланированных задач (cron jobs)
 * Использует унифицированный компонент List
 */

import { useState, useCallback } from 'react';
import { Button, Tooltip, ActionIcon, Group } from '@mantine/core';
import { IconPlayerPlay, IconRefresh } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

// Интерфейс для записи cron_job
interface SchemaCronJob {
  id: number;
  name: string;
  active: boolean;
  model_path: string;
  method_name: string;
  interval_number: number;
  interval_type: string;
  nextcall: string | null;
  lastcall: string | null;
  last_status: string;
  last_error: string | null;
  run_count: number;
  priority: number;
}

export function ViewListCronJob() {
  const { t } = useTranslation(['cron', 'common']);
  const [refetchFn, setRefetchFn] = useState<(() => void) | null>(null);

  // Callback для получения refetch
  const handleRefetch = useCallback((refetch: () => void) => {
    setRefetchFn(() => refetch);
  }, []);

  // Кнопка обновления для тулбара
  const RefreshButton = (
    <Tooltip label={t('common:refresh', 'Обновить')}>
      <ActionIcon variant="light" onClick={() => refetchFn?.()}>
        <IconRefresh size={18} />
      </ActionIcon>
    </Tooltip>
  );

  return (
    <List<SchemaCronJob>
      model="cron_job"
      order="asc"
      sort="priority"
      toolbarActions={RefreshButton}
      onRefetch={handleRefetch}>
      <Field name="id" />
      <Field name="active" />
      <Field name="name" />
      <Field name="method_name" />
      <Field name="interval_number" />
      <Field name="interval_type" />
      <Field name="nextcall" />
      <Field name="lastcall" />
      <Field name="last_status" />
      <Field name="run_count" />
      <Field name="priority" />
    </List>
  );
}

export default ViewListCronJob;
