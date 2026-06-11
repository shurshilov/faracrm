import { SegmentedControl, Group, ThemeIcon, Tooltip } from '@mantine/core';
import {
  IconMessage,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconApps,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import avitoIconUrl from '@/fara_chat_avito/assets/avito.svg';
import { MaxIcon } from '@/fara_chat_max_bot/components/MaxIcon';

interface ConnectorFilterProps {
  value: string;
  onChange: (value: string) => void;
  availableTypes?: string[];
}

// SVG-логотип Avito (project resolves *.svg в URL), оборачиваем в <img>
// чтобы вставить в тот же слот, где используются tabler-иконки.
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

// Иконки для типов коннекторов
const connectorIcons: Record<string, React.ReactNode> = {
  all: <IconApps size={16} />,
  internal: <IconMessage size={16} />,
  telegram: <IconBrandTelegram size={16} />,
  whatsapp: <IconBrandWhatsapp size={16} />,
  avito: <AvitoIcon />,
  max_bot: <MaxIcon />,
  // max_wamm: <MaxIcon />,
  max_business: <MaxIcon />,
};

// Названия типов коннекторов
const connectorLabels: Record<string, string> = {
  all: 'all',
  internal: 'internal',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
  avito: 'Avito',
  max_bot: 'MAX (бот)',
  // max_wamm: 'MAX (WAMM)',
  max_business: 'MAX Business',
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
                  : type === 'avito'
                    ? 'lime'
                    : type === 'max_bot'
                      ? 'grape'
                      : type === 'max_wamm'
                        ? 'grape'
                        : type === 'max_business'
                          ? 'grape'
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
