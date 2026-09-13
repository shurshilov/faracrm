/**
 * Вкладки «Реквизиты» и «Банк» в форме партнёра — из модуля contract.
 *
 * Поля живут в PartnerContractMixin (backend/base/crm/contract/models/
 * partner_ext.py), ИНН — базовое поле Partner.vat. У полей ИНН и БИК —
 * кнопка «Заполнить» (проп autofill у FieldChar): по нажатию бэк отдаёт
 * название, тип лица, КПП/ОГРН/ОКПО и адрес по ИНН или банк и корр. счёт
 * по БИК, форма их подставляет, сохраняет пользователь как обычно.
 * Источник данных — провайдер реквизитов (модуль dadata).
 *
 * Подключение: fara_contract/index.ts (side-effect импорт) и
 * config/models.ts (modelsConfig.partners.extensions). Прямые
 * FieldChar/FieldSelection вместо <Field> — как во всех расширениях
 * (см. комментарий в ViewFormSale.tsx).
 */

import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FieldText } from '@/components/Form/Fields/FieldText';
import { FormRow } from '@/components/Form/Layout';
import { IconBuildingBank, IconFileCertificate } from '@tabler/icons-react';
import { registerFormTab } from '@/shared/extensions';
import { useLazyBankByBicQuery, useLazyPartyByInnQuery } from '../api';

export function PartnerRequisitesTab() {
  const [partyByInn] = useLazyPartyByInnQuery();
  return (
    <>
      <FormRow cols={2}>
        <FieldSelection name="partner_type" label="Тип лица" />
        <FieldChar
          name="vat"
          label="ИНН"
          autofill={{
            label: 'Заполнить по ИНН',
            fetch: inn => partyByInn(inn).unwrap(),
          }}
        />
        <FieldChar name="kpp" label="КПП" />
        <FieldChar name="ogrn" label="ОГРН" />
        <FieldChar name="okpo" label="ОКПО" />
      </FormRow>
      <FieldText name="address" label="Юридический адрес" rows={2} />
    </>
  );
}

export function PartnerBankTab() {
  const [bankByBic] = useLazyBankByBicQuery();
  return (
    <FormRow cols={2}>
      <FieldChar
        name="bank_bic"
        label="БИК"
        autofill={{
          label: 'Заполнить по БИК',
          fetch: bic => bankByBic(bic).unwrap(),
        }}
      />
      <FieldChar name="bank_name" label="Банк" />
      <FieldChar name="bank_account" label="Расчётный счёт" />
      <FieldChar name="bank_corr_account" label="Корр. счёт" />
    </FormRow>
  );
}

registerFormTab(
  'partners',
  {
    name: 'requisites',
    label: 'Реквизиты',
    icon: <IconFileCertificate size={16} />,
    component: PartnerRequisitesTab,
  },
  ['partner_type', 'vat', 'kpp', 'ogrn', 'okpo', 'address'],
);

registerFormTab(
  'partners',
  {
    name: 'bank',
    label: 'Банк',
    icon: <IconBuildingBank size={16} />,
    component: PartnerBankTab,
  },
  ['bank_bic', 'bank_name', 'bank_account', 'bank_corr_account'],
);
