import { TextInput, Tooltip, ActionIcon, Group } from '@mantine/core';
import { IconLanguage } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldTranslatedCharProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

/**
 * Поле для TranslatedChar модели DotORM.
 *
 * Выглядит как обычный TextInput, но рядом со значением показывает
 * иконку-индикатор IconLanguage с тултипом — пользователь видит что
 * это поле переводимое и сейчас редактирует только текущий язык.
 *
 * При сохранении строка уйдёт на бэк, бэк положит её в текущий язык
 * пользователя в JSONB, остальные переводы затрутся (см.
 * TranslatedChar.serialization). Для multi-language редактирования
 * нужен отдельный расширенный компонент — пока MVP только индикатор.
 */
export const FieldTranslatedChar = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldTranslatedCharProps) => {
  const form = useFormContext();
  const { t, i18n } = useTranslation('common');
  const displayLabel = label ?? name;
  const currentLang = (i18n.language || 'en').split('-')[0].toUpperCase();

  const tooltipText = t(
    'translatedFieldTooltip',
    `Переводимое поле. Сейчас редактируется язык: ${currentLang}. ` +
      `Изменения затронут только этот язык, остальные переводы останутся.`,
  );

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <TextInput
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
        required={required}
        rightSection={
          <Tooltip label={tooltipText} multiline w={260} withArrow>
            <ActionIcon
              variant="subtle"
              size="sm"
              color="blue"
              tabIndex={-1}
              aria-label="Translated field"
              style={{ cursor: 'help' }}>
              <IconLanguage size={16} />
            </ActionIcon>
          </Tooltip>
        }
        rightSectionPointerEvents="auto"
      />
    </FieldWrapper>
  );
};
