/**
 * ActiveFilters - отображение активных фильтров в виде тегов
 */
import {
  Group,
  Badge,
  ActionIcon,
  Tooltip,
  Text,
  SegmentedControl,
} from '@mantine/core';
import { IconX, IconTrash } from '@tabler/icons-react';
import { ActiveFilter } from './types';

interface ActiveFiltersProps {
  filters: ActiveFilter[];
  combineMode: 'and' | 'or';
  onRemove: (filterId: string) => void;
  onClear: () => void;
  onCombineModeChange: (mode: 'and' | 'or') => void;
}

export function ActiveFilters({
  filters,
  combineMode,
  onRemove,
  onClear,
  onCombineModeChange,
}: ActiveFiltersProps) {
  if (filters.length === 0) {
    return null;
  }

  return (
    <Group gap="xs" wrap="wrap">
      {filters.length > 1 && (
        <SegmentedControl
          size="xs"
          value={combineMode}
          onChange={value => onCombineModeChange(value as 'and' | 'or')}
          data={[
            { value: 'and', label: 'И' },
            { value: 'or', label: 'ИЛИ' },
          ]}
        />
      )}

      {filters.map((filter, index) => (
        <Group key={filter.id} gap={4} wrap="nowrap">
          {index > 0 && filters.length > 1 && (
            <Text size="xs" c="dimmed">
              {combineMode === 'and' ? 'и' : 'или'}
            </Text>
          )}
          <Badge
            variant="light"
            color="blue"
            size="lg"
            pr={3}
            rightSection={
              <ActionIcon
                size="xs"
                color="blue"
                radius="xl"
                variant="transparent"
                onClick={() => onRemove(filter.id)}>
                <IconX size={12} />
              </ActionIcon>
            }>
            {filter.label}
          </Badge>
        </Group>
      ))}

      {filters.length > 0 && (
        <Tooltip label="Очистить все фильтры">
          <ActionIcon variant="subtle" color="gray" size="sm" onClick={onClear}>
            <IconTrash size={14} />
          </ActionIcon>
        </Tooltip>
      )}
    </Group>
  );
}
