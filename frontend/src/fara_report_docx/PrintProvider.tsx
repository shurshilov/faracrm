/**
 * Источник печати для кнопки «Печать» ядра (components/Form/PrintButton):
 * DOCX-шаблоны модели «по записи» (report_template) и, администратору,
 * пункты «Настроить шаблон» — конструктор report_docx_design с этой записью
 * в превью. Невидимый компонент: считает пункты и отдаёт их через onItems.
 * Молчит, пока модуль report_docx не установлен или шаблонов нет.
 */
import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import {
  IconFileTypeDocx,
  IconFileTypePdf,
  IconLayoutBoard,
} from '@tabler/icons-react';
import type { PrintItem, PrintProviderProps } from '@/shared/extensions/print';
import { selectCurrentSession } from '@/slices/authSlice';
import { useInstalledApps } from '@/hooks/useInstalledApps';
import { downloadReport, useRecordTemplatesQuery } from './api';
import { useCanDesignTemplates } from './useCanDesign';

const NO_ITEMS: PrintItem[] = [];

export function ReportPrintProvider({
  model,
  recordId,
  onItems,
}: PrintProviderProps) {
  const { t } = useTranslation('reports');
  const navigate = useNavigate();
  const token = useSelector(selectCurrentSession)?.token;
  const { isInstalled } = useInstalledApps();
  const enabled = isInstalled('report_docx');
  // «Настроить шаблон» — администратору и только с модулем конструктора
  const canDesign =
    useCanDesignTemplates() && isInstalled('report_docx_design');
  // Только документы по записи: сводные отчёты (report_type=summary) к
  // конкретной записи не относятся, их собирают кнопкой «Сформировать» на
  // форме шаблона и cron-рассылки.
  // Один запрос на модель: RTK кэширует одинаковые аргументы.
  const { data } = useRecordTemplatesQuery(model, { skip: !enabled });
  const templates = data?.data;

  const items = useMemo<PrintItem[]>(() => {
    if (!templates?.length || !token) return NO_ITEMS;
    const print = templates.map(tmpl => {
      const format = tmpl.output_format || 'docx';
      const Icon = format === 'pdf' ? IconFileTypePdf : IconFileTypeDocx;
      return {
        key: `report-${tmpl.id}`,
        label: tmpl.name,
        icon: <Icon size={16} />,
        onSelect: () => void downloadReport(token, tmpl.id, recordId, format),
      };
    });
    if (!canDesign) return print;
    const design = templates.map(tmpl => ({
      key: `design-${tmpl.id}`,
      label: tmpl.name,
      icon: <IconLayoutBoard size={16} />,
      group: t('designer.configure'),
      onSelect: () =>
        navigate(`/report_template/${tmpl.id}/design?record_id=${recordId}`),
    }));
    return [...print, ...design];
  }, [templates, token, canDesign, recordId, navigate, t]);

  useEffect(() => {
    onItems(items);
  }, [items, onItems]);

  return null;
}
