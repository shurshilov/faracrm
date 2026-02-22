import { useEffect, useState } from 'react';
import {
  Avatar,
  Group,
  Menu,
  Text,
  UnstyledButton,
  useMantineColorScheme,
  Image,
  Box,
} from '@mantine/core';
import {
  IconChevronDown,
  IconChevronRight,
  IconLogout,
  IconUser,
  IconLayout,
  IconLayoutSidebar,
  IconLayoutNavbar,
  IconBell,
  IconBellOff,
  IconVolume,
  IconVolumeOff,
} from '@tabler/icons-react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useMediaQuery } from '@mantine/hooks';
import { logOut, storeSession, selectCurrentSession } from '@/slices/authSlice';
import { authApi } from '@/services/auth/auth';
import { attachmentPreviewUrl } from '@/utils/attachmentUrls';
import {
  useReadQuery,
  useSearchQuery,
  useUpdateMutation,
} from '@/services/api/crudApi';
import { flags } from '@/assets/flags';
import { useLayoutTheme } from '@/components/ModernTheme';
import classes from './UserMenu.module.css';

const getFlag = (code: string): string => {
  return flags[code.toLowerCase()] || flags['us'];
};

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

function UserMenu() {
  const { colorScheme } = useMantineColorScheme();
  const { i18n, t } = useTranslation();
  const dark = colorScheme === 'dark';
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const session = useSelector(selectCurrentSession);
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null);

  // Тема layout
  const { layoutTheme, setLayoutTheme } = useLayoutTheme();

  const { data: userData } = useReadQuery(
    {
      model: 'users',
      id: session?.user_id.id ?? 0,
      fields: [
        'id',
        'name',
        'image',
        'lang_id',
        'notification_popup',
        'notification_sound',
      ],
    },
    { skip: !session?.user_id },
  );

  const { data: languagesData, isError: languagesError } = useSearchQuery({
    model: 'language',
    filter: [['active', '=', true]],
    fields: ['id', 'code', 'name', 'flag', 'active'],
    sort: 'code',
    order: 'asc',
  });

  const [updateUser] = useUpdateMutation();

  const user = userData?.data;
  const userName = user?.name ?? t('common:user', 'Пользователь');
  const imageId = user?.image?.id;
  const userLangId = user?.lang_id?.id;

  const apiLanguages = (languagesData?.data as Language[]) || [];
  const languages = apiLanguages.length > 0 ? apiLanguages : FALLBACK_LANGUAGES;

  // Находим язык пользователя по id из БД
  const userLang = languages.find(lang => lang.id === userLangId);

  const currentLang =
    userLang ||
    languages.find(lang => lang.code === i18n.language) ||
    languages.find(lang => lang.code === i18n.language?.split('-')[0]) ||
    languages[0];

  // Синхронизируем i18n с языком пользователя из БД
  useEffect(() => {
    if (currentLang?.code && currentLang.code !== i18n.language) {
      i18n.changeLanguage(currentLang.code);
      localStorage.setItem('i18nextLng', currentLang.code);
    }
  }, [currentLang?.code]);

  useEffect(() => {
    setAvatarSrc(null);
    if (!imageId) return;

    setAvatarSrc(attachmentPreviewUrl(imageId, 50, 50));
  }, [imageId]);

  const handleLogout = () => {
    dispatch(logOut());
    dispatch(authApi.internalActions?.resetApiState());
  };

  const handleProfile = () => {
    if (session?.user_id.id) {
      navigate(`/users/${session.user_id.id}`);
    }
  };

  const handleLanguageChange = async (code: string) => {
    await i18n.changeLanguage(code);
    localStorage.setItem('i18nextLng', code);

    if (!languagesError && session?.user_id?.id) {
      // Находим язык по коду чтобы получить его id
      const selectedLang = languages.find(l => l.code === code);
      if (selectedLang && 'id' in selectedLang) {
        try {
          await updateUser({
            model: 'users',
            id: session.user_id.id,
            values: { lang_id: selectedLang.id },
          });
        } catch (e) {
          // Ignore
        }
      }
    }
  };

  const handleLayoutThemeChange = async (theme: 'classic' | 'modern') => {
    // Сначала сохраняем в БД, потом переключаем UI.
    // При смене темы layout перемонтируется → async код прервётся,
    // поэтому updateUser должен завершиться ДО setLayoutTheme.
    if (session?.user_id?.id) {
      try {
        await updateUser({
          model: 'users',
          id: session.user_id.id,
          values: { layout_theme: theme },
        });
      } catch (e) {
        // БД не обновилась — не переключаем тему
        return;
      }
    }
    // Обновляем session в redux + localStorage чтобы F5 сразу показал правильную тему
    if (session) {
      dispatch(
        storeSession({
          session: {
            ...session,
            user_id: { ...session.user_id, layout_theme: theme },
          },
        }),
      );
    }
    setLayoutTheme(theme);
  };

  const notificationPopup = user?.notification_popup ?? true;
  const notificationSound = user?.notification_sound ?? true;

  const handleTogglePopup = async () => {
    if (session?.user_id?.id) {
      try {
        await updateUser({
          model: 'users',
          id: session.user_id.id,
          values: { notification_popup: !notificationPopup },
        });
      } catch (e) {
        // Ignore
      }
    }
  };

  const handleToggleSound = async () => {
    if (session?.user_id?.id) {
      try {
        await updateUser({
          model: 'users',
          id: session.user_id.id,
          values: { notification_sound: !notificationSound },
        });
      } catch (e) {
        // Ignore
      }
    }
  };

  // На touch-устройствах hover на вложенных меню не работает — используем click
  const isTouchDevice = useMediaQuery('(hover: none)');
  const subMenuTrigger = isTouchDevice
    ? ('click' as const)
    : ('click-hover' as const);

  return (
    <Menu
      width={200}
      position="bottom-end"
      transitionProps={{ transition: 'pop-top-right' }}
      withinPortal
      shadow="md">
      <Menu.Target>
        <UnstyledButton className={classes.user}>
          <Group gap={7}>
            <Avatar
              src={avatarSrc}
              alt={userName}
              radius="xl"
              size={32}
              color={dark ? 'blue' : 'blue.6'}>
              {!avatarSrc && userName.charAt(0).toUpperCase()}
            </Avatar>
            <Text fw={500} size="sm" lh={1} mr={3} visibleFrom="sm">
              {userName}
            </Text>
            <IconChevronDown style={{ width: 14, height: 14 }} stroke={1.5} />
          </Group>
        </UnstyledButton>
      </Menu.Target>

      <Menu.Dropdown>
        {/* Профиль */}
        <Menu.Item
          leftSection={
            <IconUser style={{ width: 16, height: 16 }} stroke={1.5} />
          }
          onClick={handleProfile}>
          {t('common:myProfile', 'Мой профиль')}
        </Menu.Item>

        {/* Язык - подменю */}
        <Menu
          trigger={subMenuTrigger}
          position="left-start"
          offset={2}
          withinPortal
          shadow="md">
          <Menu.Target>
            <Box>
              <Menu.Item
                rightSection={
                  <Group gap={6}>
                    <Image
                      src={getFlag(currentLang?.flag || 'us')}
                      w={18}
                      h={13}
                      radius={2}
                    />
                    <IconChevronRight
                      style={{ width: 14, height: 14 }}
                      stroke={1.5}
                    />
                  </Group>
                }>
                {t('common:language', 'Язык')}
              </Menu.Item>
            </Box>
          </Menu.Target>
          <Menu.Dropdown>
            {languages.map(lang => (
              <Menu.Item
                key={lang.code}
                leftSection={
                  <Image src={getFlag(lang.flag)} w={20} h={15} radius={2} />
                }
                onClick={() => handleLanguageChange(lang.code)}
                className={
                  lang.code === currentLang?.code
                    ? classes.activeItem
                    : undefined
                }>
                {lang.name}
              </Menu.Item>
            ))}
          </Menu.Dropdown>
        </Menu>

        {/* Тема интерфейса - подменю */}
        <Menu
          trigger={subMenuTrigger}
          position="left-start"
          offset={2}
          withinPortal
          shadow="md">
          <Menu.Target>
            <Box>
              <Menu.Item
                leftSection={
                  <IconLayout style={{ width: 16, height: 16 }} stroke={1.5} />
                }
                rightSection={
                  <IconChevronRight
                    style={{ width: 14, height: 14 }}
                    stroke={1.5}
                  />
                }>
                {t('common:layoutTheme', 'Тема интерфейса')}
              </Menu.Item>
            </Box>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item
              leftSection={
                <IconLayoutSidebar
                  style={{ width: 16, height: 16 }}
                  stroke={1.5}
                />
              }
              onClick={() => handleLayoutThemeChange('classic')}
              className={
                layoutTheme === 'classic' ? classes.activeItem : undefined
              }>
              {t('common:themeClassic', 'Классическая')}
            </Menu.Item>
            <Menu.Item
              leftSection={
                <IconLayoutNavbar
                  style={{ width: 16, height: 16 }}
                  stroke={1.5}
                />
              }
              onClick={() => handleLayoutThemeChange('modern')}
              className={
                layoutTheme === 'modern' ? classes.activeItem : undefined
              }>
              {t('common:themeModern', 'Современная')}
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>

        {/* Уведомления - подменю */}
        <Menu
          trigger={subMenuTrigger}
          position="left-start"
          offset={2}
          withinPortal
          shadow="md">
          <Menu.Target>
            <Box>
              <Menu.Item
                leftSection={
                  <IconBell style={{ width: 16, height: 16 }} stroke={1.5} />
                }
                rightSection={
                  <IconChevronRight
                    style={{ width: 14, height: 14 }}
                    stroke={1.5}
                  />
                }>
                {t('common:notifications', 'Уведомления')}
              </Menu.Item>
            </Box>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item
              leftSection={
                notificationPopup ? (
                  <IconBell style={{ width: 16, height: 16 }} stroke={1.5} />
                ) : (
                  <IconBellOff style={{ width: 16, height: 16 }} stroke={1.5} />
                )
              }
              onClick={handleTogglePopup}>
              {t('common:notificationPopup', 'Всплывающие')}
              {notificationPopup ? ' ✓' : ''}
            </Menu.Item>
            <Menu.Item
              leftSection={
                notificationSound ? (
                  <IconVolume style={{ width: 16, height: 16 }} stroke={1.5} />
                ) : (
                  <IconVolumeOff
                    style={{ width: 16, height: 16 }}
                    stroke={1.5}
                  />
                )
              }
              onClick={handleToggleSound}>
              {t('common:notificationSound', 'Звук')}
              {notificationSound ? ' ✓' : ''}
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>

        <Menu.Divider />

        {/* Выход */}
        <Menu.Item
          color="red"
          leftSection={
            <IconLogout style={{ width: 16, height: 16 }} stroke={1.5} />
          }
          onClick={handleLogout}>
          {t('common:logout', 'Выход')}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

export default UserMenu;
