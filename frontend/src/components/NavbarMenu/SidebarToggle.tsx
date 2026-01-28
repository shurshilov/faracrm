import { ActionIcon, Tooltip } from '@mantine/core';
import {
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconLayoutSidebarInactive,
  IconMenu2,
  IconX,
} from '@tabler/icons-react';
import { SidebarState } from './SidebarContext';
import classes from './SidebarToggle.module.css';

interface SidebarToggleProps {
  state: SidebarState;
  onToggle: () => void;
}

const stateConfig: Record<
  SidebarState,
  {
    icon: typeof IconLayoutSidebarLeftCollapse;
    tooltip: string;
  }
> = {
  expanded: {
    icon: IconLayoutSidebarLeftCollapse,
    tooltip: 'Свернуть меню',
  },
  collapsed: {
    icon: IconX,
    tooltip: 'Скрыть меню',
  },
  hidden: {
    icon: IconMenu2,
    tooltip: 'Показать меню',
  },
};

export function SidebarToggle({ state, onToggle }: SidebarToggleProps) {
  const { icon: Icon, tooltip } = stateConfig[state];

  return (
    <Tooltip label={tooltip} position="right" withArrow>
      <ActionIcon
        variant="subtle"
        size="lg"
        radius="md"
        onClick={onToggle}
        className={classes.toggle}
        aria-label={tooltip}>
        <Icon size={20} stroke={1.5} />
      </ActionIcon>
    </Tooltip>
  );
}
