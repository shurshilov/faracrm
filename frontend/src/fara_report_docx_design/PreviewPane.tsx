/**
 * Панель превью конструктора: запись (или параметры) для примера, формат,
 * автообновление и сам результат — docx во втором экземпляре редактора
 * (режим просмотра) либо PDF в iframe. Рендер делает бэк (/reports/preview),
 * запрос шлёт DesignerPage.
 */
import { lazy, Suspense, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Box,
  Button,
  Center,
  Group,
  Loader,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  Tooltip,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconDownload, IconRefresh } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';

const DocxEditorFrame = lazy(() =>
  import('@/components/Attachment/DocxEditorFrame').then(m => ({
    default: m.DocxEditorFrame,
  })),
);

export type PreviewResult =
  | { bytes: Uint8Array; blob: Blob; filename: string }
  | { url: string; filename: string }
  | null;
export type PreviewFormat = 'docx' | 'pdf';

interface PreviewPaneProps {
  model: string;
  reportType: 'record' | 'summary';
  /** У модели есть поле name — можно искать запись по имени */
  hasNameField: boolean;
  recordId: number | null;
  onRecordIdChange: (id: number | null) => void;
  paramsText: string;
  onParamsTextChange: (value: string) => void;
  format: PreviewFormat;
  onFormatChange: (format: PreviewFormat) => void;
  auto: boolean;
  onAutoChange: (auto: boolean) => void;
  loading: boolean;
  error: string | null;
  preview: PreviewResult;
  onRefresh: () => void;
  onDownload: () => void;
}

/** Выбор записи модели по имени (ilike), последние записи — первыми. */
function RecordSelect({
  model,
  value,
  onChange,
}: {
  model: string;
  value: number | null;
  onChange: (id: number | null) => void;
}) {
  const { t } = useTranslation('reportsDesign');
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search.trim(), 300);
  const { data } = useSearchQuery({
    model,
    fields: ['id', 'name'],
    filter: debounced ? [['name', 'ilike', debounced]] : undefined,
    sort: 'id',
    order: 'desc',
    limit: 20,
  });
  const records = (data?.data || []) as { id: number; name?: string }[];
  const options = records.map(record => ({
    value: String(record.id),
    label: record.name ? `${record.name} (#${record.id})` : `#${record.id}`,
  }));
  if (value && !options.some(option => option.value === String(value))) {
    options.unshift({ value: String(value), label: `#${value}` });
  }
  return (
    <Select
      size="xs"
      searchable
      clearable
      data={options}
      value={value ? String(value) : null}
      onChange={selected => onChange(selected ? Number(selected) : null)}
      searchValue={search}
      onSearchChange={setSearch}
      placeholder={t('designer.record')}
      nothingFoundMessage={t('designer.noRecords')}
    />
  );
}

export function PreviewPane({
  model,
  reportType,
  hasNameField,
  recordId,
  onRecordIdChange,
  paramsText,
  onParamsTextChange,
  format,
  onFormatChange,
  auto,
  onAutoChange,
  loading,
  error,
  preview,
  onRefresh,
  onDownload,
}: PreviewPaneProps) {
  const { t } = useTranslation('reportsDesign');

  return (
    <Stack gap="xs" h="100%" style={{ minHeight: 0 }}>
      <Stack gap="xs" px="xs" pt="xs">
        {reportType === 'summary' ? (
          <Textarea
            size="xs"
            autosize
            minRows={1}
            label={t('designer.params')}
            value={paramsText}
            onChange={e => onParamsTextChange(e.currentTarget.value)}
            placeholder='{"days": 7}'
          />
        ) : hasNameField ? (
          <RecordSelect
            model={model}
            value={recordId}
            onChange={onRecordIdChange}
          />
        ) : (
          <NumberInput
            size="xs"
            placeholder={t('designer.recordId')}
            value={recordId ?? ''}
            onChange={value =>
              onRecordIdChange(typeof value === 'number' ? value : null)
            }
            min={1}
          />
        )}
        <Group gap="xs" justify="space-between" wrap="nowrap">
          <SegmentedControl
            size="xs"
            value={format}
            onChange={value => onFormatChange(value as PreviewFormat)}
            data={[
              { value: 'docx', label: 'DOCX' },
              { value: 'pdf', label: 'PDF' },
            ]}
          />
          <Switch
            size="xs"
            label={t('designer.auto')}
            checked={auto}
            onChange={e => onAutoChange(e.currentTarget.checked)}
          />
          <Group gap={4} wrap="nowrap">
            <Button
              size="compact-xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              onClick={onRefresh}
              loading={loading}>
              {t('designer.refresh')}
            </Button>
            <Tooltip label={preview?.filename ?? t('designer.download')}>
              <ActionIcon
                size="sm"
                variant="light"
                aria-label={t('designer.download')}
                disabled={!preview}
                onClick={onDownload}>
                <IconDownload size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
        {error && (
          <Alert color="red" p="xs">
            <Text size="xs">{error}</Text>
          </Alert>
        )}
      </Stack>
      <Box
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        }}>
        {preview && 'url' in preview ? (
          <iframe
            src={preview.url}
            title="preview"
            style={{ flex: 1, width: '100%', border: 0 }}
          />
        ) : preview && 'bytes' in preview ? (
          <Suspense
            fallback={
              <Center style={{ flex: 1 }}>
                <Loader />
              </Center>
            }>
            <DocxEditorFrame
              document={preview.bytes}
              mode="view"
              chrome={false}
            />
          </Suspense>
        ) : (
          <Center style={{ flex: 1 }}>
            <Text size="sm" c="dimmed">
              {loading ? t('designer.rendering') : t('designer.noPreview')}
            </Text>
          </Center>
        )}
      </Box>
    </Stack>
  );
}
