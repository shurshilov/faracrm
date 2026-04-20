/**
 * Хелперы для доступа к бинарному контенту через cookie-auth.
 *
 * Используют роуты /attachments/{id}/content и /attachments/{id}/content/preview,
 * которые авторизуются через HttpOnly cookie (cookie_token) вместо Bearer header.
 *
 * Преимущества перед fetch+blob+base64:
 * - Нативное браузерное кеширование
 * - Нет JS overhead (нет FileReader, нет base64 раздувание)
 * - Параллельная загрузка изображений браузером
 * - Можно использовать в <img src>, <audio src>, <a href>
 */

import { API_BASE_URL } from '@/services/baseQueryWithReauth';

/** URL для скачивания файла (cookie auth) */
export function attachmentContentUrl(id: number | string): string {
  return `${API_BASE_URL}/attachments/${id}/content`;
}

/** URL для превью изображения (cookie auth) */
export function attachmentPreviewUrl(
  id: number | string,
  width?: number,
  height?: number,
  checksum?: string | null,
): string {
  const base = `${API_BASE_URL}/attachments/${id}/content/preview`;
  const params = new URLSearchParams();
  if (width) params.set('w', String(width));
  if (height) params.set('h', String(height));
  if (checksum) params.set('v', checksum);
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

/** URL для скачивания (download link, cookie auth) */
export function attachmentDownloadUrl(id: number | string): string {
  return `${API_BASE_URL}/attachments/${id}/content`;
}

// ============================================================
// Google Drive
// ============================================================

/**
 * MIME-типы, которые можно редактировать в Google Docs/Sheets/Slides.
 * Google при открытии этих файлов через /edit URL автоматически
 * запускает соответствующий редактор.
 */
const GOOGLE_EDITABLE_MIMES: Record<string, string> = {
  // Word / Google Docs
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
    'document',
  'application/msword': 'document',
  'application/vnd.google-apps.document': 'document',
  'text/plain': 'document',
  'text/markdown': 'document',

  // Excel / Google Sheets
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
    'spreadsheets',
  'application/vnd.ms-excel': 'spreadsheets',
  'application/vnd.google-apps.spreadsheet': 'spreadsheets',
  'text/csv': 'spreadsheets',

  // PowerPoint / Google Slides
  'application/vnd.openxmlformats-officedocument.presentationml.presentation':
    'presentation',
  'application/vnd.ms-powerpoint': 'presentation',
  'application/vnd.google-apps.presentation': 'presentation',
};

/**
 * Проверить, можно ли редактировать файл в Google Docs онлайн.
 * Возвращает true для docx/xlsx/pptx/csv/txt и родных Google-форматов.
 */
export function isGoogleEditable(mimetype: string | null | undefined): boolean {
  if (!mimetype) return false;
  return mimetype in GOOGLE_EDITABLE_MIMES;
}

/**
 * Ссылка на открытие файла для РЕДАКТИРОВАНИЯ в Google Docs/Sheets/Slides.
 * Работает только для совместимых MIME-типов (docx, xlsx, pptx, csv, txt,
 * и родных google-форматов). Для несовместимых файлов вернёт null — в UI
 * нужно скрыть кнопку "Редактировать".
 *
 * Google при открытии такого URL автоматически конвертирует Office-формат
 * во внутренний Google-формат и запускает редактор.
 *
 * Для остальных файлов (картинки, PDF, zip и т.д.) используй
 * `storage_file_url` (webViewLink) — откроет preview на drive.google.com.
 */
export function googleEditUrl(
  storageFileId: string | null | undefined,
  mimetype: string | null | undefined,
): string | null {
  if (!storageFileId || !mimetype) return null;
  const editor = GOOGLE_EDITABLE_MIMES[mimetype];
  if (!editor) return null;
  return `https://docs.google.com/${editor}/d/${storageFileId}/edit`;
}
