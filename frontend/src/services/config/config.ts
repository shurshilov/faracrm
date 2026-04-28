import { baseQuery, API_BASE_URL } from '@services/baseQueryWithReauth';
import { createApi } from '@reduxjs/toolkit/query/react';

/**
 * Branding-настройки текущей компании.
 */
export interface BrandingConfig {
  /** Загружен ли логотип для шапки CRM */
  has_logo: boolean;
  /** Загружен ли логотип для login-страницы */
  has_login_logo: boolean;
  /** Загружен ли фон для login-страницы */
  has_login_background: boolean;
  /** Заголовок на странице входа (если задан в Company) */
  login_title: string | null;
  /** Подзаголовок (под логотипом) на странице входа */
  login_subtitle: string | null;
}

export interface PublicConfig {
  version: string;
  demo_mode: boolean;
  branding: BrandingConfig;
}

export type BrandingFileField =
  | 'logo_id'
  | 'login_logo_id'
  | 'login_background_id';

/**
 * URL для публичной branding-картинки. Нормализует префикс /api,
 * чтобы поддержать оба варианта VITE_API_URL — с /api и без.
 */
export function brandingFileUrl(field: BrandingFileField): string {
  const base = API_BASE_URL.replace(/\/$/, '');
  const apiPrefix = base.endsWith('/api') ? '' : '/api';
  return `${base}${apiPrefix}/public/branding/${field}`;
}

/**
 * Публичная конфигурация сервера (доступна без авторизации).
 */
export const configApi = createApi({
  reducerPath: 'configApi',
  baseQuery,
  endpoints: builder => ({
    getPublicConfig: builder.query<PublicConfig, void>({
      query: () => ({
        url: '/api/public/config/',
        method: 'GET',
      }),
    }),
  }),
});

export const { useGetPublicConfigQuery } = configApi;
