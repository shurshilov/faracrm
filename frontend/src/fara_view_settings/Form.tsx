/**
 * Форма настройки колонок (column_settings): модель + три JSON-поля как
 * есть. Это ремонтный экран (см. List.tsx) — JSON правится текстом.
 */
import type { ColumnSettingRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormRow, FormSheet } from '@/components/Form/Layout';

export function ViewFormColumnSettings(props: ViewFormProps) {
  const { t } = useTranslation('column_settings');

  return (
    <Form<ColumnSettingRecord> model="column_settings" {...props}>
      <FormSheet>
        <FormRow cols={2}>
          <Field name="model_name" label={t('fields.model_name')} />
          <Field name="created_at" label={t('fields.created_at')} />
        </FormRow>
        <Field name="columns" label={t('fields.columns')} />
        <Field name="widgets" label={t('fields.widgets')} />
        <Field name="filters" label={t('fields.filters')} />
      </FormSheet>
    </Form>
  );
}

export default ViewFormColumnSettings;
