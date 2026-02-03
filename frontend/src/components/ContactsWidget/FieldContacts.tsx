import { useContext, useEffect, useState } from 'react';
import { InputBase } from '@mantine/core';
import {
  FormFieldsContext,
  useFormContext,
} from '@/components/Form/FormContext';
import { FieldWrapper } from '@/components/Form/Fields/FieldWrapper';
import { LabelPosition } from '@/components/Form/FormSettingsContext';
import { ContactsWidget } from './ContactsWidget';
import { Contact, ContactType } from './types';
import { useParams } from 'react-router-dom';
import { useSearchQuery } from '@/services/api/crudApi';

interface FieldContactsProps {
  /** Имя поля в форме */
  name: string;
  /** Модель (передаётся автоматически из Form) */
  model?: string;
  /** Лейбл */
  label?: string;
  /** Позиция лейбла: 'left' (по умолчанию) или 'top' */
  labelPosition?: LabelPosition;
  /** Типы контактов для отображения */
  allowedTypes?: ContactType[];
  /** Максимальное количество */
  maxContacts?: number;
  /** Скрыть звёздочку основного */
  hidePrimary?: boolean;
  /**
   * Имя поля формы, из которого брать ID владельца контактов.
   * Например, parentField="partner_id" — контакты загружаются по partner_id клиента.
   * Если не указан — используется id текущей записи (поведение по умолчанию).
   */
  parentField?: string;
  /**
   * Модель владельца контактов (для определения relatedModel/relatedField).
   * Например, parentModel="partners" — используется когда contact_ids не является
   * полем текущей модели, а берётся из связанной модели.
   * Если не указан — берётся из fieldsServer[name].
   */
  parentModel?: string;
  /** Вложенные поля (игнорируются, нужны только для запроса) */
  children?: React.ReactNode;
}

/**
 * Кастомный компонент для One2many поля contact_ids.
 *
 * Заменяет стандартный FieldOne2many на красивый виджет ввода контактов.
 * Должен быть зарегистрирован в FieldComponents как FieldContacts.
 *
 * @example
 * В форме используется как обычный Field:
 * ```tsx
 * <Field name="contact_ids" widget="contacts" label="Контакты">
 *   <Field name="id" />
 *   <Field name="contact_type_id" />
 *   <Field name="name" />
 *   <Field name="is_primary" />
 * </Field>
 * ```
 */
export function FieldContacts({
  name,
  model,
  label,
  labelPosition,
  allowedTypes,
  maxContacts,
  hidePrimary,
  parentField,
  parentModel,
  children,
}: FieldContactsProps) {
  const form = useFormContext();
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const { id } = useParams<{ id: string }>();

  const displayLabel = label ?? name;

  // Определяем ID владельца контактов:
  // Если указан parentField — берём значение Many2one поля из формы (например partner_id)
  // Иначе — используем id текущей записи из URL
  const parentValue = parentField ? form.getValues()?.[parentField] : null;
  const ownerId: number | null = parentField
    ? (typeof parentValue === 'object' && parentValue !== null
        ? parentValue.id
        : typeof parentValue === 'number'
          ? parentValue
          : null)
    : (id ? Number(id) : null);

  // Определяем relatedField для фильтра запроса:
  // Если parentField указан — используем его как фильтр (partner_id)
  // Иначе — берём из метаданных сервера
  const relatedField = parentField
    ? parentField
    : (fieldsServer[name]?.relatedField || 'partner_id');

  // Определяем модель для запроса контактов:
  // Если parentModel указан — берём relatedModel из fieldsServer родительской модели
  // через parentModel + name. Иначе — из fieldsServer текущей модели.
  // Фоллбэк — 'contact'.
  const queryModel = fieldsServer[name]?.relatedModel || 'contact';

  // Локальное состояние для контактов
  const [contacts, setContacts] = useState<Contact[]>([]);

  // Запрос к связанной модели contact
  const { data, isFetching } = useSearchQuery(
    {
      model: queryModel,
      fields: ['id', 'contact_type_id', 'name', 'is_primary'],
      filter: [
        [relatedField, '=', ownerId!],
      ],
      limit: 100,
    },
    {
      skip: !ownerId,
      refetchOnMountOrArgChange: true,
    },
  );

  // Инициализация из данных запроса
  // Используем isFetching чтобы обновлять только когда данные реально загружены
  useEffect(() => {
    if (data?.data && !isFetching) {
      const initialContacts: Contact[] = data.data.map((item: any) => ({
        id: item.id,
        contact_type: item.contact_type_id?.name || item.contact_type_id,
        name: item.name,
        is_primary: item.is_primary || false,
        _isNew: false,
        _isDeleted: false,
      }));
      setContacts(initialContacts);
    }
  }, [data, isFetching]);

  // Сброс при смене записи или владельца
  useEffect(() => {
    setContacts([]);
  }, [id, ownerId]);

  const handleChange = (newContacts: Contact[]) => {
    setContacts(newContacts);

    // Собираем изменения для сохранения
    const created: any[] = [];
    const deleted: number[] = [];

    for (const contact of newContacts) {
      if (contact._isNew && !contact._isDeleted) {
        created.push({
          contact_type_id: contact.contact_type_id,
          name: contact.name,
          is_primary: contact.is_primary,
          [relatedField]: ownerId || 'VirtualId',
        });
      } else if (contact._isDeleted && contact.id) {
        deleted.push(contact.id);
      }
    }

    // Сохраняем изменения в служебное поле (как FieldOne2many)
    const changesFieldName = `_${name}`;
    form.setValues({
      [changesFieldName]: {
        created,
        deleted,
        fieldsServer: fieldsServer,
      },
    });
  };

  return (
    <FieldWrapper label={displayLabel} labelPosition={labelPosition}>
      {/* Hidden input для формы */}
      <InputBase
        display="none"
        readOnly
        key={form.key(name)}
        {...form.getInputProps(name)}
      />

      {/* Наш кастомный виджет */}
      <ContactsWidget
        name={name}
        value={contacts}
        onChange={handleChange}
        allowedTypes={allowedTypes}
        maxContacts={maxContacts}
        hidePrimary={hidePrimary}
        loading={isFetching}
      />
    </FieldWrapper>
  );
}
