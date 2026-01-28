import { useState, useEffect } from 'react';
import {
  Modal,
  TextInput,
  Textarea,
  Button,
  Stack,
  Group,
  Text,
  Avatar,
  Box,
  Loader,
  Divider,
  ActionIcon,
  Badge,
  Tabs,
  Switch,
  Paper,
  Tooltip,
} from '@mantine/core';
import {
  IconSettings,
  IconUsers,
  IconTrash,
  IconUserMinus,
  IconMessage,
  IconShield,
  IconCrown,
  IconSearch,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import {
  Chat,
  ChatMember,
  useGetChatQuery,
  useUpdateChatMutation,
  useRemoveChatMemberMutation,
  useLeaveChatMutation,
  useDeleteChatMutation,
  chatApi,
} from '@/services/api/chat';
import { useDispatch } from 'react-redux';
import { notifications } from '@mantine/notifications';

interface MemberPermissions {
  can_read: boolean;
  can_write: boolean;
  can_invite: boolean;
  can_pin: boolean;
  can_delete_others: boolean;
  is_admin: boolean;
}

interface ChatDefaultPermissions {
  default_can_read: boolean;
  default_can_write: boolean;
  default_can_invite: boolean;
  default_can_pin: boolean;
  default_can_delete_others: boolean;
}

interface ChatSettingsModalProps {
  opened: boolean;
  onClose: () => void;
  chat: Chat;
  currentUserId: number;
  onChatDeleted?: () => void;
}

// Компонент для управления разрешениями
function PermissionsBlock({
  permissions,
  onChange,
  disabled = false,
  showAdmin = true,
  t,
}: {
  permissions: MemberPermissions | ChatDefaultPermissions;
  onChange: (key: string, value: boolean) => void;
  disabled?: boolean;
  showAdmin?: boolean;
  t: (key: string) => string;
}) {
  const isAdminMode = 'is_admin' in permissions && permissions.is_admin;

  const permissionItems = [
    {
      key: 'can_read',
      defaultKey: 'default_can_read',
      label: t('permissions.canRead'),
    },
    {
      key: 'can_write',
      defaultKey: 'default_can_write',
      label: t('permissions.canWrite'),
    },
    {
      key: 'can_invite',
      defaultKey: 'default_can_invite',
      label: t('permissions.canInvite'),
    },
    {
      key: 'can_pin',
      defaultKey: 'default_can_pin',
      label: t('permissions.canPin'),
    },
    {
      key: 'can_delete_others',
      defaultKey: 'default_can_delete_others',
      label: t('permissions.canDeleteOthers'),
    },
  ];

  return (
    <Stack gap="xs">
      {permissionItems.map(item => {
        const key = 'is_admin' in permissions ? item.key : item.defaultKey;
        const value = (permissions as Record<string, boolean>)[key] ?? false;

        return (
          <Group key={key} justify="space-between">
            <Text size="sm">{item.label}</Text>
            <Switch
              checked={isAdminMode || value}
              onChange={e => onChange(key, e.currentTarget.checked)}
              disabled={disabled || isAdminMode}
              size="sm"
            />
          </Group>
        );
      })}

      {showAdmin && 'is_admin' in permissions && (
        <>
          <Divider my="xs" />
          <Group justify="space-between">
            <Group gap="xs">
              <IconCrown size={16} color="var(--mantine-color-yellow-6)" />
              <Text size="sm" fw={500}>
                {t('permissions.isAdmin')}
              </Text>
            </Group>
            <Switch
              checked={permissions.is_admin}
              onChange={e => onChange('is_admin', e.currentTarget.checked)}
              disabled={disabled}
              size="sm"
              color="yellow"
            />
          </Group>
        </>
      )}
    </Stack>
  );
}

// Модалка редактирования прав участника
function MemberPermissionsModal({
  opened,
  onClose,
  member,
  onSave,
  isSaving,
  t,
}: {
  opened: boolean;
  onClose: () => void;
  member: (ChatMember & { permissions?: MemberPermissions }) | null;
  onSave: (permissions: MemberPermissions) => void;
  isSaving: boolean;
  t: (key: string) => string;
}) {
  const [permissions, setPermissions] = useState<MemberPermissions>({
    can_read: true,
    can_write: true,
    can_invite: false,
    can_pin: false,
    can_delete_others: false,
    is_admin: false,
  });

  useEffect(() => {
    if (member?.permissions) {
      setPermissions(member.permissions);
    }
  }, [member]);

  const handleChange = (key: string, value: boolean) => {
    setPermissions(prev => ({ ...prev, [key]: value }));
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="xs">
          <IconShield size={20} />
          <Text fw={600}>{t('permissions.memberPermissions')}</Text>
        </Group>
      }
      size="sm">
      <Stack gap="md">
        {member && (
          <Paper p="sm" withBorder>
            <Group gap="sm">
              <Avatar color="blue" radius="xl" size="md">
                {member.name?.slice(0, 2).toUpperCase()}
              </Avatar>
              <Box>
                <Text fw={500}>{member.name}</Text>
                {member.email && (
                  <Text size="xs" c="dimmed">
                    {member.email}
                  </Text>
                )}
              </Box>
            </Group>
          </Paper>
        )}

        <PermissionsBlock
          permissions={permissions}
          onChange={handleChange}
          disabled={isSaving}
          showAdmin={true}
          t={t}
        />

        <Group justify="flex-end" mt="md">
          <Button variant="subtle" onClick={onClose} disabled={isSaving}>
            {t('cancel')}
          </Button>
          <Button onClick={() => onSave(permissions)} loading={isSaving}>
            {t('save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// Компонент списка участников
function MembersList({
  members,
  currentUserId,
  isGroupChat,
  onRemove,
  onEditPermissions,
  isBusy,
  t,
  showSearch = false,
}: {
  members: (ChatMember & { permissions?: MemberPermissions })[];
  currentUserId: number;
  isGroupChat: boolean;
  onRemove: (id: number) => void;
  onEditPermissions: (
    member: ChatMember & { permissions?: MemberPermissions },
  ) => void;
  isBusy: boolean;
  t: (key: string) => string;
  showSearch?: boolean;
}) {
  const [search, setSearch] = useState('');

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const getRoleBadge = (
    member: ChatMember & { permissions?: MemberPermissions },
  ) => {
    if (member.permissions?.is_admin) {
      return (
        <Badge size="xs" color="yellow" variant="light">
          {t('member.roles.admin')}
        </Badge>
      );
    }
    if (member.permissions?.can_write === false) {
      return (
        <Badge size="xs" color="gray" variant="light">
          {t('member.roles.readonly')}
        </Badge>
      );
    }
    return null;
  };

  // Сортируем: текущий пользователь первый
  const sortedMembers = [...members].sort((a, b) => {
    if (a.id === currentUserId) return -1;
    if (b.id === currentUserId) return 1;
    return 0;
  });

  // Фильтруем участников по поиску
  const filteredMembers = search.trim()
    ? sortedMembers.filter(
        m =>
          m.name?.toLowerCase().includes(search.toLowerCase()) ||
          m.email?.toLowerCase().includes(search.toLowerCase()),
      )
    : sortedMembers;

  return (
    <Stack gap="xs">
      {showSearch && members.length > 5 && (
        <TextInput
          placeholder={t('searchUsers')}
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
          leftSection={<IconSearch size={16} />}
          size="sm"
          mb="xs"
        />
      )}

      {filteredMembers.length === 0 ? (
        <Text size="sm" c="dimmed" ta="center" py="md">
          {t('noUsersFound')}
        </Text>
      ) : (
        filteredMembers.map(member => {
          const isCurrentUser = member.id === currentUserId;

          return (
            <Group key={member.id} justify="space-between">
              <Group gap="sm">
                <Avatar
                  color={isCurrentUser ? 'green' : 'blue'}
                  radius="xl"
                  size="sm">
                  {getInitials(member.name || 'U')}
                </Avatar>
                <Box>
                  <Group gap="xs">
                    <Text size="sm" fw={500}>
                      {member.name}
                      {isCurrentUser && (
                        <Text span c="dimmed" size="xs" ml="xs">
                          ({t('you')})
                        </Text>
                      )}
                    </Text>
                    {getRoleBadge(member)}
                  </Group>
                  {member.email && (
                    <Text size="xs" c="dimmed">
                      {member.email}
                    </Text>
                  )}
                </Box>
              </Group>

              <Group gap="xs">
                {/* Edit permissions button - for group chats, not for self */}
                {isGroupChat && (
                  <Tooltip
                    label={
                      t('permissions.memberPermissions') || 'Edit permissions'
                    }>
                    <ActionIcon
                      variant="subtle"
                      color="blue"
                      size="sm"
                      onClick={() => onEditPermissions(member)}
                      disabled={isBusy}>
                      <IconShield size={16} />
                    </ActionIcon>
                  </Tooltip>
                )}

                {/* Remove member button - for group chats, not for self */}
                {isGroupChat && !isCurrentUser && (
                  <Tooltip label={t('removeMember')}>
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      size="sm"
                      onClick={() => onRemove(member.id)}
                      disabled={isBusy}>
                      <IconUserMinus size={16} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </Group>
            </Group>
          );
        })
      )}
    </Stack>
  );
}

export function ChatSettingsModal({
  opened,
  onClose,
  chat,
  currentUserId,
  onChatDeleted,
}: ChatSettingsModalProps) {
  const { t } = useTranslation('chat');
  const dispatch = useDispatch();

  // API hooks
  const {
    data: chatData,
    isLoading,
    refetch,
  } = useGetChatQuery({ chatId: chat.id }, { skip: !opened });
  const [updateChat, { isLoading: isUpdating }] = useUpdateChatMutation();
  const [removeMember, { isLoading: isRemoving }] =
    useRemoveChatMemberMutation();
  const [leaveChat, { isLoading: isLeaving }] = useLeaveChatMutation();
  const [deleteChat, { isLoading: isDeleting }] = useDeleteChatMutation();

  const [name, setName] = useState(chat.name);
  const [description, setDescription] = useState('');
  const [activeTab, setActiveTab] = useState<string | null>('settings');
  const [isSavingPermissions, setIsSavingPermissions] = useState(false);
  const [isSavingMemberPerms, setIsSavingMemberPerms] = useState(false);

  // Default permissions state
  const [defaultPermissions, setDefaultPermissions] =
    useState<ChatDefaultPermissions>({
      default_can_read: true,
      default_can_write: true,
      default_can_invite: false,
      default_can_pin: false,
      default_can_delete_others: false,
    });

  // Member permissions modal
  const [editingMember, setEditingMember] = useState<
    (ChatMember & { permissions?: MemberPermissions }) | null
  >(null);

  // Update form when data loads
  useEffect(() => {
    if (chatData?.data) {
      setName(chatData.data.name);
      setDescription(chatData.data.description || '');
      if (chatData.data.default_can_read !== undefined) {
        setDefaultPermissions({
          default_can_read: chatData.data.default_can_read ?? true,
          default_can_write: chatData.data.default_can_write ?? true,
          default_can_invite: chatData.data.default_can_invite ?? false,
          default_can_pin: chatData.data.default_can_pin ?? false,
          default_can_delete_others:
            chatData.data.default_can_delete_others ?? false,
        });
      }
    }
  }, [chatData]);

  // Refetch when opened
  useEffect(() => {
    if (opened) {
      refetch();
      setActiveTab('settings');
    }
  }, [opened, refetch]);

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const members = chatData?.data?.members || chat.members || [];
  const isGroupChat = chat.chat_type !== 'direct';

  const handleSave = async () => {
    try {
      await updateChat({
        chatId: chat.id,
        name: name !== chat.name ? name : undefined,
        description,
      }).unwrap();

      dispatch(
        chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
          const cachedChat = draft.data.find(c => c.id === chat.id);
          if (cachedChat) {
            cachedChat.name = name;
          }
        }),
      );

      onClose();
    } catch (error) {
      console.error('Failed to update chat:', error);
    }
  };

  const handleSaveDefaultPermissions = async () => {
    setIsSavingPermissions(true);
    try {
      await updateChat({
        chatId: chat.id,
        default_can_read: defaultPermissions.default_can_read,
        default_can_write: defaultPermissions.default_can_write,
        default_can_invite: defaultPermissions.default_can_invite,
        default_can_pin: defaultPermissions.default_can_pin,
        default_can_delete_others: defaultPermissions.default_can_delete_others,
      }).unwrap();

      notifications.show({
        title: t('save'),
        message: t('permissions.defaultPermissions') + ' ✓',
        color: 'green',
      });
      refetch();
    } catch (error) {
      console.error('Failed to update default permissions:', error);
      notifications.show({
        title: t('connector.error'),
        message: String(error),
        color: 'red',
      });
    } finally {
      setIsSavingPermissions(false);
    }
  };

  const handleDefaultPermissionChange = (key: string, value: boolean) => {
    setDefaultPermissions(prev => ({ ...prev, [key]: value }));
  };

  const handleRemoveMember = async (memberId: number) => {
    try {
      await removeMember({ chatId: chat.id, memberId }).unwrap();
      refetch();
    } catch (error) {
      console.error('Failed to remove member:', error);
    }
  };

  const handleSaveMemberPermissions = async (
    permissions: MemberPermissions,
  ) => {
    if (!editingMember) return;

    setIsSavingMemberPerms(true);
    try {
      // TODO: Implement updateMemberPermissions API
      notifications.show({
        title: t('save'),
        message: 'Member permissions saved (API not implemented yet)',
        color: 'blue',
      });
      setEditingMember(null);
    } catch (error) {
      console.error('Failed to update member permissions:', error);
    } finally {
      setIsSavingMemberPerms(false);
    }
  };

  const handleLeaveChat = async () => {
    try {
      await leaveChat({ chatId: chat.id }).unwrap();

      dispatch(
        chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
          draft.data = draft.data.filter(c => c.id !== chat.id);
        }),
      );

      onClose();
      onChatDeleted?.();
    } catch (error) {
      console.error('Failed to leave chat:', error);
    }
  };

  const handleDeleteChat = async () => {
    try {
      await deleteChat({ chatId: chat.id }).unwrap();

      dispatch(
        chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
          draft.data = draft.data.filter(c => c.id !== chat.id);
        }),
      );

      onClose();
      onChatDeleted?.();
    } catch (error) {
      console.error('Failed to delete chat:', error);
    }
  };

  const isBusy =
    isUpdating ||
    isRemoving ||
    isLeaving ||
    isDeleting ||
    isSavingPermissions ||
    isSavingMemberPerms;

  // Для direct чатов - простой вид без вкладок
  if (!isGroupChat) {
    return (
      <Modal
        opened={opened}
        onClose={onClose}
        title={
          <Group gap="xs">
            <IconSettings size={20} />
            <Text fw={600}>{t('chatSettings')}</Text>
          </Group>
        }
        size="md">
        {isLoading ? (
          <Stack align="center" py="xl">
            <Loader />
            <Text c="dimmed">{t('loading')}</Text>
          </Stack>
        ) : (
          <Stack gap="md">
            {/* Chat info */}
            <Group gap="md">
              <Avatar color="blue" radius="xl" size="lg">
                {getInitials(chat.name)}
              </Avatar>
              <Box style={{ flex: 1 }}>
                <Text fw={600} size="lg">
                  {chat.name}
                </Text>
                <Badge size="sm" variant="light">
                  {t('directChat')}
                </Badge>
              </Box>
            </Group>

            <Divider />

            {/* Members section */}
            <Box>
              <Group justify="space-between" mb="sm">
                <Group gap="xs">
                  <IconUsers size={18} />
                  <Text fw={500}>{t('members')}</Text>
                </Group>
                <Badge variant="light">{members.length}</Badge>
              </Group>

              <MembersList
                members={members}
                currentUserId={currentUserId}
                isGroupChat={false}
                onRemove={handleRemoveMember}
                onEditPermissions={setEditingMember}
                isBusy={isBusy}
                t={t}
              />
            </Box>

            <Divider />

            {/* Danger zone */}
            <Box>
              <Text size="sm" c="red" fw={500} mb="sm">
                {t('dangerZone')}
              </Text>
              <Button
                variant="light"
                color="red"
                leftSection={<IconTrash size={16} />}
                onClick={handleDeleteChat}
                loading={isDeleting}
                disabled={isBusy}>
                {t('deleteChat')}
              </Button>
            </Box>

            <Divider />

            {/* Action buttons */}
            <Group justify="flex-end">
              <Button variant="subtle" onClick={onClose} disabled={isBusy}>
                {t('cancel')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    );
  }

  // Для group/channel чатов - вкладки
  return (
    <>
      <Modal
        opened={opened}
        onClose={onClose}
        title={
          <Group gap="xs">
            <IconSettings size={20} />
            <Text fw={600}>{t('chatSettings')}</Text>
          </Group>
        }
        size="lg">
        {isLoading ? (
          <Stack align="center" py="xl">
            <Loader />
            <Text c="dimmed">{t('loading')}</Text>
          </Stack>
        ) : (
          <Tabs value={activeTab} onChange={setActiveTab}>
            <Tabs.List>
              <Tabs.Tab
                value="settings"
                leftSection={<IconSettings size={16} />}>
                {t('chat.tabs.main') || t('settings')}
              </Tabs.Tab>
              <Tabs.Tab value="members" leftSection={<IconUsers size={16} />}>
                {t('chat.tabs.members') || t('members')}
              </Tabs.Tab>
              <Tabs.Tab
                value="permissions"
                leftSection={<IconShield size={16} />}>
                {t('chat.tabs.permissions') || t('permissions.title')}
              </Tabs.Tab>
            </Tabs.List>

            {/* Main Settings Tab */}
            <Tabs.Panel value="settings" pt="md">
              <Stack gap="md">
                {/* Chat info */}
                <Group gap="md" mb="md">
                  <Avatar color="cyan" radius="xl" size="lg">
                    <IconMessage size={24} />
                  </Avatar>
                  <Box style={{ flex: 1 }}>
                    <Text fw={600} size="lg">
                      {chat.name}
                    </Text>
                    <Badge size="sm" variant="light">
                      {chat.chat_type === 'group'
                        ? t('groupChat')
                        : t('channel')}
                    </Badge>
                  </Box>
                </Group>

                {/* Editable fields */}
                <TextInput
                  label={t('chatName')}
                  value={name}
                  onChange={e => setName(e.currentTarget.value)}
                  placeholder={t('enterChatName')}
                  disabled={isBusy}
                />
                <Textarea
                  label={t('description')}
                  value={description}
                  onChange={e => setDescription(e.currentTarget.value)}
                  placeholder={t('enterDescription')}
                  minRows={2}
                  maxRows={4}
                  disabled={isBusy}
                />

                <Divider />

                {/* Danger zone */}
                <Box>
                  <Text size="sm" c="red" fw={500} mb="sm">
                    {t('dangerZone')}
                  </Text>
                  <Button
                    variant="light"
                    color="red"
                    leftSection={<IconUserMinus size={16} />}
                    onClick={handleLeaveChat}
                    loading={isLeaving}
                    disabled={isBusy}>
                    {t('leaveChat')}
                  </Button>
                </Box>

                <Divider />

                {/* Action buttons */}
                <Group justify="flex-end">
                  <Button variant="subtle" onClick={onClose} disabled={isBusy}>
                    {t('cancel')}
                  </Button>
                  <Button
                    onClick={handleSave}
                    loading={isUpdating}
                    disabled={isBusy}>
                    {t('save')}
                  </Button>
                </Group>
              </Stack>
            </Tabs.Panel>

            {/* Members Tab */}
            <Tabs.Panel value="members" pt="md">
              <Stack gap="md">
                <Group justify="space-between">
                  <Text fw={500}>{t('members')}</Text>
                  <Badge variant="light">{members.length}</Badge>
                </Group>

                <MembersList
                  members={members}
                  currentUserId={currentUserId}
                  isGroupChat={true}
                  onRemove={handleRemoveMember}
                  onEditPermissions={setEditingMember}
                  isBusy={isBusy}
                  t={t}
                  showSearch={true}
                />
              </Stack>
            </Tabs.Panel>

            {/* Default Permissions Tab */}
            <Tabs.Panel value="permissions" pt="md">
              <Stack gap="md">
                <Box>
                  <Text fw={500} mb="xs">
                    {t('chat.groups.defaultPermissions') ||
                      'Default Permissions'}
                  </Text>
                  <Text size="sm" c="dimmed" mb="md">
                    {t('permissions.defaultPermissions') ||
                      'Default permissions for new members'}
                  </Text>
                </Box>

                <Paper p="md" withBorder>
                  <PermissionsBlock
                    permissions={defaultPermissions}
                    onChange={handleDefaultPermissionChange}
                    disabled={isBusy}
                    showAdmin={false}
                    t={t}
                  />
                </Paper>

                <Group justify="flex-end">
                  <Button
                    onClick={handleSaveDefaultPermissions}
                    loading={isSavingPermissions}
                    disabled={isBusy}>
                    {t('save')}
                  </Button>
                </Group>
              </Stack>
            </Tabs.Panel>
          </Tabs>
        )}
      </Modal>

      {/* Member Permissions Modal */}
      <MemberPermissionsModal
        opened={editingMember !== null}
        onClose={() => setEditingMember(null)}
        member={editingMember}
        onSave={handleSaveMemberPermissions}
        isSaving={isSavingMemberPerms}
        t={t}
      />
    </>
  );
}

export default ChatSettingsModal;
