import type { ReportTemplateRecord as ReportTemplate } from '@/types/records';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconFileDescription, IconSettings } from '@tabler/icons-react';

/**
 * Форма шаблона отчёта
 */
export function ViewFormReportTemplate(props: ViewFormProps) {
  return (
    <Form<ReportTemplate> model="report_template" {...props}>
      <FormSection
        title="Основные данные"
        icon={<IconFileDescription size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="active" label="Активен" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="model_name" label="Модель" />
          <Field name="python_function" label="Функция данных" />
        </FormRow>
      </FormSection>

      <FormSection title="Настройки" icon={<IconSettings size={18} />}>
        <FormRow cols={2}>
          <Field name="output_format" label="Формат по умолчанию" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="description" label="Описание" />
          <Field name="template_file" label="Шаблон DOCX" />
        </FormRow>
      </FormSection>
    </Form>
  );
}
