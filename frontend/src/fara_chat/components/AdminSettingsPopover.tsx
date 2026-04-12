import { useState } from 'react';
import { useSelector } from 'react-redux';
import { ActionIcon, Popover, Stack, Switch } from '@mantine/core';
import { IconAdjustments } from '@tabler/icons-react';

/**
 * Одна опция в поповере настроек админа.
 */
export interface AdminSettingsOption {
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
}

interface AdminSettingsPopoverProps {
  /** Список опций. Если пусто — компонент не рендерится. */
  options: AdminSettingsOption[];
  /** Тултип на иконке. По умолчанию — "Настройки админа". */
  title?: string;
  /** Размер ActionIcon. По умолчанию 'md'. */
  size?: 'sm' | 'md' | 'lg';
  /** Вариант ActionIcon. По умолчанию 'subtle'. */
  variant?: 'subtle' | 'light' | 'filled' | 'default';
  /** Позиция поповера относительно кнопки. */
  position?: 'bottom-end' | 'bottom-start' | 'bottom' | 'top-end' | 'top';
}

/**
 * Кнопка-поповер с админскими переключателями видимости.
 *
 * Рендерится только если текущий пользователь — админ
 * (session.user_id.is_admin === true). Для обычного пользователя
 * компонент возвращает null — можно безусловно ставить в JSX.
 *
 * Иконка подсвечивается оранжевым, если хотя бы одна опция включена —
 * визуальный индикатор, что админ сейчас видит "не как все".
 *
 * Состояние опций — controlled: родитель держит state и колбеки.
 * Компонент сам управляет только состоянием open/closed своего popover.
 */
export function AdminSettingsPopover({
  options,
  title = 'Настройки админа',
  size = 'md',
  variant = 'subtle',
  position = 'bottom-end',
}: AdminSettingsPopoverProps) {
  const session = useSelector((s: any) => s.auth?.session);
  const isAdmin = !!session?.user_id?.is_admin;
  const [opened, setOpened] = useState(false);

  if (!isAdmin || options.length === 0) {
    return null;
  }

  const anyActive = options.some(o => o.checked);

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
          {options.map(opt => (
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

export default AdminSettingsPopover;
