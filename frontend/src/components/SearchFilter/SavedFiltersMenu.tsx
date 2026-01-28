/**
 * SavedFiltersMenu - меню с сохранёнными и недавними фильтрами
 */
import { useState } from 'react';
import {
  Menu,
  ActionIcon,
  Text,
  Group,
  Divider,
  TextInput,
  Button,
  Stack,
  Modal,
  Badge,
} from '@mantine/core';
import {
  IconBookmark,
  IconHistory,
  IconTrash,
  IconStar,
  IconStarFilled,
  IconPlus,
  IconWorld,
} from '@tabler/icons-react';
import { SavedFilter, PresetFilter, FilterTriplet } from './types';

interface SavedFiltersMenuProps {
  recentFilters: SavedFilter[];
  savedFilters: SavedFilter[];
  presetFilters?: PresetFilter[];
  hasActiveFilters: boolean;
  onApply: (filter: SavedFilter) => void;
  onSave: (name: string) => void;
  onDelete: (filterId: string) => void;
  onClearRecent: () => void;
}

export function SavedFiltersMenu({
  recentFilters,
  savedFilters,
  presetFilters = [],
  hasActiveFilters,
  onApply,
  onSave,
  onDelete,
  onClearRecent,
}: SavedFiltersMenuProps) {
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [filterName, setFilterName] = useState('');

  const handleSave = () => {
    if (filterName.trim()) {
      onSave(filterName.trim());
      setFilterName('');
      setSaveModalOpen(false);
    }
  };

  const hasAnyFilters =
    recentFilters.length > 0 ||
    savedFilters.length > 0 ||
    presetFilters.length > 0;

  // Форматируем фильтры для отображения
  const formatFilterSummary = (filters: FilterTriplet[]): string => {
    if (filters.length === 0) return '';
    if (filters.length === 1) {
      const f = filters[0];
      return `${f.field} ${f.operator} ${f.value}`;
    }
    return `${filters.length} условий`;
  };

  return (
    <>
      <Menu shadow="md" width={320} position="bottom-start">
        <Menu.Target>
          <ActionIcon
            variant={savedFilters.length > 0 ? 'light' : 'subtle'}
            color={savedFilters.length > 0 ? 'blue' : 'gray'}
            size="md">
            <IconBookmark size={18} />
          </ActionIcon>
        </Menu.Target>

        <Menu.Dropdown>
          {/* Сохранить текущий фильтр */}
          {hasActiveFilters && (
            <>
              <Menu.Item
                leftSection={<IconPlus size={14} />}
                onClick={() => setSaveModalOpen(true)}>
                Сохранить текущий фильтр
              </Menu.Item>
              <Divider />
            </>
          )}

          {/* Предустановленные фильтры */}
          {presetFilters.length > 0 && (
            <>
              <Menu.Label>Предустановленные</Menu.Label>
              {presetFilters.map(filter => (
                <Menu.Item
                  key={filter.id}
                  leftSection={
                    <IconStarFilled
                      size={14}
                      color="var(--mantine-color-yellow-6)"
                    />
                  }
                  onClick={() =>
                    onApply({
                      id: filter.id,
                      name: filter.name,
                      filters: filter.filters,
                      createdAt: 0,
                    })
                  }>
                  <Group
                    justify="space-between"
                    wrap="nowrap"
                    style={{ flex: 1 }}>
                    <Text size="sm" lineClamp={1}>
                      {filter.name}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {formatFilterSummary(filter.filters)}
                    </Text>
                  </Group>
                </Menu.Item>
              ))}
              <Divider />
            </>
          )}

          {/* Сохранённые фильтры */}
          {savedFilters.length > 0 && (
            <>
              <Menu.Label>Сохранённые</Menu.Label>
              {savedFilters.map(filter => (
                <Menu.Item
                  key={filter.id}
                  leftSection={
                    filter.isGlobal ? (
                      <IconWorld
                        size={14}
                        color="var(--mantine-color-green-6)"
                      />
                    ) : (
                      <IconStar size={14} />
                    )
                  }
                  rightSection={
                    <ActionIcon
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={e => {
                        e.stopPropagation();
                        onDelete(filter.id);
                      }}>
                      <IconTrash size={12} />
                    </ActionIcon>
                  }
                  onClick={() => onApply(filter)}>
                  <Group
                    justify="space-between"
                    wrap="nowrap"
                    style={{ flex: 1, minWidth: 0 }}>
                    <Text size="sm" lineClamp={1}>
                      {filter.name}
                    </Text>
                    {filter.isDefault && (
                      <Badge size="xs" variant="light">
                        По умолч.
                      </Badge>
                    )}
                  </Group>
                </Menu.Item>
              ))}
              <Divider />
            </>
          )}

          {/* Недавние фильтры */}
          {recentFilters.length > 0 && (
            <>
              <Group justify="space-between" px="xs" py={4}>
                <Menu.Label m={0}>Недавние</Menu.Label>
                <ActionIcon
                  size="xs"
                  variant="subtle"
                  color="gray"
                  onClick={e => {
                    e.stopPropagation();
                    onClearRecent();
                  }}
                  title="Очистить историю">
                  <IconTrash size={12} />
                </ActionIcon>
              </Group>
              {recentFilters.slice(0, 5).map(filter => (
                <Menu.Item
                  key={filter.id}
                  leftSection={<IconHistory size={14} />}
                  onClick={() => onApply(filter)}>
                  <Group
                    justify="space-between"
                    wrap="nowrap"
                    style={{ flex: 1 }}>
                    <Text size="sm" lineClamp={1}>
                      {filter.name}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {formatFilterSummary(filter.filters)}
                    </Text>
                  </Group>
                </Menu.Item>
              ))}
            </>
          )}

          {!hasAnyFilters && !hasActiveFilters && (
            <Menu.Item disabled>
              <Text size="sm" c="dimmed">
                Нет сохранённых фильтров
              </Text>
            </Menu.Item>
          )}
        </Menu.Dropdown>
      </Menu>

      {/* Модальное окно для сохранения */}
      <Modal
        opened={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        title="Сохранить фильтр"
        size="sm"
        centered>
        <Stack gap="md">
          <TextInput
            label="Название фильтра"
            placeholder="Введите название"
            value={filterName}
            onChange={e => setFilterName(e.currentTarget.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleSave();
            }}
            autoFocus
          />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => setSaveModalOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleSave} disabled={!filterName.trim()}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
