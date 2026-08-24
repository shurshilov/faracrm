import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';
import { PhoneConnectorActions } from '@/fara_chat/components/PhoneConnectorActions';
import { Accordion, Text } from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';

// Поля коннектора Asterisk (нужны, чтобы форма их подгрузила): доступ к внешнему
// Asterisk-agent (REST, Basic-auth) + webhook приёма ARI-событий.
const ASTERISK_FIELDS = [
  'connector_url',
  'access_token',
  'refresh_token',
  'webhook_url',
  'webhook_state',
  'webhook_hash',
];

/**
 * Секция «Подключение» коннектора Asterisk / FreePBX.
 *
 * Транспорт один — внешний Asterisk-agent рядом с АТС: ARI-события он шлёт на
 * webhook FARA, историю (CDR), записи и номера FARA тянет из его REST API.
 */
export function ViewFormConnectorAsterisk() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  return (
    <FormSection
      title={t('connector.groups.asterisk', 'Asterisk / FreePBX')}
      collapsible>
      <FormRow cols={1}>
        <FieldChar
          name="connector_url"
          label={t('connector.fields.asteriskUrl', 'URL Asterisk-agent')}
          placeholder="http://host:8082"
        />
      </FormRow>
      <FormRow cols={2}>
        <FieldChar
          name="access_token"
          label={t('connector.fields.asteriskLogin', 'Логин (Basic-auth)')}
        />
        <FieldChar
          name="refresh_token"
          label={t('connector.fields.asteriskPassword', 'Пароль (Basic-auth)')}
          type="password"
        />
      </FormRow>
      <Text size="xs" c="dimmed" mt={4}>
        {t(
          'connector.asterisk.webhookHint',
          'Укажите webhook-URL (вкладка «Webhooks») как адрес отправки ARI-событий в конфиге Asterisk-agent.',
        )}
      </Text>

      <PhoneConnectorActions />
    </FormSection>
  );
}

/** Webhook-секция Asterisk (агент шлёт сюда ARI-события). */
export function ViewFormConnectorAsteriskWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  return <WebhookSection sourceName="Asterisk" />;
}

/**
 * Таб «Авторизация» = настройки звонилки в браузере (SIP поверх WebSocket).
 *
 * К доступу самого коннектора отношения не имеет — тот ходит по Basic-auth из
 * «Подключения». Занимаем этот таб, потому что реестр расширений умеет только
 * встраиваться в СУЩЕСТВУЮЩИЕ табы, а список табов общий для всех коннекторов.
 */
export function ViewFormConnectorAsteriskSip() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  return (
    <FormSection
      title={t('connector.asterisk.sipGroup', 'Звонилка в браузере (WebRTC)')}>
      <Text size="xs" c="dimmed" mb="xs">
        {t(
          'connector.asterisk.sipHint',
          'Адрес АТС видит только сервер ФАРЫ — наружу его открывать не нужно, ' +
            'браузер ходит через ФАРУ. Пусто — звонилка выключена, кнопки ' +
            'телефона в шапке не будет. Пароль SIP задаётся у каждой линии в ' +
            'разделе «Номера».',
        )}
      </Text>
      <FormRow cols={1}>
        <FieldChar
          name="sip_ws_url"
          label={t('connector.fields.sipWsUrl', 'Веб-сокет АТС')}
          placeholder="ws://192.168.1.10:8088/ws"
        />
      </FormRow>
      <FormRow cols={2}>
        <FieldChar
          name="sip_realm"
          label={t('connector.fields.sipRealm', 'SIP-домен (realm)')}
          placeholder="pbx.example.com"
        />
        <FieldChar
          name="sip_ice"
          label={t('connector.fields.sipIce', 'ICE-серверы (через запятую)')}
          placeholder="stun:stun.l.google.com:19302"
        />
      </FormRow>

      <Accordion variant="contained" radius="md" mt="sm">
        <Accordion.Item value="freepbx">
          <Accordion.Control icon={<IconInfoCircle size={16} />}>
            {t(
              'connector.asterisk.sipSetupTitle',
              'Что настроить на FreePBX',
            )}
          </Accordion.Control>
          <Accordion.Panel>
            <Text size="xs" component="div">
              <ol style={{ margin: 0, paddingLeft: 18 }}>
                <li>
                  Settings → Asterisk SIP Settings → включить транспорт{' '}
                  <b>WS</b> (порт 8088). Наружу его открывать не нужно: браузер
                  ходит через ФАРУ, ей достаточно доступа к АТС по внутренней
                  сети.
                </li>
                <li>
                  Включить у extension режим <b>WebRTC</b> (в Advanced: Enable
                  AVPF, ICE Support, rtcp Mux, Media Encryption DTLS-SRTP). Эти
                  настройки действуют на <b>весь</b> extension.
                </li>
                <li>
                  Если сотрудник говорит <b>только из браузера</b> — включайте их
                  на его обычном extension. Если у него есть ещё настольный
                  телефон или софтфон — заведите <b>отдельный</b> extension для
                  браузера (например 2201 при столе 201): обычная трубка не умеет
                  DTLS-SRTP и на WebRTC-extension не зарегистрируется, а на один
                  extension по умолчанию пускается только одно устройство.
                </li>
                <li>
                  Открыть наружу <b>UDP 10000–20000</b> — звук идёт напрямую
                  браузер ↔ АТС, мимо ФАРЫ.
                </li>
                <li>
                  Нажать «Синхронизировать номера». Если завели отдельный
                  extension — добавьте сотруднику контакт с его значением, чтобы
                  обе линии привязались к нему. Пароль SIP задаётся у линии в
                  разделе «Номера».
                </li>
              </ol>
            </Text>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </FormSection>
  );
}

// Регистрируем расширения формы коннектора (гейт по type='phone_asterisk')
registerExtension(
  'chat_connector',
  ViewFormConnectorAsterisk,
  'after:FormTab:connection',
  ASTERISK_FIELDS,
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAsteriskWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAsteriskSip,
  'after:FormTab:auth',
  ['sip_ws_url', 'sip_realm', 'sip_ice'],
);

export default ViewFormConnectorAsterisk;
