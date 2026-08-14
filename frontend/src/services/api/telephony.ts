// Copyright 2025 FARA CRM
// Telephony API — звонки и аналитика (экран «Звонки»).
//
// Инжектим эндпоинты в общий crudApi (как chat.ts), чтобы не трогать store.

import { crudApi } from './crudApi';

export type CallDisposition =
  | 'answered'
  | 'no_answer'
  | 'busy'
  | 'failed'
  | 'cancelled';

export interface CallRow {
  id: number;
  call_direction: 'incoming' | 'outgoing' | null;
  is_internal: boolean;
  call_disposition: CallDisposition | null;
  call_duration: number | null;
  call_talk_duration: number | null;
  /** Время начала звонка (ISO) */
  started_at: string | null;
  number_from: string | null;
  number_to: string | null;
  connector_id: number;
  connector_type: string;
  connector_name: string;
  partner_id: number | null;
  partner_name: string | null;
  /** Наша линия (extension/номер) и её оператор */
  line_number: string | null;
  line_name: string | null;
  operator_name: string | null;
  /** Внешний контрагент (нога, противоположная нашей линии) */
  client_number: string | null;
  record_id: number | null;
  lead_id: number | null;
}

export interface CallStatRow {
  direction: string | null;
  disposition: string | null;
  cnt: number;
}

export interface CallsParams {
  limit?: number;
  offset?: number;
  direction?: string;
  disposition?: string;
  connector_id?: number;
  search?: string;
  date_from?: string;
  date_to?: string;
}

const telephonyApi = crudApi.injectEndpoints({
  endpoints: build => ({
    getCalls: build.query<{ data: CallRow[] }, CallsParams>({
      query: params => ({ url: 'telephony/calls', params }),
    }),
    getCallsStats: build.query<
      { data: CallStatRow[] },
      Omit<CallsParams, 'limit' | 'offset' | 'direction' | 'disposition' | 'search'>
    >({
      query: params => ({ url: 'telephony/calls/stats', params }),
    }),
  }),
});

export const { useGetCallsQuery, useGetCallsStatsQuery } = telephonyApi;
