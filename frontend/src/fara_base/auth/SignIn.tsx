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
  IconBrandGithub,
  IconBrandYoutube,
  IconBrandVk,
  IconBrandWhatsapp,
  IconBrandLinkedin,
  IconBrandX,
  IconBrandFacebook,
  IconBrandInstagram,
  IconBrandDiscord,
  IconMail,
  IconWorld,
  IconLanguage,
  IconCheck,
} from '@tabler/icons-react';
import classes from './SignIn.module.css';
import { useEffect, useState } from 'react';
import { UserInput } from '@/services/auth/types';
import { useLoginMutation } from '@/services/auth/auth';
import {
  useGetPublicConfigQuery,
  brandingFileUrl,
} from '@/services/config/config';
import { storeSession } from '@/slices/authSlice';
import Logo from '@/components/Logo';
import AnimatedBackground from './AnimatedBackground';

// RuTube icon
const IconRuTube = ({ size = 20 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" />
  </svg>
);

/**
 * Таблица типов соцсетей: icon + label + color.
 * Используется как для дефолтных ссылок FARA, так и для пользовательских
 * из branding (Company.login_socialN_type → ключ этой таблицы).
 *
 * Чтобы добавить новый тип:
 * 1. Добавь option в _SOCIAL_OPTIONS в backend/.../company.py
 * 2. Добавь запись здесь.
 */
type SocialMeta = {
  icon: React.ComponentType<{ size?: number }>;
  label: string;
  color: string;
};

const SOCIAL_TYPE_META: Record<string, SocialMeta> = {
  telegram: { icon: IconBrandTelegram, label: 'Telegram', color: '#2AABEE' },
  github: { icon: IconBrandGithub, label: 'GitHub', color: '#333' },
  rutube: { icon: IconRuTube, label: 'RuTube', color: '#1B1F3B' },
  youtube: { icon: IconBrandYoutube, label: 'YouTube', color: '#FF0000' },
  vk: { icon: IconBrandVk, label: 'ВКонтакте', color: '#0077FF' },
  whatsapp: { icon: IconBrandWhatsapp, label: 'WhatsApp', color: '#25D366' },
  linkedin: { icon: IconBrandLinkedin, label: 'LinkedIn', color: '#0A66C2' },
  x: { icon: IconBrandX, label: 'X', color: '#000' },
  facebook: { icon: IconBrandFacebook, label: 'Facebook', color: '#1877F2' },
  instagram: { icon: IconBrandInstagram, label: 'Instagram', color: '#E4405F' },
  discord: { icon: IconBrandDiscord, label: 'Discord', color: '#5865F2' },
  email: { icon: IconMail, label: 'Email', color: '#666' },
  website: { icon: IconWorld, label: 'Website', color: '#444' },
};

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

/**
 * Дефолтные ссылки FARA — показываются если в branding не настроена
 * ни одна соцсеть. Формат тот же что у пользовательских (type + url),
 * чтобы рендеринг был единообразный.
 */
const DEFAULT_SOCIAL_LINKS: { type: string; url: string }[] = [
  { type: 'telegram', url: 'https://t.me/faracrm' },
  { type: 'github', url: 'https://github.com/shurshilov/faracrm' },
  { type: 'rutube', url: 'https://rutube.ru/channel/75678685' },
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
      login: '',
      password: '',
    },
    validate: yupResolver(validationSchema),
  });

  // Публичная конфигурация сервера (доступна без авторизации).
  // Если demo_mode=true — префилим форму логина admin/admin.
  const { data: publicConfig } = useGetPublicConfigQuery();
  const demoMode = !!publicConfig?.demo_mode;

  useEffect(() => {
    if (demoMode) {
      form.setValues({ login: 'admin', password: 'admin' });
    }
  }, [demoMode]);

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

  // Стиль карточки логина: elevated (объёмный, default) или flat (плоский).
  // Берём из branding, фолбэк на elevated.
  const cardStyle = publicConfig?.branding?.login_card_style || 'elevated';
  const formClassName =
    cardStyle === 'flat'
      ? `${classes.form} ${classes.formFlat}`
      : `${classes.form} ${classes.formElevated}`;

  // Соцсети для отрисовки. Источник:
  // 1. branding.login_socials если непустой — пользовательские из Company
  // 2. иначе DEFAULT_SOCIAL_LINKS (FARA Telegram/GitHub/RuTube)
  // Дополнительно отфильтровываем неизвестные типы — на случай если
  // в БД лежит type, для которого нет записи в SOCIAL_TYPE_META
  // (например, после downgrade'а фронта).
  const brandingSocials = publicConfig?.branding?.login_socials;
  const socialLinks = (
    brandingSocials && brandingSocials.length > 0
      ? brandingSocials
      : DEFAULT_SOCIAL_LINKS
  ).filter(link => link.type in SOCIAL_TYPE_META);

  return (
    <div className={classes.wrapper}>
      {/* Левая часть — форма */}
      <Paper className={formClassName} radius={0}>
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
              <Logo variant="login" />
              <Text size="sm" c="dimmed" mt={8}>
                {publicConfig?.branding?.login_subtitle || t('auth.subtitle')}
              </Text>
            </div>

            {/* Заголовок */}
            <div>
              <Text className={classes.title}>{t('auth.title')}</Text>
              <Text size="sm" c="dimmed" mt={4}>
                {publicConfig?.branding?.login_title || t('auth.description')}
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
              className={classes.submitBtn}
              style={
                publicConfig?.branding?.login_button_color
                  ? ({
                      '--login-btn-color':
                        publicConfig.branding.login_button_color,
                    } as React.CSSProperties)
                  : undefined
              }>
              {t('auth.signIn')}
            </Button>

            {/* Ошибка авторизации */}
            {loginError && (
              <Text c="red" size="sm" ta="center" data-testid="login-error">
                {loginError}
              </Text>
            )}

            {/* Соцсети — если есть что показать */}
            {socialLinks.length > 0 && (
              <>
                <Divider
                  label={
                    <Text size="xs" c="dimmed">
                      {t('auth.community')}
                    </Text>
                  }
                  labelPosition="center"
                />

                <Group justify="center" gap="lg">
                  {socialLinks.map((link, idx) => {
                    const meta = SOCIAL_TYPE_META[link.type];
                    const Icon = meta.icon;
                    return (
                      <Tooltip
                        key={`${link.type}-${idx}`}
                        label={meta.label}
                        withArrow>
                        <ActionIcon
                          component="a"
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          variant="subtle"
                          size="lg"
                          className={classes.socialIcon}
                          style={
                            {
                              '--social-color': meta.color,
                            } as React.CSSProperties
                          }>
                          <Icon size={22} />
                        </ActionIcon>
                      </Tooltip>
                    );
                  })}
                </Group>
              </>
            )}

            <Text ta="center" size="xs" c="dimmed" className={classes.version}>
              FARA CRM v{publicConfig?.version}
            </Text>
          </Stack>
        </form>
      </Paper>

      {/* Правая часть — кастомный фон от branding или анимированный */}
      <div
        className={classes.background}
        style={
          publicConfig?.branding?.has_login_background
            ? {
                backgroundImage: `url("${brandingFileUrl('login_background_id')}")`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat',
              }
            : undefined
        }>
        {!publicConfig?.branding?.has_login_background && (
          <AnimatedBackground />
        )}
      </div>
    </div>
  );
}
