/**
 * ContactMultiSelect — компонент выбора контактов с поиском.
 *
 * Резолвит контакт в user_id или partner_id (depending on what contact points to).
 * Возвращает массив результатов, каждый с type и sourceId.
 *
 * Используется внутри ChatParticipantSelect для режима "контакты".
 */
import { useState } from 'react';
import { MultiSelect, Loader } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useSearchQuery } from '@/services/api/crudApi';

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

interface ContactMultiSelectProps {
  value: ContactSelection[];
  onChange: (selections: ContactSelection[]) => void;
  /** ID пользователей, которых нужно исключить (например уже в чате) */
  excludeUserIds?: number[];
  /** ID партнёров, которых нужно исключить */
  excludePartnerIds?: number[];
  label?: string;
  placeholder?: string;
  maxValues?: number;
  disabled?: boolean;
}

export function ContactMultiSelect({
  value,
  onChange,
  excludeUserIds = [],
  excludePartnerIds = [],
  label = 'Выберите контакт',
  placeholder = 'Поиск по телефону, email...',
  maxValues,
  disabled = false,
}: ContactMultiSelectProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const { data: contactsData, isFetching } = useSearchQuery({
    model: 'contact',
    fields: ['id', 'name', 'contact_type_id', 'partner_id', 'user_id'],
    filter: searchQuery
      ? [['name', 'ilike', `%${searchQuery}%`]]
      : [],
    limit: 50,
  });

  const excludeUsers = new Set(excludeUserIds);
  const excludePartners = new Set(excludePartnerIds);

  // Трансформируем контакты в опции
  const options =
    contactsData?.data
      ?.filter((c: any) => c.partner_id?.id || c.user_id?.id)
      .filter((c: any) => {
        // Скрываем уже добавленных
        if (c.user_id?.id && excludeUsers.has(c.user_id.id)) return false;
        if (c.partner_id?.id && excludePartners.has(c.partner_id.id))
          return false;
        return true;
      })
      .map((contact: any) => {
        const isPartner = !!contact.partner_id?.id;
        const ownerName = isPartner
          ? contact.partner_id?.name
          : contact.user_id?.name;
        return {
          value: `contact-${contact.id}`,
          label: `${ownerName} (${contact.name})`,
          contactId: contact.id,
          type: isPartner ? ('partner' as const) : ('user' as const),
          sourceId: isPartner ? contact.partner_id.id : contact.user_id.id,
        };
      }) || [];

  // Текущее значение — массив value-строк для MultiSelect
  const stringValue = value.map(v => `contact-${v.contactId}`);

  const handleChange = (vals: string[]) => {
    const selected: ContactSelection[] = [];
    for (const v of vals) {
      const opt = options.find((o: any) => o.value === v);
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
      value={stringValue}
      onChange={handleChange}
      maxValues={maxValues}
      leftSection={isFetching ? <Loader size="xs" /> : <IconSearch size={16} />}
      nothingFoundMessage={isFetching ? 'Поиск...' : 'Контакты не найдены'}
      clearable
      disabled={disabled}
    />
  );
}
