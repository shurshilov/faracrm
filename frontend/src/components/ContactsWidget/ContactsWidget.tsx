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
  IconSend,
  IconShoppingBag,
  IconMessageCircle,
  IconCamera,
  IconAddressBook,
  IconX,
} from '@tabler/icons-react';
import { Contact, ContactType, ContactsWidgetProps } from './types';
import {
  CONTACT_TYPE_CONFIG,
  detectContactType,
  getAllContactTypes,
  getContactTypeConfig,
} from './config';
import classes from './ContactsWidget.module.css';

// Маппинг иконок
const ICON_MAP: Record<string, React.ElementType> = {
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
 * Особенности:
 * - Автоопределение типа контакта при вводе
 * - Единый инпут для добавления
 * - Пометка основного контакта
 * - Soft delete (помечает как удалённые)
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

  const combobox = useCombobox({
    onDropdownClose: () => combobox.resetSelectedOption(),
  });

  // Фильтруем типы если указаны allowedTypes
  const availableTypes = useMemo(() => {
    const allTypes = getAllContactTypes();
    if (!allowedTypes) return allTypes;
    return allTypes.filter(t => allowedTypes.includes(t.name));
  }, [allowedTypes]);

  // Автоопределение типа при вводе
  const detectedType = useMemo(() => {
    if (!inputValue.trim()) return null;
    const detected = detectContactType(inputValue);
    // Если тип не в списке доступных, возвращаем null
    if (detected && allowedTypes && !allowedTypes.includes(detected)) {
      return null;
    }
    return detected;
  }, [inputValue, allowedTypes]);

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

    const newContact: Contact = {
      contact_type: typeToAdd,
      name: inputValue.trim(),
      is_primary: activeContacts.length === 0, // Первый контакт — основной
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
          // Если это новый контакт — удаляем полностью
          if (c._isNew) return null;
          // Иначе помечаем как удалённый
          return { ...c, _isDeleted: true };
        })
        .filter(Boolean) as Contact[];

      onChange(updated);
    },
    [disabled, value, onChange],
  );

  // Восстановить удалённый контакт
  const handleRestore = useCallback(
    (index: number) => {
      if (disabled) return;

      const updated = value.map((c, i) => {
        if (i !== index) return c;
        return { ...c, _isDeleted: false };
      });

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
        // Сбрасываем is_primary для контактов того же типа
        if (c.contact_type === contact.contact_type) {
          return { ...c, is_primary: i === index };
        }
        return c;
      });

      onChange(updated);
    },
    [disabled, hidePrimary, value, onChange],
  );

  // Обработка Enter
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && typeToAdd) {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <Box className={classes.container} pos="relative">
      <LoadingOverlay
        // visible={loading}
        zIndex={10}
        overlayProps={{ blur: 2 }}
      />

      {/* Input area - всегда сверху */}
      {!disabled && canAdd && (
        <Box className={classes.inputArea}>
          <Box className={classes.inputWrapper}>
            {/* Type selector - показываем если есть текст или showTypeButton */}
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
                        const config = getContactTypeConfig(typeToAdd);
                        const Icon = getIcon(config.icon);
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
                  ? getContactTypeConfig(typeToAdd).placeholder
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
                const config = getContactTypeConfig(detectedType);
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

            const config = getContactTypeConfig(contact.contact_type);
            const IconComponent = getIcon(config.icon);

            return (
              <Box
                key={contact.id || `new-${index}`}
                className={`${classes.contactItem} ${contact._isNew ? classes.contactItemNew : ''}`}>
                <Box
                  className={classes.contactIcon}
                  data-type={contact.contact_type}>
                  <IconComponent size={14} />
                </Box>

                <Text className={classes.contactValue}>{contact.name}</Text>

                <Text className={classes.contactType}>{config.label}</Text>

                <Group className={classes.contactActions} gap={2}>
                  {/* Primary toggle */}
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

                  {/* Delete */}
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
              </Box>
            );
          })}
        </Box>
      )}
    </Box>
  );
}
