/**
 * ViewMenu — кнопка «⋮» в шапке вида (список, канбан, форма): одно место
 * для настроек вида и действий над ним, везде одинаковое. Пункты
 * (Menu.Item) передаёт сам вид.
 */
import { ReactNode } from 'react';
import { ActionIcon, Menu, Tooltip } from '@mantine/core';
import { IconDotsVertical } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

export function ViewMenu({ children }: { children: ReactNode }) {
  const { t } = useTranslation('common');

  return (
    <Menu shadow="md" position="bottom-end" withinPortal>
      <Menu.Target>
        <Tooltip label={t('more')}>
          <ActionIcon variant="subtle" color="gray" size="md">
            <IconDotsVertical size={18} />
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>{children}</Menu.Dropdown>
    </Menu>
  );
}
