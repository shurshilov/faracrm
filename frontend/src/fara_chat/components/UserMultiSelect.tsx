/**
 * UserMultiSelect — переиспользуемый компонент выбора пользователей.
 *
 * Используется:
 *   - NewChatModal — выбор участников при создании чата
 *   - ChatSettingsModal — добавление участников в существующий чат
 *
 * Поддерживает поиск по имени пользователя.
 * Опционально исключает уже выбранных/существующих пользователей из списка.
 */
import { useEffect, useState } from 'react';
import { MultiSelect, Loader } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useRouteUsersSearchPostMutation } from '@/services/api/users';

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
}

export function UserMultiSelect({
  value,
  onChange,
  excludeIds = [],
  label,
  placeholder,
  maxValues,
  disabled = false,
}: UserMultiSelectProps) {
  const { t } = useTranslation('chat');
  const [searchQuery, setSearchQuery] = useState('');

  const [searchUsers, { data: usersData, isLoading }] =
    useRouteUsersSearchPostMutation();

  // Загружаем при монтировании и при изменении поиска
  useEffect(() => {
    const filter: any[] = [];
    if (searchQuery.trim()) {
      filter.push(['name', 'ilike', `%${searchQuery}%`]);
    }

    searchUsers({
      userSearchInput: {
        fields: ['id', 'name'],
        filter,
        limit: 50,
      },
    });
  }, [searchQuery, searchUsers]);

  // Преобразуем в опции MultiSelect, исключая excludeIds
  const excludeSet = new Set(excludeIds);
  const options =
    usersData?.data
      ?.filter(u => !excludeSet.has(u.id))
      .map(u => ({
        value: u.id.toString(),
        label: u.name || `#${u.id}`,
      })) || [];

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
      value={stringValue}
      onChange={vals => onChange(vals.map(v => parseInt(v, 10)))}
      maxValues={maxValues}
      leftSection={isLoading ? <Loader size="xs" /> : <IconSearch size={16} />}
      nothingFoundMessage={isLoading ? t('searching') : t('noUsersFound')}
      clearable
      disabled={disabled}
    />
  );
}
