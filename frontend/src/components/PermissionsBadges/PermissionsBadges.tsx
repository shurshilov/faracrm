import { Group, Paper, ActionIcon, Tooltip } from '@mantine/core';
import { IconPlus, IconEye, IconPencil, IconTrash } from '@tabler/icons-react';
import classes from './PermissionsBadges.module.css';

export interface PermissionsBadgesProps {
  create?: boolean;
  read?: boolean;
  update?: boolean;
  delete?: boolean;
  /** Компактный режим для таблиц */
  compact?: boolean;
}

/**
 * Компонент отображения CRUD разрешений
 *
 * @example
 * // В Kanban карточке
 * <PermissionsBadges create={true} read={true} update={false} delete={false} />
 *
 * // В таблице (компактный режим)
 * <PermissionsBadges create={true} read={true} update={false} delete={false} compact />
 */
export function PermissionsBadges({
  create = false,
  read = false,
  update = false,
  delete: del = false,
  compact = false,
}: PermissionsBadgesProps) {
  const size = compact ? 'xs' : 'sm';
  const iconSize = compact ? 12 : 14;

  return (
    <Paper
      className={classes.wrapper}
      data-compact={compact || undefined}
      radius="md"
      p={compact ? 2 : 4}>
      <Group gap={compact ? 2 : 4}>
        <Tooltip label="Создание" withArrow disabled={compact}>
          <ActionIcon
            size={size}
            variant={create ? 'filled' : 'subtle'}
            color={create ? 'teal' : 'gray'}
            radius="md"
            className={classes.icon}
            data-active={create || undefined}>
            <IconPlus size={iconSize} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Чтение" withArrow disabled={compact}>
          <ActionIcon
            size={size}
            variant={read ? 'filled' : 'subtle'}
            color={read ? 'blue' : 'gray'}
            radius="md"
            className={classes.icon}
            data-active={read || undefined}>
            <IconEye size={iconSize} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Изменение" withArrow disabled={compact}>
          <ActionIcon
            size={size}
            variant={update ? 'filled' : 'subtle'}
            color={update ? 'orange' : 'gray'}
            radius="md"
            className={classes.icon}
            data-active={update || undefined}>
            <IconPencil size={iconSize} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Удаление" withArrow disabled={compact}>
          <ActionIcon
            size={size}
            variant={del ? 'filled' : 'subtle'}
            color={del ? 'red' : 'gray'}
            radius="md"
            className={classes.icon}
            data-active={del || undefined}>
            <IconTrash size={iconSize} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Paper>
  );
}

export default PermissionsBadges;
