/**
 * Кнопка печати с выпадающим меню шаблонов отчётов.
 *
 * Использование:
 *   <Form model="sale" actions={<PrintButton model="sale" recordId={id} />}>
 *
 * Кнопка автоматически скрывается если нет шаблонов для модели.
 */

import { Menu, Button, Loader, Text } from '@mantine/core';
import {
  IconPrinter,
  IconFileTypePdf,
  IconFileTypeDocx,
} from '@tabler/icons-react';
import { useSearchQuery } from '@/services/api/crudApi';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';

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
  const session = useSelector(selectCurrentSession);
  const { data, isLoading } = useSearchQuery({
    model: 'report_template',
    filter: [
      ['model_name', '=', model],
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
        headers: {
          Authorization: `Bearer ${session.token}`,
        },
      });

      if (!response.ok) {
        console.error('Report generation failed:', response.status);
        return;
      }

      // Получаем имя файла из заголовка
      const disposition = response.headers.get('Content-Disposition');
      let filename = `report_${templateId}_${recordId}.${format}`;

      if (disposition) {
        const match = disposition.match(/filename="?([^";\n]+)"?/);
        if (match) {
          filename = decodeURIComponent(match[1].trim());
        }
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error('Report download error:', error);
    }
  };

  // Один шаблон — простая кнопка, формат из шаблона
  if (templates.length === 1) {
    const tmpl = templates[0];
    const format = tmpl.output_format || 'docx';
    const FormatIcon = format === 'pdf' ? IconFileTypePdf : IconFileTypeDocx;

    return (
      <Button
        variant="light"
        size="xs"
        leftSection={
          isLoading ? <Loader size={14} /> : <IconPrinter size={16} />
        }
        onClick={() => handlePrint(tmpl.id, format)}>
        Печать
      </Button>
    );
  }

  // Несколько шаблонов — меню со списком
  return (
    <Menu shadow="md" width={220} position="bottom-end">
      <Menu.Target>
        <Button
          variant="light"
          size="xs"
          leftSection={
            isLoading ? <Loader size={14} /> : <IconPrinter size={16} />
          }>
          Печать
        </Button>
      </Menu.Target>

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
      </Menu.Dropdown>
    </Menu>
  );
}
