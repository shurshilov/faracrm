import { useState, useCallback, useMemo } from 'react';
import {
  ActionIcon,
  Box,
  Combobox,
  Group,
  LoadingOverlay,
  Text,
  TextInput,
  Tooltip,
  useCombobox,
} from '@mantine/core';
import {
  IconStar,
  IconStarFilled,
  IconPlus,
  IconPhone,
  IconMail,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBrandInstagram,
  IconShoppingBag,
  IconMessageCircle,
  IconCamera,
  IconWorld,
  IconAddressBook,
  IconX,
  IconSend,
  IconPencil,
  IconCheck,
} from '@tabler/icons-react';
import { Contact, ContactType, ContactsWidgetProps } from './types';
import {
  useContactTypes,
  detectContactType,
  getContactTypeConfig,
} from './config';
import classes from './ContactsWidget.module.css';

// Маппинг иконок (tabler icon name → component)
const ICON_MAP: Record<string, React.ElementType> = {
  IconPhone,
  IconMail,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBrandInstagram,
  IconShoppingBag,
  IconMessageCircle,
  IconCamera,
  IconWorld,
  IconSend,
  // Легаси маппинг (для старых данных)
  phone: IconPhone,
  mail: IconMail,
  send: IconSend,
  'shopping-bag': IconShoppingBag,
  'message-circle': IconMessageCircle,
  camera: IconCamera,
};

function getIcon(iconName: string): React.ElementType {
  return ICON_MAP[iconName] || IconAddressBook;
}

/**
 * Виджет для управления контактами партнёра/пользователя.
 *
 * Типы контактов загружаются из API (таблица contact_type).
 */
