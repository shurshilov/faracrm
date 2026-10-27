import { useEffect, useState } from 'react';
import {
  Modal,
  TextInput,
  Button,
  Stack,
  Group,
  SegmentedControl,
} from '@mantine/core';
import { IconUsers, IconUser } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import {
  useCreateChatMutation,
  useResolveContactChatQuery,
  Chat,
} from '@/services/api/chat';
import {
  ChatParticipantSelect,
  ParticipantSelection,
} from './ChatParticipantSelect';
import type { ContactSelection } from './ContactMultiSelect';

interface NewChatModalProps {
  opened: boolean;
  onClose: () => void;
  onChatCreated: (chat: Chat) => void;
  currentUserId: number;
  /**
   * Собеседник со значка контакта (ChatPage, ?new_contact): клиент → группа
   * с именем партнёра, сотрудник → личный. Создаёт пользователь кнопкой.
   */
  contactId?: number | null;
}

export function NewChatModal({
  opened,
  onClose,
  onChatCreated,
  currentUserId,
  contactId,
}: NewChatModalProps) {
  const { t } = useTranslation('chat');
  const [chatType, setChatType] = useState<'direct' | 'group'>('direct');
  const [groupName, setGroupName] = useState('');
  const [selection, setSelection] = useState<ParticipantSelection>({
    userIds: [],
    partnerIds: [],
  });

  // Собеседник по контакту. Пока он не загружен, окно не открываем: выбор
  // участников монтируется уже с ним (initialContacts). currentData — ответ
  // именно для этого контакта.
  const { currentData: contact } = useResolveContactChatQuery(
    { contactId: contactId || 0 },
    { skip: !contactId },
  );
  const peer =
    contact && (contact.partner_id || contact.user_id) ? contact : null;
  useEffect(() => {
    if (!opened || !peer) return;
    const partner = peer.partner_id;
    setChatType(partner ? 'group' : 'direct');
    setGroupName(partner ? peer.name || '' : '');
    setSelection(
      partner
        ? { userIds: [], partnerIds: [partner] }
        : { userIds: [peer.user_id as number], partnerIds: [] },
    );
  }, [opened, peer]);
  // Клиент — во вкладке «Контакты», сотрудник — в «Пользователи».
  const initialContacts: ContactSelection[] =
    peer?.partner_id && contactId
      ? [
          {
            contactId,
            type: 'partner',
            sourceId: peer.partner_id,
            label: peer.name || '',
          },
        ]
      : [];
  const initialUsers = peer?.user_id
    ? [{ id: peer.user_id, name: peer.name || '' }]
    : [];

  const [createChat, { isLoading: isCreating }] = useCreateChatMutation();

  const handleCreate = async () => {
    if (selection.userIds.length + selection.partnerIds.length === 0) return;

    try {
      const result = await createChat({
        name: chatType === 'group' ? groupName : undefined,
        chat_type: chatType,
        user_ids: selection.userIds,
        partner_ids: selection.partnerIds,
      }).unwrap();

      // Reset form
      setSelection({ userIds: [], partnerIds: [] });
      setGroupName('');
      setChatType('direct');

      // Окно закрывает родитель — вместе с переходом к созданному чату.
      onChatCreated(result.data as unknown as Chat);
    } catch (error) {
      console.error('Failed to create chat:', error);
    }
  };

  const totalSelected =
    selection.userIds.length + selection.partnerIds.length;
  const canCreate =
    totalSelected > 0 && (chatType !== 'group' || groupName.trim().length > 0);

  const handleClose = () => {
    setSelection({ userIds: [], partnerIds: [] });
    setGroupName('');
    setChatType('direct');
    onClose();
  };

  return (
    <Modal
      opened={opened && (!contactId || !!contact)}
      onClose={handleClose}
      title={t('createNewChat')}
      size="md">
      <Stack gap="md">
        {/* Chat type selector */}
        <SegmentedControl
          value={chatType}
          onChange={value => {
            setChatType(value as 'direct' | 'group');
            setSelection({ userIds: [], partnerIds: [] });
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

        {/* Participant selection (users/contacts switcher) */}
        <ChatParticipantSelect
          value={selection}
          onChange={setSelection}
          excludeUserIds={[currentUserId]}
          maxValues={chatType === 'direct' ? 1 : undefined}
          initialContacts={initialContacts}
          initialUsers={initialUsers}
        />

        {/* Action buttons */}
        <Group justify="flex-end" mt="md">
          <Button variant="subtle" onClick={handleClose}>
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
