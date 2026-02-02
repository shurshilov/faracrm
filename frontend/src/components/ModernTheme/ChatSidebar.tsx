import { useMemo } from 'react';
import {
  Stack,
  Text,
  UnstyledButton,
  Group,
  Divider,
} from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  IconMessage,
  IconUsers,
  IconWorld,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconMail,
  IconMessageCircle,
} from '@tabler/icons-react';
import { useGetMyConnectorsQuery } from '@/services/api/chat';
import classes from './ChatSidebar.module.css';

// ─── Цветовая карта коннекторов ─────────────────────────────────────────────
// connector.type → иконка + CSS-переменные для light-темы.
// Dark-тема обрабатывается в CSS через @mixin dark (осветлённые варианты).
// Добавил новый тип коннектора? Добавь 1 запись сюда.

interface ConnectorTheme {
  icon: React.ComponentType<{ size?: number }>;
  color: string;       // основной цвет иконки
  activeBg: string;    // фон при active
  activeText: string;  // текст при active
}

const CONNECTOR_THEME: Record<string, ConnectorTheme> = {
  telegram: {
    icon: IconBrandTelegram,
    color: '#0088cc',
    activeBg: 'rgba(0, 136, 204, 0.1)',
    activeText: '#006699',
  },
  whatsapp: {
    icon: IconBrandWhatsapp,
    color: '#25d366',
    activeBg: 'rgba(37, 211, 102, 0.1)',
    activeText: '#128c44',
  },
  email: {
    icon: IconMail,
    color: '#f59e0b',
    activeBg: 'rgba(245, 158, 11, 0.1)',
    activeText: '#b45309',
  },
};

// Фоллбэк — нейтральный серый для неизвестных типов
const DEFAULT_THEME: Omit<ConnectorTheme, 'icon'> = {
  color: '#6b7280',
  activeBg: 'rgba(107, 114, 128, 0.08)',
  activeText: '#374151',
};

// ─── Статические пункты (внутренние) ────────────────────────────────────────

interface StaticItem {
  id: string;
  labelKey: string;
  fallback: string;
  to: string;
  icon: React.ComponentType<{ size?: number }>;
}

const INTERNAL_ITEMS: StaticItem[] = [
  {
    id: 'all_internal',
    labelKey: 'chat:menu.allInternal',
    fallback: 'Все',
    to: '/chat?is_internal=true',
    icon: IconMessage,
  },
  {
    id: 'direct',
    labelKey: 'chat:menu.direct',
    fallback: 'Личные',
    to: '/chat?is_internal=true&chat_type=direct',
    icon: IconMessage,
  },
  {
    id: 'groups',
    labelKey: 'chat:menu.groups',
    fallback: 'Группы',
    to: '/chat?is_internal=true&chat_type=group',
    icon: IconUsers,
  },
];

// ─── Компонент ──────────────────────────────────────────────────────────────

export function ChatSidebar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentPath = location.pathname + location.search;

  // Динамически загружаем коннекторы текущего пользователя
  const { data: connectorsData } = useGetMyConnectorsQuery();

  // Группируем по типу (2 telegram-коннектора → 1 пункт «Telegram»)
  const externalItems = useMemo(() => {
    if (!connectorsData?.data) return [];

    const seen = new Map<string, string>();
    for (const c of connectorsData.data) {
      if (!seen.has(c.type)) {
        seen.set(c.type, c.name);
      }
    }

    return Array.from(seen, ([type, name]) => ({
      id: type,
      type,
      labelKey: `chat:menu.${type}`,
      fallback: name || type.charAt(0).toUpperCase() + type.slice(1),
      to: `/chat?is_internal=false&connector_type=${type}`,
    }));
  }, [connectorsData]);

  const hasExternal = externalItems.length > 0;

  return (
    <Stack gap={4}>
      {/* ── Внутренние (стиль B — left accent bar) ── */}
      <Text size="xs" fw={600} c="dimmed" px="sm" py="xs" tt="uppercase">
        {t('chat:menu.internal', 'Внутренние')}
      </Text>

      {INTERNAL_ITEMS.map(item => {
        const Icon = item.icon;
        const isActive = currentPath === item.to;

        return (
          <UnstyledButton
            key={item.id}
            className={`${classes.item} ${classes.internal}`}
            data-active={isActive || undefined}
            onClick={() => navigate(item.to)}>
            <Group gap="sm">
              <Icon size={18} />
              <Text size="sm" fw={isActive ? 600 : 400}>
                {t(item.labelKey, item.fallback)}
              </Text>
            </Group>
          </UnstyledButton>
        );
      })}

      {/* ── Разделитель + заголовок ── */}
      {hasExternal && (
        <Divider
          my="sm"
          mx="sm"
          labelPosition="left"
          label={
            <Text size="xs" fw={600} c="dimmed" tt="uppercase">
              {t('chat:menu.external', 'Внешние')}
            </Text>
          }
        />
      )}

      {/* ── Все внешние ── */}
      {hasExternal && (() => {
        const isActive = currentPath === '/chat?is_internal=false';
        return (
          <UnstyledButton
            className={`${classes.item} ${classes.external}`}
            data-active={isActive || undefined}
            onClick={() => navigate('/chat?is_internal=false')}
            style={{
              '--c-icon': '#0ea5e9',
              '--c-active-bg': 'rgba(14, 165, 233, 0.1)',
              '--c-active-text': '#0369a1',
            } as React.CSSProperties}>
            <Group gap="sm">
              <IconWorld size={18} />
              <Text size="sm" fw={isActive ? 600 : 400}>
                {t('chat:menu.allExternal', 'Все')}
              </Text>
            </Group>
          </UnstyledButton>
        );
      })()}

      {/* ── Динамические коннекторы (стиль A — colored pills) ── */}
      {externalItems.map(item => {
        const theme = CONNECTOR_THEME[item.type];
        const color = theme?.color || DEFAULT_THEME.color;
        const activeBg = theme?.activeBg || DEFAULT_THEME.activeBg;
        const activeText = theme?.activeText || DEFAULT_THEME.activeText;
        const Icon = theme?.icon || IconMessageCircle;
        const isActive = currentPath === item.to;

        return (
          <UnstyledButton
            key={item.id}
            className={`${classes.item} ${classes.external}`}
            data-active={isActive || undefined}
            onClick={() => navigate(item.to)}
            style={{
              '--c-icon': color,
              '--c-active-bg': activeBg,
              '--c-active-text': activeText,
            } as React.CSSProperties}>
            <Group gap="sm">
              <Icon size={18} />
              <Text size="sm" fw={isActive ? 600 : 400}>
                {t(item.labelKey, item.fallback)}
              </Text>
            </Group>
          </UnstyledButton>
        );
      })}
    </Stack>
  );
}
