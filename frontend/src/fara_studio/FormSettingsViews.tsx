/**
 * Общие настройки форм (form_settings) — Прочее → Настройки форм.
 *
 * Одна запись на модель: обязательные поля и зона «Дополнительно» (место,
 * сетка, клетки). Правятся в режиме студии; здесь — обзор и ремонт: JSON
 * правится текстом, как у настроек колонок.
 */
import type { FormSettingRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { FormRow, FormSheet } from '@/components/Form/Layout';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { ViewFormProps } from '@/route/type';

export function ViewListFormSettings() {
  const { t } = useTranslation('studio');

  return (
    <List<FormSettingRecord>
      model="form_settings"
      order="asc"
      sort="model_name">
      <Field name="id" label={t('formSettings.id')} />
      <Field name="model_name" label={t('formSettings.model_name')} />
      <Field name="extra_placement" label={t('formSettings.extra_placement')} />
      <Field name="required" label={t('formSettings.required')} />
      <Field name="extra_fields" label={t('formSettings.extra_fields')} />
    </List>
  );
}

export function ViewFormFormSettings(props: ViewFormProps) {
  const { t } = useTranslation('studio');

  return (
    <Form<FormSettingRecord> model="form_settings" {...props}>
      <FormSheet>
        <Field name="model_name" label={t('formSettings.model_name')} />
        <FormRow cols={3}>
          <Field
            name="extra_placement"
            label={t('formSettings.extra_placement')}
          />
          <Field name="extra_columns" label={t('formSettings.extra_columns')} />
          <Field name="extra_rows" label={t('formSettings.extra_rows')} />
        </FormRow>
        <Field name="required" label={t('formSettings.required')} />
        <Field name="extra_fields" label={t('formSettings.extra_fields')} />
      </FormSheet>
    </Form>
  );
}
