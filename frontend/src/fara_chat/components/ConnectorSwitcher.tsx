import { ChatConnectorDetail } from '@/services/api/chat';
import { ActionIcon, Menu, Tooltip, Text, Group } from '@mantine/core';
import {
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconMail,
  IconMessage,
  IconChevronDown,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import avitoIconUrl from '@/fara_chat_avito/assets/avito.svg';
import { MaxIcon } from '@/fara_chat_max_bot/components/MaxIcon';

interface ConnectorSwitcherProps {
  connectors: ChatConnectorDetail[];
  selectedConnectorId: number | null;
  onSelect: (connectorId: number | null) => void;
  disabled?: boolean;
}

// SVG-логотип Avito отдаётся как URL (project resolves *.svg в строку),
// поэтому рендерим через <img>. Размер совпадает с tabler-иконками (16px);
// draggable=false чтобы внутри Menu.Item иконка не «отрывалась» при drag.
const AvitoIcon = () => (
  <img
    src={avitoIconUrl}
    width={16}
    height={16}
    alt="Avito"
    draggable={false}
    style={{ display: 'block' }}
  />
);

const connectorIcons: Record<string, React.ReactNode> = {
  internal: <IconMessage size={16} />,
  telegram: <IconBrandTelegram size={16} />,
  whatsapp: <IconBrandWhatsapp size={16} />,
  email: <IconMail size={16} />,
  avito: <AvitoIcon />,
  max_bot: <MaxIcon />,
  // max_wamm: <MaxIcon />,
  max_business: <MaxIcon />,
};

const connectorColors: Record<string, string> = {
  internal: 'gray',
  telegram: 'blue',
  whatsapp: 'green',
  email: 'orange',
  avito: 'lime',
  max_bot: 'grape',
  // max_wamm: 'grape',
  max_business: 'grape',
};

export function ConnectorSwitcher({
  connectors,
  selectedConnectorId,
  onSelect,
  disabled,
}: ConnectorSwitcherProps) {
  const { t } = useTranslation('chat');

  const selectedConnector =
    connectors.find(c => c.connector_id === selectedConnectorId) ||
    connectors[0];

  if (!selectedConnector) {
    return null;
  }

  // Если только один коннектор - не показываем выбор
  if (connectors.length <= 1) {
    return (
      <Tooltip label={selectedConnector.connector_name}>
        <ActionIcon
          variant="subtle"
          size="lg"
          color={connectorColors[selectedConnector.connector_type] || 'gray'}
          disabled>
          {connectorIcons[selectedConnector.connector_type] || (
            <IconMessage size={16} />
          )}
        </ActionIcon>
      </Tooltip>
    );
  }

  return (
    <Menu position="top-start" withArrow disabled={disabled}>
      <Menu.Target>
        <Tooltip label={t('selectConnector')}>
          <ActionIcon
            variant="light"
            size="lg"
            color={connectorColors[selectedConnector.connector_type] || 'gray'}>
            <Group gap={2}>
              {connectorIcons[selectedConnector.connector_type] || (
                <IconMessage size={16} />
              )}
              <IconChevronDown size={12} />
            </Group>
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{t('sendVia')}</Menu.Label>
        {connectors.map(connector => (
          <Menu.Item
            key={connector.connector_id ?? 'internal'}
            leftSection={
              connectorIcons[connector.connector_type] || (
                <IconMessage size={16} />
              )
            }
            onClick={() => onSelect(connector.connector_id)}
            color={
              connector.connector_id === selectedConnectorId
                ? connectorColors[connector.connector_type]
                : undefined
            }>
            <Text
              size="sm"
              fw={connector.connector_id === selectedConnectorId ? 600 : 400}>
              {connector.connector_name}
            </Text>
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}

export default ConnectorSwitcher;
