import { useState, useEffect } from 'react';
import {
  Modal,
  Text,
  Button,
  Stack,
  Group,
  ThemeIcon,
  Box,
  List,
} from '@mantine/core';
import {
  IconShieldOff,
  IconLock,
  IconAlertTriangle,
  IconForms,
} from '@tabler/icons-react';
import { apiErrorEmitter, ApiError, ValidationErrorItem } from './errorEvents';

// Встроенные переводы (без зависимости от i18n)
const TRANSLATIONS: Record<
  string,
  Record<string, { title: string; description: string }>
> = {
  ru: {
    ACCESS_DENIED: {
      title: 'Доступ запрещён',
      description: 'У вас нет доступа к этому ресурсу.',
    },
    PERMISSION_DENIED: {
      title: 'Недостаточно прав',
      description: 'У вас нет прав для выполнения этого действия.',
    },
    ADMIN_REQUIRED: {
      title: 'Требуются права администратора',
      description: 'Только администраторы чата могут выполнить это действие.',
    },
    CANNOT_ADD_TO_DIRECT_CHAT: {
      title: 'Невозможно добавить участника',
      description: 'В личный чат нельзя добавлять участников.',
    },
    CANNOT_REMOVE_FROM_DIRECT_CHAT: {
      title: 'Невозможно удалить участника',
      description: 'Из личного чата нельзя удалять участников.',
    },
    CANNOT_LEAVE_DIRECT_CHAT: {
      title: 'Невозможно покинуть чат',
      description: 'Личный чат нельзя покинуть.',
    },
    CANNOT_EDIT_DIRECT_CHAT: {
      title: 'Невозможно редактировать чат',
      description: 'Личные чаты нельзя редактировать.',
    },
    MEMBER_NOT_FOUND: {
      title: 'Участник не найден',
      description: 'Указанный участник не найден в этом чате.',
    },
    NOT_FOUND: {
      title: 'Не найдено',
      description: 'Запрашиваемый ресурс не найден.',
    },
    EMPTY_MESSAGE: {
      title: 'Пустое сообщение',
      description: 'Введите текст сообщения или прикрепите файл.',
    },
    VALIDATION_ERROR: {
      title: 'Ошибка валидации',
      description: 'Проверьте правильность заполнения полей:',
    },
    UNKNOWN: {
      title: 'Ошибка',
      description: 'Произошла непредвиденная ошибка. Попробуйте ещё раз.',
    },
  },
  en: {
    ACCESS_DENIED: {
      title: 'Access Denied',
      description: "You don't have access to this resource.",
    },
    PERMISSION_DENIED: {
      title: 'Permission Denied',
      description: "You don't have permission to perform this action.",
    },
    ADMIN_REQUIRED: {
      title: 'Admin Rights Required',
      description: 'Only chat administrators can perform this action.',
    },
    CANNOT_ADD_TO_DIRECT_CHAT: {
      title: 'Cannot Add Member',
      description: 'You cannot add members to a direct chat.',
    },
    CANNOT_REMOVE_FROM_DIRECT_CHAT: {
      title: 'Cannot Remove Member',
      description: 'You cannot remove members from a direct chat.',
    },
    CANNOT_LEAVE_DIRECT_CHAT: {
      title: 'Cannot Leave Chat',
      description: 'You cannot leave a direct chat.',
    },
    CANNOT_EDIT_DIRECT_CHAT: {
      title: 'Cannot Edit Chat',
      description: 'Direct chats cannot be edited.',
    },
    MEMBER_NOT_FOUND: {
      title: 'Member Not Found',
      description: 'The specified member was not found in this chat.',
    },
    NOT_FOUND: {
      title: 'Not Found',
      description: 'The requested resource was not found.',
    },
    EMPTY_MESSAGE: {
      title: 'Empty Message',
      description: 'Please enter a message or attach a file.',
    },
    VALIDATION_ERROR: {
      title: 'Validation Error',
      description: 'Please check the following fields:',
    },
    UNKNOWN: {
      title: 'Error',
      description: 'An unexpected error occurred. Please try again.',
    },
  },
};

// Переводы сообщений валидации Pydantic
const VALIDATION_MESSAGES: Record<string, Record<string, string>> = {
  ru: {
    'Field required': 'Обязательное поле',
    missing: 'Обязательное поле',
    'value_error.missing': 'Обязательное поле',
    string_too_short: 'Слишком короткое значение',
    string_too_long: 'Слишком длинное значение',
    'value_error.email': 'Некорректный email',
    'type_error.integer': 'Должно быть числом',
    'type_error.float': 'Должно быть числом',
    'type_error.none.not_allowed': 'Поле не может быть пустым',
  },
  en: {
    'Field required': 'Required field',
    missing: 'Required field',
    'value_error.missing': 'Required field',
    string_too_short: 'Value is too short',
    string_too_long: 'Value is too long',
    'value_error.email': 'Invalid email',
    'type_error.integer': 'Must be a number',
    'type_error.float': 'Must be a number',
    'type_error.none.not_allowed': 'Field cannot be empty',
  },
};

