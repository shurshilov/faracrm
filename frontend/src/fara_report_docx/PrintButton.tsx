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
  IconChevronRight,
} from '@tabler/icons-react';
import { useSearchQuery } from '@/services/api/crudApi';

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

  const handlePrint = (templateId: number, format: 'docx' | 'pdf') => {
    if (!recordId) return;
    const url = `/api/reports/generate/${templateId}/${recordId}?output_format=${format}`;
    window.open(url, '_blank');
  };

  // Один шаблон — простая кнопка с выбором формата
  if (templates.length === 1) {
    const tmpl = templates[0];
    return (
      <Menu shadow="md" width={140} position="bottom-end">
        <Menu.Target>
          <Button
            variant="light"
            size="xs"
            leftSection={
              isLoading ? <Loader size={14} /> : <IconPrinter size={16} />
            }
          >
            Печать
          </Button>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item
            leftSection={<IconFileTypePdf size={16} />}
            onClick={() => handlePrint(tmpl.id, 'pdf')}
          >
            PDF
          </Menu.Item>
          <Menu.Item
            leftSection={<IconFileTypeDocx size={16} />}
            onClick={() => handlePrint(tmpl.id, 'docx')}
          >
            DOCX
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
    );
  }

  // Несколько шаблонов — меню с подменю
  return (
    <Menu shadow="md" width={220} position="bottom-end">
      <Menu.Target>
        <Button
          variant="light"
          size="xs"
          leftSection={
            isLoading ? <Loader size={14} /> : <IconPrinter size={16} />
          }
        >
          Печать
        </Button>
      </Menu.Target>

      <Menu.Dropdown>
        {templates.map((tmpl) => (
          <Menu key={tmpl.id} trigger="hover" position="left-start" offset={2}>
            <Menu.Target>
              <Menu.Item rightSection={<IconChevronRight size={14} />}>
                <Text size="sm" truncate>
                  {tmpl.name}
                </Text>
              </Menu.Item>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconFileTypePdf size={16} />}
                onClick={() => handlePrint(tmpl.id, 'pdf')}
              >
                PDF
              </Menu.Item>
              <Menu.Item
                leftSection={<IconFileTypeDocx size={16} />}
                onClick={() => handlePrint(tmpl.id, 'docx')}
              >
                DOCX
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
