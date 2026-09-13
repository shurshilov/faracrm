/**
 * API модуля contract: реквизиты по ИНН и банк по БИК для кнопки
 * «Заполнить» у поля (см. extensions/ViewFormPartner.tsx). Бэк —
 * backend/base/crm/contract/routers/requisites.py, источник данных —
 * провайдер реквизитов (модуль dadata).
 */
import { crudApi } from '@/services/api/crudApi';

/** Значения полей партнёра для подстановки в форму; {} — не найдено. */
export type RequisitesValues = Record<string, unknown>;

const contractApi = crudApi.injectEndpoints({
  endpoints: build => ({
    partyByInn: build.query<RequisitesValues, string>({
      query: inn => ({ url: '/requisites/party', params: { inn } }),
    }),
    bankByBic: build.query<RequisitesValues, string>({
      query: bic => ({ url: '/requisites/bank', params: { bic } }),
    }),
  }),
});

export const { useLazyPartyByInnQuery, useLazyBankByBicQuery } = contractApi;