const OK_BUTTON: Record<string, string> = { ru: 'OK', en: 'OK' };

function getLocale(): string {
  // Пробуем получить из localStorage, потом из браузера
  const stored =
    localStorage.getItem('i18nextLng') || localStorage.getItem('language');
  if (stored?.startsWith('ru')) return 'ru';
  if (navigator.language?.startsWith('ru')) return 'ru';
  return 'en';
}

function getErrorIcon(content: string) {
  if (content === 'VALIDATION_ERROR') {
    return IconForms;
  }
  if (content.includes('ADMIN') || content.includes('PERMISSION')) {
    return IconShieldOff;
  }
  if (content.includes('ACCESS') || content.includes('DENIED')) {
    return IconLock;
  }
  return IconAlertTriangle;
}

function getErrorColor(statusCode?: number): string {
  if (statusCode === 422) return 'orange';
  if (statusCode === 403) return 'orange';
  if (statusCode === 404) return 'gray';
  if (statusCode && statusCode >= 500) return 'red';
  return 'yellow';
}

function translateValidationMessage(msg: string, locale: string): string {
  const messages = VALIDATION_MESSAGES[locale] || VALIDATION_MESSAGES.en;
  return messages[msg] || msg;
}

function formatFieldName(loc: (string | number)[]): string {
  // loc обычно ['body', 'field_name'] или ['body', 'nested', 'field']
  const parts = loc.filter(p => p !== 'body' && typeof p === 'string');
  return parts.join('.');
}

function isValidationError(detail: unknown): detail is ValidationErrorItem[] {
  return (
    Array.isArray(detail) &&
    detail.length > 0 &&
    'loc' in detail[0] &&
    'msg' in detail[0]
  );
}

export function ApiErrorModal() {
  const [error, setError] = useState<ApiError | null>(null);
  const [opened, setOpened] = useState(false);

  useEffect(() => {
    const unsubscribe = apiErrorEmitter.subscribe(err => {
      setError(err);
      setOpened(true);
    });
    return unsubscribe;
  }, []);

  const handleClose = () => {
    setOpened(false);
    setTimeout(() => setError(null), 200);
  };

  if (!error) return null;

  const locale = getLocale();
  const translations = TRANSLATIONS[locale] || TRANSLATIONS.en;
  const errorInfo = translations[error.content] || translations.UNKNOWN;
  const Icon = getErrorIcon(error.content);
  const color = getErrorColor(error.status_code);

  const isValidation =
    error.content === 'VALIDATION_ERROR' && isValidationError(error.detail);

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={
        <Group gap="sm">
          <ThemeIcon color={color} variant="light" size="lg" radius="xl">
            <Icon size={20} />
          </ThemeIcon>
          <Text fw={600}>{errorInfo.title}</Text>
        </Group>
      }
      centered
      size="sm">
      <Stack gap="md">
        <Text c="dimmed" size="sm">
          {errorInfo.description}
        </Text>

        {/* Ошибки валидации - список полей */}
        {isValidation && (
          <Box
            p="sm"
            style={{
              backgroundColor: 'var(--mantine-color-orange-0)',
              borderRadius: 'var(--mantine-radius-sm)',
              border: '1px solid var(--mantine-color-orange-3)',
            }}>
            <List size="sm" spacing="xs">
              {(error.detail as ValidationErrorItem[]).map((item, index) => (
                <List.Item key={index}>
                  <Text size="sm">
                    <Text span fw={500}>
                      {formatFieldName(item.loc)}
                    </Text>
                    {': '}
                    <Text span c="dimmed">
                      {translateValidationMessage(item.msg, locale)}
                    </Text>
                  </Text>
                </List.Item>
              ))}
            </List>
          </Box>
        )}

        {/* Обычная ошибка - detail как строка */}
        {!isValidation && error.detail && typeof error.detail === 'string' && (
          <Box
            p="xs"
            style={{
              backgroundColor: 'var(--mantine-color-gray-0)',
              borderRadius: 'var(--mantine-radius-sm)',
              border: '1px solid var(--mantine-color-gray-3)',
            }}>
            <Text size="xs" c="dimmed" ff="monospace">
              {error.detail}
            </Text>
          </Box>
        )}

        <Group justify="flex-end" mt="md">
          <Button variant="light" onClick={handleClose}>
            {OK_BUTTON[locale] || 'OK'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function useApiError() {
  const showError = (error: ApiError) => {
    apiErrorEmitter.emit(error);
  };
  return { showError };
}
