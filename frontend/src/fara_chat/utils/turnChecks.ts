// Copyright 2025 FARA CRM
// Сведение результатов проверки релея в один список состояний.
//
// Проверка одна, а источников три: конфиг, который уезжает в браузер; ответ
// релея на запрос с сервера; поведение самого браузера. Раньше каждый из них
// приходилось выяснять отдельно — «то ли порт закрыт, то ли секрет не тот, то
// ли сервер за NAT». Здесь они сводятся в один список, где у каждой строки
// есть вердикт и, если что-то не так, готовая команда.
//
// Функция чистая: на вход данные, на выход список. Ни запросов, ни рендера.

import type { IceConfig, IceTestResult } from '@/services/api/ice';
import type { IceGatherResult, RelayLoopResult } from './iceProbe';

export type CheckStatus = 'ok' | 'warn' | 'fail';

export interface TurnCheck {
  id: string;
  title: string;
  status: CheckStatus;
  detail: string;
  /** Что делать. Заполняется только когда есть проблема. */
  fix?: string;
  /** Готовая строка .env или команда под fix. */
  command?: string;
  /**
   * Чем посмотреть это звено руками. Показываем всегда, а не только при
   * ошибке: зелёная строка тоже вызывает вопрос «а точно?», и ответ на него
   * не должен требовать похода в документацию.
   */
  diagnose?: string;
}

type Translate = (key: string, defaultValue: string) => string;

export interface TurnCheckInput {
  t: Translate;
  config?: IceConfig;
  server?: IceTestResult;
  /** Серверная часть не выполнилась целиком (403, 429, сеть). */
  serverError?: string;
  browser?: IceGatherResult;
  browserError?: string;
  loop?: RelayLoopResult;
}

/** Приватный ли адрес — то же правило, что у релея в denied-peer-ip. */
export function isPrivateAddress(address: string): boolean {
  const parts = address.split('.').map(Number);
  if (parts.length !== 4 || parts.some(part => Number.isNaN(part))) return false;
  const [a, b] = parts;
  return (
    a === 10 ||
    a === 127 ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 169 && b === 254) ||
    (a === 100 && b >= 64 && b <= 127)
  );
}

const EXTERNAL_IP_FIX =
  'TURN_EXTRA_ARGS="--external-ip=БЕЛЫЙ_IP/ПРИВАТНЫЙ_IP"\ndocker compose up -d turn';

const PORTS_FIX =
  'sudo ufw allow 3478/udp\nsudo ufw allow 3478/tcp\nsudo ufw allow 49160:49259/udp';

/**
 * STUN Binding по UDP одной строкой — проверка, которую нельзя сделать с
 * сервера: он за NAT и сам себя снаружи не видит. Запускать с ДРУГОЙ машины,
 * не из сети сервера, иначе пакет не пойдёт через роутер и ответ ничего не
 * докажет. Без зависимостей: голый сокет и 20 байт заголовка.
 */
function udpProbeCommand(host: string): string {
  return (
    `python3 -c "import socket,struct,os;s=socket.socket(2,2);` +
    `s.settimeout(3);s.sendto(struct.pack('>HHI',1,0,0x2112A442)` +
    `+os.urandom(12),('${host}',3478));s.recv(2048);` +
    `print('UDP отвечает')" 2>/dev/null || echo "UDP молчит"`
  );
}

