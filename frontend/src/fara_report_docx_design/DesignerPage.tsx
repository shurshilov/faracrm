/**
 * Конструктор шаблона отчёта (модуль report_docx_design):
 * /report_template/:id/design
 *
 * Слева — DOCX-шаблон во встроенном редакторе, в середине — каталог полей
 * (клик вставляет поле в позицию курсора как content control), справа —
 * превью с данными выбранной записи: бэк рендерит несохранённый документ
 * (POST /reports/preview) после каждой правки с задержкой. Сохранение пишет
 * файл в вложение шаблона (или создаёт его, если шаблон был без файла).
 */
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Center,
  Flex,
  Group,
  Loader,
  Stack,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconArrowLeft, IconDeviceFloppy } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useReadQuery, useUpdateMutation } from '@/services/api/crudApi';
import { selectCurrentSession } from '@/slices/authSlice';
import { attachmentContentUrl, triggerDownload } from '@/utils/attachmentUrls';
import { arrayBufferToBase64 } from '@/utils/base64';
import type { DocxEditorFrameHandle } from '@/components/Attachment/DocxEditorFrame';
import type { ReportParamValues } from '@/fara_report_docx/api';
import { fetchReportPreview, useTemplateFieldsQuery } from './api';
import type { ReportFieldNode } from './api';
import { FieldCatalog } from './FieldCatalog';
import {
  PreviewPane,
  type PreviewFormat,
  type PreviewResult,
} from './PreviewPane';

const DocxEditorFrame = lazy(() =>
  import('@/components/Attachment/DocxEditorFrame').then(m => ({
    default: m.DocxEditorFrame,
  })),
);

const DOCX_MIMETYPE =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const PREVIEW_DELAY_MS = 1200;

interface TemplateRecord {
  id: number;
  name: string;
  model_name: string;
  report_type?: 'record' | 'summary';
  output_format?: 'docx' | 'pdf';
  template_file?: { id: number; name?: string } | null;
}

const columnBorder = {
  borderLeft: '1px solid var(--mantine-color-default-border)',
};

