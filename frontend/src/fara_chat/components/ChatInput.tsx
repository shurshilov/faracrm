import { useState, useRef, useCallback } from 'react';
import {
  Box,
  TextInput,
  ActionIcon,
  Group,
  FileButton,
  Tooltip,
  Menu,
  Popover,
  SimpleGrid,
  Text,
} from '@mantine/core';
import {
  IconSend,
  IconPaperclip,
  IconMoodSmile,
  IconPhoto,
  IconFile,
  IconX,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSendMessageMutation } from '@/services/api/chat';
import {
  AttachmentPreview,
  ImageGalleryModal,
  VoiceRecorder,
  isImageMimetype,
  formatFileSize,
} from '@/components/Attachment';
import type { GalleryItem } from '@/components/Attachment';
import { EmojiPicker } from './EmojiPicker';
import { ConnectorSwitcher, ConnectorOption } from './ConnectorSwitcher';
import styles from './ChatInput.module.css';

interface AttachmentFile {
  name: string;
  mimetype: string;
  size: number;
  content: string;
  _localId: string;
}

interface ChatInputProps {
  chatId: number;
  currentUserId: number;
  currentUserName?: string;
  onTyping?: () => void;
  connectorId?: number;
  disabled?: boolean;
  // Для ConnectorSwitcher
  connectors?: ConnectorOption[];
  onConnectorSelect?: (connectorId: number | null) => void;
  // Callback после отправки сообщения
  onMessageSent?: () => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_FILES = 10;

export function ChatInput({
  chatId,
  currentUserId,
  currentUserName,
  onTyping,
  connectorId,
  disabled,
  connectors,
  onConnectorSelect,
  onMessageSent,
}: ChatInputProps) {
  const { t } = useTranslation('chat');
  const [message, setMessage] = useState('');
  const [attachments, setAttachments] = useState<AttachmentFile[]>([]);
  const [emojiOpened, setEmojiOpened] = useState(false);
  const [galleryOpened, setGalleryOpened] = useState(false);
  const [galleryIndex, setGalleryIndex] = useState(0);
  const [isRecording, setIsRecording] = useState(false);

  const [sendMessage] = useSendMessageMutation();
  const inputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<() => void>(null);
  const fileInputRef = useRef<() => void>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Голосовое сообщение готово к отправке
  const [pendingVoice, setPendingVoice] = useState<{
    name: string;
    mimetype: string;
    size: number;
    content: string;
    is_voice: boolean;
  } | null>(null);

  // Счётчик для сброса VoiceRecorder после отправки
  const [voiceResetKey, setVoiceResetKey] = useState(0);

  const handleSend = useCallback(async () => {
    const trimmedMessage = message.trim();

    // Отправка голосового сообщения
    if (pendingVoice) {
      try {
        await sendMessage({
          chatId,
          body: ' ',
          connector_id: connectorId,
          currentUserId,
          currentUserName,
          attachments: [pendingVoice],
        }).unwrap();
        setPendingVoice(null);
        setIsRecording(false);
        setVoiceResetKey(k => k + 1); // Сбрасываем VoiceRecorder
        onMessageSent?.();
      } catch (error) {
        console.error('Failed to send voice message:', error);
      }
      return;
    }

    // Обычное сообщение
    if ((!trimmedMessage && attachments.length === 0) || disabled) return;

    try {
      await sendMessage({
        chatId,
        body: trimmedMessage || ' ',
        connector_id: connectorId,
        currentUserId,
        currentUserName,
        attachments:
          attachments.length > 0
            ? attachments.map(({ name, mimetype, size, content }) => ({
                name,
                mimetype,
                size,
                content,
              }))
            : undefined,
      }).unwrap();

      setMessage('');
      setAttachments([]);
      inputRef.current?.focus();
      onMessageSent?.();
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  }, [
    message,
    attachments,
    pendingVoice,
    chatId,
    connectorId,
    currentUserId,
    currentUserName,
    disabled,
    sendMessage,
    onMessageSent,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMessage(e.target.value);

    if (onTyping) {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      onTyping();
      typingTimeoutRef.current = setTimeout(() => {
        typingTimeoutRef.current = null;
      }, 2000);
    }
  };

  const handleEmojiSelect = (emoji: string) => {
    setMessage(prev => prev + emoji);
    setEmojiOpened(false);
    inputRef.current?.focus();
  };

  const readFileAsBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]);
      };
      reader.readAsDataURL(file);
    });
  };

  const handleFileSelect = async (files: File[] | null) => {
    if (!files || files.length === 0) return;

    if (attachments.length + files.length > MAX_FILES) {
      console.warn(`Maximum ${MAX_FILES} files allowed`);
      return;
    }

    const newAttachments: AttachmentFile[] = [];

    for (const file of files) {
      if (file.size > MAX_FILE_SIZE) {
        console.warn(
          `File ${file.name} exceeds ${formatFileSize(MAX_FILE_SIZE)}`,
        );
        continue;
      }

      try {
        const content = await readFileAsBase64(file);
        newAttachments.push({
          name: file.name,
          mimetype: file.type || 'application/octet-stream',
          size: file.size,
          content,
          _localId: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        });
      } catch (err) {
        console.error('Error reading file:', err);
      }
    }

    if (newAttachments.length > 0) {
      setAttachments(prev => [...prev, ...newAttachments]);
    }
  };

  const handleRemoveAttachment = (localId: string) => {
    setAttachments(prev => prev.filter(a => a._localId !== localId));
  };

  const handleVoiceRecorded = async (voiceFile: {
    name: string;
    mimetype: string;
    size: number;
    content: string;
    is_voice: boolean;
  }) => {
    // Отправляем голосовое сообщение сразу
    try {
      await sendMessage({
        chatId,
        body: '',
        connector_id: connectorId,
        currentUserId,
        currentUserName,
        attachments: [voiceFile],
      }).unwrap();
      setIsRecording(false);
    } catch (error) {
      console.error('Failed to send voice message:', error);
    }
  };

  const handleOpenGallery = (index: number) => {
    const imageFiles = attachments.filter(a => isImageMimetype(a.mimetype));
    const file = attachments[index];
    const imageIndex = imageFiles.findIndex(f => f._localId === file._localId);

    if (imageIndex >= 0) {
      setGalleryIndex(imageIndex);
      setGalleryOpened(true);
    }
  };

  const galleryItems: GalleryItem[] = attachments
    .filter(a => isImageMimetype(a.mimetype))
    .map(a => ({
      id: undefined,
      name: a.name,
      mimetype: a.mimetype,
      content: a.content,
    }));

  const canAddMore = attachments.length < MAX_FILES;

  const handleClearAllAttachments = () => {
    setAttachments([]);
  };

  return (
    <Box className={styles.container}>
      {attachments.length > 0 && (
        <Box className={styles.attachmentsPreview}>
          <Group justify="space-between" mb="xs">
            <Text size="xs" c="dimmed">
              {t('attachedFiles', { count: attachments.length })}
            </Text>
            <ActionIcon
              variant="subtle"
              size="xs"
              color="gray"
              onClick={handleClearAllAttachments}
              title={t('clearAll')}>
              <IconX size={14} />
            </ActionIcon>
          </Group>
          <SimpleGrid cols={6} spacing="xs">
            {attachments.map((file, index) => (
              <AttachmentPreview
                key={file._localId}
                attachment={{
                  name: file.name,
                  mimetype: file.mimetype,
                  size: file.size,
                  content: file.content,
                }}
                onDelete={() => handleRemoveAttachment(file._localId)}
                onClick={
                  isImageMimetype(file.mimetype)
                    ? () => handleOpenGallery(index)
                    : undefined
                }
                showPreview={true}
                previewSize={60}
                compact
              />
            ))}
          </SimpleGrid>
        </Box>
      )}

      {/* Hidden FileButtons */}
      <FileButton
        onChange={handleFileSelect}
        accept="image/*"
        multiple
        resetRef={imageInputRef}>
        {props => (
          <button {...props} style={{ display: 'none' }} id="image-input" />
        )}
      </FileButton>
      <FileButton
        onChange={handleFileSelect}
        accept="*/*"
        multiple
        resetRef={fileInputRef}>
        {props => (
          <button {...props} style={{ display: 'none' }} id="file-input" />
        )}
      </FileButton>

      <Group gap="xs" wrap="nowrap">
        <Menu position="top-start" withArrow>
          <Menu.Target>
            <ActionIcon
              variant="subtle"
              size="lg"
              disabled={disabled || !canAddMore}
              title={t('attach')}>
              <IconPaperclip size={20} />
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item
              leftSection={<IconPhoto size={16} />}
              onClick={() => document.getElementById('image-input')?.click()}>
              {t('attachImage')}
            </Menu.Item>
            <Menu.Item
              leftSection={<IconFile size={16} />}
              onClick={() => document.getElementById('file-input')?.click()}>
              {t('attachFile')}
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>

        <TextInput
          ref={inputRef}
          className={styles.input}
          placeholder={t('typeMessage')}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rightSection={
            <Popover
              opened={emojiOpened}
              onChange={setEmojiOpened}
              position="top-end"
              withArrow
              shadow="md">
              <Popover.Target>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  disabled={disabled}
                  title={t('emoji')}
                  onClick={() => setEmojiOpened(o => !o)}>
                  <IconMoodSmile size={18} />
                </ActionIcon>
              </Popover.Target>
              <Popover.Dropdown p={0}>
                <EmojiPicker onSelect={handleEmojiSelect} />
              </Popover.Dropdown>
            </Popover>
          }
        />

        <VoiceRecorder
          key={voiceResetKey}
          onRecorded={handleVoiceRecorded}
          onRecordingReady={setPendingVoice}
          onCancel={() => {
            setIsRecording(false);
            setPendingVoice(null);
          }}
          disabled={disabled || attachments.length > 0}
          showSendButton={false}
        />

        {/* Переключатель коннектора */}
        {connectors && connectors.length > 1 && onConnectorSelect && (
          <ConnectorSwitcher
            connectors={connectors}
            selectedConnectorId={connectorId ?? null}
            onSelect={onConnectorSelect}
            disabled={disabled}
          />
        )}

        <Tooltip label={t('send')} position="top">
          <ActionIcon
            variant="filled"
            size="lg"
            onClick={handleSend}
            disabled={
              (!message.trim() && attachments.length === 0 && !pendingVoice) ||
              disabled
            }>
            <IconSend size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <ImageGalleryModal
        opened={galleryOpened}
        onClose={() => setGalleryOpened(false)}
        items={galleryItems}
        initialIndex={galleryIndex}
      />
    </Box>
  );
}

export default ChatInput;
