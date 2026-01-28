import { Stack, Text, UnstyledButton, Group, Badge } from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  IconMessage,
  IconUsers,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconMail,
  IconWorld,
} from '@tabler/icons-react';
import classes from './ChatSidebar.module.css';

interface ChatMenuItem {
  id: string;
  label: string;
  labelKey: string;
  to: string;
  icon: React.ComponentType<{ size?: number }>;
  badge?: number;
}

const chatMenuItems: ChatMenuItem[] = [
  // Внутренние
  {
    id: 'all_internal',
    label: 'Все внутренние',
    labelKey: 'chat:menu.all',
    to: '/chat?is_internal=true',
    icon: IconMessage,
  },
  {
    id: 'direct',
    label: 'Личные',
    labelKey: 'chat:menu.direct',
    to: '/chat?is_internal=true&chat_type=direct',
    icon: IconMessage,
  },
  {
    id: 'groups',
    label: 'Группы',
    labelKey: 'chat:menu.groups',
    to: '/chat?is_internal=true&chat_type=group',
    icon: IconUsers,
  },
  // Разделитель (визуально через paddingTop)
  {
    id: 'all_external',
    label: 'Все внешние',
    labelKey: 'chat:menu.all',
    to: '/chat?is_internal=false',
    icon: IconWorld,
  },
  {
    id: 'telegram',
    label: 'Telegram',
    labelKey: 'chat:menu.telegram',
    to: '/chat?is_internal=false&connector_type=telegram',
    icon: IconBrandTelegram,
  },
  {
    id: 'whatsapp',
    label: 'WhatsApp',
    labelKey: 'chat:menu.whatsapp',
    to: '/chat?is_internal=false&connector_type=whatsapp',
    icon: IconBrandWhatsapp,
  },
  {
    id: 'email',
    label: 'Email',
    labelKey: 'chat:menu.email',
    to: '/chat?is_internal=false&connector_type=email',
    icon: IconMail,
  },
];

export function ChatSidebar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentPath = location.pathname + location.search;

  return (
    <Stack gap={4}>
      <Text size="xs" fw={600} c="dimmed" px="sm" py="xs" tt="uppercase">
        {t('chat:menu.internal', 'Внутренние')}
      </Text>

      {chatMenuItems.slice(0, 3).map(item => (
        <ChatMenuItem
          key={item.id}
          item={item}
          isActive={currentPath === item.to}
          onClick={() => navigate(item.to)}
          t={t}
        />
      ))}

      <Text
        size="xs"
        fw={600}
        c="dimmed"
        px="sm"
        py="xs"
        tt="uppercase"
        mt="md">
        {t('chat:menu.external', 'Внешние')}
      </Text>

      {chatMenuItems.slice(3).map(item => (
        <ChatMenuItem
          key={item.id}
          item={item}
          isActive={currentPath === item.to}
          onClick={() => navigate(item.to)}
          t={t}
        />
      ))}
    </Stack>
  );
}

interface ChatMenuItemProps {
  item: ChatMenuItem;
  isActive: boolean;
  onClick: () => void;
  t: (key: string, fallback?: string) => string;
}

function ChatMenuItem({ item, isActive, onClick, t }: ChatMenuItemProps) {
  const Icon = item.icon;

  return (
    <UnstyledButton
      className={classes.chatItem}
      data-active={isActive || undefined}
      onClick={onClick}>
      <Group gap="sm">
        <Icon size={18} />
        <Text size="sm" fw={isActive ? 600 : 400}>
          {t(item.labelKey, item.label)}
        </Text>
      </Group>
      {item.badge !== undefined && item.badge > 0 && (
        <Badge size="sm" variant="filled" color="blue">
          {item.badge}
        </Badge>
      )}
    </UnstyledButton>
  );
}
