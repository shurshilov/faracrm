import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewListProps } from '@/route/type';
import type { ActivityRecord, ActivityTypeRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';

// Re-export for backward compat (used by Form.tsx)
export type { ActivityRecord, ActivityTypeRecord } from '@/types/records';

// ==================== Activity List ====================

export function ViewListActivity(props: ViewListProps) {
  const { t } = useTranslation('activity');
  return (
    <List<ActivityRecord> model="activity" {...props}>
      <Field name="id" label="ID" />
      <Field name="summary" label={t('fields.summary')} />
      <Field name="activity_type_id" label={t('fields.activity_type_id')} />
      <Field name="res_model" label={t('fields.res_model')} />
      <Field name="res_id" label={t('fields.res_id')} />
      <Field name="user_id" label={t('fields.user_id')} />
      <Field name="date_deadline" label={t('fields.date_deadline')} />
      <Field name="state" label={t('fields.state')} />
      <Field name="done" label={t('fields.done')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}

// ==================== Activity Type List ====================

export function ViewListActivityType(props: ViewListProps) {
  const { t } = useTranslation('activity');
  return (
    <List<ActivityTypeRecord> model="activity_type" {...props}>
      <Field name="id" label="ID" />
      <Field name="name" label={t('fields.name')} />
      <Field name="icon" label={t('fields.icon')} />
      <Field name="color" label={t('fields.color')} />
      <Field name="default_days" label={t('fields.default_days')} />
      <Field name="sequence" label={t('fields.sequence')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}
