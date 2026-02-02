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
} from '@mantine/core';
import * as yup from 'yup';
import { useForm, yupResolver } from '@mantine/form';
import { useDispatch } from 'react-redux';
import {
  IconBrandTelegram,
  IconBrandYoutube,
  IconBrandGithub,
} from '@tabler/icons-react';
import classes from './SignIn.module.css';
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
  const [login, { isLoading: loading }] = useLoginMutation();

  const validationSchema = yup.object({
    login: yup
      .string()
      .required('Введите логин')
      .max(120, 'Логин слишком длинный'),
    password: yup.string().required('Введите пароль'),
  });

  const form = useForm({
    initialValues: {
      login: 'admin',
      password: '12345678!Aaa',
    },
    validate: yupResolver(validationSchema),
  });

  const onSubmitHandler = async (values: UserInput) => {
    try {
      const session = await login(values).unwrap();
      dispatch(storeSession({ session }));
    } catch {
      // handled by error modal
    }
  };

  return (
    <div className={classes.wrapper}>
      {/* Левая часть — форма */}
      <Paper className={classes.form} radius={0}>
        <form onSubmit={form.onSubmit(onSubmitHandler)}>
          <Stack gap="xl" className={classes.formInner}>
            {/* Лого */}
            <div className={classes.logoBlock}>
              <Logo />
              <Text size="sm" c="dimmed" mt={8}>
                Платформа для управления бизнесом
              </Text>
            </div>

            {/* Заголовок */}
            <div>
              <Text className={classes.title}>Вход в систему</Text>
              <Text size="sm" c="dimmed" mt={4}>
                Введите данные для доступа к CRM
              </Text>
            </div>

            {/* Поля */}
            <Stack gap="md">
              <TextInput
                {...form.getInputProps('login')}
                name="login"
                label="Логин"
                withAsterisk
                placeholder="Имя пользователя"
                size="md"
                classNames={{ label: classes.inputLabel }}
              />
              <PasswordInput
                {...form.getInputProps('password')}
                name="password"
                label="Пароль"
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
              Войти
            </Button>

            {/* Соцсети */}
            <Divider
              label={
                <Text size="xs" c="dimmed">
                  Сообщество
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
