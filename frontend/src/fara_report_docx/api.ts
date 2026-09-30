/**
 * API модуля отчётов: движок PDF (индикатор администратора на списке
 * шаблонов, GET /reports/pdf-engine). Скачивание отчётов идёт fetch-ом в
 * PrintButton — там бинарный ответ.
 */
import { crudApi } from '@/services/api/crudApi';

export interface PdfEngineInfo {
  /** libreoffice — точная вёрстка Word, builtin — встроенный конвертер */
  engine: 'libreoffice' | 'builtin';
  path: string | null;
  version: string | null;
}

const reportsApi = crudApi.injectEndpoints({
  endpoints: build => ({
    pdfEngine: build.query<{ data: PdfEngineInfo }, { recheck?: boolean }>({
      query: ({ recheck }) => ({
        url: '/reports/pdf-engine',
        // recheck — заново поискать LibreOffice (поставили без рестарта)
        params: recheck ? { recheck: true } : undefined,
      }),
    }),
  }),
});

export const { useLazyPdfEngineQuery } = reportsApi;
