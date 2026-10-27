/**
 * UserMultiSelect — переиспользуемый компонент выбора пользователей.
 *
 * Используется:
 *   - NewChatModal — выбор участников при создании чата
 *   - ChatSettingsModal — добавление участников в существующий чат
 *
 * Поиск по имени — GET /chats/members: у сотрудника, с которым уже есть
 * личный чат, приходит chat_id — бейдж «есть чат» со стрелкой в опции.
 * Опционально исключает уже выбранных/существующих пользователей из списка.
 */
import { useState } from 'react';
import { MultiSelect, Loader } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSearchChatMembersQuery } from '@/services/api/chat';
import { MemberOption, renderMemberOption } from './MemberOption';

interface UserMultiSelectProps {
  /** Выбранные ID пользователей */
  value: number[];
  /** Колбек при изменении выбора */
  onChange: (userIds: number[]) => void;
  /** ID пользователей которых нужно исключить из списка (например уже добавленных) */
  excludeIds?: number[];
  /** Лейбл компонента */
  label?: string;
  /** Плейсхолдер */
  placeholder?: string;
  /** Максимум выбранных (1 для прямого чата) */
  maxValues?: number;
  /** Disabled state */
  disabled?: boolean;
  /**
   * Пользователи, выбранные снаружи (визард со значка контакта): в выдаче
   * поиска их может не быть, а пилюле нужна подпись.
   */
  knownUsers?: { id: number; name: string }[];
}

export function UserMultiSelect({
  value,
  onChange,
  excludeIds = [],
  label,
  placeholder,
  maxValues,
  disabled = false,
  knownUsers = [],
}: UserMultiSelectProps) {
  const { t } = useTranslation('chat');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: usersData, isFetching } = useSearchChatMembersQuery({
    kind: 'users',
    search: searchQuery.trim(),
  });

  // Преобразуем в опции MultiSelect, исключая excludeIds
  const excludeSet = new Set(excludeIds);
  const options: MemberOption[] =
    usersData?.data
      .filter(u => !excludeSet.has(u.id))
      .map(u => ({
        value: u.id.toString(),
        label: u.name || `#${u.id}`,
        chatId: u.chat_id ?? undefined,
      })) || [];
  for (const u of knownUsers) {
    if (!options.some(o => o.value === String(u.id))) {
      options.push({ value: String(u.id), label: u.name || `#${u.id}` });
    }
  }

  // Value как строки для MultiSelect
  const stringValue = value.map(id => id.toString());

  return (
    <MultiSelect
      label={label || t('selectMembers')}
      placeholder={placeholder || t('searchUsers')}
      searchable
      searchValue={searchQuery}
      onSearchChange={setSearchQuery}
      data={options}
      // Фильтрует бэкенд (и по контактам, которых в подписи нет) — свой
      // фильтр по подписи MultiSelect выключаем.
      filter={({ options }) => options}
      value={stringValue}
      onChange={vals => onChange(vals.map(v => parseInt(v, 10)))}
      maxValues={maxValues}
      renderOption={renderMemberOption}
      leftSection={isFetching ? <Loader size="xs" /> : <IconSearch size={16} />}
      nothingFoundMessage={isFetching ? t('searching') : t('noUsersFound')}
      clearable
      disabled={disabled}
    />
  );
}
