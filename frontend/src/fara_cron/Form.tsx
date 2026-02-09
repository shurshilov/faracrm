import type { CronJobRecord as SchemaCronJob } from '@/types/records';
/**
 * Форма редактирования cron job
 * Использует унифицированный компонент Form
 */

import { useState } from 'react';
import { Button, Alert } from '@mantine/core';
import {
  IconPlayerPlay,
  IconClock,
  IconCode,
  IconHistory,
  IconInfoCircle,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import {
  FormSection,
  FormRow,
  FormTabs,
  FormTab,
} from '@/components/Form/Layout';
import { ViewFormProps } from '@/route/type';
import { useRunCronJobMutation } from './cronApi';

export function ViewFormCronJob(props: ViewFormProps) {
  const { t } = useTranslation(['cron', 'common']);
  const { id } = useParams<{ id: string }>();
  const jobId = Number(id);

  const [runJob, { isLoading: isRunning }] = useRunCronJobMutation();
  const [runResult, setRunResult] = useState<{
    success: boolean;
    error?: string;
  } | null>(null);

  const handleRunNow = async () => {
    if (!jobId) return;
    try {
      const result = await runJob(jobId).unwrap();
      setRunResult(result);
    } catch (error) {
      setRunResult({ success: false, error: String(error) });
    }
  };

  // Кнопка запуска (только для существующей задачи)
  const RunButton = jobId ? (
    <Button
      variant="light"
      leftSection={<IconPlayerPlay size={16} />}
      onClick={handleRunNow}
      loading={isRunning}>
      {t('cron:actions.run_now')}
    </Button>
  ) : null;

  return (
    <Form<SchemaCronJob> model="cron_job" actions={RunButton} {...props}>
      {/* Результат запуска */}
      {runResult && (
        <Alert
          color={runResult.success ? 'green' : 'red'}
          mb="md"
          withCloseButton
          onClose={() => setRunResult(null)}>
          {runResult.success ? t('common:success', 'Успешно') : runResult.error}
        </Alert>
      )}

      {/* Основная информация */}
      <FormSection
        title={t('cron:sections.main')}
        icon={<IconInfoCircle size={18} />}>
        <FormRow cols={2}>
          <Field name="name" />
          <Field name="active" />
        </FormRow>
        <Field name="id" />
      </FormSection>

      {/* Вкладки */}
      <FormTabs defaultTab="code">
        {/* Код */}
        <FormTab
          name="code"
          label={t('cron:sections.code')}
          icon={<IconCode size={16} />}>
          <Field name="code" />
        </FormTab>

        {/* Метод модели */}
        <FormTab
          name="method"
          label={t('cron:sections.method')}
          icon={<IconCode size={16} />}>
          <FormRow cols={2}>
            <Field name="model_name" />
            <Field name="method_name" />
          </FormRow>
          <Field name="args" />
          <Field name="kwargs" />
        </FormTab>

        {/* Расписание */}
        <FormTab
          name="schedule"
          label={t('cron:sections.schedule')}
          icon={<IconClock size={16} />}>
          <FormRow cols={2}>
            <Field name="interval_number" />
            <Field name="interval_type" />
          </FormRow>
          <FormRow cols={2}>
            <Field name="numbercall" />
            <Field name="priority" />
          </FormRow>
          <FormRow cols={2}>
            <Field name="timeout" />
            <Field name="doall" />
          </FormRow>
        </FormTab>

        {/* История */}
        <FormTab
          name="history"
          label={t('cron:sections.history')}
          icon={<IconHistory size={16} />}>
          <FormRow cols={2}>
            <Field name="last_status" />
            <Field name="run_count" />
          </FormRow>
          <FormRow cols={2}>
            <Field name="lastcall" />
            <Field name="nextcall" />
          </FormRow>
          <Field name="last_duration" />
          <Field name="last_error" />
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export default ViewFormCronJob;
