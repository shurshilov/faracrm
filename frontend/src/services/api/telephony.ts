// Copyright 2025 FARA CRM
// Telephony API — сводка по звонкам для экрана «Звонки».
//
// Сам реестр звонков читается обычным авто-CRUD (/auto/call/search) — экран
// это стандартный list/form модели `call`. Здесь только аналитика, которую
// нельзя посчитать по странице таблицы.
//
// Инжектим эндпоинт в общий crudApi (как chat.ts), чтобы не трогать store.

import { crudApi } from './crudApi';
import { FilterExpression } from './crudTypes';

export interface CallsStatsParams {
  /** Фильтр таблицы (тот же, что уходит в /auto/call/search). */
  filter?: FilterExpression;
}

/**
 * Настройки SIP-регистрации браузера. available:false — звонилка выключена.
 *
 * Адреса АТС здесь нет: браузер подключается к НАШЕМУ /ws/sip, а тот уже знает,
 * куда переслать (адрес АТС — в настройках коннектора). Так его можно менять из
 * интерфейса, не трогая конфиг nginx.
 */
export interface SipConfig {
  available: boolean;
  /** Чего не хватает — кнопка всегда видна и объясняет это пользователю. */
  has_line?: boolean;
  has_transport?: boolean;
  has_password?: boolean;
  line?: string;
  realm?: string;
  ice?: string[];
  extension?: string;
  password?: string | null;
}

export interface CallsStats {
  total: number;
  answered: number;
  missed: number;
  incoming: number;
  outgoing: number;
}

const telephonyApi = crudApi.injectEndpoints({
  endpoints: build => ({
    getCallsStats: build.query<CallsStats, CallsStatsParams>({
      query: ({ filter }) => ({
        method: 'POST',
        url: 'telephony/calls/stats',
        body: { filter },
      }),
      // Сводка обязана меняться вместе с таблицей: правка/создание звонка
      // инвалидирует список модели — тем же тегом инвалидируется и она.
      providesTags: [{ type: 'call', id: 'LIST' }],
    }),

    // Настройки звонилки для ТЕКУЩЕГО пользователя. available:false —
    // штатный ответ (нет своей линии, не задан WSS или пароль).
    getSipConfig: build.query<{ data: SipConfig }, void>({
      query: () => ({ method: 'GET', url: 'telephony/sip/config' }),
    }),

    // Пароль линии — private-поле, в generic-форму не приезжает.
    setSipPassword: build.mutation<
      { data: { ok: boolean } },
      { phoneNumberId: number; password: string }
    >({
      query: ({ phoneNumberId, password }) => ({
        method: 'PUT',
        url: `telephony/sip/password/${phoneNumberId}`,
        body: { password },
      }),
    }),
  }),
});

export const {
  useGetCallsStatsQuery,
  useGetSipConfigQuery,
  useSetSipPasswordMutation,
} = telephonyApi;
