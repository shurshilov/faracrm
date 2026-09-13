/**
 * Настройки колонок списков (column_settings) — Прочее → Настройки колонок.
 *
 * Per-user строки: какие колонки показывать, виджеты и фильтры колонок-
 * связей. Обычно правятся через меню колонок самого списка; здесь —
 * обзор и ремонт: устаревшая настройка (поле переименовано/удалено, битый
 * JSON) чинится или удаляется, не залезая в БД. Правила доступа отдают
 * только свои строки.
 */
import type { ColumnSettingRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

export function ViewListColumnSettings() {
  const { t } = useTranslation('column_settings');

  return (
    <List<ColumnSettingRecord> model="column_settings" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="model_name" label={t('fields.model_name')} />
      <Field name="columns" label={t('fields.columns')} />
      <Field name="widgets" label={t('fields.widgets')} />
      <Field name="filters" label={t('fields.filters')} />
      <Field name="created_at" label={t('fields.created_at')} hidden />
    </List>
  );
}

export default ViewListColumnSettings;
