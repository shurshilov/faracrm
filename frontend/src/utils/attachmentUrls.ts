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
