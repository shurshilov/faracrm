import { crudApi } from '@/services/api/crudApi';

/** Приложение реестра (GET /apps/catalog): описание из info модуля плюс флаг. */
export interface CatalogApp {
  code: string;
  name: string;
  summary: string;
  category: string | null;
  version: string | null;
  /** Коды приложений-зависимостей. */
  depends: string[];
  /** Системное — удалить нельзя (сервисы и core-модули). */
  core: boolean;
  installed: boolean;
  /** ui_menu_name UI-приложения (ключ группы меню) или null. */
  app_key: string | null;
}

/** Каталог с бэкенда; app_keys — группы меню установленных UI-приложений. */
export interface AppsCatalog {
  apps: CatalogApp[];
  app_keys: string[];
}

const CATALOG_TAG = { type: 'apps', id: 'CATALOG' };

export const appsApi = crudApi.injectEndpoints({
  endpoints: build => ({
    getAppsCatalog: build.query<AppsCatalog, void>({
      query: () => ({ url: '/apps/catalog', method: 'GET' }),
      providesTags: [CATALOG_TAG],
    }),
    installApp: build.mutation<{ installed: string[] }, string>({
      query: code => ({ url: `/apps/${code}/install`, method: 'POST' }),
      invalidatesTags: [CATALOG_TAG],
    }),
    uninstallApp: build.mutation<{ uninstalled: string[] }, string>({
      query: code => ({ url: `/apps/${code}/uninstall`, method: 'POST' }),
      invalidatesTags: [CATALOG_TAG],
    }),
  }),
});

export const {
  useGetAppsCatalogQuery,
  useInstallAppMutation,
  useUninstallAppMutation,
} = appsApi;
