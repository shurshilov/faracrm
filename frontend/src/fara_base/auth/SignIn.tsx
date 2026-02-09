import {
  Paper,
  TextInput,
  PasswordInput,
  Button,
  Text,
  Group,
  ActionIcon,
  Tooltip,
  Stack,
  Divider,
  Menu,
} from '@mantine/core';
import * as yup from 'yup';
import { useForm, yupResolver } from '@mantine/form';
import { useDispatch } from 'react-redux';
import { useTranslation } from 'react-i18next';
import {
  IconBrandTelegram,
  IconBrandYoutube,
  IconBrandGithub,
  IconLanguage,
  IconCheck,
} from '@tabler/icons-react';
import classes from './SignIn.module.css';
import { useState } from 'react';
import { UserInput } from '@/services/auth/types';
import { useLoginMutation } from '@/services/auth/auth';
import { storeSession } from '@/slices/authSlice';
import Logo from '@/components/Logo';
import AnimatedBackground from './AnimatedBackground';

// RuTube icon
const IconRuTube = ({ size = 20 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" />
  </svg>
);

const LANGUAGES = [
  { code: 'ru', label: 'Русский' },
  { code: 'en', label: 'English' },
];

// SVG флаги — компактные, без emoji
const FlagRu = () => (
  <svg width="20" height="14" viewBox="0 0 20 14" style={{ borderRadius: 2 }}>
    <rect width="20" height="4.67" fill="#fff" />
    <rect y="4.67" width="20" height="4.67" fill="#0039A6" />
    <rect y="9.33" width="20" height="4.67" fill="#D52B1E" />
  </svg>
);

const FlagEn = () => (
  <svg width="20" height="14" viewBox="0 0 20 14" style={{ borderRadius: 2 }}>
    <rect width="20" height="14" fill="#012169" />
    <path d="M0 0L20 14M20 0L0 14" stroke="#fff" strokeWidth="2.4" />
    <path d="M0 0L20 14M20 0L0 14" stroke="#C8102E" strokeWidth="1.2" />
    <path d="M10 0V14M0 7H20" stroke="#fff" strokeWidth="4" />
    <path d="M10 0V14M0 7H20" stroke="#C8102E" strokeWidth="2.4" />
  </svg>
);

const FLAG_ICONS: Record<string, React.FC> = { ru: FlagRu, en: FlagEn };

const SOCIAL_LINKS = [
  {
    icon: IconBrandTelegram,
    label: 'Telegram',
    href: 'https://t.me/fara_crm',
    color: '#2AABEE',
  },
  {
    icon: IconBrandGithub,
    label: 'GitHub',
    href: 'https://github.com/fara-crm',
    color: '#333',
  },
  {
    icon: IconBrandYoutube,
    label: 'YouTube',
    href: 'https://youtube.com/@fara_crm',
    color: '#FF0000',
  },
  {
    icon: IconRuTube,
    label: 'RuTube',
    href: 'https://rutube.ru/channel/fara_crm',
    color: '#1B1F3B',
  },
];

export default function SignIn() {
  const dispatch = useDispatch();
  const { t, i18n } = useTranslation('common');
  const [login, { isLoading: loading }] = useLoginMutation();
  const [loginError, setLoginError] = useState<string | null>(null);

  const validationSchema = yup.object({
    login: yup
      .string()
      .required(t('auth.loginRequired'))
      .max(120, t('auth.loginTooLong')),
    password: yup.string().required(t('auth.passwordRequired')),
  });

  const form = useForm({
    initialValues: {
      login: 'admin',
      password: 'admin',
    },
    validate: yupResolver(validationSchema),
  });

  const onSubmitHandler = async (values: UserInput) => {
    try {
      setLoginError(null);
      const session = await login(values).unwrap();
      dispatch(storeSession({ session }));
    } catch {
      setLoginError(t('auth.invalidCredentials', 'Неверный логин или пароль'));
    }
  };

  const currentLang = i18n.language?.substring(0, 2) || 'ru';

  return (
    <div className={classes.wrapper}>
      {/* Левая часть — форма */}
      <Paper className={classes.form} radius={0}>
        {/* Переключатель языка — правый верхний угол */}
        <div className={classes.langSwitcher}>
          <Menu shadow="sm" width={160} position="bottom-end">
            <Menu.Target>
              <ActionIcon
                variant="subtle"
                size="lg"
                className={classes.langBtn}>
                <IconLanguage size={20} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              {LANGUAGES.map(lang => {
                const Flag = FLAG_ICONS[lang.code];
                return (
                  <Menu.Item
                    key={lang.code}
                    onClick={() => i18n.changeLanguage(lang.code)}
                    leftSection={<Flag />}
                    rightSection={
                      currentLang === lang.code ? (
                        <IconCheck size={14} color="#009982" />
                      ) : null
                    }>
                    {lang.label}
                  </Menu.Item>
                );
              })}
            </Menu.Dropdown>
          </Menu>
        </div>

        <form onSubmit={form.onSubmit(onSubmitHandler)}>
          <Stack gap="xl" className={classes.formInner}>
            {/* Лого */}
            <div className={classes.logoBlock}>
              <Logo />
              <Text size="sm" c="dimmed" mt={8}>
                {t('auth.subtitle')}
              </Text>
            </div>

            {/* Заголовок */}
            <div>
              <Text className={classes.title}>{t('auth.title')}</Text>
              <Text size="sm" c="dimmed" mt={4}>
                {t('auth.description')}
              </Text>
            </div>

            {/* Поля */}
            <Stack gap="md">
              <TextInput
                {...form.getInputProps('login')}
                name="login"
                label={t('auth.login')}
                placeholder={t('auth.loginPlaceholder')}
                size="md"
                classNames={{ label: classes.inputLabel }}
              />
              <PasswordInput
                {...form.getInputProps('password')}
                name="password"
                label={t('auth.password')}
                placeholder="••••••••"
                size="md"
                classNames={{ label: classes.inputLabel }}
              />
            </Stack>

            {/* Кнопка */}
            <Button
              loading={loading}
              type="submit"
              fullWidth
              size="md"
              className={classes.submitBtn}>
              {t('auth.signIn')}
            </Button>

            {/* Ошибка авторизации */}
            {loginError && (
              <Text c="red" size="sm" ta="center" data-testid="login-error">
                {loginError}
              </Text>
            )}

            {/* Соцсети */}
            <Divider
              label={
                <Text size="xs" c="dimmed">
                  {t('auth.community')}
                </Text>
              }
              labelPosition="center"
            />

            <Group justify="center" gap="lg">
              {SOCIAL_LINKS.map(link => (
                <Tooltip key={link.label} label={link.label} withArrow>
                  <ActionIcon
                    component="a"
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="subtle"
                    size="lg"
                    className={classes.socialIcon}
                    style={
                      { '--social-color': link.color } as React.CSSProperties
                    }>
                    <link.icon size={22} />
                  </ActionIcon>
                </Tooltip>
              ))}
            </Group>

            <Text ta="center" size="xs" c="dimmed" className={classes.version}>
              FARA CRM v1.0
            </Text>
          </Stack>
        </form>
      </Paper>

      {/* Правая часть — анимированный фон */}
      <div className={classes.background}>
        <AnimatedBackground />
      </div>
    </div>
  );
}
