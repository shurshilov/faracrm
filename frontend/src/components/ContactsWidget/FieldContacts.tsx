import { useContext, useEffect, useState } from 'react';
import { InputBase } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  FormFieldsContext,
  useFormContext,
} from '@/components/Form/FormContext';
import { FieldWrapper } from '@/components/Form/Fields/FieldWrapper';
import { LabelPosition } from '@/components/Form/FormSettingsContext';
import { ContactsWidget } from './ContactsWidget';
import { Contact, ContactType } from './types';
import { useNavigate, useParams } from 'react-router-dom';
import {
  useCreateMutation,
  useDeleteBulkMutation,
  useSearchQuery,
} from '@/services/api/crudApi';
import { useCreateChatMutation } from '@/services/api/chat';

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
   * Имя поля ФОРМЫ, из которого брать ID владельца контактов (партнёра).
   * Например parentField="partner_id" (на заказе) или "parent_id" (на лиде).
   * По нему же открывается чат с партнёром.
   * Поле модели contact для фильтра/создания берётся ОТДЕЛЬНО — из метаданных
   * One2many (relatedField), поэтому имя поля-владельца в форме и имя FK в
   * модели contact могут отличаться (на лиде: parent_id ↔ contact.partner_id).
   * Если не указан — используется id текущей записи из URL.
   */
  parentField?: string;
  /**
   * Модель владельца контактов (для определения relatedModel/relatedField).
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
  const navigate = useNavigate();
  const [deleteBulk] = useDeleteBulkMutation();
  const [create, { isLoading }] = useCreateMutation();
  const [createChat, { isLoading: creatingChat }] = useCreateChatMutation();

  const displayLabel = label ?? name;

  // ID владельца контактов:
  // Если указан parentField — берём значение Many2one поля из формы
  // (partner_id на заказе / parent_id на лиде). Иначе — id текущей записи.
  const parentValue = parentField ? form.getValues()?.[parentField] : null;
  const ownerId: number | null = parentField
    ? typeof parentValue === 'object' && parentValue !== null
      ? parentValue.id
      : typeof parentValue === 'number'
        ? parentValue
        : null
    : id
      ? Number(id)
      : null;

  // Поле модели contact для фильтра/создания (partner_id / user_id) — берём
  // из метаданных One2many (relation_table_field), а НЕ из parentField:
  // имя поля-владельца в форме может отличаться от имени FK в contact
  // (на лиде владелец в parent_id, а контакт фильтруется по partner_id).
  const relatedField = fieldsServer[name]?.relatedField || 'partner_id';

  // Модель для запроса контактов (фоллбэк — 'contact').
  const queryModel = fieldsServer[name]?.relatedModel || 'contact';

  // Локальное состояние для контактов
  const [contacts, setContacts] = useState<Contact[]>([]);

  // Запрос к связанной модели contact
  const { data, isFetching } = useSearchQuery(
    {
      model: queryModel,
      fields: ['id', 'contact_type_id', 'name', 'is_primary'],
      filter: [[relatedField, '=', ownerId!]],
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

  const handleChange = async (newContacts: Contact[]) => {
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
        });
      } else if (contact._isDeleted && contact.id) {
        deleted.push(contact.id);
      }
    }

    // Нет владельца (новая запись ещё не сохранена) — откладываем
    // API-вызовы до момента создания родителя.
    if (!ownerId) {
      form.setValues({
        [`_${name}`]: { created, deleted, relatedField },
      });
      return;
    }

    // Владелец есть — работаем через API сразу.
    try {
      if (deleted.length > 0) {
        await deleteBulk({ model: 'contact', ids: deleted }).unwrap();
      }
      for (const item of created) {
        await create({
          model: 'contact',
          values: { ...item, [relatedField]: ownerId },
        });
      }
    } catch (error) {
      console.error('Failed to delete or create contact:', error);
    }
  };

  // ── Чат с партнёром ─────────────────────────────────────────────────
  // Чат в системе — на уровне партнёра (chat_member.partner_id), а контакт
  // это канал. Поэтому иконка одна на виджет и открывает чат с владельцем.
  // Показываем только если владелец-партнёр известен И есть хотя бы один
  // контакт (без канала чат бессмысленен). Только для партнёров.
  const activeContactsCount = contacts.filter(c => !c._isDeleted).length;
  const canOpenChat =
    !!ownerId && activeContactsCount > 0 && relatedField === 'partner_id';

  const handleOpenChat = async () => {
    if (!ownerId) return;
    try {
      // /chats делает get-or-create, поэтому повторный клик откроет тот же чат.
      const res = await createChat({
        chat_type: 'direct',
        user_ids: [],
        partner_ids: [ownerId],
      }).unwrap();

      const params = new URLSearchParams();
      // Передаём is_internal, чтобы ChatPage загрузил список с этим чатом
      // и ?open смог его найти (партнёрский чат — is_internal=false).
      if (res.data.is_internal !== undefined) {
        params.set('is_internal', String(res.data.is_internal));
      }
      params.set('open', String(res.data.id));
      navigate(`/chat?${params.toString()}`);
    } catch {
      notifications.show({
        color: 'red',
        message: 'Не удалось открыть чат',
      });
    }
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

      {/* Наш кастомный виджет. Иконка «открыть чат» рендерится в конце
          инпута добавления контакта (см. ContactsWidget). */}
      <ContactsWidget
        name={name}
        value={contacts}
        onChange={handleChange}
        allowedTypes={allowedTypes}
        maxContacts={maxContacts}
        hidePrimary={hidePrimary}
        loading={isFetching}
        canOpenChat={canOpenChat}
        onOpenChat={handleOpenChat}
        chatLoading={creatingChat}
      />
    </FieldWrapper>
  );
}

FieldContacts.displayName = 'FieldContacts';
