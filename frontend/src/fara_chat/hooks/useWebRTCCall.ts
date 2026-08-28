/**
 * useWebRTCCall — хук для аудио-звонков 1-на-1 через WebRTC.
 *
 * Архитектура:
 *   - Сигналинг идёт через существующий WebSocket чата (call.offer/answer/ice).
 *   - Старт/принятие/завершение — через HTTP эндпоинты /calls/*.
 *   - Медиа (голос) — peer-to-peer между браузерами (через STUN), а там,
 *     где p2p не собирается (симметричный NAT, закрытый наружу UDP) — через
 *     наш TURN-релей. Список серверов НЕ хардкодится здесь: он общий с
 *     телефонией и приходит с бэкенда (services/api/ice.ts).
 *
 * State machine:
 *   idle → calling   (мы инициировали, ждём ответа)
 *   idle → incoming  (нам позвонили, ждём решения юзера)
 *   calling/incoming → connecting (accepted — идёт обмен SDP/ICE)
 *   connecting → active (P2P соединение установлено, идёт разговор)
 *   any → ended (звонок завершён: rejected/timeout/hangup)
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '@/store/store';
import { useChatWebSocketContext } from '@/fara_chat/context/ChatWebSocketContext';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { useIceConfig } from '@/services/api/ice';

/**
 * Идентификатор ЭТОЙ вкладки.
 *
 * Сигналинг бэкенд адресует пользователю, а не соединению: invite и следом
 * offer приходят на все устройства сотрудника разом. Без пометки «кому» на
 * один звонок отвечали и компьютер, и телефон — каждый своим SDP, и второй
 * ответ ронял уже собравшийся разговор. Живёт в модуле, а не в состоянии:
 * должен пережить любое перемонтирование хука и не меняться за сеанс.
 */
