import { useState } from 'react';
import { Menu, UnstyledButton, Group, Text, Image } from '@mantine/core';
import { IconChevronDown } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { useSearchQuery, useUpdateMutation } from '@/services/api/crudApi';
import { selectCurrentSession } from '@/slices/authSlice';
import { flags } from '@/assets/flags';
import classes from './LanguageSelector.module.css';

// Получить локальный SVG флаг
const getFlag = (code: string): string => {
  return flags[code.toLowerCase()] || flags['us'];
};

// Fallback языки если API недоступен
const FALLBACK_LANGUAGES = [
  { code: 'en', name: 'English', flag: 'us', active: true },
  { code: 'ru', name: 'Русский', flag: 'ru', active: true },
];

interface Language {
  id: number;
  code: string;
  name: string;
  flag: string;
  active: boolean;
}

export function LanguageSelector() {
  const { i18n } = useTranslation();
  const [opened, setOpened] = useState(false);
  const session = useSelector(selectCurrentSession);

  // Используем стандартный search с фильтром
  const { data, isError } = useSearchQuery({
    model: 'language',
    filter: [['active', '=', true]],
    fields: ['id', 'code', 'name', 'flag', 'active'],
    sort: 'code',
    order: 'asc',
  });

  const [updateUser] = useUpdateMutation();

  // Используем API языки или fallback
  const apiLanguages = (data?.data as Language[]) || [];
  const languages = apiLanguages.length > 0 ? apiLanguages : FALLBACK_LANGUAGES;

  const currentLang =
    languages.find(lang => lang.code === i18n.language) ||
    languages.find(
      lang => lang.code === i18n.language?.split('-')[0], // en-US -> en
    ) ||
    languages[0];

  const handleLanguageChange = async (code: string) => {
    // Меняем язык в i18next
    await i18n.changeLanguage(code);
    // Сохраняем в localStorage
    localStorage.setItem('i18nextLng', code);

    // Обновляем язык пользователя через стандартный CRUD
    // lang_id это Many2one, отправляем id языка
    if (!isError && session?.user_id?.id) {
      const selectedLang = languages.find(l => l.code === code);
      if (selectedLang && 'id' in selectedLang) {
        try {
          await updateUser({
            model: 'users',
            id: session.user_id.id,
            values: { lang_id: selectedLang.id },
          });
        } catch (e) {
          // Игнорируем ошибку API
        }
      }
    }
    setOpened(false);
  };

  if (!currentLang) {
    return null;
  }

  const items = languages.map(lang => (
    <Menu.Item
      key={lang.code}
      onClick={() => handleLanguageChange(lang.code)}
      leftSection={
        <Image
          src={getFlag(lang.flag)}
          alt={lang.name}
          w={18}
          h={14}
          radius={2}
        />
      }
      className={
        lang.code === currentLang.code ? classes.activeItem : undefined
      }>
      {lang.name}
    </Menu.Item>
  ));

  return (
    <Menu
      onOpen={() => setOpened(true)}
      onClose={() => setOpened(false)}
      radius="md"
      width={160}
      withinPortal>
      <Menu.Target>
        <UnstyledButton
          className={classes.control}
          data-opened={opened || undefined}>
          <Group gap={6}>
            <Image
              src={getFlag(currentLang.flag)}
              alt={currentLang.name}
              w={22}
              h={16}
              radius={2}
            />
            <Text size="sm" fw={500} className={classes.label}>
              {currentLang.code.toUpperCase()}
            </Text>
          </Group>
          <IconChevronDown size={16} className={classes.chevron} stroke={1.5} />
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>{items}</Menu.Dropdown>
    </Menu>
  );
}
