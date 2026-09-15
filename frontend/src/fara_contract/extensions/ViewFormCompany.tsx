/**
 * Вкладки «Реквизиты» и «Банк» в форме компании (настройки) — из модуля
 * contract, тот же набор, что в карточке партнёра.
 *
 * Поля — RequisitesMixin (backend/base/crm/contract/models/
 * requisites_ext.py), сверх него подписанты счёта (руководитель, главный
 * бухгалтер) — CompanyContractMixin (company_ext.py); сами вкладки общие
 * с партнёром — см. ../Requisites.tsx. Реквизиты и банк компании уходят в
 * печатную форму счёта (sale_ext.sale_invoice_rus).
 *
 * Подключение: fara_contract/index.ts (side-effect импорт) и
 * config/models.ts (modelsConfig.company.extensions).
 */

import { FieldMany2one } from '@/components/Form/Fields/FieldMany2one';
import { FormRow } from '@/components/Form/Layout';
import { IconFileCertificate } from '@tabler/icons-react';
import { registerFormTab } from '@/shared/extensions';
import {
  REQUISITES_FIELDS,
  RequisitesFields,
  registerBankTab,
} from '../Requisites';

export function CompanyRequisitesTab() {
  return (
    <>
      <RequisitesFields />
      <FormRow cols={2}>
        <FieldMany2one name="chief_id" label="Руководитель" />
        <FieldMany2one name="accountant_id" label="Главный бухгалтер" />
      </FormRow>
    </>
  );
}

registerFormTab(
  'company',
  {
    name: 'requisites',
    label: 'Реквизиты',
    icon: <IconFileCertificate size={16} />,
    component: CompanyRequisitesTab,
  },
  [...REQUISITES_FIELDS, 'chief_id', 'accountant_id'],
);

registerBankTab('company');
