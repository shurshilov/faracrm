/**
 * API модуля отчётов: шаблоны «по записи» и скачивание отчёта для кнопки
 * «Печать» (PrintProvider) и движок PDF (индикатор администратора на списке
 * шаблонов, GET /reports/pdf-engine).
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
    pdfEngine: build.query<{ data: PdfEngineInfo }, { recheck?: boolean }>({
      query: ({ recheck }) => ({
        url: '/reports/pdf-engine',
        // recheck — заново поискать LibreOffice (поставили без рестарта)
        params: recheck ? { recheck: true } : undefined,
      }),
    }),
  }),
});

export const { useRecordTemplatesQuery, useLazyPdfEngineQuery } = reportsApi;

/**
 * Скачать отчёт по шаблону для записи. Бинарный ответ, поэтому fetch, а не
 * RTK Query; Bearer и HttpOnly-кука обязательны оба (Token Binding). Имя
 * файла — из Content-Disposition (бэк шлёт filename*=utf-8''…).
 */
export async function downloadReport(
  token: string,
  templateId: number,
  recordId: number | string,
  format: 'docx' | 'pdf',
): Promise<void> {
  const url = `${API_BASE_URL}/reports/generate/${templateId}/${recordId}?output_format=${format}`;
  try {
    const response = await fetch(url, {
      credentials: 'include',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      console.error('Report generation failed:', response.status);
      return;
    }
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
}
