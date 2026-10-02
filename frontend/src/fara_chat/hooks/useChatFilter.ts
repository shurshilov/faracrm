import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ChatSection } from '@/services/api/chat';

/**
 * Фильтр списка чатов живёт в URL (/chat?section=clients&scope=team&unread=1):
 * квадраты сайдбара и чипы над списком меняют параметры, список их читает.
 * Без параметров — «Сотрудники»; своя папка (folder_id) — вместо раздела.
 */
export interface ChatFilter {
  section?: ChatSection;
  folder_id?: number;
  chat_type?: 'direct' | 'group';
  scope?: 'mine' | 'team';
  connector_id?: number;
  unread?: true;
}

function parseSection(params: URLSearchParams): ChatSection | undefined {
  if (params.has('folder_id')) return undefined;
  const section = params.get('section');
  if (section) return section as ChatSection;
  // Чат из уведомления (?open=id): его раздел ещё не известен — ищем по
  // всем, ChatPage после открытия переключит на раздел чата.
  return params.has('open') ? undefined : 'staff';
}

export function useChatFilter() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const folderId = params.get('folder_id');
  const connectorId = params.get('connector_id');
  const filter: ChatFilter = {
    section: parseSection(params),
    folder_id: folderId ? Number(folderId) : undefined,
    chat_type:
      (params.get('chat_type') as ChatFilter['chat_type']) || undefined,
    scope: (params.get('scope') as ChatFilter['scope']) || undefined,
    connector_id: connectorId ? Number(connectorId) : undefined,
    unread: params.get('unread') === '1' || undefined,
  };

  // Чип: меняет свой параметр, остальные оставляет.
  const update = (patch: Partial<ChatFilter>) =>
    setParams(prev => {
      const next = new URLSearchParams(prev);
      for (const [key, value] of Object.entries(patch)) {
        if (value === undefined) next.delete(key);
        else next.set(key, value === true ? '1' : String(value));
      }
      return next;
    });

  // Квадрат: другой раздел или папка — чипы сбрасываются.
  const open = (target: { section: ChatSection } | { folder_id: number }) => {
    const [key, value] = Object.entries(target)[0];
    navigate(`/chat?${key}=${value}`);
  };

  return { filter, update, open };
}
