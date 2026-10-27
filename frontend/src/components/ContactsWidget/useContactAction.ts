import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import { useHasWorkspaceApp } from '@/hooks/useWorkspaceApps';
import { useLazyResolveContactChatQuery } from '@/services/api/chat';
import { sipDial } from '@/fara_sip_phone/dialer';
import type { Contact } from './types';

/** Что делает клик по значку контакта. */
export interface ContactAction {
  /** Подсказка на значке. */
  label: string;
  run: () => void;
}

type ContactLike = Pick<
  Contact,
  'id' | 'value' | 'contact_type' | 'contact_type_id'
>;

// Телефонные типы набирает звонилка, остальные — каналы переписки, кроме
// сайта и подписки на пуши.
const CALL_TYPES = new Set(['phone', 'sip']);
const NO_CHAT_TYPES = new Set(['website', 'web_push']);

/**
 * Действие по клику на значок контакта (issue #47): телефон — номер в
 * звонилку в шапке (звонок — по её кнопке), мессенджер/email — чат
 * собеседника в «Общении» с каналом этого контакта; чата нет — визард
 * создания с этим собеседником (ChatPage, ?new_contact). null — значок не
 * кликабелен: нет приложения «Общение» или контакт ещё не сохранён.
 */
export function useContactAction(): (
  contact: ContactLike,
) => ContactAction | null {
  const { t } = useTranslation('common');
  const navigate = useNavigate();
  const communication = useHasWorkspaceApp()('communication');
  const [resolveChat] = useLazyResolveContactChatQuery();

  return useCallback(
    contact => {
      if (!communication) return null;
      if (CALL_TYPES.has(contact.contact_type)) {
        return {
          label: t('contacts.call'),
          run: () => {
            // false — звонилки в шапке нет (телефония не установлена).
            if (!sipDial(contact.value)) {
              notifications.show({
                color: 'yellow',
                message: t('contacts.phoneUnavailable'),
              });
            }
          },
        };
      }

      const contactId = contact.id;
      if (!contactId || NO_CHAT_TYPES.has(contact.contact_type)) return null;
      return {
        label: t('contacts.openChat'),
        run: async () => {
          try {
            const found = await resolveChat({ contactId }).unwrap();
            const params = new URLSearchParams();
            if (found.chat_id) {
              params.set('open', String(found.chat_id));
            } else if (found.partner_id || found.user_id) {
              params.set('new_contact', String(contactId));
            } else {
              return; // свой контакт
            }
            // ChatPage подставит канал этого контакта.
            if (contact.contact_type_id) {
              params.set('contact_type', String(contact.contact_type_id));
            }
            navigate(`/chat?${params}`);
          } catch (e) {
            console.error('Resolve contact chat failed:', e);
            notifications.show({
              color: 'red',
              message: t('contacts.chatFailed'),
            });
          }
        },
      };
    },
    [t, navigate, communication, resolveChat],
  );
}
