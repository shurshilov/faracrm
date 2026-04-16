import { useState } from 'react';
import { useSelector } from 'react-redux';
import { ActionIcon, Popover, Stack, Switch } from '@mantine/core';
import { IconAdjustments } from '@tabler/icons-react';

/**
 * Одна опция в поповере настроек вида.
 */
export interface ViewSettingsOption {
  /** Уникальный ключ опции (для React key). */
  key: string;
  /** Подпись рядом со Switch. */
  label: string;
  /** Текущее состояние переключателя (controlled). */
  checked: boolean;
  /** Колбек изменения состояния. */
  onChange: (value: boolean) => void;
  /** Опциональный disabled. */
  disabled?: boolean;
  /** Опция видна только админам (session.user_id.is_admin). */
  adminOnly?: boolean;
}

interface ViewSettingsPopoverProps {
  /** Список опций. Если после фильтрации по adminOnly пусто — компонент не рендерится. */
  options: ViewSettingsOption[];
  /** Тултип на иконке. По умолчанию — "Настройки". */
  title?: string;
  /** Размер ActionIcon. По умолчанию 'md'. */
  size?: 'sm' | 'md' | 'lg';
  /** Вариант ActionIcon. По умолчанию 'subtle'. */
  variant?: 'subtle' | 'light' | 'filled' | 'default';
  /** Позиция поповера относительно кнопки. */
  position?: 'bottom-end' | 'bottom-start' | 'bottom' | 'top-end' | 'top';
}

/**
 * Кнопка-поповер с переключателями видимости.
 *
 * Доступен всем пользователям. Опции с `adminOnly: true` скрываются
 * для не-админов (session.user_id.is_admin !== true). Если в итоге
 * видимых опций нет — возвращает null, можно безусловно ставить в JSX.
 *
 * Иконка подсвечивается оранжевым, если хотя бы одна видимая опция включена —
 * визуальный индикатор, что пользователь сейчас видит "не как по умолчанию".
 *
 * Состояние опций — controlled: родитель держит state и колбеки.
 * Компонент сам управляет только состоянием open/closed своего popover.
 */
export function ViewSettingsPopover({
  options,
  title = 'Настройки',
  size = 'md',
  variant = 'subtle',
  position = 'bottom-end',
}: ViewSettingsPopoverProps) {
  const session = useSelector((s: any) => s.auth?.session);
  const isAdmin = !!session?.user_id?.is_admin;
  const [opened, setOpened] = useState(false);

  // Фильтруем admin-only опции для обычных пользователей
  const visibleOptions = options.filter(o => !o.adminOnly || isAdmin);

  if (visibleOptions.length === 0) {
    return null;
  }

  const anyActive = visibleOptions.some(o => o.checked);

  return (
    <Popover
      opened={opened}
      onChange={setOpened}
      position={position}
      withArrow
      shadow="md">
      <Popover.Target>
        <ActionIcon
          variant={variant}
          size={size}
          onClick={() => setOpened(o => !o)}
          title={title}
          color={anyActive ? 'orange' : undefined}>
          <IconAdjustments size={size === 'lg' ? 20 : 18} />
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap="xs">
          {visibleOptions.map(opt => (
            <Switch
              key={opt.key}
              checked={opt.checked}
              onChange={e => opt.onChange(e.currentTarget.checked)}
              label={opt.label}
              disabled={opt.disabled}
              size="sm"
            />
          ))}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

export default ViewSettingsPopover;
