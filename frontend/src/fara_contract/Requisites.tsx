/**
 * Общие куски вкладок «Реквизиты» и «Банк» партнёра и компании — фронтовая
 * пара RequisitesMixin (backend/base/crm/contract/models/requisites_ext.py):
 * имена полей у обеих моделей одни. Сами вкладки регистрируют
 * extensions/ViewFormPartner.tsx и extensions/ViewFormCompany.tsx (у
 * компании сверх набора — подписанты счёта, у партнёра — дата рождения,
 * паспорт и адрес доставки, PartnerRequisitesMixin там же на бэке).
 *
 * Кнопка «Заполнить» (проп autofill у FieldChar): по ИНН бэк отдаёт
 * название, тип лица, КПП/ОГРН/ОКПО и адрес, по БИК — банк и корр. счёт;
 * форма подставляет их, сохраняет пользователь как обычно. Источник —
 * провайдер реквизитов (модуль dadata).
 */

import { useState } from 'react';
import { FieldChar, FieldAutofill } from '@/components/Form/Fields/FieldChar';
import { FieldDate } from '@/components/Form/Fields/FieldDate';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FieldText } from '@/components/Form/Fields/FieldText';
import { useFormContext } from '@/components/Form/FormContext';
import { FormRow, FormSection } from '@/components/Form/Layout';
import {
  IconBuildingBank,
  IconFileCertificate,
  IconMapPin,
} from '@tabler/icons-react';
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

/** Тип лица живьём. Форма в mode='uncontrolled': значение читаем снимком
 *  из getValues, а form.watch только перерисовывает при смене (хук, зовётся
 *  во время рендера — как enabledBy у FieldProgress). */
function useLegalType(): string | null | undefined {
  const form = useFormContext();
  const [, rerender] = useState(0);
  form.watch('legal_type', () => rerender(n => n + 1));
  return form.getValues()?.legal_type;
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

/** Только у партнёра (PartnerRequisitesMixin). */
export const PARTNER_REQUISITES_FIELDS = [
  'birth_date',
  'passport',
  'address_delivery',
];

/**
 * Секции вкладки: регистрационные данные (тип лица, ИНН…; у партнёра,
 * пока он не юрлицо, ещё дата рождения и паспорт), адреса (адрес
 * доставки — только партнёр).
 */
export function RequisitesFields({ partner = false }: { partner?: boolean }) {
  const innAutofill = useInnAutofill();
  const legalType = useLegalType();
  return (
    <>
      <FormSection
        title="Регистрационные данные"
        icon={<IconFileCertificate size={18} />}>
        <FormRow cols={2}>
          <FieldSelection name="legal_type" label="Тип лица" />
          <FieldChar name="vat" label="ИНН" autofill={innAutofill} />
          <FieldChar name="kpp" label="КПП" />
          <FieldChar name="ogrn" label="ОГРН" />
          <FieldChar name="okpo" label="ОКПО" />
        </FormRow>
        {partner && legalType !== 'company' && (
          <FormRow cols={2}>
            <FieldDate name="birth_date" label="Дата рождения" />
            <FieldChar name="passport" label="№ паспорта" />
          </FormRow>
        )}
      </FormSection>
      <FormSection title="Адреса" icon={<IconMapPin size={18} />}>
        <FieldText name="address" label="Юридический адрес" rows={2} />
        {partner && (
          <FieldText name="address_delivery" label="Адрес доставки" rows={2} />
        )}
      </FormSection>
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
