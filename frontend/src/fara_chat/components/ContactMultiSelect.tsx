/**
 * ContactMultiSelect — выбор партнёров по их контактам (вкладка «Партнёры»).
 *
 * Только контакты партнёров: сотрудников выбирают во вкладке «Пользователи».
 * Поиск — GET /chats/members?kind=partners: у партнёра, чей внешний чат уже
 * есть, приходит chat_id — бейдж «есть чат» со стрелкой в опции (второго не
 * создать, модель 1:1). Возвращает массив результатов с type и sourceId.
 *
 * Используется внутри ChatParticipantSelect для режима "partners".
 */
import { useState } from 'react';
import { MultiSelect, Loader } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useSearchChatMembersQuery } from '@/services/api/chat';
import { MemberOption, renderMemberOption } from './MemberOption';

export interface ContactSelection {
  /** Оригинальный ID контакта */
  contactId: number;
  /** К чему относится контакт */
  type: 'user' | 'partner';
  /** ID пользователя или партнёра */
  sourceId: number;
  /** Отображаемое имя */
  label: string;
}

type ContactOption = MemberOption & {
  contactId: number;
  type: 'partner';
  sourceId: number;
};

interface ContactMultiSelectProps {
  value: ContactSelection[];
  onChange: (selections: ContactSelection[]) => void;
  /** ID партнёров, которых нужно исключить (например уже в чате) */
  excludePartnerIds?: number[];
  label?: string;
  placeholder?: string;
  maxValues?: number;
  disabled?: boolean;
}

export function ContactMultiSelect({
  value,
  onChange,
  excludePartnerIds = [],
  label = 'Выберите партнёра',
  placeholder = 'Поиск по телефону, email, имени...',
  maxValues,
  disabled = false,
}: ContactMultiSelectProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const { data: contactsData, isFetching } = useSearchChatMembersQuery({
    kind: 'partners',
    search: searchQuery.trim(),
  });

  const excludePartners = new Set(excludePartnerIds);

  // Трансформируем контакты в опции, скрывая уже добавленных
  const options: ContactOption[] =
    contactsData?.data
      .filter(c => c.partner_id && !excludePartners.has(c.partner_id))
      .map(c => ({
        value: `contact-${c.id}`,
        label: `${c.partner_name} (${c.name})`,
        contactId: c.id,
        type: 'partner' as const,
        sourceId: c.partner_id as number,
        chatId: c.chat_id ?? undefined,
      })) || [];

  // Контакт, заданный снаружи (визард со значка контакта), в выдаче поиска
  // может не быть: MultiSelect рисует пилюлю по опциям, и без своей опции
  // она выйдет с сырым value «contact-N» вместо имени.
  for (const sel of value) {
    if (!options.some(o => o.value === `contact-${sel.contactId}`)) {
      options.push({
        value: `contact-${sel.contactId}`,
        label: sel.label,
        contactId: sel.contactId,
        type: 'partner',
        sourceId: sel.sourceId,
      });
    }
  }

  // Текущее значение — массив value-строк для MultiSelect
  const stringValue = value.map(v => `contact-${v.contactId}`);

  const handleChange = (vals: string[]) => {
    const selected: ContactSelection[] = [];
    for (const v of vals) {
      const opt = options.find(o => o.value === v);
      if (opt) {
        selected.push({
          contactId: opt.contactId,
          type: opt.type,
          sourceId: opt.sourceId,
          label: opt.label,
        });
      } else {
        // Уже выбранный — берём из value
        const existing = value.find(x => `contact-${x.contactId}` === v);
        if (existing) selected.push(existing);
      }
    }
    onChange(selected);
  };

  return (
    <MultiSelect
      label={label}
      placeholder={placeholder}
      searchable
      searchValue={searchQuery}
      onSearchChange={setSearchQuery}
      data={options}
      // Фильтрует бэкенд — свой фильтр по подписи MultiSelect выключаем.
      filter={({ options }) => options}
      value={stringValue}
      onChange={handleChange}
      maxValues={maxValues}
      renderOption={renderMemberOption}
      leftSection={isFetching ? <Loader size="xs" /> : <IconSearch size={16} />}
      nothingFoundMessage={isFetching ? 'Поиск...' : 'Партнёры не найдены'}
      clearable
      disabled={disabled}
    />
  );
}
