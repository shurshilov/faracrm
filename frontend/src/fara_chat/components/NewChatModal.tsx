import { useState, useEffect } from 'react';
import {
  Modal,
  TextInput,
  Button,
  Stack,
  Group,
  SegmentedControl,
  MultiSelect,
  Text,
  Avatar,
  Box,
  Loader,
  Badge,
} from '@mantine/core';
import {
  IconSearch,
  IconUsers,
  IconUser,
  IconAddressBook,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useCreateChatMutation, Chat } from '@/services/api/chat';
import { useRouteUsersSearchPostMutation } from '@/services/api/users';
import { useSearchQuery } from '@/services/api/crudApi';

interface NewChatModalProps {
  opened: boolean;
  onClose: () => void;
  onChatCreated: (chat: Chat) => void;
  currentUserId: number;
}

// Тип для результата поиска (пользователь или контакт)
interface SearchResult {
  id: string;
  label: string;
  type: 'user' | 'partner';
  sourceId: number; // user_id или partner_id
  contactValue?: string; // значение контакта (телефон, email)
  contactType?: string;
}

export function NewChatModal({
  opened,
  onClose,
  onChatCreated,
  currentUserId,
}: NewChatModalProps) {
  const { t } = useTranslation('chat');
  const [chatType, setChatType] = useState<'direct' | 'group'>('direct');
  const [searchMode, setSearchMode] = useState<'users' | 'contacts'>('users');
  const [groupName, setGroupName] = useState('');
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  const [createChat, { isLoading: isCreating }] = useCreateChatMutation();
  const [searchUsers, { data: usersData, isLoading: isSearchingUsers }] =
    useRouteUsersSearchPostMutation();

  // Поиск по контактам
  const { data: contactsData, isFetching: isSearchingContacts } =
    useSearchQuery(
      {
        model: 'contact',
        fields: ['id', 'name', 'contact_type_id', 'partner_id', 'user_id'],
        filter:
          searchQuery.length > 0 ? [['name', 'ilike', `%${searchQuery}%`]] : [],
        limit: 50,
      },
      {
        skip: searchMode !== 'contacts' || !opened,
        refetchOnMountOrArgChange: true,
      },
    );

  // Load users when modal opens
  useEffect(() => {
    if (opened && searchMode === 'users') {
      loadUsers('');
    }
  }, [opened, searchMode]);

  // Load users function
  const loadUsers = async (query: string) => {
    const filter: any[] = [];
    if (query.length > 0) {
      filter.push(['name', 'ilike', `%${query}%`]);
    }

    await searchUsers({
      userSearchInput: {
        fields: ['id', 'name'],
        filter,
        limit: 50,
      },
    });
  };

  // Search when query changes
  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (searchMode === 'users') {
      await loadUsers(query);
    }
  };

  // Transform users to select options
  const userOptions: SearchResult[] =
    usersData?.data
      ?.filter(u => Number(u.id) !== Number(currentUserId))
      .map(user => ({
        id: `user-${user.id}`,
        label: user.name || `User ${user.id}`,
        type: 'user' as const,
        sourceId: Number(user.id),
      })) || [];

  // Transform contacts to select options
  const contactOptions: SearchResult[] =
    contactsData?.data
      ?.filter((c: any) => {
        // Исключаем контакты текущего пользователя
        if (c.user_id?.id === currentUserId) return false;
        // Должен быть либо partner_id, либо user_id
        return c.partner_id?.id || c.user_id?.id;
      })
      .map((contact: any) => {
        const isPartner = !!contact.partner_id?.id;
        const ownerName = isPartner
          ? contact.partner_id?.name
          : contact.user_id?.name;

        return {
          id: `contact-${contact.id}`,
          label: `${ownerName} (${contact.name})`,
          type: isPartner ? ('partner' as const) : ('user' as const),
          sourceId: isPartner ? contact.partner_id.id : contact.user_id.id,
          contactValue: contact.name,
          contactType: contact.contact_type_id?.name,
        };
      }) || [];

  // Объединяем опции в зависимости от режима
  const selectOptions = searchMode === 'users' ? userOptions : contactOptions;
  const isSearching =
    searchMode === 'users' ? isSearchingUsers : isSearchingContacts;

  // Преобразуем для MultiSelect
  const multiSelectData = selectOptions.map(opt => ({
    value: opt.id,
    label: opt.label,
  }));

  const handleCreate = async () => {
    if (selectedItems.length === 0) return;

    // Парсим выбранные элементы
    const selectedResults = selectedItems
      .map(id => {
        return selectOptions.find(opt => opt.id === id);
      })
      .filter(Boolean) as SearchResult[];

    // Собираем user_ids и partner_ids
    const userIds: number[] = [];
    const partnerIds: number[] = [];

    for (const item of selectedResults) {
      if (item.type === 'user') {
        userIds.push(item.sourceId);
      } else {
        partnerIds.push(item.sourceId);
      }
    }

    try {
      const result = await createChat({
        name: chatType === 'group' ? groupName : undefined,
        chat_type: chatType,
        user_ids: userIds,
        partner_ids: partnerIds,
      }).unwrap();

      // Reset form
      setSelectedItems([]);
      setGroupName('');
      setSearchQuery('');
      setChatType('direct');
      setSearchMode('users');

      onChatCreated(result.data as unknown as Chat);
      onClose();
    } catch (error) {
      console.error('Failed to create chat:', error);
    }
  };

  const canCreate =
    selectedItems.length > 0 &&
    (chatType === 'direct'
      ? selectedItems.length === 1
      : groupName.trim().length > 0);

  return (
    <Modal opened={opened} onClose={onClose} title={t('newChat')} size="md">
      <Stack gap="md">
        {/* Chat type selector */}
        <SegmentedControl
          value={chatType}
          onChange={value => {
            setChatType(value as 'direct' | 'group');
            setSelectedItems([]);
          }}
          data={[
            {
              value: 'direct',
              label: (
                <Group gap="xs" justify="center">
                  <IconUser size={16} />
                  <span>{t('directChat')}</span>
                </Group>
              ),
            },
            {
              value: 'group',
              label: (
                <Group gap="xs" justify="center">
                  <IconUsers size={16} />
                  <span>{t('groupChat')}</span>
                </Group>
              ),
            },
          ]}
          fullWidth
        />

        {/* Search mode selector */}
        <SegmentedControl
          value={searchMode}
          onChange={value => {
            setSearchMode(value as 'users' | 'contacts');
            setSelectedItems([]);
            setSearchQuery('');
          }}
          data={[
            {
              value: 'users',
              label: (
                <Group gap="xs" justify="center">
                  <IconUser size={14} />
                  <span>Пользователи</span>
                </Group>
              ),
            },
            {
              value: 'contacts',
              label: (
                <Group gap="xs" justify="center">
                  <IconAddressBook size={14} />
                  <span>Контакты</span>
                </Group>
              ),
            },
          ]}
          fullWidth
          size="xs"
        />

        {/* Group name input (only for group chats) */}
        {chatType === 'group' && (
          <TextInput
            label={t('groupName')}
            placeholder={t('enterGroupName')}
            value={groupName}
            onChange={e => setGroupName(e.currentTarget.value)}
            required
          />
        )}

        {/* User/Contact search and selection */}
        <MultiSelect
          label={
            chatType === 'direct'
              ? searchMode === 'users'
                ? t('selectUser')
                : 'Выберите контакт'
              : t('selectMembers')
          }
          placeholder={
            searchMode === 'users'
              ? t('searchUsers')
              : 'Поиск по телефону, email...'
          }
          searchable
          searchValue={searchQuery}
          onSearchChange={handleSearch}
          data={multiSelectData}
          value={selectedItems}
          onChange={setSelectedItems}
          maxValues={chatType === 'direct' ? 1 : undefined}
          leftSection={
            isSearching ? <Loader size="xs" /> : <IconSearch size={16} />
          }
          nothingFoundMessage={
            isSearching
              ? t('searching')
              : searchMode === 'users'
                ? t('noUsersFound')
                : 'Контакты не найдены'
          }
          clearable
        />

        {/* Helper text */}
        <Text size="sm" c="dimmed">
          {searchMode === 'contacts'
            ? 'Поиск по номеру телефона, email или имени контакта'
            : chatType === 'direct'
              ? t('directChatHint')
              : t('groupChatHint')}
        </Text>

        {/* Action buttons */}
        <Group justify="flex-end" mt="md">
          <Button variant="subtle" onClick={onClose}>
            {t('cancel')}
          </Button>
          <Button
            onClick={handleCreate}
            loading={isCreating}
            disabled={!canCreate}>
            {t('create')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default NewChatModal;
