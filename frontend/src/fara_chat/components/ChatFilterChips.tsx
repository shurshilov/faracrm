import { UnstyledButton } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useChatFilter } from '../hooks/useChatFilter';
import classes from './ChatFilterChips.module.css';

// Чипы над списком чатов. Какие показать в разделе, решает список
// (ChatList); каждый чип сам читает и меняет свой параметр URL.

interface SegmentsProps<T extends string> {
  value: T;
  data: { value: T; label: string }[];
  onChange: (value: T) => void;
}

/** Пилюля из вариантов — один выбран всегда. */
function Segments<T extends string>({
  value,
  data,
  onChange,
}: SegmentsProps<T>) {
  return (
    <div className={classes.seg} role="radiogroup">
      {data.map(item => (
        <UnstyledButton
          key={item.value}
          className={classes.segItem}
          role="radio"
          aria-checked={item.value === value}
          data-active={item.value === value || undefined}
          onClick={() => onChange(item.value)}>
          {item.label}
        </UnstyledButton>
      ))}
    </div>
  );
}

/** «Сотрудники»: все / личные / группы. */
export function ChatTypeChips() {
  const { t } = useTranslation('chat');
  const { filter, update } = useChatFilter();
  return (
    <Segments
      value={filter.chat_type ?? 'all'}
      onChange={value =>
        update({ chat_type: value === 'all' ? undefined : value })
      }
      data={[
        { value: 'all', label: t('all', 'Все') },
        { value: 'direct', label: t('filterDirect', 'Личные') },
        { value: 'group', label: t('filterGroups', 'Группы') },
      ]}
    />
  );
}

/** «Клиенты»: где я участник / ещё и чаты моих команд. */
export function ChatScopeChips() {
  const { t } = useTranslation('chat');
  const { filter, update } = useChatFilter();
  return (
    <Segments
      value={filter.scope ?? 'mine'}
      onChange={value =>
        update({ scope: value === 'team' ? 'team' : undefined })
      }
      data={[
        { value: 'mine', label: t('scopeMine', 'Мои') },
        { value: 'team', label: t('scopeTeam', 'Моя команда') },
      ]}
    />
  );
}

/** Только чаты с непрочитанными — накладывается на остальные чипы. */
export function UnreadChip() {
  const { t } = useTranslation('chat');
  const { filter, update } = useChatFilter();
  return (
    <UnstyledButton
      className={classes.chip}
      aria-pressed={!!filter.unread}
      data-active={filter.unread}
      onClick={() => update({ unread: filter.unread ? undefined : true })}>
      {t('unreadChats', 'Непрочитанные')}
    </UnstyledButton>
  );
}