export function ContactsWidget({
  name,
  value = [],
  onChange,
  allowedTypes,
  maxContacts,
  disabled = false,
  hidePrimary = false,
  loading = false,
  showTypeButton = false,
}: Omit<ContactsWidgetProps, 'label'> & {
  loading?: boolean;
  showTypeButton?: boolean;
}) {
  const [inputValue, setInputValue] = useState('');
  const [selectedType, setSelectedType] = useState<ContactType | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  // Загружаем типы контактов из БД
  const { contactTypes, isLoading: typesLoading } = useContactTypes();

  const combobox = useCombobox({
    onDropdownClose: () => combobox.resetSelectedOption(),
  });

  // Фильтруем типы если указаны allowedTypes
  const availableTypes = useMemo(() => {
    if (!allowedTypes) return contactTypes;
    return contactTypes.filter(t => allowedTypes.includes(t.name));
  }, [allowedTypes, contactTypes]);

  // Автоопределение типа при вводе
  const detectedType = useMemo(() => {
    if (!inputValue.trim() || contactTypes.length === 0) return null;
    const detected = detectContactType(inputValue, contactTypes);
    if (detected && allowedTypes && !allowedTypes.includes(detected)) {
      return null;
    }
    return detected;
  }, [inputValue, allowedTypes, contactTypes]);

  // Тип для добавления (выбранный или определённый)
  const typeToAdd = selectedType || detectedType;

  // Активные контакты (не удалённые)
  const activeContacts = useMemo(
    () => value.filter(c => !c._isDeleted),
    [value],
  );

  // Можно ли добавить ещё
  const canAdd = !maxContacts || activeContacts.length < maxContacts;

  // Добавить контакт
  const handleAdd = useCallback(() => {
    if (!inputValue.trim() || !typeToAdd || disabled || !canAdd) return;

    // Получаем id типа контакта для сохранения в БД
    const typeConfig = contactTypes.find(ct => ct.name === typeToAdd);

    const newContact: Contact = {
      contact_type: typeToAdd,
      contact_type_id: typeConfig?.id,
      name: inputValue.trim(),
      is_primary: activeContacts.length === 0,
      _isNew: true,
    };

    onChange([...value, newContact]);
    setInputValue('');
    setSelectedType(null);
  }, [
    inputValue,
    typeToAdd,
    disabled,
    canAdd,
    activeContacts.length,
    value,
    onChange,
  ]);

  // Удалить контакт
  const handleDelete = useCallback(
    (index: number) => {
      if (disabled) return;

      const updated = value
        .map((c, i) => {
          if (i !== index) return c;
          if (c._isNew) return null;
          return { ...c, _isDeleted: true };
        })
        .filter(Boolean) as Contact[];

      onChange(updated);
    },
    [disabled, value, onChange],
  );

  // Переключить основной контакт
  const handleTogglePrimary = useCallback(
    (index: number) => {
      if (disabled || hidePrimary) return;

      const contact = value[index];
      const updated = value.map((c, i) => {
        if (c.contact_type === contact.contact_type) {
          return { ...c, is_primary: i === index };
        }
        return c;
      });

      onChange(updated);
    },
    [disabled, hidePrimary, value, onChange],
  );

  // Начать редактирование
  const handleStartEdit = useCallback(
    (index: number) => {
      if (disabled) return;
      setEditingIndex(index);
      setEditValue(value[index].name);
    },
    [disabled, value],
  );

  // Сохранить редактирование
  const handleSaveEdit = useCallback(() => {
    if (editingIndex === null || !editValue.trim()) return;

    const updated = value.map((c, i) => {
      if (i !== editingIndex) return c;
      return { ...c, name: editValue.trim() };
    });

    onChange(updated);
    setEditingIndex(null);
    setEditValue('');
  }, [editingIndex, editValue, value, onChange]);

  // Отменить редактирование
  const handleCancelEdit = useCallback(() => {
    setEditingIndex(null);
    setEditValue('');
  }, []);

  // Обработка Enter
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && typeToAdd) {
      e.preventDefault();
      handleAdd();
    }
  };

  // Обработка Enter/Escape в режиме редактирования
  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  };

  return (
    <Box className={classes.container} pos="relative">
      <LoadingOverlay
        visible={typesLoading}
        zIndex={10}
        overlayProps={{ blur: 2 }}
      />

      {/* Input area */}
      {!disabled && canAdd && (
        <Box className={classes.inputArea}>
          <Box className={classes.inputWrapper}>
            {(showTypeButton || inputValue.trim()) && (
              <Combobox
                store={combobox}
                width={160}
                position="bottom-start"
                onOptionSubmit={val => {
                  setSelectedType(val as ContactType);
                  combobox.closeDropdown();
                }}>
                <Combobox.Target>
                  <ActionIcon
                    variant="light"
                    size="lg"
                    onClick={() => combobox.toggleDropdown()}
                    className={classes.typeButton}>
                    {typeToAdd ? (
                      (() => {
                        const config = getContactTypeConfig(
                          typeToAdd,
                          contactTypes,
                        );
                        const Icon = getIcon(config?.icon || '');
                        return <Icon size={18} />;
                      })()
                    ) : (
                      <IconPlus size={18} />
                    )}
                  </ActionIcon>
                </Combobox.Target>

                <Combobox.Dropdown>
                  <Combobox.Options>
                    {availableTypes.map(type => {
                      const Icon = getIcon(type.icon);
                      return (
                        <Combobox.Option
                          key={type.name}
                          value={type.name}
                          className={classes.typeOption}>
                          <Box className={classes.typeOptionIcon}>
                            <Icon size={16} />
                          </Box>
                          <Text size="sm">{type.label}</Text>
                        </Combobox.Option>
                      );
                    })}
                  </Combobox.Options>
                </Combobox.Dropdown>
              </Combobox>
            )}

            {/* Value input */}
            <TextInput
              className={classes.input}
              placeholder={
                typeToAdd
                  ? getContactTypeConfig(typeToAdd, contactTypes)
                      ?.placeholder || 'Введите значение...'
                  : 'Телефон, email, Telegram...'
              }
              value={inputValue}
              onChange={e => setInputValue(e.currentTarget.value)}
              onKeyDown={handleKeyDown}
              rightSection={
                inputValue &&
                typeToAdd && (
                  <ActionIcon
                    variant="filled"
                    color="blue"
                    size="sm"
                    onClick={handleAdd}>
                    <IconPlus size={14} />
                  </ActionIcon>
                )
              }
            />
          </Box>

          {/* Detected type hint */}
          {inputValue && detectedType && !selectedType && (
            <Box className={classes.detectedType}>
              {(() => {
                const config = getContactTypeConfig(detectedType, contactTypes);
                if (!config) return null;
                const Icon = getIcon(config.icon);
                return (
                  <>
                    <Icon size={14} />
                    <Text size="xs">{config.label}</Text>
                  </>
                );
              })()}
            </Box>
          )}
        </Box>
      )}

      {/* Contacts list */}
      {activeContacts.length > 0 && (
        <Box className={classes.listContainer}>
          {value.map((contact, index) => {
            if (contact._isDeleted) return null;

            const config = getContactTypeConfig(
              contact.contact_type,
              contactTypes,
            );
            const IconComponent = getIcon(config?.icon || '');
            const isEditing = editingIndex === index;

            return (
              <Box
                key={contact.id || `new-${index}`}
                className={`${classes.contactItem} ${contact._isNew ? classes.contactItemNew : ''} ${isEditing ? classes.contactItemEditing : ''}`}>
                <Box
                  className={classes.contactIcon}
                  data-type={contact.contact_type}>
                  <IconComponent size={14} />
                </Box>

                {isEditing ? (
                  <TextInput
                    className={classes.editInput}
                    size="xs"
                    value={editValue}
                    onChange={e => setEditValue(e.currentTarget.value)}
                    onKeyDown={handleEditKeyDown}
                    onBlur={handleSaveEdit}
                    autoFocus
                    rightSection={
                      <ActionIcon
                        size="xs"
                        variant="subtle"
                        color="green"
                        onClick={handleSaveEdit}>
                        <IconCheck size={12} />
                      </ActionIcon>
                    }
                  />
                ) : (
                  <>
                    <Text className={classes.contactValue}>{contact.name}</Text>

                    <Text className={classes.contactType}>
                      {config?.label || contact.contact_type}
                    </Text>

                    <Group className={classes.contactActions} gap={2}>
                      {!disabled && (
                        <Tooltip label="Редактировать" withArrow>
                          <ActionIcon
                            size="xs"
                            variant="subtle"
                            color="blue"
                            onClick={() => handleStartEdit(index)}>
                            <IconPencil size={12} />
                          </ActionIcon>
                        </Tooltip>
                      )}

                      {!hidePrimary && (
                        <Tooltip
                          label={
                            contact.is_primary ? 'Основной' : 'Сделать основным'
                          }
                          withArrow>
                          <ActionIcon
                            size="xs"
                            variant="subtle"
                            color={contact.is_primary ? 'yellow' : 'gray'}
                            onClick={() => handleTogglePrimary(index)}
                            disabled={disabled}>
                            {contact.is_primary ? (
                              <IconStarFilled size={12} />
                            ) : (
                              <IconStar size={12} />
                            )}
                          </ActionIcon>
                        </Tooltip>
                      )}

                      <Tooltip label="Удалить" withArrow>
                        <ActionIcon
                          size="xs"
                          variant="subtle"
                          color="red"
                          onClick={() => handleDelete(index)}
                          disabled={disabled}>
                          <IconX size={12} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </>
                )}
              </Box>
            );
          })}
        </Box>
      )}
    </Box>
  );
}
