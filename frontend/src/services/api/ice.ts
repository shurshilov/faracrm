// Copyright 2025 FARA CRM
// ICE/TURN — общий источник конфигурации для ВСЕХ звонков.
//
// Потребителей два и они не связаны между собой:
//   - fara_chat/useWebRTCCall  — внутренние звонки сотрудник↔сотрудник,
//   - fara_sip_phone/useSipPhone — звонилка в браузере к АТС.
// Раньше у каждого был свой список серверов (у первого — захардкоженный
// Google STUN, у второго — строка в коннекторе), поэтому «работает у одних
// и не работает у других» чинилось в двух местах по-разному.
//
// Креды TURN временные (см. backend/base/crm/chat/turn.py), поэтому хук сам
// перезапрашивает их до истечения ttl — вкладку CRM держат открытой днями.

import { useEffect, useMemo, useState } from 'react';
import { crudApi } from './crudApi';

export interface IceServer {
  urls: string[];
  username?: string;
  credential?: string;
}

export interface IceConfig {
  ice_servers: IceServer[];
  /** 'relay' — принудительно гнать весь трафик через TURN (TURN__FORCE_RELAY). */
  ice_transport_policy: 'all' | 'relay';
  /** Секунды до истечения кредов. 0 — TURN не настроен, отдан только STUN. */
  ttl: number;
}

export interface IcePeerCheck {
  ip: string;
  allowed: boolean;
  error: string;
}

export interface IceTestResult {
  ok: boolean;
  error: string;
  /** Релей ответил хотя бы на STUN — отличает «молчит» от «отказал». */
  reached: boolean;
  mapped_address: string;
  relayed_address: string;
  /** Релей раздаёт приватный адрес: он за NAT и не знает своего белого. */
  relay_private: boolean;
  /** Пустит ли релей трафик к АТС: приватные адреса ему запрещены. */
  peers: IcePeerCheck[];
  /** Заполнен, если снаружи сервер себя не видит и проверка прошла изнутри. */
  probed_via?: string;
}

const iceApi = crudApi.injectEndpoints({
  endpoints: build => ({
    getIceServers: build.query<{ data: IceConfig }, void>({
      query: () => ({ method: 'GET', url: 'ice/servers' }),
    }),

    // Настоящая аллокация на релее — отвечает не «порт открыт», а
    // «звонок через релей пойдёт».
    testIce: build.mutation<{ data: IceTestResult }, void>({
      query: () => ({ method: 'POST', url: 'ice/test' }),
    }),
  }),
});

export const { useGetIceServersQuery, useTestIceMutation } = iceApi;

/**
 * RTCConfiguration для нового соединения. Пустой список серверов (TURN не
 * настроен, STUN-фоллбэк выключен) — валидное значение: звонок в одной сети
 * соберётся и без них.
 */
export function useIceConfig(): RTCConfiguration {
  const { data, isError, refetch } = useGetIceServersQuery();
  const config = data?.data;
  const ttl = config?.ttl ?? 0;

  // Обновляем заранее (90% ttl) и ПОВТОРЯЮЩИМСЯ таймером: вкладку CRM держат
  // открытой сутками, а с одноразовым setTimeout эффект больше не запускался
  // бы — ttl в ответе тот же, зависимости не меняются, и второе обновление
  // никогда не наступало. Протухшие креды = молча неработающий релей.
  useEffect(() => {
    if (!ttl) return;
    const timer = setInterval(() => refetch(), ttl * 900);
    return () => clearInterval(timer);
  }, [ttl, refetch]);

  // Ошибка запроса (сеть моргнула, бэкенд ещё не обновлён) оставила бы
  // конфиг пустым НАВСЕГДА — звонки лишились бы даже STUN, который работал
  // до всей этой затеи. Повторяем, пока не получится: счётчик попыток нужен
  // именно для «пока» — без него isError не меняется и эффект не перезапустится.
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!isError) return;
    const timer = setTimeout(() => {
      setAttempt(value => value + 1);
      refetch();
    }, 15000);
    return () => clearTimeout(timer);
  }, [isError, attempt, refetch]);

  // Ссылочная стабильность важна: потребители кладут конфиг в ref и сравнивают
  // по ссылке, иначе эффект дёргается на каждый рендер.
  return useMemo(
    () => ({
      iceServers: config?.ice_servers || [],
      iceTransportPolicy: config?.ice_transport_policy || 'all',
    }),
    [config],
  );
}
