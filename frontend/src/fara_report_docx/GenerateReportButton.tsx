/**
 * «Сформировать» в тулбаре формы сводного шаблона (report_type = summary):
 * окно с параметрами отчёта (ReportParamsForm) → скачивание через
 * GET /reports/generate/{id}?params= в формате шаблона. Документы по записи
 * печатаются с формы самой записи («Печать»), у них кнопки нет.
 *
 * Тулбар не рендерит actions в режиме создания, поэтому id из маршрута
 * здесь всегда есть; тип шаблона — из контекста формы.
 */
import { useState } from 'react';
import { Alert, Button, Group, Modal, Text } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconFileDownload } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';
import { useFormContext } from '@/components/Form/FormContext';
import { selectCurrentSession } from '@/slices/authSlice';
import { downloadSummaryReport, type ReportParamValues } from './api';
import { ReportParamsForm } from './ReportParamsForm';

export function GenerateReportButton() {
  const { t } = useTranslation(['reports', 'common']);
  const { id } = useParams<{ id: string }>();
  const form = useFormContext();
  const token = useSelector(selectCurrentSession)?.token || '';
  const [opened, { open, close }] = useDisclosure(false);
  const [values, setValues] = useState<ReportParamValues>({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (form.getValues().report_type !== 'summary') return null;

  const handleGenerate = async () => {
    setRunning(true);
    setError(null);
    try {
      await downloadSummaryReport(token, Number(id), values);
      close();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <Button
        variant="light"
        size="xs"
        leftSection={<IconFileDownload size={16} />}
        onClick={open}>
        {t('generate.open')}
      </Button>

      <Modal
        opened={opened}
        onClose={close}
        title={t('generate.title')}
        size="sm"
        centered>
        <ReportParamsForm
          templateId={Number(id)}
          values={values}
          onChange={setValues}
        />
        {error && (
          <Alert color="red" mt="md" p="xs">
            <Text size="xs">{error}</Text>
          </Alert>
        )}
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={close} disabled={running}>
            {t('common:cancel')}
          </Button>
          <Button
            leftSection={<IconFileDownload size={16} />}
            onClick={handleGenerate}
            loading={running}>
            {t('generate.download')}
          </Button>
        </Group>
      </Modal>
    </>
  );
}
