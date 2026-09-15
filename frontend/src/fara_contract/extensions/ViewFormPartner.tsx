/**
 * Вкладки «Реквизиты» и «Банк» в форме партнёра — из модуля contract.
 *
 * Поля — RequisitesMixin (backend/base/crm/contract/models/
 * requisites_ext.py), сами вкладки общие с компанией — см. ../Requisites.tsx.
 *
 * Подключение: fara_contract/index.ts (side-effect импорт) и
 * config/models.ts (modelsConfig.partners.extensions). Прямые
 * FieldChar/FieldSelection вместо <Field> — как во всех расширениях
 * (см. комментарий в ViewFormSale.tsx).
 */

import { IconFileCertificate } from '@tabler/icons-react';
import { registerFormTab } from '@/shared/extensions';
import {
  REQUISITES_FIELDS,
  RequisitesFields,
  registerBankTab,
} from '../Requisites';

registerFormTab(
  'partners',
  {
    name: 'requisites',
    label: 'Реквизиты',
    icon: <IconFileCertificate size={16} />,
    component: RequisitesFields,
  },
  REQUISITES_FIELDS,
);

registerBankTab('partners');
