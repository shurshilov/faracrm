/**
 * Кнопка печати с выпадающим меню шаблонов отчётов.
 *
 * Использование:
 *   <Form model="sales" actions={<PrintButton model="sales" recordId={id} />}>
 *
 * Кнопка автоматически скрывается если нет шаблонов для модели.
 * Администратору (system_admin) меню дополнительно предлагает открыть
 * конструктор шаблона — с этой записью в превью.
 */

import { Menu, Button, Loader, Text } from '@mantine/core';
import {
  filenameFromDisposition,
  triggerDownload,
} from '@/utils/attachmentUrls';
import {
  IconPrinter,
  IconFileTypePdf,
  IconFileTypeDocx,
  IconLayoutBoard,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';
import { useInstalledApps } from '@/fara_apps/useInstalledApps';
import { useCanDesignTemplates } from './useCanDesign';

interface ReportTemplate {
  id: number;
  name: string;
  model_name: string;
  output_format: 'docx' | 'pdf';
}

interface PrintButtonProps {
  /** Имя модели (sale, partners, etc.) */
  model: string;
  /** ID записи для печати */
  recordId: number | string | undefined;
}

export function PrintButton({ model, recordId }: PrintButtonProps) {
  const { t } = useTranslation('reports');
  const navigate = useNavigate();
  const session = useSelector(selectCurrentSession);
  const { isInstalled } = useInstalledApps();
  // Пункты «Настроить шаблон» — администратору и только с модулем конструктора
  const canDesign =
    useCanDesignTemplates() && isInstalled('report_docx_design');
  // Только документы по записи: сводные отчёты (report_type=summary) к
  // конкретной записи не относятся, их собирают cron-рассылки.
  const { data, isLoading } = useSearchQuery({
    model: 'report_template',
    filter: [
      ['model_name', '=', model],
      ['report_type', '=', 'record'],
      ['active', '=', true],
    ],
    fields: ['id', 'name', 'output_format'],
    limit: 50,
  });

  const templates = (data?.data || []) as ReportTemplate[];

  // Нет шаблонов — не показываем кнопку
  if (!isLoading && templates.length === 0) {
    return null;
  }

  const handlePrint = async (templateId: number, format: 'docx' | 'pdf') => {
    if (!recordId || !session?.token) return;
    const url = `${API_BASE_URL}/reports/generate/${templateId}/${recordId}?output_format=${format}`;

    try {
      const response = await fetch(url, {
        // Bearer + HttpOnly-кука — оба обязательны для verify_access
        credentials: 'include',
        headers: {
          Authorization: `Bearer ${session.token}`,
        },
      });

      if (!response.ok) {
        console.error('Report generation failed:', response.status);
        return;
      }

      // Имя файла — из заголовка (бэк отдаёт filename*=utf-8''…)
      const filename =
        filenameFromDisposition(response.headers.get('Content-Disposition')) ||
        `report_${templateId}_${recordId}.${format}`;

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      triggerDownload(blobUrl, filename);
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error('Report download error:', error);
    }
  };

  const openDesigner = (templateId: number) => {
    const query = recordId ? `?record_id=${recordId}` : '';
    navigate(`/report_template/${templateId}/design${query}`);
  };

  const simple = templates.length === 1 && !canDesign;
  const button = (
    <Button
      variant="light"
      size="xs"
      leftSection={isLoading ? <Loader size={14} /> : <IconPrinter size={16} />}
      onClick={
        simple
          ? () =>
              handlePrint(templates[0].id, templates[0].output_format || 'docx')
          : undefined
      }>
      Печать
    </Button>
  );

  // Один шаблон и не администратор — простая кнопка, формат из шаблона
  if (simple) {
    return button;
  }

  // Несколько шаблонов (или администратор) — меню со списком
  return (
    <Menu shadow="md" width={240} position="bottom-end">
      <Menu.Target>{button}</Menu.Target>

      <Menu.Dropdown>
        {templates.map(tmpl => {
          const format = tmpl.output_format || 'docx';
          const FormatIcon =
            format === 'pdf' ? IconFileTypePdf : IconFileTypeDocx;
          return (
            <Menu.Item
              key={tmpl.id}
              leftSection={<FormatIcon size={16} />}
              onClick={() => handlePrint(tmpl.id, format)}>
              <Text size="sm" truncate>
                {tmpl.name}
              </Text>
            </Menu.Item>
          );
        })}
        {canDesign && templates.length > 0 && (
          <>
            <Menu.Divider />
            <Menu.Label>{t('designer.configure')}</Menu.Label>
            {templates.map(tmpl => (
              <Menu.Item
                key={`design-${tmpl.id}`}
                leftSection={<IconLayoutBoard size={16} />}
                onClick={() => openDesigner(tmpl.id)}>
                <Text size="sm" truncate>
                  {tmpl.name}
                </Text>
              </Menu.Item>
            ))}
          </>
        )}
      </Menu.Dropdown>
    </Menu>
  );
}
