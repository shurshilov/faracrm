import { useEffect, useRef, useState } from 'react';
import {
  Box,
  Text,
  Stack,
  Group,
  Avatar,
  Paper,
  ScrollArea,
  Skeleton,
  ActionIcon,
  SimpleGrid,
  Modal,
  TextInput,
  Button,
  Tooltip,
} from '@mantine/core';
import {
  IconArrowDown,
  IconCopy,
  IconEdit,
  IconTrash,
  IconPin,
  IconPinFilled,
  IconEyeOff,
  IconArrowForward,
  IconDownload,
  IconMoodSmile,
  IconCheck,
  IconChecks,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import {
  useGetChatMessagesQuery,
  useDeleteMessageMutation,
  useEditMessageMutation,
  usePinMessageMutation,
  useMarkMessageUnreadMutation,
  useForwardMessageMutation,
  useAddReactionMutation,
  useGetChatsQuery,
  chatApi,
  ChatMessage,
  Chat,
} from '@/services/api/chat';
import {
  AttachmentPreview,
  ImageGalleryModal,
  isImageMimetype,
} from '@/components/Attachment';
import type { GalleryItem } from '@/components/Attachment';
import { useDispatch } from 'react-redux';
import styles from './ChatMessages.module.css';
import { EmailMessageContent } from './EmailMessageContent';

const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🎉', '🔥', '👏'];

interface ChatMessagesProps {
  chat: Chat;
  currentUserId: number;
  newMessages?: ChatMessage[];
  onChatUpdate?: (updatedChat: Partial<Chat>) => void;
  onMarkUnread?: () => void;
}

export function ChatMessages({
  chat,
  currentUserId,
  newMessages = [],
  onChatUpdate,
  onMarkUnread,
}: ChatMessagesProps) {
  const { t } = useTranslation('chat');
  const dispatch = useDispatch();
  const viewportRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [galleryOpened, setGalleryOpened] = useState(false);
  const [galleryItems, setGalleryItems] = useState<GalleryItem[]>([]);
  const [galleryIndex, setGalleryIndex] = useState(0);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    message: ChatMessage;
  } | null>(null);
  const [editModal, setEditModal] = useState<{
    opened: boolean;
    message: ChatMessage | null;
  }>({ opened: false, message: null });
  const [editText, setEditText] = useState('');
  const [forwardModal, setForwardModal] = useState<{
    opened: boolean;
    message: ChatMessage | null;
  }>({ opened: false, message: null });
  const [reactionPicker, setReactionPicker] = useState<{
    messageId: number;
    opened: boolean;
  } | null>(null);

  const { data, isLoading, error, refetch } = useGetChatMessagesQuery({
    chatId: chat.id,
    limit: 50,
  });
  const { data: chatsData } = useGetChatsQuery({ limit: 100 });

  const [deleteMessage] = useDeleteMessageMutation();
  const [editMessage] = useEditMessageMutation();
  const [pinMessage] = usePinMessageMutation();
  const [markUnread] = useMarkMessageUnreadMutation();
  const [forwardMessage] = useForwardMessageMutation();
  const [addReaction] = useAddReactionMutation();

  const fetchedMessages = data?.data || [];
  const fetchedIds = new Set(fetchedMessages.map(m => m.id));
  const uniqueNewMessages = newMessages.filter(m => !fetchedIds.has(m.id));
  const allMessages = [...fetchedMessages, ...uniqueNewMessages].sort(
    (a, b) => {
      const dateA = a.create_date ? new Date(a.create_date).getTime() : 0;
      const dateB = b.create_date ? new Date(b.create_date).getTime() : 0;
      return dateA - dateB;
    },
  );

  useEffect(() => {
    if (isAtBottom && viewportRef.current) {
      viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
    }
  }, [allMessages.length, isAtBottom]);

  useEffect(() => {
    if (viewportRef.current && !isLoading) {
      setTimeout(() => {
        if (viewportRef.current) {
          viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
        }
      }, 0);
    }
  }, [isLoading, chat.id]);

  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    if (contextMenu) {
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [contextMenu]);

  const handleScroll = (position: { x: number; y: number }) => {
    if (viewportRef.current) {
      const { scrollHeight, clientHeight } = viewportRef.current;
      const atBottom = scrollHeight - position.y - clientHeight < 100;
      setIsAtBottom(atBottom);
      setShowScrollButton(!atBottom);
    }
  };

  const scrollToBottom = () => {
    if (viewportRef.current) {
      viewportRef.current.scrollTo({
        top: viewportRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  };

  const formatTime = (dateString?: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return t('today');
    if (date.toDateString() === yesterday.toDateString()) return t('yesterday');
    return date.toLocaleDateString([], {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const shouldShowDate = (message: ChatMessage, index: number) => {
    if (index === 0) return true;
    const prevMessage = allMessages[index - 1];
    if (!message.create_date || !prevMessage.create_date) return false;
    return (
      new Date(message.create_date).toDateString() !==
      new Date(prevMessage.create_date).toDateString()
    );
  };

  const isOwnMessage = (message: ChatMessage) =>
    message.author?.type === 'user' &&
    Number(message.author?.id) === Number(currentUserId);

  const handleOpenGallery = (message: ChatMessage, attachmentIndex: number) => {
    const imageAttachments =
      message.attachments?.filter(a => isImageMimetype(a.mimetype)) || [];
    if (imageAttachments.length === 0) return;
    setGalleryItems(
      imageAttachments.map(a => ({
        id: a.id,
        name: a.name,
        mimetype: a.mimetype,
        checksum: a.checksum,
      })),
    );
    setGalleryIndex(attachmentIndex);
    setGalleryOpened(true);
  };

  const handleDownloadAttachment = (attachmentId: number) => {
    window.open(`/api/attachments/${attachmentId}`, '_blank');
  };

  const handleContextMenu = (e: React.MouseEvent, message: ChatMessage) => {
    e.preventDefault();
    const menuWidth = 200,
      menuHeight = 350;
    let x = e.clientX,
      y = e.clientY;
    if (x + menuWidth > window.innerWidth)
      x = window.innerWidth - menuWidth - 10;
    if (y + menuHeight > window.innerHeight)
      y = window.innerHeight - menuHeight - 10;
    if (x < 10) x = 10;
    if (y < 10) y = 10;
    setContextMenu({ x, y, message });
  };

  const handleCopyText = () => {
    if (contextMenu?.message.body) {
      navigator.clipboard.writeText(contextMenu.message.body);
      notifications.show({ message: t('textCopied'), color: 'green' });
    }
    setContextMenu(null);
  };

  const handleDownloadFile = () => {
    if (contextMenu?.message.attachments?.length) {
      contextMenu.message.attachments.forEach(att =>
        handleDownloadAttachment(att.id),
      );
    }
    setContextMenu(null);
  };

  const handleEditClick = () => {
    if (contextMenu?.message) {
      setEditText(contextMenu.message.body || '');
      setEditModal({ opened: true, message: contextMenu.message });
    }
    setContextMenu(null);
  };

  const handleEditSave = async () => {
    if (!editModal.message) return;
    try {
      await editMessage({
        chatId: chat.id,
        messageId: editModal.message.id,
        body: editText,
      }).unwrap();
      notifications.show({ message: t('messageEdited'), color: 'green' });
      refetch();
    } catch {
      notifications.show({ message: t('errorEditingMessage'), color: 'red' });
    }
    setEditModal({ opened: false, message: null });
  };

  const handleDelete = async () => {
    if (!contextMenu?.message) return;
    try {
      await deleteMessage({
        chatId: chat.id,
        messageId: contextMenu.message.id,
      }).unwrap();
      notifications.show({ message: t('messageDeleted'), color: 'green' });
      refetch();
    } catch {
      notifications.show({ message: t('errorDeletingMessage'), color: 'red' });
    }
    setContextMenu(null);
  };

  const handlePin = async () => {
    if (!contextMenu?.message) return;
    try {
      await pinMessage({
        chatId: chat.id,
        messageId: contextMenu.message.id,
        pinned: !contextMenu.message.pinned,
      }).unwrap();
      notifications.show({
        message: contextMenu.message.pinned
          ? t('messageUnpinned')
          : t('messagePinned'),
        color: 'green',
      });
      refetch();
    } catch {
      notifications.show({ message: t('errorPinningMessage'), color: 'red' });
    }
    setContextMenu(null);
  };

  const handleMarkUnread = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onMarkUnread?.();
    if (!contextMenu?.message) return;
    try {
      const result = await markUnread({
        chatId: chat.id,
        messageId: contextMenu.message.id,
      }).unwrap();
      // Обновляем кеш чатов напрямую
      dispatch(
        chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
          const cachedChat = draft.data.find((c: Chat) => c.id === chat.id);
          if (cachedChat) {
            cachedChat.unread_count = result.unread_count;
          }
        }),
      );
      // Обновляем локальный selectedChat через callback
      onChatUpdate?.({ unread_count: result.unread_count });
      notifications.show({ message: t('markedAsUnread'), color: 'green' });
    } catch {
      notifications.show({ message: t('errorMarkingUnread'), color: 'red' });
    }
    setContextMenu(null);
  };

  const handleForwardClick = () => {
    if (contextMenu?.message)
      setForwardModal({ opened: true, message: contextMenu.message });
    setContextMenu(null);
  };

  const handleForward = async (targetChatId: number) => {
    if (!forwardModal.message) return;
    try {
      await forwardMessage({
        chatId: chat.id,
        messageId: forwardModal.message.id,
        targetChatId,
      }).unwrap();
      notifications.show({ message: t('messageForwarded'), color: 'green' });
    } catch {
      notifications.show({
        message: t('errorForwardingMessage'),
        color: 'red',
      });
    }
    setForwardModal({ opened: false, message: null });
  };

  const handleAddReaction = async (messageId: number, emoji: string) => {
    try {
      await addReaction({ chatId: chat.id, messageId, emoji }).unwrap();
      await refetch();
    } catch {
      notifications.show({ message: t('errorAddingReaction'), color: 'red' });
    }
    setReactionPicker(null);
    setContextMenu(null);
  };

  const handleReactionClick = () => {
    if (contextMenu?.message)
      setReactionPicker({ messageId: contextMenu.message.id, opened: true });
    setContextMenu(null);
  };

  const hasAttachments = (message: ChatMessage) =>
    message.attachments && message.attachments.length > 0;
  const hasText = (message: ChatMessage) =>
    message.body && message.body.trim().length > 0;

  if (error) {
    return (
      <Box className={styles.container}>
        <Text c="red" ta="center" p="md">
          {t('errorLoadingMessages')}
        </Text>
      </Box>
    );
  }

  return (
    <Box className={styles.container}>
      <ScrollArea
        viewportRef={viewportRef}
        className={styles.messageList}
        onScrollPositionChange={handleScroll}>
        {isLoading ? (
          <Stack p="md" gap="md">
            {[1, 2, 3, 4, 5].map(i => (
              <Group key={i} justify={i % 2 === 0 ? 'flex-end' : 'flex-start'}>
                <Skeleton height={60} width="60%" radius="md" />
              </Group>
            ))}
          </Stack>
        ) : allMessages.length === 0 ? (
          <Box className={styles.emptyState}>
            <Text c="dimmed" ta="center">
              {t('noMessagesYet')}
            </Text>
            <Text size="sm" c="dimmed" ta="center">
              {t('startConversation')}
            </Text>
          </Box>
        ) : (
          <Stack gap="xs" p="md">
            {allMessages.map((message, index) => (
              <Box key={message.id}>
                {shouldShowDate(message, index) && (
                  <Box className={styles.dateSeparator}>
                    <Text size="xs" c="dimmed">
                      {formatDate(message.create_date)}
                    </Text>
                  </Box>
                )}
                <Group
                  justify={isOwnMessage(message) ? 'flex-end' : 'flex-start'}
                  align="flex-start"
                  gap="xs"
                  wrap="nowrap">
                  {!isOwnMessage(message) && (
                    <Avatar color="blue" radius="xl" size="sm" mt={4}>
                      {getInitials(message.author?.name)}
                    </Avatar>
                  )}
                  <Stack
                    gap={4}
                    style={{ maxWidth: '70%' }}
                    align={isOwnMessage(message) ? 'flex-end' : 'flex-start'}>
                    {!isOwnMessage(message) && chat.chat_type !== 'direct' && (
                      <Text size="xs" fw={500} c="blue">
                        {message.author?.name}
                      </Text>
                    )}

                    {/* Вложения - отдельный блок */}
                    {message.attachments && message.attachments.length > 0 && (
                      <Box
                        onContextMenu={e => handleContextMenu(e, message)}
                        className={styles.attachmentsContainer}
                        style={{ position: 'relative' }}>
                        {/* Pin иконка на вложениях только если нет текста */}
                        {message.pinned && !message.body?.trim() && (
                          <Box className={styles.pinnedIcon}>
                            <IconPinFilled
                              size={14}
                              color="var(--mantine-color-orange-6)"
                            />
                          </Box>
                        )}
                        <SimpleGrid
                          cols={message.attachments.length === 1 ? 1 : 2}
                          spacing={4}>
                          {message.attachments.map((att, attIndex) => (
                            <AttachmentPreview
                              key={att.id}
                              attachment={{
                                id: att.id,
                                name: att.name,
                                mimetype: att.mimetype,
                                size: att.size,
                                is_voice: att.is_voice,
                              }}
                              onClick={
                                isImageMimetype(att.mimetype)
                                  ? () => handleOpenGallery(message, attIndex)
                                  : undefined
                              }
                              onDownload={() =>
                                handleDownloadAttachment(att.id)
                              }
                              showPreview={att.show_preview !== false}
                              previewSize={
                                message.attachments!.length === 1 ? 250 : 120
                              }
                              showActions={false}
                            />
                          ))}
                        </SimpleGrid>
                      </Box>
                    )}

                    {/* Текстовое сообщение - отдельный bubble */}
                    {message.body?.trim() && (
                      <Paper
                        className={`${styles.messageBubble} ${isOwnMessage(message) ? styles.own : styles.other} ${message.message_type === 'email' ? styles.emailBubble : ''}`}
                        onContextMenu={e => handleContextMenu(e, message)}
                        style={{ position: 'relative' }}>
                        {/* Pin иконка на текстовом bubble */}
                        {message.pinned && (
                          <Box className={styles.pinnedIcon}>
                            <IconPinFilled
                              size={14}
                              color="var(--mantine-color-orange-6)"
                            />
                          </Box>
                        )}
                        {/* Email сообщения отображаем через EmailMessageContent */}
                        {message.message_type === 'email' ? (
                          <EmailMessageContent body={message.body} />
                        ) : (
                          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                            {message.body}
                          </Text>
                        )}
                        {/* Реакции и время в одной строке */}
                        <Group
                          justify="space-between"
                          gap={8}
                          mt={4}
                          wrap="nowrap">
                          {/* Реакции слева */}
                          {message.reactions && message.reactions.length > 0 ? (
                            <Group gap={4} wrap="wrap" style={{ flex: 1 }}>
                              {message.reactions.map(reaction => (
                                <Tooltip
                                  key={reaction.emoji}
                                  label={reaction.users
                                    .map(u => u.user_name)
                                    .join(', ')}
                                  position="top"
                                  withArrow>
                                  <Box
                                    className={`${styles.reactionBadge} ${isOwnMessage(message) ? styles.reactionBadgeOwn : ''}`}
                                    onClick={() =>
                                      handleAddReaction(
                                        message.id,
                                        reaction.emoji,
                                      )
                                    }>
                                    <span>{reaction.emoji}</span>
                                    <Text
                                      size="xs"
                                      span
                                      c={
                                        isOwnMessage(message)
                                          ? 'white'
                                          : undefined
                                      }>
                                      {reaction.count}
                                    </Text>
                                  </Box>
                                </Tooltip>
                              ))}
                            </Group>
                          ) : (
                            <Box />
                          )}
                          {/* Время и статус справа */}
                          <Group gap={4} wrap="nowrap">
                            {message.is_edited && (
                              <Text
                                size="xs"
                                c={
                                  isOwnMessage(message) ? undefined : 'dimmed'
                                }>
                                {t('edited')}
                              </Text>
                            )}
                            {message.connector_type && (
                              <Text
                                size="xs"
                                c={
                                  isOwnMessage(message) ? undefined : 'dimmed'
                                }>
                                via {message.connector_type}
                              </Text>
                            )}
                            <Text
                              size="xs"
                              c={isOwnMessage(message) ? undefined : 'dimmed'}>
                              {formatTime(message.create_date)}
                            </Text>
                            {isOwnMessage(message) && (
                              <Tooltip
                                label={
                                  message.is_read ? t('read') : t('delivered')
                                }
                                position="top"
                                withArrow>
                                <Box className={styles.readStatus}>
                                  {message.is_read ? (
                                    <IconChecks
                                      size={14}
                                      className={styles.readIcon}
                                    />
                                  ) : (
                                    <IconCheck
                                      size={14}
                                      className={styles.deliveredIcon}
                                    />
                                  )}
                                </Box>
                              </Tooltip>
                            )}
                          </Group>
                        </Group>
                      </Paper>
                    )}

                    {/* Время для сообщений только с вложениями */}
                    {!message.body?.trim() &&
                      message.attachments &&
                      message.attachments.length > 0 && (
                        <Group
                          gap={8}
                          justify="space-between"
                          style={{ width: '100%' }}>
                          {/* Реакции */}
                          {message.reactions && message.reactions.length > 0 ? (
                            <Group gap={4} wrap="wrap">
                              {message.reactions.map(reaction => (
                                <Tooltip
                                  key={reaction.emoji}
                                  label={reaction.users
                                    .map(u => u.user_name)
                                    .join(', ')}
                                  position="top"
                                  withArrow>
                                  <Box
                                    className={styles.reactionBadge}
                                    onClick={() =>
                                      handleAddReaction(
                                        message.id,
                                        reaction.emoji,
                                      )
                                    }>
                                    <span>{reaction.emoji}</span>
                                    <Text size="xs" span>
                                      {reaction.count}
                                    </Text>
                                  </Box>
                                </Tooltip>
                              ))}
                            </Group>
                          ) : (
                            <Box />
                          )}
                          <Group gap={4}>
                            <Text size="xs" c="dimmed">
                              {formatTime(message.create_date)}
                            </Text>
                            {isOwnMessage(message) && (
                              <Tooltip
                                label={
                                  message.is_read ? t('read') : t('delivered')
                                }
                                position="top"
                                withArrow>
                                <Box className={styles.readStatus}>
                                  {message.is_read ? (
                                    <IconChecks
                                      size={14}
                                      className={styles.readIcon}
                                    />
                                  ) : (
                                    <IconCheck
                                      size={14}
                                      className={styles.deliveredIcon}
                                    />
                                  )}
                                </Box>
                              </Tooltip>
                            )}
                          </Group>
                        </Group>
                      )}
                  </Stack>
                </Group>
              </Box>
            ))}
          </Stack>
        )}
      </ScrollArea>

      {contextMenu && (
        <Paper
          className={styles.contextMenu}
          style={{ top: contextMenu.y, left: contextMenu.x }}
          shadow="md"
          withBorder>
          <Stack gap={0}>
            <Box className={styles.contextMenuReactions}>
              {REACTION_EMOJIS.slice(0, 6).map(emoji => (
                <ActionIcon
                  key={emoji}
                  variant="subtle"
                  size="sm"
                  onClick={() =>
                    handleAddReaction(contextMenu.message.id, emoji)
                  }>
                  <span style={{ fontSize: '16px' }}>{emoji}</span>
                </ActionIcon>
              ))}
              <ActionIcon
                variant="subtle"
                size="sm"
                onClick={handleReactionClick}>
                <IconMoodSmile size={16} />
              </ActionIcon>
            </Box>
            <Box className={styles.contextMenuDivider} />
            {hasText(contextMenu.message) && (
              <Box className={styles.contextMenuItem} onClick={handleCopyText}>
                <IconCopy size={16} />
                <Text size="sm">{t('copyText')}</Text>
              </Box>
            )}
            {hasAttachments(contextMenu.message) && (
              <Box
                className={styles.contextMenuItem}
                onClick={handleDownloadFile}>
                <IconDownload size={16} />
                <Text size="sm">{t('downloadFile')}</Text>
              </Box>
            )}
            {isOwnMessage(contextMenu.message) && (
              <Box className={styles.contextMenuItem} onClick={handleEditClick}>
                <IconEdit size={16} />
                <Text size="sm">{t('edit')}</Text>
              </Box>
            )}
            <Box className={styles.contextMenuItem} onClick={handlePin}>
              {contextMenu.message.pinned ? (
                <IconPinFilled size={16} />
              ) : (
                <IconPin size={16} />
              )}
              <Text size="sm">
                {contextMenu.message.pinned ? t('unpin') : t('pin')}
              </Text>
            </Box>
            {!isOwnMessage(contextMenu.message) && (
              <Box
                className={styles.contextMenuItem}
                onClick={handleMarkUnread}>
                <IconEyeOff size={16} />
                <Text size="sm">{t('markAsUnread')}</Text>
              </Box>
            )}
            <Box
              className={styles.contextMenuItem}
              onClick={handleForwardClick}>
              <IconArrowForward size={16} />
              <Text size="sm">{t('forward')}</Text>
            </Box>
            {isOwnMessage(contextMenu.message) && (
              <Box
                className={styles.contextMenuItemDanger}
                onClick={handleDelete}>
                <IconTrash size={16} />
                <Text size="sm">{t('delete')}</Text>
              </Box>
            )}
          </Stack>
        </Paper>
      )}

      <Modal
        opened={!!reactionPicker?.opened}
        onClose={() => setReactionPicker(null)}
        title={t('selectReaction')}
        size="xs"
        centered>
        <Group gap="xs" justify="center">
          {REACTION_EMOJIS.map(emoji => (
            <ActionIcon
              key={emoji}
              variant="light"
              size="xl"
              onClick={() =>
                reactionPicker &&
                handleAddReaction(reactionPicker.messageId, emoji)
              }>
              <span style={{ fontSize: '24px' }}>{emoji}</span>
            </ActionIcon>
          ))}
        </Group>
      </Modal>

      {showScrollButton && (
        <ActionIcon
          className={styles.scrollButton}
          variant="filled"
          size="lg"
          radius="xl"
          onClick={scrollToBottom}>
          <IconArrowDown size={20} />
        </ActionIcon>
      )}

      <ImageGalleryModal
        opened={galleryOpened}
        onClose={() => setGalleryOpened(false)}
        items={galleryItems}
        initialIndex={galleryIndex}
        onDownload={item => item.id && handleDownloadAttachment(item.id)}
      />

      <Modal
        opened={editModal.opened}
        onClose={() => setEditModal({ opened: false, message: null })}
        title={t('editMessage')}>
        <Stack>
          <TextInput
            value={editText}
            onChange={e => setEditText(e.target.value)}
            placeholder={t('messageText')}
          />
          <Group justify="flex-end">
            <Button
              variant="subtle"
              onClick={() => setEditModal({ opened: false, message: null })}>
              {t('cancel')}
            </Button>
            <Button onClick={handleEditSave}>{t('save')}</Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={forwardModal.opened}
        onClose={() => setForwardModal({ opened: false, message: null })}
        title={t('forwardMessage')}>
        <Stack>
          <Text size="sm" c="dimmed">
            {t('selectChat')}
          </Text>
          {chatsData?.data
            .filter(c => c.id !== chat.id)
            .map(c => (
              <Paper
                key={c.id}
                p="sm"
                withBorder
                className={styles.forwardChatItem}
                onClick={() => handleForward(c.id)}>
                <Text>{c.name || c.members.map(m => m.name).join(', ')}</Text>
              </Paper>
            ))}
        </Stack>
      </Modal>
    </Box>
  );
}

export default ChatMessages;
