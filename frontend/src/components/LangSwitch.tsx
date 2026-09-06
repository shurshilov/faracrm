import { SegmentedControl } from '@mantine/core';
import { useTranslation } from 'react-i18next';

const LANGS = [
  { value: 'ru', label: 'RU' },
  { value: 'en', label: 'EN' },
];

/**
 * Переключатель языка для публичных страниц (каталог, регистрация).
 * Выбор запоминает сам i18next (localStorage), как и на странице входа.
 */
export function LangSwitch() {
  const { i18n } = useTranslation();
  const current = i18n.language?.startsWith('en') ? 'en' : 'ru';

  return (
    <SegmentedControl
      size="xs"
      radius="md"
      data={LANGS}
      value={current}
      onChange={value => i18n.changeLanguage(value)}
    />
  );
}
