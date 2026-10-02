import { Menu } from '@mantine/core';
import {
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconChevronDown,
  IconMail,
  IconMessageCircle,
  IconX,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';
import avitoIconUrl from '@/fara_chat_avito/assets/avito.svg';
import { MaxIcon } from '@/fara_chat_max_bot/components/MaxIcon';
import { VkIcon } from '@/fara_chat_vk/components/VkIcon';
import { useChatFilter } from '../hooks/useChatFilter';
import chipClasses from './ChatFilterChips.module.css';

// SVG-логотип Avito (project resolves *.svg в URL), оборачиваем в <img>
// чтобы вставить в тот же слот, где используются tabler-иконки.
const AvitoIcon = () => (
  <img
    src={avitoIconUrl}
    width={14}
    height={14}
    alt="Avito"
    draggable={false}
    style={{ display: 'block' }}
  />
);

// Иконки по типу коннектора.
const CONNECTOR_ICONS: Record<string, React.ReactNode> = {
  telegram: <IconBrandTelegram size={14} />,
  whatsapp: <IconBrandWhatsapp size={14} />,
  whatsapp_chatapp: <IconBrandWhatsapp size={14} />,
  email: <IconMail size={14} />,
  avito: <AvitoIcon />,
  max_bot: <MaxIcon size={14} />,
  max_business: <MaxIcon size={14} />,
  vk: <VkIcon size={14} />,
};

const connectorIcon = (type: string) =>
  CONNECTOR_ICONS[type] ?? <IconMessageCircle size={14} />;

interface Connector {
  id: number;
  type: string;
  name: string;
  category?: string | null;
}

/**
 * Чип «Источник ▾» у клиентов: коннекторы — пунктами меню, поэтому ширина
 * не растёт с их числом. Коннектор один — выбирать не из чего, чипа нет.
 */
export function ConnectorFilter() {
  const { t } = useTranslation('chat');
  const { filter, update } = useChatFilter();
  const { data } = useSearchQuery({
    model: 'chat_connector',
    fields: ['id', 'type', 'name', 'category'],
    filter: [['active', '=', true]],
    limit: 200,
  });
  // Уведомления (web_push) — не канал переписки.
  const connectors = ((data?.data as unknown as Connector[]) || []).filter(
    c => c.category !== 'notification',
  );
  if (connectors.length < 2) return null;

  const current = connectors.find(c => c.id === filter.connector_id);
  return (
    <Menu position="bottom-start" withinPortal shadow="md">
      <Menu.Target>
        <button
          type="button"
          className={chipClasses.chip}
          data-active={!!current || undefined}>
          {current && connectorIcon(current.type)}
          {current?.name ?? t('source', 'Источник')}
          <IconChevronDown size={12} />
        </button>
      </Menu.Target>
      <Menu.Dropdown>
        {current && (
          <Menu.Item
            leftSection={<IconX size={14} />}
            onClick={() => update({ connector_id: undefined })}>
            {t('allSources', 'Все источники')}
          </Menu.Item>
        )}
        {connectors.map(c => (
          <Menu.Item
            key={c.id}
            leftSection={connectorIcon(c.type)}
            onClick={() => update({ connector_id: c.id })}>
            {c.name}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}

export default ConnectorFilter;
