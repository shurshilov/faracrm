import { useContext, useEffect, useState } from 'react';
import { InputBase, Text, Group } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconUserPlus } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
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
  useUpdateMutation,
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
  label,
  labelPosition,
  allowedTypes,
  maxContacts,
  hidePrimary,
  parentField,
}: FieldContactsProps) {
  const form = useFormContext();
  const { t } = useTranslation('common');
  const { fields: fieldsServer, isCreateForm } = useContext(FormFieldsContext);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [deleteBulk] = useDeleteBulkMutation();
  const [create] = useCreateMutation();
  const [update] = useUpdateMutation();
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
    : // В режиме создания записи id из URL брать НЕЛЬЗЯ: форма создания может
      // быть открыта в попапе поверх маршрута с чужим id (…/leads/5 → попап
      // создания партнёра). Иначе новый партнёр «унаследует» контакты записи 5.
      isCreateForm
      ? null
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
      fields: ['id', 'contact_type_id', 'value', 'name', 'is_primary'],
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
        // Фоллбэк на name — легаси-записи, созданные до рефактора name→value
        // (миграция PartnersApp._migration_contact_name_to_value заполняет
        // value на старте бэка, но до неё значение лежит только в name).
        value: item.value ?? item.name ?? '',
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
    // Правки уже сохранённых контактов уходят в update прямо здесь, поэтому
    // флаг _isDirty в состоянии не держим — иначе тот же PUT полетел бы
    // повторно на каждое следующее изменение виджета.
    setContacts(newContacts.map(c => ({ ...c, _isDirty: false })));

    // Собираем изменения для сохранения
    const created: any[] = [];
    const updated: { id: number; value: string }[] = [];
    const deleted: number[] = [];

    for (const contact of newContacts) {
      if (contact._isNew && !contact._isDeleted) {
        created.push({
          contact_type_id: contact.contact_type_id,
          // value — реальное значение (по нему матчинг на бэке).
          value: contact.value,
          // name в модели NOT NULL и означает описание; при создании из
          // виджета описания нет — кладём значение (так же делает бэк в
          // Contact.create_with_partner).
          name: contact.value,
          is_primary: contact.is_primary,
        });
      } else if (contact._isDeleted && contact.id) {
        deleted.push(contact.id);
      } else if (contact._isDirty && contact.id) {
        updated.push({ id: contact.id, value: contact.value });
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
      // unwrap обязателен: без него RTK резолвит промис объектом {error},
      // catch не срабатывает, и отказ бэка (валидация, права) выглядит как
      // успешное сохранение — контакт есть на экране и нет в БД.
      for (const item of created) {
        await create({
          model: 'contact',
          values: { ...item, [relatedField]: ownerId },
        }).unwrap();
      }
      for (const item of updated) {
        await update({
          model: 'contact',
          id: item.id,
          values: { value: item.value },
        }).unwrap();
      }
    } catch (error) {
      console.error('Failed to save contact:', error);
      notifications.show({
        color: 'red',
        message: t('contacts.saveFailed'),
      });
    }
  };

  // ── Чат с партнёром ─────────────────────────────────────────────────
  // Чат в системе — на уровне партнёра (chat_member.partner_id), а контакт
  // это канал. Поэтому иконка одна на виджет и открывает чат с владельцем.
  // Показываем только если владелец-партнёр известен И есть хотя бы один
  // контакт (без канала чат бессмысленен). Только для партнёров.
  const activeContactsCount = contacts.filter(c => !c._isDeleted).length;
  // Кнопка чата из виджета «Контакты» отключена: она создавала ЛИЧНЫЙ (direct)
  // чат с партнёром, что теперь запрещено (модель 1:1 — переписка с клиентом в
  // едином ГРУППОВОМ чате партнёра, см. вкладку «Чат» в форме + create-правило
  // на бэке). onOpenChat остаётся, но не показывается.
  void activeContactsCount;
  const canOpenChat = false;

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

  // Контакт в модели принадлежит партнёру (contact.partner_id). На лиде/
  // заказе виджет привязан к partner_id (parentField): телефон должен
  // сохраниться у ПАРТНЁРА, а не у лида (в contact нет lead_id — вешать
  // некуда). Пока партнёр не выбран, класть контакт некуда — поэтому не даём
  // вводить и просим сначала выбрать партнёра, иначе номер молча потеряется.
  // На форме партнёра/юзера parentField нет → виджет виден всегда.
  const ownerMissing = !!parentField && !ownerId;

  return (
    <FieldWrapper label={displayLabel} labelPosition={labelPosition}>
      {/* Hidden input для формы */}
      <InputBase
        display="none"
        readOnly
        key={form.key(name)}
        {...form.getInputProps(name)}
      />

      {ownerMissing ? (
        <Group
          gap="sm"
          wrap="nowrap"
          align="center"
          style={{
            padding: '12px 14px',
            border: '1px dashed var(--mantine-color-default-border)',
            borderRadius: 'var(--mantine-radius-md)',
            background: 'var(--mantine-color-default-hover)',
          }}>
          <IconUserPlus
            size={22}
            stroke={1.5}
            color="var(--mantine-color-dimmed)"
            style={{ flexShrink: 0 }}
          />
          <div>
            <Text size="sm" fw={500}>
              {t('contacts.selectPartnerFirst')}
            </Text>
            <Text size="xs" c="dimmed">
              {t('contacts.selectPartnerHint')}
            </Text>
          </div>
        </Group>
      ) : (
        /* Наш кастомный виджет. Иконка «открыть чат» рендерится в конце
           инпута добавления контакта (см. ContactsWidget). */
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
      )}
    </FieldWrapper>
  );
}

FieldContacts.displayName = 'FieldContacts';
