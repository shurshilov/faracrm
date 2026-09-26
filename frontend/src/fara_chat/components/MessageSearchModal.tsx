/**
 * Поиск сообщений в открытом чате (лупа в шапке): строка ввода + список
 * совпадений с бэка (GET /chats/{id}/messages/search — ILIKE по тексту,
 * новые первыми). Как модалка закреплённых: список результатов, без
 * перехода к сообщению в ленте.
 */

import { useState } from 'react';
import {
  Center,
  Loader,
  Modal,
  Paper,
  ScrollArea,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSearchMessagesQuery } from '@/services/api/chat';
import { getMessagePreview } from './ChatList';

const MIN_CHARS = 2;

interface MessageSearchModalProps {
  opened: boolean;
  onClose: () => void;
  chatId: number;
}

export function MessageSearchModal({
  opened,
  onClose,
  chatId,
}: MessageSearchModalProps) {
  const { t } = useTranslation('chat');
  const [query, setQuery] = useState('');
  const [debounced] = useDebouncedValue(query.trim(), 300);
  const active = opened && debounced.length >= MIN_CHARS;

  const { data, isFetching } = useSearchMessagesQuery(
    { chatId, q: debounced },
    { skip: !active },
  );
  const results = data?.data || [];

  const handleClose = () => {
    setQuery('');
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={t('searchMessages', 'Поиск по сообщениям')}
      size="md">
      <TextInput
        data-autofocus
        placeholder={t('searchMessagesPlaceholder', 'Текст сообщения...')}
        leftSection={<IconSearch size={16} />}
        value={query}
        onChange={e => setQuery(e.currentTarget.value)}
        mb="sm"
      />
      <ScrollArea h={400}>
        {!active ? (
          <Text c="dimmed" ta="center">
            {t('searchMinChars', 'Введите минимум 2 символа')}
          </Text>
        ) : isFetching && results.length === 0 ? (
          <Center py="md">
            <Loader size="sm" />
          </Center>
        ) : results.length === 0 ? (
          <Text c="dimmed" ta="center">
            {t('searchNoResults', 'Ничего не найдено')}
          </Text>
        ) : (
          <Stack gap="sm">
            {results.map(msg => (
              <Paper key={msg.id} p="sm" withBorder>
                <Text size="xs" c="dimmed" mb={4}>
                  {msg.author?.name} •{' '}
                  {msg.create_datetime
                    ? new Date(msg.create_datetime).toLocaleString()
                    : ''}
                </Text>
                <Text size="sm" lineClamp={3}>
                  {getMessagePreview(msg, t)}
                </Text>
              </Paper>
            ))}
          </Stack>
        )}
      </ScrollArea>
    </Modal>
  );
}
