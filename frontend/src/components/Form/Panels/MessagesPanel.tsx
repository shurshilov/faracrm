import { useState, useRef, useEffect } from 'react';
import {
  Stack,
  Text,
  Group,
  ActionIcon,
  Box,
  Badge,
  Avatar,
  Loader,
  Button,
  TextInput,
  ScrollArea,
} from '@mantine/core';
import { IconSend, IconUser } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSearchQuery, useCreateMutation } from '@/services/api/crudApi';
import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';
import { AttachmentPreview, isImageMimetype } from '@/components/Attachment';

const PAGE_SIZE = 80;

const TYPE_COLORS: Record<string, string> = {
  comment: 'blue',
  notification: 'yellow',
  system: 'gray',
  email: 'violet',
};

interface MessagesPanelProps {
  resModel: string;
  resId: number;
}

export function MessagesPanel({ resModel, resId }: MessagesPanelProps) {
  const { t } = useTranslation(['common']);
  const session = useSelector(selectCurrentSession);
  const currentUserId = session?.user_id?.id;
  const currentUserName = session?.user_id?.name;

  const [messageText, setMessageText] = useState('');
  const [limit, setLimit] = useState(PAGE_SIZE);
  const viewportRef = useRef<HTMLDivElement>(null);

  const { data: messagesData, isLoading } = useSearchQuery({
    model: 'chat_message',
    fields: [
      'id',
      'body',
      'message_type',
      'author_user_id',
      'author_partner_id',
      'create_date',
      'is_read',
      'pinned',
      'starred',
    ],
    filter: [
      ['res_model', '=', resModel],
      ['res_id', '=', resId],
      ['is_deleted', '=', false],
    ],
    sort: 'create_date',
    order: 'desc',
    limit,
  });

  const [createMessage, { isLoading: isSending }] = useCreateMutation();
  const messages = messagesData?.data || [];
  const total = messagesData?.total || 0;
  const hasMore = total > messages.length;

  // Reversed for display (newest at bottom)
  const sortedMessages = [...messages].reverse();

  // Auto-scroll to bottom on new message
  useEffect(() => {
    if (viewportRef.current) {
      viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleSend = async () => {
    if (!messageText.trim()) return;

    try {
      await createMessage({
        model: 'chat_message',
        values: {
          body: messageText.trim(),
          message_type: 'comment',
          res_model: resModel,
          res_id: resId,
          author_user_id: currentUserId,
          create_date: new Date().toISOString(),
          write_date: new Date().toISOString(),
          is_read: false,
          is_deleted: false,
          starred: false,
          pinned: false,
          is_edited: false,
        },
      }).unwrap();

      setMessageText('');
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleLoadMore = () => {
    setLimit((prev) => prev + PAGE_SIZE);
  };

  if (isLoading && messages.length === 0) {
    return (
      <Stack align="center" py="xl">
        <Loader size="sm" />
      </Stack>
    );
  }

  return (
    <Stack gap="sm" style={{ height: '100%', minHeight: 0 }}>
      {/* Messages list (scrollable) */}
      <Box
        ref={viewportRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mantine-spacing-xs)',
        }}
      >
        {/* Load more */}
        {hasMore && (
          <Button
            variant="subtle"
            size="compact-xs"
            onClick={handleLoadMore}
            loading={isLoading}
            fullWidth
            mb="xs"
          >
            {t('common:loadMore', 'Загрузить ещё')} ({total - messages.length})
          </Button>
        )}

        {sortedMessages.length === 0 && (
          <Text size="sm" c="dimmed" ta="center" py="md">
            {t('common:noMessages', 'Нет сообщений')}
          </Text>
        )}

        {sortedMessages.map((msg: any) => (
          <MessageItem
            key={msg.id}
            message={msg}
            currentUserId={currentUserId}
          />
        ))}
      </Box>

      {/* Input */}
      <Group gap="xs" wrap="nowrap" style={{ flexShrink: 0 }}>
        <TextInput
          size="xs"
          style={{ flex: 1 }}
          value={messageText}
          onChange={(e) => setMessageText(e.currentTarget.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('common:message', 'Написать сообщение...')}
        />
        <ActionIcon
          variant="filled"
          size="md"
          onClick={handleSend}
          loading={isSending}
          disabled={!messageText.trim()}
        >
          <IconSend size={16} />
        </ActionIcon>
      </Group>
    </Stack>
  );
}

// ─── Message item ─────────────────────────────────────────────

function MessageItem({
  message,
  currentUserId,
}: {
  message: any;
  currentUserId?: number;
}) {
  const authorName =
    message.author_user_id?.name ||
    message.author_partner_id?.name ||
    '';
  const isOwn =
    message.author_user_id?.id === currentUserId ||
    (typeof message.author_user_id === 'number' &&
      message.author_user_id === currentUserId);
  const typeColor = TYPE_COLORS[message.message_type] || 'gray';

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const time = d.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
    if (isToday) return time;
    return `${d.toLocaleDateString()} ${time}`;
  };

  const getInitials = (name: string) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const stripHtml = (html: string) => {
    if (!html) return '';
    return html.replace(/<[^>]*>/g, '');
  };

  return (
    <Group
      gap="xs"
      wrap="nowrap"
      align="flex-start"
      style={{
        flexDirection: isOwn ? 'row-reverse' : 'row',
      }}
    >
      <Avatar size="sm" radius="xl" color={isOwn ? 'blue' : 'gray'}>
        {getInitials(authorName)}
      </Avatar>

      <Box
        p="xs"
        style={{
          borderRadius: 'var(--mantine-radius-md)',
          background: isOwn
            ? 'var(--mantine-color-blue-0)'
            : 'var(--mantine-color-gray-0)',
          maxWidth: '85%',
          minWidth: 0,
        }}
      >
        <Stack gap={2}>
          <Group justify="space-between" gap="xs">
            <Text size="xs" fw={500} c={isOwn ? 'blue' : undefined}>
              {authorName}
            </Text>
            {message.message_type !== 'comment' && (
              <Badge size="xs" color={typeColor} variant="light">
                {message.message_type}
              </Badge>
            )}
          </Group>

          <Text size="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {stripHtml(message.body || '')}
          </Text>

          <Text size="xs" c="dimmed" ta={isOwn ? 'left' : 'right'}>
            {formatDate(message.create_date)}
          </Text>
        </Stack>
      </Box>
    </Group>
  );
}
