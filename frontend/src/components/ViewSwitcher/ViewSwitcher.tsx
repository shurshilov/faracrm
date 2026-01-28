import { ActionIcon, Group, Tooltip } from '@mantine/core';
import { IconList, IconLayoutKanban, IconFileText, IconTimeline } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

export type ViewType = 'list' | 'kanban' | 'gantt' | 'form';

interface ViewSwitcherProps {
  value: ViewType;
  onChange: (value: ViewType) => void;
  availableViews?: ViewType[];
}

const viewIcons = {
  list: IconList,
  kanban: IconLayoutKanban,
  gantt: IconTimeline,
  form: IconFileText,
};

export function ViewSwitcher({ 
  value, 
  onChange,
  availableViews = ['list', 'form'],
}: ViewSwitcherProps) {
  const { t } = useTranslation('common');

  const views = [
    { id: 'list' as const, label: t('viewSwitcher.list', 'Список') },
    { id: 'kanban' as const, label: t('viewSwitcher.kanban', 'Канбан') },
    { id: 'gantt' as const, label: t('viewSwitcher.gantt', 'Гант') },
    { id: 'form' as const, label: t('viewSwitcher.form', 'Форма') },
  ].filter(view => availableViews.includes(view.id));

  return (
    <Group gap={4}>
      {views.map(view => {
        const Icon = viewIcons[view.id];
        const isActive = value === view.id;
        
        return (
          <Tooltip key={view.id} label={view.label} position="bottom" withArrow>
            <ActionIcon
              variant={isActive ? 'filled' : 'subtle'}
              color={isActive ? 'blue' : 'gray'}
              size="md"
              onClick={() => onChange(view.id)}
            >
              <Icon size={18} />
            </ActionIcon>
          </Tooltip>
        );
      })}
    </Group>
  );
}
