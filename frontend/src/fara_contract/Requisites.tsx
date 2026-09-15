/**
 * Общие куски вкладок «Реквизиты» и «Банк» партнёра и компании — фронтовая
 * пара RequisitesMixin (backend/base/crm/contract/models/requisites_ext.py):
 * имена полей у обеих моделей одни. Сами вкладки регистрируют
 * extensions/ViewFormPartner.tsx и extensions/ViewFormCompany.tsx (у
 * компании сверх набора — подписанты счёта).
 *
 * Кнопка «Заполнить» (проп autofill у FieldChar): по ИНН бэк отдаёт
 * название, тип лица, КПП/ОГРН/ОКПО и адрес, по БИК — банк и корр. счёт;
 * форма подставляет их, сохраняет пользователь как обычно. Источник —
 * провайдер реквизитов (модуль dadata).
 */

import { FieldChar, FieldAutofill } from '@/components/Form/Fields/FieldChar';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FieldText } from '@/components/Form/Fields/FieldText';
import { FormRow } from '@/components/Form/Layout';
import { IconBuildingBank } from '@tabler/icons-react';
import { registerFormTab } from '@/shared/extensions';
import { useLazyBankByBicQuery, useLazyPartyByInnQuery } from './api';

function useInnAutofill(): FieldAutofill {
  const [partyByInn] = useLazyPartyByInnQuery();
  return {
    label: 'Заполнить по ИНН',
    fetch: inn => partyByInn(inn).unwrap(),
  };
}

function useBicAutofill(): FieldAutofill {
  const [bankByBic] = useLazyBankByBicQuery();
  return {
    label: 'Заполнить по БИК',
    fetch: bic => bankByBic(bic).unwrap(),
  };
}

/** Поля вкладки «Реквизиты» — для registerFormTab. */
export const REQUISITES_FIELDS = [
  'legal_type',
  'vat',
  'kpp',
  'ogrn',
  'okpo',
  'address',
];

export function RequisitesFields() {
  const innAutofill = useInnAutofill();
  return (
    <>
      <FormRow cols={2}>
        <FieldSelection name="legal_type" label="Тип лица" />
        <FieldChar name="vat" label="ИНН" autofill={innAutofill} />
        <FieldChar name="kpp" label="КПП" />
        <FieldChar name="ogrn" label="ОГРН" />
        <FieldChar name="okpo" label="ОКПО" />
      </FormRow>
      <FieldText name="address" label="Юридический адрес" rows={2} />
    </>
  );
}

export function BankTab() {
  const bicAutofill = useBicAutofill();
  return (
    <FormRow cols={2}>
      <FieldChar name="bank_bic" label="БИК" autofill={bicAutofill} />
      <FieldChar name="bank_name" label="Банк" />
      <FieldChar name="bank_account" label="Расчётный счёт" />
      <FieldChar name="bank_corr_account" label="Корр. счёт" />
    </FormRow>
  );
}

/** Вкладка «Банк» одинакова у обеих моделей — регистрируется одной строкой. */
export function registerBankTab(model: string) {
  registerFormTab(
    model,
    {
      name: 'bank',
      label: 'Банк',
      icon: <IconBuildingBank size={16} />,
      component: BankTab,
    },
    ['bank_bic', 'bank_name', 'bank_account', 'bank_corr_account'],
  );
}
