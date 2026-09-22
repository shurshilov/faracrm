/**
 * ImportModal — загрузка записей из Excel.
 *
 * Файл разбирает бэк (/excel/{model}/preview): колонки с примерами
 * значений и поля модели, которые можно заполнить. Колонки сопоставляются
 * с полями автоматически по заголовку (имя поля; режим поиска связи
 * «uom_id (name)» бэк читает из заголовка сам), дальше — руками;
 * ненужные колонки остаются «не импортировать». Импорт создаёт записи и
 * показывает счётчик и ошибки по строкам.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Anchor,
  Button,
  FileInput,
  Group,
  Modal,
  ScrollArea,
  Select,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { IconFileSpreadsheet } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import {
  ExcelImportResult,
  ExcelPreview,
  fileToBase64,
  useExcelImportMutation,
  useExcelPreviewMutation,
} from './api';
import contactTemplate from './templates/contact.xlsx?url';
import partnersTemplate from './templates/partners.xlsx?url';
import productsTemplate from './templates/products.xlsx?url';
import usersTemplate from './templates/users.xlsx?url';

const XLSX_ACCEPT =
  '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

// Готовые файлы с примерами строк и листом «Справка» — по имени модели.
const TEMPLATES: Record<string, string> = {
  products: productsTemplate,
  users: usersTemplate,
  partners: partnersTemplate,
  contact: contactTemplate,
};

interface ImportModalProps {
  opened: boolean;
  onClose: () => void;
  model: string;
}

export function ImportModal({ opened, onClose, model }: ImportModalProps) {
  const { t } = useTranslation(['excel', 'common']);
  const [previewFile, { isLoading: previewLoading }] =
    useExcelPreviewMutation();
  const [importFile, { isLoading: importing }] = useExcelImportMutation();

  const [file, setFile] = useState<File | null>(null);
  const [content, setContent] = useState('');
  const [preview, setPreview] = useState<ExcelPreview | null>(null);
  // Индекс колонки файла → имя поля (только сопоставленные).
  const [mapping, setMapping] = useState<Record<number, string>>({});
  const [result, setResult] = useState<ExcelImportResult | null>(null);

  useEffect(() => {
    if (opened) {
      setFile(null);
      setContent('');
      setPreview(null);
      setMapping({});
      setResult(null);
    }
  }, [opened]);

  const handleFile = async (next: File | null) => {
    setFile(next);
    setPreview(null);
    setMapping({});
    if (!next) return;
    const base64 = await fileToBase64(next);
    setContent(base64);
    const data = await previewFile({ model, content: base64 })
      .unwrap()
      .catch(() => null);
    if (!data) return;
    setPreview(data);
    // Автосопоставление: поле, которое бэк распознал в заголовке.
    const auto: Record<number, string> = {};
    const used = new Set<string>();
    for (const column of data.columns) {
      if (column.field && !used.has(column.field)) {
        auto[column.index] = column.field;
        used.add(column.field);
      }
    }
    setMapping(auto);
  };

  const setColumnField = (index: number, name: string | null) =>
    setMapping(prev => {
      const next = { ...prev };
      if (name) next[index] = name;
      else delete next[index];
      return next;
    });

  const mapped = useMemo(() => new Set(Object.values(mapping)), [mapping]);
  const missingRequired = (preview?.fields ?? []).filter(
    field => field.required && !mapped.has(field.name),
  );

  const handleImport = async () => {
    // Ошибку (400) покажет общая модалка ошибок.
    const data = await importFile({ model, content, mapping })
      .unwrap()
      .catch(() => null);
    if (data) setResult(data);
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('importTitle')}
      size="lg"
      centered>
      <Stack gap="sm">
        {!result && (
          <>
            <FileInput
              label={t('file')}
              description={t('firstRowHint')}
              placeholder={t('chooseFile')}
              accept={XLSX_ACCEPT}
              leftSection={<IconFileSpreadsheet size={16} />}
              value={file}
              onChange={handleFile}
              clearable
            />
            {TEMPLATES[model] && (
              <Anchor
                size="xs"
                href={TEMPLATES[model]}
                download={`${model}.xlsx`}>
                {t('template')}
              </Anchor>
            )}
          </>
        )}

        {preview && !result && (
          <>
            <Text size="sm" c="dimmed">
              {t('rowsFound', { count: preview.rows_total })}
            </Text>
            <ScrollArea.Autosize mah={400} type="auto" offsetScrollbars="y">
              <Table verticalSpacing={4} withRowBorders={false}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('fileColumn')}</Table.Th>
                    <Table.Th>{t('sample')}</Table.Th>
                    <Table.Th w={220}>{t('field')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {preview.columns.map(column => (
                    <Table.Tr key={column.index}>
                      <Table.Td>
                        <Text size="sm" fw={500}>
                          {column.header}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="xs" c="dimmed" lineClamp={2}>
                          {column.samples.join(', ')}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Select
                          size="xs"
                          searchable
                          clearable
                          placeholder={t('skipColumn')}
                          value={mapping[column.index] ?? null}
                          onChange={name => setColumnField(column.index, name)}
                          // Поле — только в одну колонку.
                          data={preview.fields
                            .filter(
                              field =>
                                !mapped.has(field.name) ||
                                mapping[column.index] === field.name,
                            )
                            .map(field => ({
                              value: field.name,
                              label: field.name + (field.required ? ' *' : ''),
                            }))}
                        />
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea.Autosize>
            {missingRequired.length > 0 && (
              <Text size="xs" c="red">
                {t('requiredUnmapped', {
                  fields: missingRequired.map(field => field.name).join(', '),
                })}
              </Text>
            )}
            <Text size="xs" c="dimmed">
              {t('mappingHint')}
            </Text>
          </>
        )}

        {result && (
          <>
            <Text size="sm" c="green">
              {t('created', { count: result.created })}
            </Text>
            {result.errors.length > 0 && (
              <>
                <Text size="sm" c="red">
                  {t('skipped', { count: result.errors.length })}
                </Text>
                <ScrollArea.Autosize mah={240} type="auto">
                  <Stack gap={2}>
                    {result.errors.map((error, index) => (
                      <Text size="xs" key={index}>
                        {t('row', { row: error.row })}
                        {error.field ? `, ${error.field}` : ''}: {error.message}
                      </Text>
                    ))}
                  </Stack>
                </ScrollArea.Autosize>
              </>
            )}
          </>
        )}

        <Group justify="flex-end" gap="xs">
          <Button variant="default" onClick={onClose}>
            {result ? t('common:close') : t('common:cancel')}
          </Button>
          {!result && (
            <Button
              onClick={handleImport}
              loading={previewLoading || importing}
              disabled={
                !preview || mapped.size === 0 || missingRequired.length > 0
              }>
              {t('importButton')}
            </Button>
          )}
        </Group>
      </Stack>
    </Modal>
  );
}
