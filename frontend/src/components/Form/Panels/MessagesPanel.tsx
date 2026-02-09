/**
 * MessagesPanel — панель сообщений привязанных к записи.
 *
 * При открытии формы: GET /records/{model}/{id}/chat → find (без создания)
 * Если чат есть → ChatMessages + ChatInput
 * Если нет → поле ввода, при первом сообщении создаёт чат
 *
 * Follow/Unfollow: POST create → становишься мембером
 * Leave: POST /chats/{id}/leave → выходишь из чата
 */

import { useState, useCallback } from 'react';
import {
  Text,
  Loader,
  Center,
  Group,
  ActionIcon,
  TextInput,
  Button,
  Tooltip,
  Avatar,
} from '@mantine/core';
import { IconSend, IconBell, IconBellOff } from '@tabler/icons-react';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { selectCurrentSession } from '@/slices/authSlice';
import {
  useFindRecordChatQuery,
  useGetOrCreateRecordChatMutation,
  useGetChatQuery,
  useSendMessageMutation,
  useLeaveChatMutation,
} from '@/services/api/chat';
import { ChatMessages } from '@/fara_chat/components/ChatMessages';
import { ChatInput } from '@/fara_chat/components/ChatInput';

interface MessagesPanelProps {
  resModel: string;
  resId: number;
}

export function MessagesPanel({ resModel, resId }: MessagesPanelProps) {
  const { t } = useTranslation('chat');
  const session = useSelector(selectCurrentSession);
  const currentUserId = session?.user_id?.id || 0;
  const currentUserName = session?.user_id?.name || '';

  // Step 1: Find existing record chat (no creation)
  const {
    data: findData,
    isLoading: isFinding,
    refetch: refetchFind,
  } = useFindRecordChatQuery(
    { resModel, resId },
    { skip: !resModel || !resId },
  );

  const [getOrCreateChat] = useGetOrCreateRecordChatMutation();
  const [sendMessage] = useSendMessageMutation();
  const [leaveChat] = useLeaveChatMutation();

  const [messageText, setMessageText] = useState('');
  const [isSending, setIsSending] = useState(false);

  const chatId = findData?.chat_id || undefined;

  // Step 2: Load full Chat object (only if chat exists)
  const { data: chatData, isLoading: isChatLoading } = useGetChatQuery(
    { chatId: chatId || 0 },
    { skip: !chatId },
  );

  const chat = chatData?.data;

  // Check if current user is a member
  const isMember = chat?.members?.some(
    (m) => m.user_id === currentUserId && m.is_active !== false,
  );

  // Handle Follow — get_or_create chat (user becomes member)
  const handleFollow = useCallback(async () => {
    try {
      await getOrCreateChat({ resModel, resId }).unwrap();
      refetchFind();
    } catch (error) {
      console.error('Failed to follow:', error);
    }
  }, [getOrCreateChat, resModel, resId, refetchFind]);

  // Handle Unfollow — leave chat
  const handleUnfollow = useCallback(async () => {
    if (!chatId) return;
    try {
      await leaveChat({ chatId }).unwrap();
      refetchFind();
    } catch (error) {
      console.error('Failed to unfollow:', error);
    }
  }, [leaveChat, chatId, refetchFind]);

  // Handle first message — creates chat + sends message
  const handleFirstMessage = useCallback(async () => {
    if (!messageText.trim()) return;
    setIsSending(true);

    try {
      const result = await getOrCreateChat({ resModel, resId }).unwrap();
      const newChatId = result.chat_id;

      await sendMessage({
        chatId: newChatId,
        body: messageText.trim(),
        message_type: 'comment',
      }).unwrap();

      setMessageText('');
      refetchFind();
    } catch (error) {
      console.error('Failed to send first message:', error);
    } finally {
      setIsSending(false);
    }
  }, [messageText, getOrCreateChat, sendMessage, resModel, resId, refetchFind]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleFirstMessage();
    }
  };

  if (isFinding) {
    return (
      <Center py="xl" style={{ flex: 1 }}>
        <Loader size="sm" />
      </Center>
    );
  }

  // Chat exists — render full chat UI
  if (chatId && chat) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0%', minHeight: 0 }}>
        {/* Follow/Unfollow + followers */}
        <FollowBar
          isMember={!!isMember}
          members={chat.members}
          currentUserId={currentUserId}
          onFollow={handleFollow}
          onUnfollow={handleUnfollow}
        />

        {/* Messages */}
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <ChatMessages
            chat={chat}
            currentUserId={currentUserId}
          />
        </div>

        {/* Input */}
        <div style={{ flexShrink: 0 }}>
          <ChatInput
            chatId={chatId}
            currentUserId={currentUserId}
            currentUserName={currentUserName}
          />
        </div>
      </div>
    );
  }

  // Chat loading
  if (chatId && isChatLoading) {
    return (
      <Center py="xl" style={{ flex: 1 }}>
        <Loader size="sm" />
      </Center>
    );
  }

  // No chat yet — empty state with input
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0%', minHeight: 0 }}>
      <Center style={{ flex: 1 }}>
        <Text size="sm" c="dimmed">
          Нет сообщений
        </Text>
      </Center>
      <Group gap="xs" wrap="nowrap" p="xs" style={{ flexShrink: 0 }}>
        <TextInput
          size="xs"
          style={{ flex: 1 }}
          value={messageText}
          onChange={(e) => setMessageText(e.currentTarget.value)}
          onKeyDown={handleKeyDown}
          placeholder="Написать сообщение..."
          disabled={isSending}
        />
        <ActionIcon
          variant="filled"
          size="md"
          onClick={handleFirstMessage}
          loading={isSending}
          disabled={!messageText.trim()}
        >
          <IconSend size={16} />
        </ActionIcon>
      </Group>
    </div>
  );
}

// ── Follow bar ───────────────────────────────────────────────

interface FollowBarProps {
  isMember: boolean;
  members: Array<{ user_id?: number; name?: string; is_active?: boolean }>;
  currentUserId: number;
  onFollow: () => void;
  onUnfollow: () => void;
}

function FollowBar({ isMember, members, currentUserId, onFollow, onUnfollow }: FollowBarProps) {
  const activeMembers = members?.filter((m) => m.is_active !== false) || [];

  return (
    <Group
      justify="space-between"
      px="xs"
      py={4}
      style={{
        borderBottom: '1px solid var(--mantine-color-default-border)',
        flexShrink: 0,
      }}
    >
      {/* Followers avatars */}
      <Group gap={4}>
        <Avatar.Group spacing="xs">
          {activeMembers.slice(0, 5).map((m, i) => (
            <Tooltip key={i} label={m.name || 'User'} withArrow>
              <Avatar size="xs" radius="xl" color="blue">
                {(m.name || '?').slice(0, 1).toUpperCase()}
              </Avatar>
            </Tooltip>
          ))}
          {activeMembers.length > 5 && (
            <Avatar size="xs" radius="xl" color="gray">
              +{activeMembers.length - 5}
            </Avatar>
          )}
        </Avatar.Group>
      </Group>

      {/* Follow/Unfollow button */}
      {isMember ? (
        <Tooltip label="Отписаться от уведомлений" withArrow>
          <ActionIcon
            variant="subtle"
            size="sm"
            color="gray"
            onClick={onUnfollow}
          >
            <IconBellOff size={14} />
          </ActionIcon>
        </Tooltip>
      ) : (
        <Button
          variant="subtle"
          size="compact-xs"
          leftSection={<IconBell size={14} />}
          onClick={onFollow}
        >
          Подписаться
        </Button>
      )}
    </Group>
  );
}

export default MessagesPanel;
