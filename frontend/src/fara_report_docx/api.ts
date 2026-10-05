/**
 * API модуля отчётов: шаблоны «по записи» и скачивание отчёта для кнопки
 * «Печать» (PrintProvider), параметры и скачивание сводного отчёта (кнопка
 * «Сформировать», превью конструктора) и движок PDF (индикатор
 * администратора на списке шаблонов, GET /reports/pdf-engine).
 */
import { crudApi } from '@/services/api/crudApi';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import {
  filenameFromDisposition,
  triggerDownload,
} from '@/utils/attachmentUrls';

export interface RecordTemplate {
  id: number;
  name: string;
  output_format: 'docx' | 'pdf';
}

/** Аргумент функции данных сводного отчёта (ReportTemplate.data_params). */
export interface ReportParam {
  name: string;
  type: 'int' | 'float' | 'bool' | 'str';
  default: unknown;
  label: string;
}

/** Значения формы параметров; незаполненные не отправляются — функция
 *  берёт своё значение по умолчанию. */
export type ReportParamValues = Record<string, unknown>;

export interface PdfEngineInfo {
  /** libreoffice — точная вёрстка Word, builtin — встроенный конвертер */
  engine: 'libreoffice' | 'builtin';
  path: string | null;
  version: string | null;
}

const reportsApi = crudApi.injectEndpoints({
  endpoints: build => ({
    /**
     * Активные шаблоны «по записи» модели — кнопка «Печать» в тулбаре каждой
     * формы. Тот же поиск, что generic search, но фоновый: у роли без
     * доступа к report_template отказ не всплывает модалкой на каждой форме.
     */
    recordTemplates: build.query<{ data: RecordTemplate[] }, string>({
      query: model => ({
        method: 'POST',
        url: '/auto/report_template/search',
        body: {
          filter: [
            ['model_name', '=', model],
            ['report_type', '=', 'record'],
            ['active', '=', true],
          ],
          fields: ['id', 'name', 'output_format'],
          limit: 50,
        },
      }),
      extraOptions: { silent: true },
      // Тот же тег, что у generic search: правка шаблона сбрасывает кэш
      providesTags: [{ type: 'report_template', id: 'LIST' }],
    }),
    reportParams: build.query<{ data: ReportParam[] }, number>({
      query: templateId => ({ url: `/reports/params/${templateId}` }),
    }),
    pdfEngine: build.query<{ data: PdfEngineInfo }, { recheck?: boolean }>({
      query: ({ recheck }) => ({
        url: '/reports/pdf-engine',
        // recheck — заново поискать LibreOffice (поставили без рестарта)
        params: recheck ? { recheck: true } : undefined,
      }),
    }),
  }),
});

export const {
  useRecordTemplatesQuery,
  useReportParamsQuery,
  useLazyPdfEngineQuery,
} = reportsApi;

/**
 * Скачать ответ /reports/generate. Бинарный ответ, поэтому fetch, а не
 * RTK Query; Bearer и HttpOnly-кука обязательны оба (Token Binding). Имя
 * файла — из Content-Disposition (бэк шлёт filename*=utf-8''…). Ошибка
 * сборки — исключение с текстом бэка ({"error": …}).
 */
async function fetchReport(
  token: string,
  url: string,
  fallbackName: string,
): Promise<void> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data?.error) message = String(data.error);
    } catch {
      // ответ не JSON — оставляем код статуса
    }
    throw new Error(message);
  }
  const filename =
    filenameFromDisposition(response.headers.get('Content-Disposition')) ||
    fallbackName;
  const blobUrl = URL.createObjectURL(await response.blob());
  triggerDownload(blobUrl, filename);
  URL.revokeObjectURL(blobUrl);
}

/** Скачать документ по записи (кнопка «Печать»). */
export async function downloadReport(
  token: string,
  templateId: number,
  recordId: number | string,
  format: 'docx' | 'pdf',
): Promise<void> {
  try {
    await fetchReport(
      token,
      `${API_BASE_URL}/reports/generate/${templateId}/${recordId}?output_format=${format}`,
      `report_${templateId}_${recordId}.${format}`,
    );
  } catch (error) {
    console.error('Report download error:', error);
  }
}

/** Скачать сводный отчёт в формате шаблона; ошибку показывает вызывающий. */
export function downloadSummaryReport(
  token: string,
  templateId: number,
  params: ReportParamValues,
): Promise<void> {
  const query = new URLSearchParams({ params: JSON.stringify(params) });
  return fetchReport(
    token,
    `${API_BASE_URL}/reports/generate/${templateId}?${query}`,
    `report_${templateId}`,
  );
}
