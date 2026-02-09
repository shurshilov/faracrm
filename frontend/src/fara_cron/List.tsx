import type { CronJobRecord as SchemaCronJob } from '@/types/records';
/**
 * Список запланированных задач (cron jobs)
 * Использует унифицированный компонент List
 */

import { useState, useCallback } from 'react';
import { Tooltip, ActionIcon } from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

export function ViewListCronJob() {
  const { t } = useTranslation(['cron', 'common']);
  const [refetchFn, setRefetchFn] = useState<(() => void) | null>(null);

  const handleRefetch = useCallback((refetch: () => void) => {
    setRefetchFn(() => refetch);
  }, []);

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
      <Field name="id" label={t('cron:fields.id')} />
      <Field name="active" label={t('cron:fields.active')} />
      <Field name="name" label={t('cron:fields.name')} />
      <Field name="method_name" label={t('cron:fields.method_name')} />
      <Field name="interval_number" label={t('cron:fields.interval_number')} />
      <Field name="interval_type" label={t('cron:fields.interval_type')} />
      <Field name="nextcall" label={t('cron:fields.nextcall')} />
      <Field name="lastcall" label={t('cron:fields.lastcall')} />
      <Field name="last_status" label={t('cron:fields.last_status')} />
      <Field name="run_count" label={t('cron:fields.run_count')} />
      <Field name="priority" label={t('cron:fields.priority')} />
    </List>
  );
}

export default ViewListCronJob;
