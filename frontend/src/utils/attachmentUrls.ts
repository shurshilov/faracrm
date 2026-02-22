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
): string {
  const base = `${API_BASE_URL}/attachments/${id}/content/preview`;
  if (width && height) return `${base}?w=${width}&h=${height}`;
  if (width) return `${base}?w=${width}`;
  if (height) return `${base}?h=${height}`;
  return base;
}

/** URL для скачивания (download link, cookie auth) */
export function attachmentDownloadUrl(id: number | string): string {
  return `${API_BASE_URL}/attachments/${id}/content`;
}
