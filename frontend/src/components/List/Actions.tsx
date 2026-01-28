import { Menu, Button, Text, rem } from '@mantine/core';
import {
  IconSettings,
  IconSearch,
  IconPhoto,
  IconMessageCircle,
  IconTrash,
  IconArrowsLeftRight,
} from '@tabler/icons-react';
import { useDeleteBulkMutation } from '@/services/api/crudApi';
import { FaraRecord } from '@/services/api/crudTypes';

export function Actions({
  resource,
  selectedIds,
  onClearSelection,
  onDeleteStart,
  onDeleteSuccess,
  onDeleteError,
}: {
  resource: string;
  selectedIds: FaraRecord[];
  onClearSelection?: () => void;
  onDeleteStart?: () => void;
  onDeleteSuccess?: (count: number, undo?: () => void) => void;
  onDeleteError?: () => void;
}) {
  const [deleteBulk] = useDeleteBulkMutation();

  const handleDelete = async () => {
    const count = selectedIds.length;
    const idsToDelete = selectedIds.map(obj => obj.id);

    onDeleteStart?.();
    onClearSelection?.();

    // Вызываем success сразу - optimistic update уже произошёл
    onDeleteSuccess?.(count);

    // Запрос идёт в фоне
    deleteBulk({
      model: resource,
      ids: idsToDelete,
    })
      .unwrap()
      .catch(error => {
        onDeleteError?.();
      });
  };

  return (
    <Menu shadow="md" width={200}>
      <Menu.Target>
        <Button>Actions</Button>
      </Menu.Target>

      <Menu.Dropdown>
        <Menu.Label>Application</Menu.Label>
        <Menu.Item
          leftSection={
            <IconSettings style={{ width: rem(14), height: rem(14) }} />
          }>
          Settings
        </Menu.Item>
        <Menu.Item
          leftSection={
            <IconMessageCircle style={{ width: rem(14), height: rem(14) }} />
          }>
          Messages
        </Menu.Item>
        <Menu.Item
          leftSection={
            <IconPhoto style={{ width: rem(14), height: rem(14) }} />
          }>
          Gallery
        </Menu.Item>
        <Menu.Item
          leftSection={
            <IconSearch style={{ width: rem(14), height: rem(14) }} />
          }
          rightSection={
            <Text size="xs" c="dimmed">
              ⌘K
            </Text>
          }>
          Search
        </Menu.Item>

        <Menu.Divider />

        <Menu.Label>Danger zone</Menu.Label>
        <Menu.Item
          leftSection={
            <IconArrowsLeftRight style={{ width: rem(14), height: rem(14) }} />
          }>
          Transfer my data
        </Menu.Item>
        <Menu.Item
          onClick={handleDelete}
          color="red"
          leftSection={
            <IconTrash style={{ width: rem(14), height: rem(14) }} />
          }>
          Delete records ({selectedIds.length})
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
