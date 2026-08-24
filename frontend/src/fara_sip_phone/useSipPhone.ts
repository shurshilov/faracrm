// Copyright 2025 FARA CRM
// Транспорт звонилки: SIP поверх WebSocket (JsSIP) прямо из браузера.
//
// Живёт ОТДЕЛЬНО от внутренних звонков сотрудников (fara_chat/useWebRTCCall):
// там собеседник — пользователь CRM и свой сигналинг поверх WS чата, здесь —
// номер и настоящий SIP к АТС. Общего кода почти нет, а связывать их значило бы
// переписывать работающую стейт-машину.
//
// Изоляция: любая ошибка гасится внутри хука и переводит состояние в 'offline'.
// История звонков, карточка клиента и лидогенерация к браузеру отношения не
// имеют — они питаются событиями от АТС на вебхук.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '@/store/store';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { useGetSipConfigQuery } from '@/services/api/telephony';

export type SipState =
  | 'disabled'
  | 'offline'
  | 'registered'
  | 'calling'
  | 'incoming'
  | 'active';

export interface SipPhone {
  state: SipState;
  /** Что осталось настроить (пусто — всё готово). Для подсказки в кнопке. */
  todo: string[];
  /** Номер собеседника текущего звонка. */
  peer: string;
  /** Секунды с начала разговора. */
  duration: number;
  error: string | null;
  muted: boolean;
  call: (number: string) => void;
  answer: () => void;
  hangup: () => void;
  toggleMute: () => void;
  sendDtmf: (tone: string) => void;
}

const IDLE: SipState[] = ['disabled', 'offline', 'registered'];

/**
 * Адрес SIP-сокета: НАШ же бэкенд, а не АТС напрямую. CSP разрешает WebSocket
 * только на свой домен, а адрес АТС знает бэкенд из настроек коннектора.
 * Путь /ws/* уже проксируется nginx с Upgrade-семантикой.
 */
