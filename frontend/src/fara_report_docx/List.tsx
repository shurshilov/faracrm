import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewListProps } from '@/route/type';

/**
 * Список шаблонов отчётов (Настройки → Отчёты)
 */
export function ViewListReportTemplate(props: ViewListProps) {
  return (
    <List model="report_template" {...props}>
      <Field name="id" />
      <Field name="name" label="Название" />
      <Field name="model_name" label="Модель" />
      <Field name="python_function" label="Функция" />
      <Field name="output_format" label="Формат" />
      <Field name="active" label="Активен" />
    </List>
  );
}