const CLIENT_ID =
  globalThis.crypto?.randomUUID?.() ??
  `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;

export type CallState =
  | 'idle'
  | 'calling'
  | 'incoming'
  | 'connecting'
  | 'active'
  | 'ended';

export interface CallPeer {
  id: number;
  name: string;
}

interface CallSession {
  callId: number;
  chatId: number;
  peer: CallPeer;
  isCaller: boolean;
  startedAt: number | null; // момент когда pc стал 'connected'
}

// Причины завершения — для UI-сообщения юзеру.
export type EndReason =
  | 'hangup' // кто-то сам положил трубку
  | 'rejected' // callee отклонил invite
  | 'timeout' // callee не ответил в отведённое время
  | 'offline' // callee офлайн (ответ /calls/start с delivered=false)
  | 'failed' // ошибка WebRTC или сеть
  | 'unknown';

export interface UseWebRTCCallResult {
  state: CallState;
  session: CallSession | null;
  endReason: EndReason | null;
  // Длительность разговора в секундах (от момента 'active'). Обновляется каждую секунду.
  durationSec: number;
  // Управление
  startCall: (peer: CallPeer) => Promise<void>;
  acceptCall: () => Promise<void>;
  rejectCall: () => Promise<void>;
  hangup: () => Promise<void>;
  // Контроль микрофона
  isMuted: boolean;
  toggleMute: () => void;
}

export function useWebRTCCall(): UseWebRTCCallResult {
  const { addMessageListener, send } = useChatWebSocketContext();
  const currentUserId = useSelector(
    (s: RootState) => s.auth.session?.user_id?.id ?? 0,
  );
  // Токен нужен в Authorization: Bearer ... для всех HTTP-запросов.
  // Куки идут через credentials: 'include', но бэк требует ОБЕ формы
  // (double-token pattern).
  const authToken = useSelector((s: RootState) => s.auth.session?.token ?? '');
  const authTokenRef = useRef(authToken);
  useEffect(() => {
    authTokenRef.current = authToken;
  }, [authToken]);

  // ICE-серверы держим в ref: соединение создаётся внутри обработчика
  // сигналинга, и пересобирать этот обработчик при обновлении кредов не за чем.
  const iceConfig = useIceConfig();
  const iceConfigRef = useRef(iceConfig);
  useEffect(() => {
    iceConfigRef.current = iceConfig;
  }, [iceConfig]);

  /**
   * Единая точка HTTP-запросов к /calls/*. Добавляет Authorization-header
   * + credentials: include. Использовать только внутри этого хука.
   */
  const apiCall = useCallback(
    async (path: string, init?: RequestInit): Promise<Response> => {
      return fetch(`${API_BASE_URL}${path}`, {
        ...init,
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          ...(authTokenRef.current
            ? { Authorization: `Bearer ${authTokenRef.current}` }
            : {}),
          ...(init?.headers || {}),
        },
      });
    },
    [],
  );

  const [state, setState] = useState<CallState>('idle');
  const [session, setSession] = useState<CallSession | null>(null);
  const [endReason, setEndReason] = useState<EndReason | null>(null);
  const [durationSec, setDurationSec] = useState(0);
  const [isMuted, setIsMuted] = useState(false);

  // WebRTC refs
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  // Буфер ICE-кандидатов, которые пришли до установки remoteDescription.
  // Пробуем их применить позже.
  const pendingRemoteIceRef = useRef<RTCIceCandidateInit[]>([]);
  // Вкладка собеседника, с которой идёт разговор. Звонящий узнаёт её из
  // call.accepted (какое устройство сняло трубку), принимающий — из offer.
  // Пока не известна, кадры уходят без адреса и принимаются всеми — так
  // работает старый фронт на той стороне.
  const peerClientRef = useRef<string | null>(null);

  // Таймер длительности
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (state !== 'active' || !session?.startedAt) {
      if (tickRef.current) clearInterval(tickRef.current);
      tickRef.current = null;
      return;
    }
    tickRef.current = setInterval(() => {
      setDurationSec(
        Math.floor((Date.now() - (session.startedAt as number)) / 1000),
      );
    }, 1000);
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [state, session?.startedAt]);

  // ──────────────────────────── WebRTC helpers ────────────────────────────

  /** Создать remote <audio> элемент один раз — он живёт в DOM всё время. */
  const ensureRemoteAudio = useCallback(() => {
    if (remoteAudioRef.current) return remoteAudioRef.current;
    const el = document.createElement('audio');
    el.autoplay = true;
    el.setAttribute('playsinline', 'true');
    // Без display:none — некоторые браузеры тормозят воспроизведение.
    el.style.position = 'fixed';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    remoteAudioRef.current = el;
    return el;
  }, []);

  /**
   * Создать RTCPeerConnection и навесить хэндлеры. callId известен на этот
   * момент, берём из аргумента чтобы избежать race с state.
   */
  const createPeerConnection = useCallback(
    (callId: number, toUserId: number) => {
      // Прежнее соединение здесь НЕ закрываем, хотя перетирать ссылку и
      // оставлять его жить — некрасиво. Пробовали закрывать: если сигналинг
      // продублировался (два устройства пользователя, повтор по шине),
      // второе создание убивало соединение, к которому вот-вот применят
      // пришедший answer, и звонок падал с InvalidStateError сразу после
      // ответа собеседника. Чинить надо на уровне дублей, а не здесь.
      const pc = new RTCPeerConnection(iceConfigRef.current);

      pc.onicecandidate = event => {
        if (event.candidate) {
          // Отправляем свой ICE-кандидат другой стороне через сигналинг.
          send({
            type: 'call.ice',
            call_id: callId,
            to_user_id: toUserId,
            from_client_id: CLIENT_ID,
            to_client_id: peerClientRef.current,
            candidate: event.candidate.toJSON(),
          });
        }
      };

      pc.ontrack = event => {
        // Событие от уже брошенного соединения писать в общий элемент нельзя:
        // <audio> один на весь хук, и опоздавший ontrack отвязал бы живой
        // поток от динамика.
        if (pcRef.current && pcRef.current !== pc) return;

        // streams[0] может не прийти, если в удалённом SDP нет msid — тогда
        // собираем поток из самого трека. Без этого srcObject молча получал
        // бы undefined → null, то есть тишину без единой ошибки.
        const stream = event.streams[0] || new MediaStream([event.track]);
        const audio = ensureRemoteAudio();
        audio.srcObject = stream;

        // play() обязателен, одного autoplay мало. У ЗВОНЯЩЕГО этот момент
        // отстоит от его клика на всё время дозвона (плюс бэкенд держит
        // /calls/start до 3 секунд), вкладка к тому времени часто свёрнута —
        // и политика автоплея гасит воспроизведение. Снаружи это неотличимо
        // от «медиа не дошло»: соединение установлено, таймер идёт, звука нет.
        void audio.play().catch(error => {
          console.warn('[call] браузер не дал проиграть входящий звук', error);
        });
      };

      pc.onconnectionstatechange = () => {
        const cs = pc.connectionState;
        if (cs === 'connected') {
          // P2P установлен — переходим в 'active', запускаем таймер.
          setSession(prev =>
            prev ? { ...prev, startedAt: Date.now() } : prev,
          );
          setState('active');
        } else if (cs === 'failed' || cs === 'disconnected') {
          // Не закрываем сразу на 'disconnected' — браузер пробует
          // переподключиться. 'failed' — уже капут.
          if (cs === 'failed') {
            // eslint-disable-next-line @typescript-eslint/no-use-before-define
            finishCall('failed');
          }
        }
      };

      pcRef.current = pc;
      return pc;
    },
    // finishCall определён ниже, линтер ругается — но ref-подход безопасен.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [send, ensureRemoteAudio],
  );

  /**
   * Разблокировать динамик, пока мы внутри клика пользователя.
   *
   * Браузеры разрешают звук элементу, которому дали play() по жесту. Медиа
   * приедет позже — к тому времени жеста уже не будет, особенно у звонящего:
   * между его «Позвонить» и первым пакетом проходит весь дозвон. Отказ здесь
   * ожидаем (источника ещё нет) и ни на что не влияет — важен сам факт
   * вызова из обработчика клика.
   */
  const warmRemoteAudio = useCallback(() => {
    const audio = ensureRemoteAudio();
    void audio.play().catch(() => undefined);
  }, [ensureRemoteAudio]);

  /** Захватить микрофон и добавить треки в pc. */
  const attachLocalMedia = useCallback(async (pc: RTCPeerConnection) => {
    // getUserMedia включает браузерный AEC/NS/AGC автоматически (т.к. мы
    // потом подключаем стрим к RTCPeerConnection — браузер связывает один
    // с другим и включает эхоподавление).
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
    localStreamRef.current = stream;
    for (const track of stream.getTracks()) {
      pc.addTrack(track, stream);
    }
  }, []);

  /** Закрыть всё и сбросить state. */
  const cleanupMedia = useCallback(() => {
    if (pcRef.current) {
      try {
        pcRef.current.close();
      } catch {
        // ignore
      }
      pcRef.current = null;
    }
    if (localStreamRef.current) {
      for (const track of localStreamRef.current.getTracks()) {
        track.stop();
      }
      localStreamRef.current = null;
    }
    if (remoteAudioRef.current) {
      remoteAudioRef.current.srcObject = null;
    }
    pendingRemoteIceRef.current = [];
  }, []);

  /** Единственная точка выхода из звонка. */
  const finishCall = useCallback(
    (reason: EndReason) => {
      cleanupMedia();
      peerClientRef.current = null;
      setEndReason(reason);
      setState('ended');
      setDurationSec(0);
      setIsMuted(false);
      // session оставляем для UI — компонент показывает "звонок завершён,
      // <peer.name>, длительность XX". Через 3 сек компонент сам сбросит
      // state в 'idle' (или юзер закроет модалку).
    },
    [cleanupMedia],
  );

  // ──────────────────────────── Public API ────────────────────────────

  const startCall = useCallback(
    async (peer: CallPeer) => {
      if (state !== 'idle' && state !== 'ended') {
        // Уже в звонке — игнорируем.
        return;
      }
      warmRemoteAudio();
      peerClientRef.current = null;
      setEndReason(null);
      setState('calling');
      try {
        const res = await apiCall(`/calls/start`, {
          method: 'POST',
          body: JSON.stringify({ callee_user_id: peer.id }),
        });

        if (res.status === 409) {
          // Бэкенд вернул 409 → callee не ответил ack за 3 сек,
          // считаем его оффлайн.
          finishCall('offline');
          return;
        }
        if (!res.ok) {
          finishCall('failed');
          return;
        }

        const data = (await res.json()) as {
          call_id: number;
          chat_id: number;
          callee?: { id: number; name: string };
        };

        setSession({
          callId: data.call_id,
          chatId: data.chat_id,
          peer,
          isCaller: true,
          startedAt: null,
        });
        // Ждём call.accepted события — тогда создадим pc и offer.
      } catch (err) {
        console.error('startCall failed', err);
        finishCall('failed');
      }
    },
    [state, finishCall, apiCall, warmRemoteAudio],
  );

  const acceptCall = useCallback(async () => {
    if (state !== 'incoming' || !session) return;
    warmRemoteAudio();
    try {
      const res = await apiCall(`/calls/${session.callId}/accept`, {
        method: 'POST',
        // Говорим бэкенду, КАКАЯ вкладка сняла трубку: дальше сигналинг
        // адресуется ей, а остальные устройства получат call.taken.
        body: JSON.stringify({ client_id: CLIENT_ID }),
      });
      if (!res.ok) {
        finishCall('failed');
        return;
      }
      setState('connecting');
      // Создаём pc и ждём offer от caller. Микрофон подключим
      // когда получим offer (нет смысла раньше).
    } catch (err) {
      console.error('acceptCall failed', err);
      finishCall('failed');
    }
  }, [state, session, finishCall, apiCall, warmRemoteAudio]);

  const rejectCall = useCallback(async () => {
    if (!session) return;
    try {
      await apiCall(`/calls/${session.callId}/reject`, {
        method: 'POST',
      });
    } catch (err) {
      console.error('rejectCall failed', err);
    }
    finishCall('rejected');
  }, [session, finishCall, apiCall]);

  const hangup = useCallback(async () => {
    if (!session) {
      finishCall('hangup');
      return;
    }
    try {
      await apiCall(`/calls/${session.callId}/end`, {
        method: 'POST',
        body: JSON.stringify({
          duration_seconds: durationSec || null,
        }),
      });
    } catch (err) {
      console.error('hangup failed', err);
    }
    finishCall('hangup');
  }, [session, durationSec, finishCall, apiCall]);

  const toggleMute = useCallback(() => {
    if (!localStreamRef.current) return;
    const next = !isMuted;
    for (const track of localStreamRef.current.getAudioTracks()) {
      track.enabled = !next;
    }
    setIsMuted(next);
  }, [isMuted]);

  // ──────────────────────────── Signaling listener ────────────────────────────

  useEffect(() => {
    const unsubscribe = addMessageListener(async (msg: any) => {
      if (!msg || typeof msg !== 'object' || !msg.type) return;

      // Кадр, адресованный другой вкладке того же пользователя, — не наш.
      // Одна проверка на весь сигналинг: без неё на offer отвечали все
      // устройства сотрудника сразу. Кадр без адреса принимаем — его шлёт
      // сторона, которая про адресацию ещё не знает (старая вкладка).
      if (msg.to_client_id && msg.to_client_id !== CLIENT_ID) return;

      switch (msg.type) {
        // ── invite: мы callee ──
        case 'call.invite': {
          // Игнорируем если уже в звонке.
          if (state !== 'idle' && state !== 'ended') return;
          // Подтверждаем получение → бэк снимет таймаут.
          send({ type: 'call.invite_ack', call_id: msg.call_id });
          setSession({
            callId: msg.call_id,
            chatId: msg.chat_id,
            peer: msg.caller,
            isCaller: false,
            startedAt: null,
          });
          setEndReason(null);
          setState('incoming');
          break;
        }

        // ── accepted: callee принял, мы caller — создаём pc + offer ──
        case 'call.accepted': {
          if (!session || !session.isCaller || session.callId !== msg.call_id)
            return;
          // Запоминаем, какая вкладка собеседника сняла трубку: дальше SDP и
          // кандидаты адресуем только ей.
          peerClientRef.current = msg.callee_client_id || null;
          setState('connecting');
          try {
            const pc = createPeerConnection(session.callId, session.peer.id);
            await attachLocalMedia(pc);
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            send({
              type: 'call.offer',
              call_id: session.callId,
              to_user_id: session.peer.id,
              from_client_id: CLIENT_ID,
              to_client_id: peerClientRef.current,
              sdp: offer,
            });
          } catch (err) {
            console.error('offer creation failed', err);
            finishCall('failed');
          }
          break;
        }

        // ── offer: мы callee, получили от caller — отвечаем answer ──
        case 'call.offer': {
          if (!session || session.callId !== msg.call_id) return;
          // Обратный адрес: звонящий у нас один, но пометить ответ надо —
          // так он отличит наш SDP от SDP второго устройства.
          peerClientRef.current = msg.from_client_id || null;
          try {
            const pc = createPeerConnection(session.callId, session.peer.id);
            await attachLocalMedia(pc);
            await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
            // Применяем буферизованные ICE.
            for (const c of pendingRemoteIceRef.current) {
              try {
                await pc.addIceCandidate(c);
              } catch {
                // ignore
              }
            }
            pendingRemoteIceRef.current = [];

            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);
            send({
              type: 'call.answer',
              call_id: session.callId,
              to_user_id: session.peer.id,
              from_client_id: CLIENT_ID,
              to_client_id: peerClientRef.current,
              sdp: answer,
            });
          } catch (err) {
            console.error('answer creation failed', err);
            finishCall('failed');
          }
          break;
        }

        // ── answer: мы caller, получили ответ от callee ──
        case 'call.answer': {
          if (!session || !session.isCaller || session.callId !== msg.call_id)
            return;
          const pc = pcRef.current;
          if (!pc) return;
          // Ответов может прийти НЕСКОЛЬКО: сигналинг адресуется юзеру, а не
          // сокету, поэтому offer получают все устройства собеседника и
          // каждое отвечает своим SDP. Первый ответ переводит соединение в
          // 'stable', и повторный setRemoteDescription бросает
          // InvalidStateError — а catch ниже гасил из-за этого уже живой
          // разговор («ошибка соединения» сразу после ответа). Дубликат
          // молча игнорируем: звонок держится на первом ответе.
          if (pc.signalingState !== 'have-local-offer') {
            console.warn(
              '[call] лишний answer в состоянии %s — игнорирую',
              pc.signalingState,
            );
            return;
          }
          try {
            await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
            for (const c of pendingRemoteIceRef.current) {
              try {
                await pc.addIceCandidate(c);
              } catch {
                // ignore
              }
            }
            pendingRemoteIceRef.current = [];
          } catch (err) {
            console.error('setRemoteDescription(answer) failed', err);
            finishCall('failed');
          }
          break;
        }

        // ── ice: от любой стороны ──
        case 'call.ice': {
          if (!session || session.callId !== msg.call_id) return;
          const pc = pcRef.current;
          if (!pc || !pc.remoteDescription) {
            // remoteDescription ещё не установлен — буферизуем.
            pendingRemoteIceRef.current.push(msg.candidate);
            return;
          }
          try {
            await pc.addIceCandidate(msg.candidate);
          } catch (err) {
            console.warn('addIceCandidate failed', err);
          }
          break;
        }

        // ── трубку сняли на другом устройстве ──
        case 'call.taken': {
          if (!session || session.callId !== msg.call_id) return;
          // Себя узнаём по client_id: ответившей вкладке гасить нечего.
          if (msg.client_id && msg.client_id === CLIENT_ID) return;
          // Не ошибка и не пропущенный — просто разговор идёт не здесь.
          // Поэтому тихо в 'idle', без карточки «звонок завершён».
          cleanupMedia();
          peerClientRef.current = null;
          setSession(null);
          setEndReason(null);
          setState('idle');
          break;
        }

        // ── терминальные события ──
        case 'call.rejected':
          if (session?.callId === msg.call_id) finishCall('rejected');
          break;
        case 'call.timeout':
          if (session?.callId === msg.call_id) finishCall('timeout');
          break;
        case 'call.end':
          if (session?.callId === msg.call_id) finishCall('hangup');
          break;
      }
    });
    return unsubscribe;
  }, [
    addMessageListener,
    send,
    state,
    session,
    createPeerConnection,
    attachLocalMedia,
    finishCall,
    cleanupMedia,
    currentUserId,
  ]);

  // Cleanup при размонтировании
  useEffect(
    () => () => {
      cleanupMedia();
      if (remoteAudioRef.current) {
        remoteAudioRef.current.remove();
        remoteAudioRef.current = null;
      }
    },
    [cleanupMedia],
  );

  return {
    state,
    session,
    endReason,
    durationSec,
    startCall,
    acceptCall,
    rejectCall,
    hangup,
    isMuted,
    toggleMute,
  };
}
