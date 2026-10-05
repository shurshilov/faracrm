import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewListProps } from '@/route/type';
import { PdfEngineBadge } from './PdfEngineBadge';

/**
 * Список шаблонов отчётов (Настройки → Отчёты).
 * В тулбаре — индикатор движка PDF (только администратору).
 */
export function ViewListReportTemplate(props: ViewListProps) {
  return (
    <List
      model="report_template"
      toolbarActions={<PdfEngineBadge />}
      {...props}>
      <Field name="id" />
      <Field name="name" label="Название" />
      <Field name="model_name" label="Модель" />
      <Field name="report_type" label="Тип" />
      <Field name="output_format" label="Формат" />
      <Field name="active" label="Активен" />
    </List>
  );
}
