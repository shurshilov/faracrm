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
  /** Цвет кнопки "Войти" в формате HEX (#RRGGBB), если задан в Company */
  login_button_color: string | null;
  /** Стиль карточки на странице входа: elevated (объёмный) или flat (плоский) */
  login_card_style: 'elevated' | 'flat';
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

export function brandingFileUrl(field: BrandingFileField): string {
  return `${API_BASE_URL}/public/branding/${field}`;
}

export const configApi = createApi({
  reducerPath: 'configApi',
  baseQuery,
  endpoints: builder => ({
    getPublicConfig: builder.query<PublicConfig, void>({
      query: () => ({
        url: `${API_BASE_URL}/public/config/`,
        method: 'GET',
      }),
    }),
  }),
});

export const { useGetPublicConfigQuery } = configApi;
