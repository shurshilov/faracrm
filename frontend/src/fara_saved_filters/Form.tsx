import type { SavedFilterRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import {
  FormRow,
  FormTabs,
  FormTab,
  FormSheet,
} from '@/components/Form/Layout';
import { IconFilter, IconSettings } from '@tabler/icons-react';
import { Code, Text, Paper } from '@mantine/core';

export function ViewFormSavedFilters(props: ViewFormProps) {
  const { t } = useTranslation('saved_filters');

  return (
    <Form<SavedFilterRecord> model="saved_filters" {...props}>
      <FormSheet>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name', 'Название')} />
          <Field name="model_name" label={t('fields.model_name', 'Модель')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="is_global" label={t('fields.is_global', 'Глобальный')} />
          <Field
            name="is_default"
            label={t('fields.is_default', 'По умолчанию')}
          />
        </FormRow>
        <Field name="id" label="ID" />
      </FormSheet>

      <FormTabs defaultTab="filter">
        <FormTab
          name="filter"
          label={t('tabs.filter', 'Условия фильтра')}
          icon={<IconFilter size={16} />}>
          <Field
            name="filter_data"
            label={t('fields.filter_data', 'Данные фильтра (JSON)')}
          />
        </FormTab>

        <FormTab
          name="stats"
          label={t('tabs.stats', 'Статистика')}
          icon={<IconSettings size={16} />}>
          <FormRow cols={3}>
            <Field
              name="use_count"
              label={t('fields.use_count', 'Использований')}
            />
            <Field
              name="last_used_at"
              label={t('fields.last_used_at', 'Последнее использование')}
            />
            <Field
              name="created_at"
              label={t('fields.created_at', 'Дата создания')}
            />
          </FormRow>
          <Field name="user_id" label={t('fields.user_id', 'Владелец')} />
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export default ViewFormSavedFilters;
