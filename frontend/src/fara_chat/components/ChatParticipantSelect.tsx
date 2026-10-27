/**
 * ChatParticipantSelect — компонент выбора участников чата.
 *
 * Содержит SegmentedControl переключатель между двумя режимами:
 *   1. Пользователи — сотрудники (системные пользователи)
 *   2. Партнёры — по их контактам
 *
 * Возвращает унифицированный результат: { userIds, partnerIds }.
 * Это позволяет передать результат напрямую в API создания чата
 * или в API addChatMember.
 *
 * Используется:
 *   - NewChatModal — при создании нового чата
 *   - ChatSettingsModal — при добавлении участника в существующий чат
 */
import { useState } from 'react';
import { Stack, SegmentedControl, Group, Text } from '@mantine/core';
import { IconUser, IconAddressBook } from '@tabler/icons-react';
import { UserMultiSelect } from './UserMultiSelect';
import { ContactMultiSelect, ContactSelection } from './ContactMultiSelect';

export interface ParticipantSelection {
  userIds: number[];
  partnerIds: number[];
}

interface ChatParticipantSelectProps {
  /** Текущий выбор — унифицированный */
  value: ParticipantSelection;
  /** Колбек при изменении */
  onChange: (value: ParticipantSelection) => void;
  /** ID пользователей которых нужно исключить (уже в чате) */
  excludeUserIds?: number[];
  /** ID партнёров которых нужно исключить */
  excludePartnerIds?: number[];
  /** Максимум выбранных (1 для прямого чата) */
  maxValues?: number;
  /** Disabled state */
  disabled?: boolean;
  /** Показывать ли подсказку под селектом */
  showHint?: boolean;
  /**
   * Контакты, выбранные заранее (визард со значка контакта партнёра) —
   * открывает режим «Партнёры» с ними. Читается при монтировании.
   */
  initialContacts?: ContactSelection[];
  /** Пользователи, выбранные заранее (значок контакта сотрудника). */
  initialUsers?: { id: number; name: string }[];
}

export function ChatParticipantSelect({
  value,
  onChange,
  excludeUserIds = [],
  excludePartnerIds = [],
  maxValues,
  disabled = false,
  showHint = true,
  initialContacts,
  initialUsers,
}: ChatParticipantSelectProps) {
  const [mode, setMode] = useState<'users' | 'partners'>(
    initialContacts?.length ? 'partners' : 'users',
  );
  // Локальное состояние для режима контактов — нужно чтобы помнить
  // какие контакты выбрал пользователь (а не только резолвленные IDs)
  const [contactSelections, setContactSelections] = useState<
    ContactSelection[]
  >(initialContacts ?? []);

  const handleModeChange = (newMode: string) => {
    setMode(newMode as 'users' | 'partners');
    // Сбрасываем выбор при переключении режима
    onChange({ userIds: [], partnerIds: [] });
    setContactSelections([]);
  };

  // Users mode
  const handleUsersChange = (userIds: number[]) => {
    onChange({ userIds, partnerIds: [] });
  };

  // Contacts mode
  const handleContactsChange = (selections: ContactSelection[]) => {
    setContactSelections(selections);
    const userIds: number[] = [];
    const partnerIds: number[] = [];
    for (const sel of selections) {
      if (sel.type === 'user') {
        userIds.push(sel.sourceId);
      } else {
        partnerIds.push(sel.sourceId);
      }
    }
    onChange({ userIds, partnerIds });
  };

  return (
    <Stack gap="xs">
      <SegmentedControl
        value={mode}
        onChange={handleModeChange}
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
            value: 'partners',
            label: (
              <Group gap="xs" justify="center">
                <IconAddressBook size={14} />
                <span>Партнёры</span>
              </Group>
            ),
          },
        ]}
        fullWidth
        size="xs"
        disabled={disabled}
      />

      {mode === 'users' ? (
        <UserMultiSelect
          value={value.userIds}
          onChange={handleUsersChange}
          excludeIds={excludeUserIds}
          maxValues={maxValues}
          disabled={disabled}
          knownUsers={initialUsers}
        />
      ) : (
        <ContactMultiSelect
          value={contactSelections}
          onChange={handleContactsChange}
          excludePartnerIds={excludePartnerIds}
          maxValues={maxValues}
          disabled={disabled}
        />
      )}

      {showHint && (
        <Text size="xs" c="dimmed">
          {mode === 'partners'
            ? 'Поиск по телефону, email или имени партнёра'
            : 'Поиск по имени или контакту сотрудника'}
        </Text>
      )}
    </Stack>
  );
}
