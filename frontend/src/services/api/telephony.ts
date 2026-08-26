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

/** Телефонный канал звонилки. Доступность считается для каждого отдельно:
 *  линий у сотрудника может быть несколько, по одной в разных коннекторах.
 *
 *  Адреса АТС здесь нет: браузер подключается к НАШЕМУ /ws/sip, а тот уже
 *  знает, куда переслать. Так адрес меняется из интерфейса, а не в nginx. */
export interface SipChannel {
  id: number;
  name: string;
  available: boolean;
  /** Чего не хватает именно этому каналу — показываем при его выборе. */
  has_transport: boolean;
  has_line: boolean;
  has_password: boolean;
  extension: string;
  realm: string;
  ice: string[];
  password?: string | null;
}

export interface SipConfig {
  channels: SipChannel[];
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
  }),
});

export const {
  useGetCallsStatsQuery,
  useGetSipConfigQuery,
} = telephonyApi;
