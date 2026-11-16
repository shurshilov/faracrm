import { useTranslation } from 'react-i18next';
import { Kanban } from '@/components/Kanban';
import type { PartnerRecord } from '@/types/records';

export function ViewKanbanPartners() {
  const { t } = useTranslation('partners');

  // Поля карточки по умолчанию: тип лица, ответственный и число контактов
  // (сами телефоны и email — во вкладке «Контакты» формы). У этих полей
  // выводится подпись: без неё непонятно, что за имя и что за число.
  // Набор меняется через «⋮ → Поля карточки».
  return (
    <Kanban<PartnerRecord>
      model="partners"
      fields={['id', 'name', 'legal_type', 'user_id', 'contact_ids']}
      fieldLabels={{
        legal_type: t('fields.legal_type'),
        user_id: t('fields.user_id'),
        contact_ids: t('fields.contact_ids'),
      }}
    />
  );
}
