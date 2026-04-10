import { baseQuery } from '@services/baseQueryWithReauth';
import { createApi } from '@reduxjs/toolkit/query/react';

export interface PublicConfig {
  version: string;
  demo_mode: boolean;
}

/**
 * Публичная конфигурация сервера (доступна без авторизации).
 * Отдаёт флаги, нужные фронту до логина: версия, demo_mode и т.п.
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
