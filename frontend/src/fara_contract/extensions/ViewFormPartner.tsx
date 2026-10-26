/**
 * Вкладки «Реквизиты» и «Банк» в форме партнёра — из модуля contract.
 *
 * Поля — RequisitesMixin и PartnerRequisitesMixin (backend/base/crm/
 * contract/models/requisites_ext.py): сверх общего с компанией набора у
 * партнёра дата рождения и паспорт (скрыты у юрлица) и адрес доставки.
 * Сами вкладки общие с компанией — см. ../Requisites.tsx.
 *
 * Подключение: fara_contract/index.ts (side-effect импорт) и
 * config/models.ts (modelsConfig.partners.extensions). Прямые
 * FieldChar/FieldSelection вместо <Field> — как во всех расширениях
 * (см. комментарий в ViewFormSale.tsx).
 */

import { IconFileCertificate } from '@tabler/icons-react';
import { registerFormTab } from '@/shared/extensions';
import {
  PARTNER_REQUISITES_FIELDS,
  REQUISITES_FIELDS,
  RequisitesFields,
  registerBankTab,
} from '../Requisites';

export function PartnerRequisitesTab() {
  return <RequisitesFields partner />;
}

registerFormTab(
  'partners',
  {
    name: 'requisites',
    label: 'Реквизиты',
    icon: <IconFileCertificate size={16} />,
    component: PartnerRequisitesTab,
  },
  [...REQUISITES_FIELDS, ...PARTNER_REQUISITES_FIELDS],
);

registerBankTab('partners');
