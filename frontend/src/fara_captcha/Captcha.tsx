import { useEffect, useState } from 'react';
import { ActionIcon, TextInput } from '@mantine/core';
import type { TextInputProps } from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';
import { useLazyGetCaptchaQuery } from './api';

export interface CaptchaValue {
  token: string;
  answer: string;
}

interface CaptchaFieldProps {
  label: string;
  placeholder: string;
  /** Текущие token+answer сообщаются наверх; родитель шлёт их в форме. */
  onChange: (value: CaptchaValue) => void;
  /** Меняется извне (номер попытки) → запросить новую задачку. */
  resetSignal?: number;
  size?: string;
  classNames?: TextInputProps['classNames'];
}

/**
 * Поле капчи «a + b»: задачка приходит с сервера (одноразовый token +
 * вопрос), пользователь вводит ответ. Модуль captcha; на форме показывается,
 * только когда он установлен (решает родитель по /public/config).
 */
export function CaptchaField({
  label,
  placeholder,
  onChange,
  resetSignal = 0,
  size = 'md',
  classNames,
}: CaptchaFieldProps) {
  const [fetchCaptcha, { data, isFetching }] = useLazyGetCaptchaQuery();
  const [answer, setAnswer] = useState('');
  const token = data?.data.token ?? '';
  const image = data?.data.image;

  // Новая задачка на монтировании и при сбросе (после неудачной отправки).
  useEffect(() => {
    setAnswer('');
    fetchCaptcha();
  }, [resetSignal, fetchCaptcha]);

  // Сообщаем наверх текущие token+answer (onChange у родителя стабилен).
  useEffect(() => {
    onChange({ token, answer });
  }, [token, answer, onChange]);

  return (
    <TextInput
      classNames={classNames}
      label={label}
      description={
        image ? (
          <img
            src={image}
            alt=""
            draggable={false}
            style={{
              display: 'block',
              height: 40,
              borderRadius: 6,
              userSelect: 'none',
            }}
          />
        ) : (
          '…'
        )
      }
      placeholder={placeholder}
      value={answer}
      onChange={event => setAnswer(event.currentTarget.value)}
      size={size}
      inputMode="numeric"
      rightSection={
        <ActionIcon
          variant="subtle"
          color="gray"
          onClick={() => fetchCaptcha()}
          loading={isFetching}
          aria-label={label}>
          <IconRefresh size={16} />
        </ActionIcon>
      }
    />
  );
}
