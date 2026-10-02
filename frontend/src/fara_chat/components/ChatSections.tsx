import { useState } from 'react';
import { ActionIcon, Box, Menu, UnstyledButton } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import {
  IconDotsVertical,
  IconFolder,
  IconPencil,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';
import { useDeleteBulkMutation, useSearchQuery } from '@/services/api/crudApi';
import {
  ChatFolder,
  ChatSection,
  useGetFolderUnreadQuery,
} from '@/services/api/chat';
import { useChatFilter } from '../hooks/useChatFilter';
import { SECTION_META } from '../sections';
import { FolderModal } from './FolderModal';
import classes from './ChatSections.module.css';

const SECTIONS = Object.keys(SECTION_META) as ChatSection[];

// Общая папка = без владельца (user_id NULL): её правит только администратор.
function isShared(folder: ChatFolder): boolean {
  const owner = folder.user_id;
  return owner == null || (typeof owner === 'object' && owner.id == null);
}

interface TileProps {
  icon: React.ReactNode;
  label: string;
  unread?: number;
  active?: boolean;
  className?: string;
  onClick: () => void;
  /** Поверх квадрата, но не внутри кнопки — например меню папки. */
  children?: React.ReactNode;
}

function Tile({
  icon,
  label,
  unread = 0,
  active,
  className,
  onClick,
  children,
}: TileProps) {
  return (
    <Box className={classes.tileWrap}>
      <UnstyledButton
        className={`${classes.tile} ${className ?? ''}`}
        data-active={active || undefined}
        title={label}
        onClick={onClick}>
        {icon}
        <span className={classes.label}>{label}</span>
      </UnstyledButton>
      {unread > 0 && (
        <span className={classes.badge}>{unread > 99 ? '99+' : unread}</span>
      )}
      {children}
    </Box>
  );
}

/**
 * Квадраты сайдбара чатов: разделы, ниже — папки пользователя и «+».
 * В сайдбаре — колонкой, на мобильном — полосой над списком (CSS).
 */
export function ChatSections() {
  const { t } = useTranslation('chat');
  const { filter, open } = useChatFilter();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ChatFolder | null>(null);

  const { data: foldersData } = useSearchQuery({
    model: 'chat_folder',
    fields: ['id', 'name', 'sequence', 'user_id', 'domain'],
    filter: [],
    sort: 'sequence',
    order: 'asc',
    limit: 100,
  });
  const folders = (foldersData?.data as unknown as ChatFolder[]) || [];
  const [deleteBulk] = useDeleteBulkMutation();

  // Бейджи считаются на бэке на лету. refetchOnMountOrArgChange обязателен:
  // запрос обновляется инвалидацией тега FOLDER_UNREAD, а она срабатывает
  // только при активной подписке — без флага после возврата на страницу
  // RTK отдавал бы устаревший кэш, и бейджи отставали от верхнего бабла.
  const { data: unreadData } = useGetFolderUnreadQuery(undefined, {
    refetchOnMountOrArgChange: true,
  });
  const unread = unreadData?.data;

  const openEditor = (folder: ChatFolder | null) => {
    setEditing(folder);
    setModalOpen(true);
  };

  const handleDelete = (folder: ChatFolder) => {
    deleteBulk({ model: 'chat_folder', ids: [folder.id] });
    if (filter.folder_id === folder.id) open({ section: 'staff' });
  };

  return (
    <Box className={classes.rail}>
      {SECTIONS.map(section => {
        const { Icon, color, label } = SECTION_META[section];
        return (
          <Tile
            key={section}
            icon={
              <Icon
                size={20}
                color={`var(--mantine-color-${color}-light-color)`}
              />
            }
            label={t(`sections.${section}`, label)}
            unread={unread?.sections[section]}
            active={filter.section === section}
            onClick={() => open({ section })}
          />
        );
      })}

      <Box className={classes.divider} />

      {folders.map(folder => {
        const active = filter.folder_id === folder.id;
        return (
          <Tile
            key={folder.id}
            icon={<IconFolder size={20} />}
            label={folder.name}
            unread={unread?.folders[String(folder.id)]}
            active={active}
            onClick={() => open({ folder_id: folder.id })}>
            {/* Изменить/удалить — у открытой своей папки. */}
            {active && !isShared(folder) && (
              <Menu position="right-start" withinPortal shadow="md">
                <Menu.Target>
                  <ActionIcon
                    className={classes.menu}
                    variant="subtle"
                    size="xs"
                    title={t('options')}>
                    <IconDotsVertical size={12} />
                  </ActionIcon>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item
                    leftSection={<IconPencil size={14} />}
                    onClick={() => openEditor(folder)}>
                    {t('edit', 'Изменить')}
                  </Menu.Item>
                  <Menu.Item
                    color="red"
                    leftSection={<IconTrash size={14} />}
                    onClick={() => handleDelete(folder)}>
                    {t('delete', 'Удалить')}
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            )}
          </Tile>
        );
      })}

      <Tile
        icon={<IconPlus size={20} />}
        label={t('newFolder', 'Новая папка')}
        className={classes.add}
        onClick={() => openEditor(null)}
      />

      <FolderModal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        folder={editing}
      />
    </Box>
  );
}
