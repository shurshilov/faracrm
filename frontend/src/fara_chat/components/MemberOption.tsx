/**
 * Опция выбора участника чата (UserMultiSelect, ContactMultiSelect):
 * галочка выбранного, подпись и справа бейдж «есть чат», если чат с этим
 * участником уже есть — личный с сотрудником или внешний партнёра, второго
 * не будет. Клик по бейджу открывает тот чат (ChatPage по ?open закрывает
 * окно создания).
 */
import { Badge, Group } from '@mantine/core';
import type { ComboboxItem } from '@mantine/core';
import { IconArrowRight, IconCheck } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';

/** Опция с id уже существующего чата участника. */
export type MemberOption = ComboboxItem & { chatId?: number };

function ExistingChatMark({ chatId }: { chatId: number }) {
  const navigate = useNavigate();
  return (
    <Badge
      size="xs"
      variant="light"
      color="teal"
      rightSection={<IconArrowRight size={10} />}
      title="Открыть чат"
      style={{ cursor: 'pointer' }}
      // Клик — не опции: иначе она выберется, а фокус уйдёт из поиска.
      onMouseDown={e => e.preventDefault()}
      onClick={e => {
        e.stopPropagation();
        navigate(`/chat?open=${chatId}`);
      }}>
      есть чат
    </Badge>
  );
}

export function renderMemberOption({
  option,
  checked,
}: {
  option: ComboboxItem;
  checked?: boolean;
}) {
  const { chatId } = option as MemberOption;
  return (
    <Group gap="xs" wrap="nowrap" style={{ flex: 1 }}>
      {checked && <IconCheck size={14} />}
      <span style={{ flex: 1 }}>{option.label}</span>
      {chatId && <ExistingChatMark chatId={chatId} />}
    </Group>
  );
}
