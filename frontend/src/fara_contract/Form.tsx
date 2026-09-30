import { useContext } from 'react';
import type { ContractRecord as Contract } from '@/types/records';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import {
  FormFieldsContext,
  useFormContext,
} from '@/components/Form/FormContext';
import { ViewFormProps } from '@/route/type';
import {
  FormHeader,
  FormTabs,
  FormTab,
  FormRow,
  FormSection,
} from '@/components/Form/Layout';
import { Badge, Group, Stack, Text, Title } from '@mantine/core';
import {
  IconCalendar,
  IconCheck,
  IconCircleFilled,
  IconFileText,
  IconNote,
  IconShoppingCart,
  IconX,
} from '@tabler/icons-react';

/** «2026-05-27» / Date → «27.05.2026»; пусто/невалидно → «—». */
function formatRuDate(value: unknown): string {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(String(value));
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('ru-RU');
}

/**
 * Найти подпись для значения Selection-поля по options-кортежам
 * из field-metadata (формат backend'а: [[code, label], ...]).
 * Fallback — сам code, если не нашли (или backend ещё не отдал
 * метадату).
 */
function selectionLabel(
  value: unknown,
  options: unknown,
): string {
  if (value == null || value === '') return '';
  const code = String(value);
  if (Array.isArray(options)) {
    for (const opt of options) {
      if (Array.isArray(opt) && String(opt[0]) === code) {
        return String(opt[1] ?? code);
      }
    }
  }
  return code;
}

/**
 * «Карточка» договора в шапке формы — только чтение.
 *
 * Отображает номер, контрагента/тип/компанию, срок действия и статусы
 * (подписан, печать, активен). Сами поля редактируются во вкладках
 * («Общее», «Сроки и статус»), а это — summary для быстрого взгляда.
 *
 * Чтение значений: form.getValues() в mode='uncontrolled' возвращает
 * снимок; перерендеривается вместе с родителем при инициализации
 * формы (form.initialize + setChildrenNew). Этого достаточно для
 * существующих записей — после save форма перечитывается с бэка.
 * Live-обновление при наборе в табе не предусмотрено намеренно
 * (минимум магии; добавим watch, если потребуется).
 */
function ContractHeaderSummary() {
  const form = useFormContext();
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const v = (form.getValues() ?? {}) as Partial<Contract> & {
    partner_id?: { id?: number; name?: string };
    company_id?: { id?: number; name?: string };
  };

  // Подпись типа договора — берём из options самого поля
  // (backend отдаёт fieldsServer.type.options = [[code, label], ...]),
  // чтобы не дублировать словарь и не разъезжаться с моделью.
  const typeLabel = selectionLabel(
    v.type,
    (fieldsServer as Record<string, any>)?.type?.options,
  );

  // partner · type · company — только заполненное.
  const subtitleParts = [v.partner_id?.name, typeLabel, v.company_id?.name]
    .filter(Boolean)
    .join(' · ');

  const isActive = v.active !== false; // default true для новой записи

  return (
    <Stack gap="xs">
      <Title order={4}>
        Договор{v.name ? ` № ${v.name}` : ''}
      </Title>

      {subtitleParts && <Text size="sm">{subtitleParts}</Text>}

      <Text size="sm">
        С {formatRuDate(v.date_start)} по {formatRuDate(v.date_end)}
      </Text>

      <Group gap="xs" mt={4}>
        {/* Подписан / Печать — зелёный filled если стоит, серый light если нет. */}
        <Badge
          variant={v.signed ? 'filled' : 'light'}
          color={v.signed ? 'green' : 'gray'}
          leftSection={
            v.signed ? <IconCheck size={12} /> : <IconX size={12} />
          }>
          Подписан
        </Badge>
        <Badge
          variant={v.stamp ? 'filled' : 'light'}
          color={v.stamp ? 'green' : 'gray'}
          leftSection={
            v.stamp ? <IconCheck size={12} /> : <IconX size={12} />
          }>
          Печать
        </Badge>
        {/* Активен — отдельный зелёный/серый «индикатор-точка». */}
        <Badge
          variant={isActive ? 'filled' : 'light'}
          color={isActive ? 'green' : 'gray'}
          leftSection={<IconCircleFilled size={10} />}>
          {isActive ? 'Активен' : 'Неактивен'}
        </Badge>
      </Group>
    </Stack>
  );
}

/**
 * Форма договора.
 *
 * Layout:
 *  - FormHeader: ContractHeaderSummary (read-only карточка) +
 *    smart-button «Заказы» (навигация в /sales с фильтром по contract_id).
 *  - FormTabs: 3 вкладки для редактирования.
 *    Каждая вкладка обёрнута в FormSection (paper-контейнер с border'ом).
 *
 * Принцип: хедер показывает суммарную информацию для чтения, всё
 * редактирование — во вкладках. Поля name/type/partner/company/dates/
 * signed/stamp/active дублируются в табах (как редактируемые).
 * Примечания (notes) — только во вкладке, в хедер не выносятся
 * (длинный текст ломал бы summary).
 */
export function ViewFormContract(props: ViewFormProps) {
  // Печатные формы договора даёт кнопка «Печать» тулбара формы (шаблоны
  // report_template на модели contract), подключать её здесь не нужно.
  return (
    <Form<Contract> model="contract" {...props}>
      <FormHeader
        title={<ContractHeaderSummary />}
        actions={
          <Field
            name="sale_ids"
            widget="x2mButton"
            label="Заказы"
            icon={<IconShoppingCart size={18} />}
            color="blue"
          />
        }>
        {/* children пусто — всё внутри title + actions slot */}
        <></>
      </FormHeader>

      <FormTabs defaultTab="general">
        <FormTab
          name="general"
          label="Общее"
          icon={<IconFileText size={16} />}>
          <FormSection>
            <FormRow cols={2}>
              <Field name="name" label="Номер договора" />
              <Field name="type" label="Тип" />
            </FormRow>
            <FormRow cols={2}>
              <Field name="partner_id" label="Контрагент" />
              <Field name="company_id" label="Компания" />
            </FormRow>
          </FormSection>
        </FormTab>

        <FormTab
          name="terms"
          label="Сроки и статус"
          icon={<IconCalendar size={16} />}>
          <FormSection>
            <FormRow cols={2}>
              <Field name="date_start" label="Дата начала" />
              <Field name="date_end" label="Дата окончания" />
            </FormRow>
            <FormRow cols={3}>
              <Field name="signed" label="Подписан" />
              <Field name="stamp" label="Печать" />
              <Field name="active" label="Активен" />
            </FormRow>
          </FormSection>
        </FormTab>

        <FormTab name="notes" label="Примечания" icon={<IconNote size={16} />}>
          <FormSection>
            <Field name="notes" label="Примечания" />
          </FormSection>
        </FormTab>
      </FormTabs>
    </Form>
  );
}
