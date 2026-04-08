import { useState } from 'react';
import {
  Modal,
  TextInput,
  Button,
  Stack,
  Group,
  SegmentedControl,
  Text,
} from '@mantine/core';
import { IconUsers, IconUser } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useCreateChatMutation, Chat } from '@/services/api/chat';
import {
  ChatParticipantSelect,
  ParticipantSelection,
} from './ChatParticipantSelect';

interface NewChatModalProps {
  opened: boolean;
  onClose: () => void;
  onChatCreated: (chat: Chat) => void;
  currentUserId: number;
}

export function NewChatModal({
  opened,
  onClose,
  onChatCreated,
  currentUserId,
}: NewChatModalProps) {
  const { t } = useTranslation('chat');
  const [chatType, setChatType] = useState<'direct' | 'group'>('direct');
  const [groupName, setGroupName] = useState('');
  const [selection, setSelection] = useState<ParticipantSelection>({
    userIds: [],
    partnerIds: [],
  });

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

      onChatCreated(result.data as unknown as Chat);
      onClose();
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
      opened={opened}
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
