import type { SavedFilterRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

export function ViewListSavedFilters() {
  const { t } = useTranslation('saved_filters');

  return (
    <List<SavedFilterRecord>
      model="saved_filters"
      order="desc"
      sort="use_count">
      <Field name="id" label={t('fields.id', 'ID')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="model_name" label={t('fields.model_name')} />
      <Field name="is_global" label={t('fields.is_global')} />
      <Field name="is_default" label={t('fields.is_default')} />
      <Field name="use_count" label={t('fields.use_count')} />
      <Field name="last_used_at" label={t('fields.last_used_at')} />
    </List>
  );
}

export default ViewListSavedFilters;
