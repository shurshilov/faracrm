// Copyright 2025 FARA CRM
// Проверка релея ИЗ БРАУЗЕРА — то, что сервер о себе узнать не может.
//
// Серверная проверка (POST /ice/test) отвечает на вопрос «релей жив и секрет
// совпадает», но идёт с той же машины, где релей и стоит. Закрытый снаружи
// порт, фильтрация UDP в сети клиента и приватный адрес в relay-кандидате
// видны только отсюда — из той сети, где сидит сотрудник.
//
// Микрофон не запрашиваем: кандидаты собираются и на data-канале, а разрешение
// на устройства в диагностике выглядело бы пугающе.

export interface IceCandidateInfo {
  type: string;
  address: string;
  /** Порт. Нужен, чтобы два кандидата с одного адреса не выглядели дублем. */
  port: number;
  /** Транспорт до собеседника. */
  protocol: string;
  /** Транспорт ДО релея (udp/tcp/tls) — только у relay-кандидатов. */
  relayProtocol?: string;
}

export interface IceError {
  url: string;
  code: number;
  text: string;
}

export interface IceGatherResult {
  host: IceCandidateInfo[];
  srflx: IceCandidateInfo[];
  relay: IceCandidateInfo[];
  errors: IceError[];
  /** Сбор не завершился сам — считаем то, что успели собрать. */
  timedOut: boolean;
}

export interface RelayLoopResult {
  connected: boolean;
  error: string;
  ms: number;
}

const GATHER_TIMEOUT_MS = 6000;
const LOOP_TIMEOUT_MS = 10000;

function describe(candidate: RTCIceCandidate): IceCandidateInfo {
  return {
    type: candidate.type || '',
    address: candidate.address || '',
    port: candidate.port || 0,
    protocol: candidate.protocol || '',
    // Нестандартное поле, но есть в Chrome и Firefox — именно оно отвечает на
    // вопрос «через какое плечо релея нас пустили», а он в диагностике
    // главный: в офисах с закрытым UDP работает только tcp/tls.
    relayProtocol: (candidate as RTCIceCandidate & { relayProtocol?: string })
      .relayProtocol,
  };
}

/**
 * Собрать ICE-кандидаты этого браузера теми же серверами, что и в звонке.
 *
 * Что доказывает результат:
 *   relay-кандидат  — до релея дошли, креды приняты, аллокация выдана;
 *   только srflx    — STUN отвечает, а аллокация не состоялась (секрет/квота);
 *   ни того, ни другого — 3478 недоступен из этой сети.
 */
export async function gatherIceCandidates(
  servers: RTCIceServer[],
  timeoutMs = GATHER_TIMEOUT_MS,
): Promise<IceGatherResult> {
  const result: IceGatherResult = {
    host: [],
    srflx: [],
    relay: [],
    errors: [],
    timedOut: false,
  };

  // iceTransportPolicy всегда 'all', даже когда включён режим «всё через
  // релей»: диагностике нужна полная картина, иначе не отличить «релей
  // недоступен» от «прямые соединения запрещены настройкой».
  const pc = new RTCPeerConnection({
    iceServers: servers,
    iceTransportPolicy: 'all',
  });
  let timer: ReturnType<typeof setTimeout> | undefined;

  try {
    pc.createDataChannel('turn-probe');

    const finished = new Promise<void>(resolve => {
      pc.addEventListener('icecandidate', event => {
        if (!event.candidate || !event.candidate.candidate) {
          resolve(); // null-кандидат = сбор завершён
          return;
        }
        const info = describe(event.candidate);
        if (info.type === 'relay') result.relay.push(info);
        else if (info.type === 'srflx') result.srflx.push(info);
        else if (info.type === 'host') result.host.push(info);
      });

      // Браузер честно сообщает, почему не получилось: 401 — не приняли креды,
      // 701 — до сервера не достучались. Без этого «нет relay-кандидата»
      // осталось бы гаданием.
      pc.addEventListener('icecandidateerror', event => {
        result.errors.push({
          url: event.url || '',
          code: event.errorCode,
          text: event.errorText || '',
        });
      });

      timer = setTimeout(() => {
        result.timedOut = true;
        resolve();
      }, timeoutMs);
    });

    await pc.setLocalDescription(await pc.createOffer());
    await finished;
  } finally {
    clearTimeout(timer);
    pc.close();
  }

  return result;
}

/**
 * Поднять соединение через релей и убедиться, что данные по нему идут.
 *
 * Два соединения в одной вкладке, обоим разрешён ТОЛЬКО relay — это ровно та
 * же топология, что и во внутреннем звонке двух сотрудников, когда прямой путь
 * не собрался. Сигналинг не нужен: SDP и кандидаты передаём между ними прямо
 * здесь.
 *
 * Успех означает: аллокации выданы, разрешения работают, данные через релей
 * ходят. Это самый близкий к правде ответ на вопрос «у меня звонок через релей
 * поднимется?», который можно получить, не звоня.
 */
export async function checkRelayLoop(
  servers: RTCIceServer[],
  timeoutMs = LOOP_TIMEOUT_MS,
): Promise<RelayLoopResult> {
  const config: RTCConfiguration = {
    iceServers: servers,
    iceTransportPolicy: 'relay',
  };
  const caller = new RTCPeerConnection(config);
  const callee = new RTCPeerConnection(config);
  const started = performance.now();
  let timer: ReturnType<typeof setTimeout> | undefined;

  try {
    caller.addEventListener('icecandidate', event => {
      if (event.candidate) void callee.addIceCandidate(event.candidate).catch(() => {});
    });
    callee.addEventListener('icecandidate', event => {
      if (event.candidate) void caller.addIceCandidate(event.candidate).catch(() => {});
    });

    const channel = caller.createDataChannel('turn-loop');
    const opened = new Promise<boolean>(resolve => {
      channel.addEventListener('open', () => resolve(true));
      // 'failed' приходит раньше таймаута и с ним понятнее: ICE перебрал все
      // пары и ни одна не заработала.
      caller.addEventListener('iceconnectionstatechange', () => {
        if (caller.iceConnectionState === 'failed') resolve(false);
      });
      timer = setTimeout(() => resolve(false), timeoutMs);
    });

    await caller.setLocalDescription(await caller.createOffer());
    await callee.setRemoteDescription(caller.localDescription!);
    await callee.setLocalDescription(await callee.createAnswer());
    await caller.setRemoteDescription(callee.localDescription!);

    const connected = await opened;
    return {
      connected,
      error: connected
        ? ''
        : caller.iceConnectionState === 'failed'
          ? 'ни одна пара кандидатов не заработала'
          : 'канал не открылся за отведённое время',
      ms: Math.round(performance.now() - started),
    };
  } catch (error) {
    return {
      connected: false,
      error: error instanceof Error ? error.message : String(error),
      ms: Math.round(performance.now() - started),
    };
  } finally {
    clearTimeout(timer);
    caller.close();
    callee.close();
  }
}
