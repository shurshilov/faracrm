import {
  IconFileText,
  IconHeadset,
  IconSpeakerphone,
  IconUsers,
  type TablerIcon,
} from '@tabler/icons-react';
import type { ChatSection } from '@/services/api/chat';

/**
 * Разделы чатов (бэк — Chat.SECTION_SQL), в порядке квадратов сайдбара.
 * Иконка и цвет одни на квадрате и на аватаре чата в списке — вид чата
 * узнаётся по цвету и в папках, где разделы перемешаны.
 */
export const SECTION_META: Record<
  ChatSection,
  { Icon: TablerIcon; color: string; label: string }
> = {
  staff: { Icon: IconUsers, color: 'blue', label: 'Сотрудники' },
  clients: { Icon: IconHeadset, color: 'teal', label: 'Клиенты' },
  channels: { Icon: IconSpeakerphone, color: 'orange', label: 'Каналы' },
  records: { Icon: IconFileText, color: 'grape', label: 'Документы' },
};

/** Личный чат — фото или инициалы собеседника на фоне этого цвета. */
export const DIRECT_CHAT_COLOR = 'violet';