export default function DesignerPage() {
  const { id } = useParams<{ id: string }>();
  const templateId = Number(id);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation(['reportsDesign', 'common']);
  const session = useSelector(selectCurrentSession);
  const token = session?.token || '';

  const { data: templateData, isLoading: templateLoading } = useReadQuery({
    model: 'report_template',
    id: templateId,
    fields: [
      'id',
      'name',
      'model_name',
      'report_type',
      'output_format',
      'template_file',
    ],
  });
  const template = templateData?.data as unknown as TemplateRecord | undefined;
  const { data: catalogData } = useTemplateFieldsQuery(templateId);
  const catalog: ReportFieldNode[] = catalogData?.data || [];
  const [update] = useUpdateMutation();

  // --- документ в редакторе ---
  const frameRef = useRef<DocxEditorFrameHandle>(null);
  const [document, setDocument] = useState<Uint8Array | 'blank' | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileId = template?.template_file?.id;
  const templateLoaded = !!template;

  useEffect(() => {
    if (!templateLoaded) return;
    if (!fileId) {
      setDocument('blank');
      return;
    }
    let cancelled = false;
    fetch(attachmentContentUrl(fileId), { credentials: 'include' })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.arrayBuffer();
      })
      .then(buffer => {
        if (!cancelled) setDocument(new Uint8Array(buffer));
      })
      .catch(error => {
        if (!cancelled) setLoadError(String(error));
      });
    return () => {
      cancelled = true;
    };
  }, [fileId, templateLoaded]);

  // --- превью ---
  const [recordId, setRecordId] = useState<number | null>(
    Number(searchParams.get('record_id')) || null,
  );
  const [paramValues, setParamValues] = useState<ReportParamValues>({});
  const [format, setFormat] = useState<PreviewFormat>('docx');
  const [auto, setAuto] = useState(true);
  const [preview, setPreview] = useState<PreviewResult>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const previewTimer = useRef<number | null>(null);

  const replacePreview = useCallback((next: PreviewResult) => {
    setPreview(current => {
      if (current && 'url' in current) URL.revokeObjectURL(current.url);
      return next;
    });
  }, []);

  const runPreview = useCallback(async () => {
    if (!template || !token) return;
    const buffer = await frameRef.current?.save();
    if (!buffer) return;
    setPreviewing(true);
    setPreviewError(null);
    try {
      let params = paramValues;
      if (template.report_type !== 'summary') {
        if (!recordId) {
          throw new Error(t('reportsDesign:designer.selectRecord'));
        }
        params = { record_id: recordId };
      }
      const { blob, filename } = await fetchReportPreview(token, {
        templateId,
        content: await arrayBufferToBase64(buffer),
        params,
        outputFormat: format,
      });
      if (format === 'pdf') {
        replacePreview({ url: URL.createObjectURL(blob), filename });
      } else {
        replacePreview({
          bytes: new Uint8Array(await blob.arrayBuffer()),
          blob,
          filename,
        });
      }
    } catch (error) {
      setPreviewError((error as Error).message || String(error));
    } finally {
      setPreviewing(false);
    }
  }, [
    template,
    token,
    paramValues,
    recordId,
    templateId,
    format,
    replacePreview,
    t,
  ]);

  // Последняя версия runPreview для отложенного вызова из onChange
  const runPreviewRef = useRef(runPreview);
  runPreviewRef.current = runPreview;

  const schedulePreview = useCallback(() => {
    if (previewTimer.current) window.clearTimeout(previewTimer.current);
    previewTimer.current = window.setTimeout(() => {
      previewTimer.current = null;
      void runPreviewRef.current();
    }, PREVIEW_DELAY_MS);
  }, []);

  // Автопревью при смене записи/параметров/формата и при первой загрузке
  useEffect(() => {
    if (auto && document) schedulePreview();
  }, [auto, document, recordId, paramValues, format, schedulePreview]);

  useEffect(
    () => () => {
      if (previewTimer.current) window.clearTimeout(previewTimer.current);
      replacePreview(null);
    },
    [replacePreview],
  );

  const handleChange = useCallback(() => {
    setDirty(true);
    if (auto) schedulePreview();
  }, [auto, schedulePreview]);

  // Скачать текущее превью под именем отчёта: blob-URL в iframe своего имени
  // не несёт, просмотрщик предлагал бы случайный uuid
  const downloadPreview = useCallback(() => {
    if (!preview) return;
    if ('url' in preview) {
      triggerDownload(preview.url, preview.filename);
      return;
    }
    const url = URL.createObjectURL(preview.blob);
    triggerDownload(url, preview.filename);
    URL.revokeObjectURL(url);
  }, [preview]);

  // --- вставка полей ---
  const insertField = useCallback(
    (node: ReportFieldNode) => {
      if (!node.tag) return;
      const ok = frameRef.current?.insertField({
        tag: node.key,
        title: node.label,
        text: node.tag,
      });
      if (!ok) {
        notifications.show({
          message: t('reportsDesign:designer.insertFailed'),
          color: 'yellow',
        });
      }
    },
    [t],
  );
  const insertText = useCallback(
    (text: string) => {
      if (!frameRef.current?.insertText(text)) {
        notifications.show({
          message: t('reportsDesign:designer.insertFailed'),
          color: 'yellow',
        });
      }
    },
    [t],
  );

  // --- сохранение ---
  const handleSave = useCallback(async () => {
    if (!template) return;
    const buffer = await frameRef.current?.save();
    if (!buffer) return;
    setSaving(true);
    try {
      const content = await arrayBufferToBase64(buffer);
      if (fileId) {
        await update({
          model: 'attachments',
          id: fileId,
          values: { content, size: buffer.byteLength },
        }).unwrap();
      } else {
        // Шаблон без файла: создаём вложение через полиморфное поле формы
        await update({
          model: 'report_template',
          id: templateId,
          values: {
            template_file: {
              name: `${template.name || 'template'}.docx`,
              mimetype: DOCX_MIMETYPE,
              size: buffer.byteLength,
              res_model: 'report_template',
              res_id: templateId,
              content,
            },
          },
        }).unwrap();
      }
      setDirty(false);
      notifications.show({
        message: t('reportsDesign:designer.saved'),
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: t('reportsDesign:designer.saveFailed'),
        message: String(error),
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  }, [template, fileId, templateId, update, t]);

  const handleBack = useCallback(() => {
    if (dirty && !window.confirm(t('reportsDesign:designer.unsaved'))) return;
    navigate(`/report_template/${templateId}`);
  }, [dirty, navigate, templateId, t]);

  if (templateLoading || !template) {
    return (
      <Center h="100%">
        <Loader />
      </Center>
    );
  }

  const hasNameField = catalog.some(node => node.key === 'name');

  return (
    <Stack gap={0} h="100%" style={{ minHeight: 0 }}>
      <Group
        px="sm"
        py={6}
        justify="space-between"
        wrap="nowrap"
        style={{
          borderBottom: '1px solid var(--mantine-color-default-border)',
        }}>
        <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
          <Tooltip label={t('reportsDesign:designer.back')}>
            <ActionIcon variant="subtle" onClick={handleBack}>
              <IconArrowLeft size={18} />
            </ActionIcon>
          </Tooltip>
          <Title order={5} lineClamp={1}>
            {t('reportsDesign:designer.title')}: {template.name}
          </Title>
          <Badge size="sm" variant="light">
            {template.model_name}
          </Badge>
          {!fileId && (
            <Badge size="sm" color="yellow" variant="light">
              {t('reportsDesign:designer.noFile')}
            </Badge>
          )}
          {dirty && (
            <Text size="xs" c="dimmed">
              {t('reportsDesign:designer.unsavedMark')}
            </Text>
          )}
        </Group>
        <Button
          size="xs"
          leftSection={<IconDeviceFloppy size={16} />}
          onClick={handleSave}
          loading={saving}
          disabled={!document}>
          {t('common:save')}
        </Button>
      </Group>

      <Flex style={{ flex: 1, minHeight: 0 }}>
        <Box
          style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
          }}>
          {loadError ? (
            <Center style={{ flex: 1 }}>
              <Text c="red">
                {t('reportsDesign:designer.loadFailed')}: {loadError}
              </Text>
            </Center>
          ) : document ? (
            <Suspense
              fallback={
                <Center style={{ flex: 1 }}>
                  <Loader />
                </Center>
              }>
              <DocxEditorFrame
                ref={frameRef}
                document={document}
                title={template.name}
                onSave={handleSave}
                onChange={handleChange}
              />
            </Suspense>
          ) : (
            <Center style={{ flex: 1 }}>
              <Loader />
            </Center>
          )}
        </Box>
        <Box w={290} style={{ ...columnBorder, flexShrink: 0 }}>
          <FieldCatalog
            nodes={catalog}
            onInsertField={insertField}
            onInsertText={insertText}
          />
        </Box>
        <Box
          style={{
            ...columnBorder,
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
          }}>
          <PreviewPane
            templateId={templateId}
            model={template.model_name}
            reportType={
              template.report_type === 'summary' ? 'summary' : 'record'
            }
            hasNameField={hasNameField}
            recordId={recordId}
            onRecordIdChange={setRecordId}
            paramValues={paramValues}
            onParamValuesChange={setParamValues}
            format={format}
            onFormatChange={setFormat}
            auto={auto}
            onAutoChange={setAuto}
            loading={previewing}
            error={previewError}
            preview={preview}
            onRefresh={() => void runPreview()}
            onDownload={downloadPreview}
          />
        </Box>
      </Flex>
    </Stack>
  );
}
