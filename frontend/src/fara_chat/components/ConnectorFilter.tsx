import { SegmentedControl, Group, ThemeIcon, Tooltip } from '@mantine/core';
import {
  IconMessage,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconApps,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

interface ConnectorFilterProps {
  value: string;
  onChange: (value: string) => void;
  availableTypes?: string[];
}

// Иконки для типов коннекторов
const connectorIcons: Record<string, React.ReactNode> = {
  all: <IconApps size={16} />,
  internal: <IconMessage size={16} />,
  telegram: <IconBrandTelegram size={16} />,
  whatsapp: <IconBrandWhatsapp size={16} />,
};

// Названия типов коннекторов
const connectorLabels: Record<string, string> = {
  all: 'all',
  internal: 'internal',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
};

export function ConnectorFilter({
  value,
  onChange,
  availableTypes = ['all', 'internal', 'telegram', 'email'],
}: ConnectorFilterProps) {
  const { t } = useTranslation('chat');

  const data = availableTypes.map(type => ({
    value: type,
    label: (
      <Tooltip label={connectorLabels[type] || type} position="bottom">
        <Group gap={4} wrap="nowrap">
          <ThemeIcon
            variant="transparent"
            size="xs"
            color={
              type === 'telegram'
                ? 'blue'
                : type === 'whatsapp'
                  ? 'green'
                  : 'gray'
            }>
            {connectorIcons[type] || <IconApps size={16} />}
          </ThemeIcon>
        </Group>
      </Tooltip>
    ),
  }));

  return (
    <SegmentedControl
      value={value}
      onChange={onChange}
      data={data}
      size="xs"
      fullWidth
    />
  );
}

export default ConnectorFilter;
