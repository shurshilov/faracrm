import type { ReportTemplateRecord as ReportTemplate } from '@/types/records';
import { Button } from '@mantine/core';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { useInstalledApps } from '@/fara_apps/useInstalledApps';
import {
  IconFileDescription,
  IconLayoutBoard,
  IconSettings,
} from '@tabler/icons-react';
import { GenerateReportButton } from './GenerateReportButton';
import { useCanDesignTemplates } from './useCanDesign';

/** Кнопка «Конструктор» — у сохранённого шаблона, администратору отчётов
 *  (роуты конструктора отдают 403 остальным) и только с установленным
 *  модулем конструктора (report_docx_design). */
function DesignerButton() {
  const { t } = useTranslation('reports');
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isInstalled } = useInstalledApps();
  const canDesign = useCanDesignTemplates();
  if (!id || !canDesign || !isInstalled('report_docx_design')) return null;
  return (
    <Button
      variant="light"
      size="xs"
      leftSection={<IconLayoutBoard size={16} />}
      onClick={() => navigate(`/report_template/${id}/design`)}>
      {t('designer.open')}
    </Button>
  );
}

/**
 * Форма шаблона отчёта
 */
export function ViewFormReportTemplate(props: ViewFormProps) {
  return (
    <Form<ReportTemplate>
      model="report_template"
      actions={
        <>
          <GenerateReportButton />
          <DesignerButton />
        </>
      }
      {...props}>
      <FormSection
        title="Основные данные"
        icon={<IconFileDescription size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="active" label="Активен" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="model_name" label="Модель" />
        </FormRow>
      </FormSection>

      <FormSection title="Настройки" icon={<IconSettings size={18} />}>
        <FormRow cols={2}>
          <Field name="report_type" label="Тип отчёта" />
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
