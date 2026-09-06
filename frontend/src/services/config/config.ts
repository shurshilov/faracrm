import { baseQuery, API_BASE_URL } from '@services/baseQueryWithReauth';
import { createApi } from '@reduxjs/toolkit/query/react';

/**
 * Одна соцсеть на странице логина — пара (тип, ссылка).
 * Тип маппится в иконку и подпись через SOCIAL_TYPE_META на фронте.
 */
export interface SocialLink {
  type: string;
  url: string;
}

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
  /** Загружен ли кастомный фавикон (вкладка браузера + apple-touch-icon).
   *  PWA-иконки — отдельные, см. has_manifest_icon_*. */
  has_favicon: boolean;
  /** Версия favicon-а для cache-bust. Меняется при загрузке новой картинки.
   *  Используется как `?v=<version>` в URL иконки, чтобы браузер
   *  посчитал URL новым и перетянул файл. null → favicon-а нет. */
  favicon_version: string | null;
  /** Загружена ли отдельная иконка для PWA-манифеста (192 px). */
  has_manifest_icon_192: boolean;
  /** Загружена ли отдельная иконка для PWA-манифеста (512 px). */
  has_manifest_icon_512: boolean;
  /** Версия PWA-манифеста для cache-bust URL'а /api/public/manifest.json.
   *  Хеш по содержимому JSON + id'ам иконок. Меняется при любой правке
   *  через админку. null → нет ни JSON, ни иконок. */
  manifest_version: string | null;
  /** Заголовок вкладки браузера. Бэк парсит его из manifest_json.name —
   *  отдельного поля app_title в Company больше нет. */
  app_title: string | null;
  /** Заголовок на странице входа (если задан в Company) */
  login_title: string | null;
  /** Подзаголовок (под логотипом) на странице входа */
  login_subtitle: string | null;
  /** Цвет кнопки "Войти" в формате HEX (#RRGGBB), если задан в Company */
  login_button_color: string | null;
  /** Стиль карточки на странице входа: elevated (объёмный) или flat (плоский) */
  login_card_style: 'elevated' | 'flat';
  /** Соцсети на странице входа. Пустой массив → фронт показывает дефолтные FARA-ссылки. */
  login_socials: SocialLink[];
}

export interface PublicConfig {
  version: string;
  demo_mode: boolean;
  branding: BrandingConfig;
  /** Коды установленных приложений — нужны до входа (ссылка на регистрацию).
   *  Полный каталог с описаниями — приватный GET /apps/catalog (fara_apps). */
  apps: string[];
}

export type BrandingFileField =
  | 'logo_id'
  | 'login_logo_id'
  | 'login_background_id'
  | 'favicon_id'
  | 'manifest_icon_192_id'
  | 'manifest_icon_512_id';

export function brandingFileUrl(
  field: BrandingFileField,
  version?: string | null,
): string {
  const url = `${API_BASE_URL}/public/branding/${field}`;
  return version ? `${url}?v=${encodeURIComponent(version)}` : url;
}

/**
 * Полный URL PWA-манифеста для <link rel="manifest"> с cache-bust по версии.
 * Версия — `manifest_version` из BrandingConfig (sha1 по содержимому).
 * Меняется при любой правке manifest_json или иконок — заставляет
 * браузер/Android перечитать манифест, а не отдавать из кеша.
 */
export function manifestUrl(version?: string | null): string {
  const url = `${API_BASE_URL}/public/manifest.json`;
  return version ? `${url}?v=${encodeURIComponent(version)}` : url;
}

export const configApi = createApi({
  reducerPath: 'configApi',
  baseQuery,
  endpoints: builder => ({
    getPublicConfig: builder.query<PublicConfig, void>({
      query: () => ({
        // baseQuery уже клеит API_BASE_URL ('/api/'), здесь только относительный путь.
        url: '/public/config/',
        method: 'GET',
      }),
    }),
  }),
});

export const { useGetPublicConfigQuery } = configApi;