function sipWsUrl(token: string): string {
  // Тот же способ, что у сокета чата (ChatWebSocketContext).
  const apiUrl = new URL(API_BASE_URL, window.location.origin);
  const scheme = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${apiUrl.host}/ws/sip?token=${token}`;
}

export function useSipPhone(): SipPhone {
  const { data } = useGetSipConfigQuery();
  const config = data?.data;
  const token = useSelector(
    (state: RootState) => state.auth.session?.token || '',
  );

  const [state, setState] = useState<SipState>('disabled');
  const [peer, setPeer] = useState('');
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);

  const uaRef = useRef<any>(null);
  const sessionRef = useRef<any>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Таймер разговора.
  useEffect(() => {
    if (state !== 'active') {
      setDuration(0);
      return;
    }
    const started = Date.now();
    const t = setInterval(
      () => setDuration(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(t);
  }, [state]);

  const attachSession = useCallback((session: any) => {
    sessionRef.current = session;
    setMuted(false);

    session.on('confirmed', () => setState('active'));
    session.on('ended', () => {
      sessionRef.current = null;
      setState(uaRef.current?.isRegistered() ? 'registered' : 'offline');
      setPeer('');
    });
    session.on('failed', (e: any) => {
      sessionRef.current = null;
      setState(uaRef.current?.isRegistered() ? 'registered' : 'offline');
      setPeer('');
      setError(e?.cause ? String(e.cause) : 'Звонок не состоялся');
    });
    // Удалённый звук: один <audio> на всё время жизни хука.
    session.connection?.addEventListener('track', (e: RTCTrackEvent) => {
      if (audioRef.current && e.streams[0]) {
        audioRef.current.srcObject = e.streams[0];
        audioRef.current.play().catch(() => undefined);
      }
    });
  }, []);

  // Регистрация. Пересобирается только при смене конфига.
  useEffect(() => {
    if (!config?.available || !token) {
      setState('disabled');
      return;
    }

    let cancelled = false;
    const audio = document.createElement('audio');
    audio.autoplay = true;
    document.body.appendChild(audio);
    audioRef.current = audio;

    (async () => {
      try {
        // jssip публикуется как CJS — под Vite неймспейс приезжает то напрямую,
        // то через .default, поэтому берём оба варианта.
        const mod: any = await import('jssip');
        const JsSIP = mod.UA ? mod : mod.default;
        if (cancelled) return;

        const socket = new JsSIP.WebSocketInterface(sipWsUrl(token));
        const ua = new JsSIP.UA({
          sockets: [socket],
          uri: `sip:${config.extension}@${config.realm || 'localhost'}`,
          password: config.password,
          register: true,
        });

        ua.on('registered', () => !cancelled && setState('registered'));
        ua.on('unregistered', () => !cancelled && setState('offline'));
        ua.on('disconnected', () => !cancelled && setState('offline'));
        ua.on('registrationFailed', (e: any) => {
          if (cancelled) return;
          setState('offline');
          setError(e?.cause ? String(e.cause) : 'Регистрация не удалась');
        });

        ua.on('newRTCSession', (e: any) => {
          const session = e.session;
          if (sessionRef.current) {
            // Линия занята — второй звонок не берём.
            session.terminate();
            return;
          }
          attachSession(session);
          if (session.direction === 'incoming') {
            setPeer(session.remote_identity?.uri?.user || '');
            setState('incoming');
          }
        });

        ua.start();
        uaRef.current = ua;
      } catch (e: any) {
        if (cancelled) return;
        setState('offline');
        setError('Звонилка не загрузилась');
      }
    })();

    return () => {
      cancelled = true;
      try {
        sessionRef.current?.terminate();
        uaRef.current?.stop();
      } catch {
        /* уже остановлен */
      }
      uaRef.current = null;
      sessionRef.current = null;
      audio.remove();
      audioRef.current = null;
    };
  }, [
    config?.available,
    config?.extension,
    config?.realm,
    config?.password,
    token,
    attachSession,
  ]);

  const call = useCallback(
    (number: string) => {
      const ua = uaRef.current;
      const target = number.trim();
      if (!ua || !target || !IDLE.includes(state)) return;
      setError(null);
      setPeer(target);
      setState('calling');
      try {
        ua.call(`sip:${target}@${config?.realm || 'localhost'}`, {
          mediaConstraints: { audio: true, video: false },
          pcConfig: {
            iceServers: (config?.ice || []).map(urls => ({ urls })),
          },
        });
      } catch {
        setState('registered');
        setPeer('');
        setError('Не удалось начать звонок');
      }
    },
    [state, config?.realm, config?.ice],
  );

  const answer = useCallback(() => {
    try {
      sessionRef.current?.answer({
        mediaConstraints: { audio: true, video: false },
        pcConfig: { iceServers: (config?.ice || []).map(urls => ({ urls })) },
      });
    } catch {
      setError('Не удалось ответить');
    }
  }, [config?.ice]);

  const hangup = useCallback(() => {
    try {
      sessionRef.current?.terminate();
    } catch {
      /* сессия уже закрыта */
    }
  }, []);

  const toggleMute = useCallback(() => {
    const session = sessionRef.current;
    if (!session) return;
    try {
      if (session.isMuted()?.audio) {
        session.unmute({ audio: true });
        setMuted(false);
      } else {
        session.mute({ audio: true });
        setMuted(true);
      }
    } catch {
      /* игнорируем */
    }
  }, []);

  const sendDtmf = useCallback((tone: string) => {
    try {
      sessionRef.current?.sendDTMF(tone, { transportType: 'RFC2833' });
    } catch {
      /* игнорируем */
    }
  }, []);

  const todo: string[] = [];
  if (config && !config.available) {
    if (!config.has_line) {
      todo.push('В разделе «Номера» нет линии, привязанной к вам');
    }
    if (config.has_line && !config.has_transport) {
      todo.push('У коннектора не задан адрес веб-сокета АТС');
    }
    if (config.has_line && !config.has_password) {
      todo.push('У вашей линии не задан пароль SIP');
    }
  }

  return {
    state,
    todo,
    peer,
    duration,
    error,
    muted,
    call,
    answer,
    hangup,
    toggleMute,
    sendDtmf,
  };
}