export function buildTurnChecks(input: TurnCheckInput): TurnCheck[] {
  const { t, config, server, serverError, browser, browserError, loop } = input;
  const checks: TurnCheck[] = [];

  // ── 1. Что вообще уезжает в браузер ───────────────────────────
  const turnUrls = (config?.ice_servers || [])
    .flatMap(entry => entry.urls)
    .filter(url => url.startsWith('turn'));

  // Адрес релея берём из выданного браузеру URL — команды диагностики должны
  // проверять ровно то, куда пойдёт клиент.
  const relayHost =
    turnUrls[0]?.replace(/^turns?:/, '').split(/[:?]/)[0] || 'АДРЕС_РЕЛЕЯ';

  checks.push({
    id: 'config',
    title: t('turn.checkConfig', 'Релей выдаётся браузеру'),
    status: turnUrls.length ? 'ok' : 'fail',
    detail: turnUrls.length
      ? turnUrls.join('   ')
      : t(
          'turn.checkConfigFail',
          'браузер получает только STUN — адрес релея или секрет не определились',
        ),
    fix: turnUrls.length
      ? undefined
      : t(
          'turn.checkConfigFix',
          'Причина пишется в лог бэкенда по слову TURN. Обычно не заполнен ' +
            'site_url и релею неоткуда взять адрес.',
        ),
    diagnose: 'docker compose logs backend --tail 200 | grep -i turn',
  });

  // ── 2. Что видно с сервера ────────────────────────────────────
  if (serverError) {
    checks.push({
      id: 'server',
      title: t('turn.checkServer', 'Проверка с сервера'),
      status: 'warn',
      detail: serverError,
    });
  } else if (server) {
    checks.push({
      id: 'reach',
      title: t('turn.checkReach', 'Сервер релея отвечает'),
      status: server.reached ? 'ok' : 'fail',
      detail: server.reached
        ? `${t('turn.checkMapped', 'наш внешний адрес')}: ${
            server.mapped_address || '—'
          }`
        : server.error,
      fix: server.reached
        ? undefined
        : t(
            'turn.checkReachFix',
            'Контейнер релея не поднят или порт закрыт на хосте.',
          ),
      // Команду не дублируем в fix: она же стоит в diagnose ниже.
      diagnose: 'docker compose ps turn\nss -lunp | grep 3478',
    });

    checks.push({
      id: 'alloc',
      title: t('turn.checkAlloc', 'Секрет принят, аллокация выдана'),
      status: server.ok ? 'ok' : 'fail',
      detail: server.ok
        ? `${t('turn.checkRelayed', 'релей выделил адрес')} ${
            server.relayed_address
          }`
        : server.error,
      fix:
        !server.ok && server.error.includes('401')
          ? t(
              'turn.checkAllocFix',
              'Секрет CRM и релея разошлись. Он общий и читается из файла в ' +
                'томе при старте — пересоздайте оба контейнера.',
            )
          : undefined,
      command:
        !server.ok && server.error.includes('401')
          ? 'docker compose up -d --force-recreate backend turn'
          : undefined,
      diagnose: 'docker compose logs turn --tail 50',
    });

    // Адрес аллокации что-то значит только когда проверка дошла снаружи:
    // изнутри релей выдаёт её на docker-интерфейсе, и он приватный всегда.
    if (server.ok && !server.probed_via) {
      checks.push({
        id: 'relay_ip',
        title: t('turn.checkRelayIp', 'Релей раздаёт адрес, до которого дойдут'),
        status: server.relay_private ? 'fail' : 'ok',
        detail: server.relayed_address,
        fix: server.relay_private
          ? t(
              'turn.checkRelayIpFix',
              'Адрес приватный: сервер за NAT и своего белого адреса не знает. ' +
                'Браузер такой кандидат получит, но достучаться до него не ' +
                'сможет — сигналинг есть, звука нет.',
            )
          : undefined,
        command: server.relay_private ? EXTERNAL_IP_FIX : undefined,
        diagnose: 'grep TURN_EXTRA_ARGS .env',
      });
    }

    if (server.probed_via) {
      // Изнутри «публичный адрес молчит» имеет ДВЕ причины, и с сервера они
      // неразличимы: либо роутер не разворачивает запрос на себя (hairpin —
      // норма), либо порт снаружи закрыт. Различает их браузер: если он ниже
      // получил relay-кандидат — это hairpin, если нет — закрытый порт.
      checks.push({
        id: 'probed_via',
        title: t('turn.checkVia', 'Проверено изнутри'),
        status: 'warn',
        detail:
          t(
            'turn.checkViaDetail',
            'Снаружи сервер сам себя не видит, поэтому запрос ушёл через',
          ) +
          ` ${server.probed_via}. ` +
          t(
            'turn.checkViaMeans',
            'Причин две и с сервера они неразличимы: роутер не умеет ' +
              'разворачивать запрос на себя (hairpin, это норма) — или порт ' +
              'снаружи закрыт. Что именно, показывают строки про браузер ниже: ' +
              'есть relay-кандидат — hairpin, нет — закрытый порт.',
          ),
        diagnose: 'ip route | grep default',
      });
    }
  }

  // ── 3. Что видит этот браузер ─────────────────────────────────
  if (browserError) {
    checks.push({
      id: 'browser',
      title: t('turn.checkBrowser', 'Проверка из браузера'),
      status: 'warn',
      detail: browserError,
    });
  } else if (browser) {
    const relay = browser.relay;
    const codes = browser.errors.map(item => item.code);
    const errorText = browser.errors.length
      ? ' (' +
        browser.errors
          .map(item => `${item.code} ${item.text}`.trim())
          .join('; ') +
        ')'
      : '';

    checks.push({
      id: 'browser_relay',
      title: t('turn.checkBrowserRelay', 'Этот браузер получает relay-кандидат'),
      status: relay.length ? 'ok' : 'fail',
      detail: relay.length
        ? relay
            .map(
              item =>
                `${item.address}:${item.port} ${
                  item.relayProtocol || item.protocol
                }`.trim(),
            )
            .join(', ')
        : (browser.srflx.length
            ? t(
                'turn.checkBrowserSrflx',
                'STUN отвечает, а аллокация не выдана',
              )
            : t(
                'turn.checkBrowserNone',
                'до релея из этой сети не достучались вообще',
              )) + errorText,
      fix: relay.length
        ? undefined
        : codes.includes(401)
          ? t(
              'turn.checkBrowserFix401',
              'Релей отверг креды — секрет у CRM и у релея разный.',
            )
          : browser.srflx.length
            ? t(
                'turn.checkBrowserFixAlloc',
                'До порта 3478 браузер дошёл, но аллокацию не получил: ' +
                  'кончился диапазон релей-портов или квота.',
              )
            : t(
                'turn.checkBrowserFixPorts',
                'Порт релея закрыт снаружи или UDP режется в сети этого ' +
                  'клиента. Откройте порты на хосте (в облаке — ещё и в ' +
                  'security group):',
              ),
      command:
        !relay.length && !browser.srflx.length && !codes.includes(401)
          ? PORTS_FIX
          : undefined,
      diagnose: udpProbeCommand(relayHost),
    });

    // Транспорт до релея. Кандидат есть, но только по TCP — частый и почти
    // невидимый случай: звонки работают, поэтому никто не разбирается, а
    // голос идёт худшим путём. Строка выше про такое молчит: relay-кандидат
    // ведь получен.
    if (relay.length) {
      const overUdp = relay.filter(
        item => (item.relayProtocol || item.protocol) === 'udp',
      );
      checks.push({
        id: 'browser_udp',
        title: t('turn.checkUdp', 'Релей доступен по UDP'),
        status: overUdp.length ? 'ok' : 'fail',
        detail: overUdp.length
          ? t('turn.checkUdpOk', 'кандидат получен по udp — голос пойдёт им')
          : t(
              'turn.checkUdpFail',
              'relay-кандидаты только по TCP: снаружи UDP до релея не доходит',
            ),
        fix: overUdp.length
          ? undefined
          : t(
              'turn.checkUdpFix',
              'Порт 3478/udp закрыт или не проброшен — TCP при этом проброшен, ' +
                'иначе не было бы и этих кандидатов. Пробросьте на сервер ' +
                '3478/udp и диапазон 49160–49259/udp порт в порт. Пока этого ' +
                'нет, звонки работают через TCP-плечо: на потерях оно ' +
                'переспрашивает пакеты и голос заикается.',
            ),
        diagnose: udpProbeCommand(relayHost),
      });
    }

    const privateRelay = relay.find(item => isPrivateAddress(item.address));
    if (privateRelay) {
      checks.push({
        id: 'browser_relay_private',
        title: t('turn.checkBrowserPrivate', 'Адрес relay-кандидата'),
        status: 'fail',
        detail: `${privateRelay.address} — ${t(
          'turn.checkBrowserPrivateDetail',
          'приватный: браузеры вне этой сети до него не дойдут',
        )}`,
        fix: t(
          'turn.checkRelayIpFix',
          'Релей за NAT и не знает своего белого адреса.',
        ),
        command: EXTERNAL_IP_FIX,
      });
    }

    if (relay.length && loop) {
      checks.push({
        id: 'loop',
        title: t('turn.checkLoop', 'Через релей проходят данные'),
        status: loop.connected ? 'ok' : 'fail',
        detail: loop.connected
          ? `${t('turn.checkLoopOk', 'канал открылся за')} ${loop.ms} ${t(
              'turn.ms',
              'мс',
            )}`
          : loop.error,
        fix: loop.connected
          ? undefined
          : t(
              'turn.checkLoopFix',
              'Аллокация выдаётся, но соединение через релей не поднялось. ' +
                'Так выглядит фильтрация UDP на стороне клиента: проверьте, ' +
                'что открыт и 3478/tcp — он и спасает такие сети.',
            ),
        diagnose: 'docker compose logs turn --tail 30',
      });
    }
  }

  // ── 4. АТС: пустит ли релей трафик до неё ─────────────────────
  for (const peer of server?.peers || []) {
    checks.push({
      id: `peer_${peer.ip}`,
      title: `${t('turn.checkPeer', 'Трафик до АТС')} ${peer.ip}`,
      status: peer.allowed ? 'ok' : 'fail',
      detail: peer.allowed
        ? t('turn.checkPeerOk', 'релей пропустит')
        : peer.error,
      fix: peer.allowed
        ? undefined
        : t(
            'turn.checkPeerFix',
            'Приватные адреса релею запрещены — это защита внутренней сети. ' +
              'Для АТС нужно точечное исключение: ДОПИШИТЕ флаг к ' +
              'существующей строке в .env, не заменяя её, и укажите один ' +
              'адрес, а не подсеть.',
          ),
      command: peer.allowed
        ? undefined
        : `TURN_EXTRA_ARGS="--external-ip=БЕЛЫЙ_IP/ПРИВАТНЫЙ_IP --allowed-peer-ip=${peer.ip}"\ndocker compose up -d turn`,
      diagnose: 'grep TURN_EXTRA_ARGS .env',
    });
  }

  return checks;
}
