import { useCallback, useState } from 'react';
import {
  Anchor,
  Button,
  Paper,
  PasswordInput,
  PinInput,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDispatch } from 'react-redux';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import classes from '@/fara_base/auth/SignIn.module.css';
import AnimatedBackground from '@/fara_base/auth/AnimatedBackground';
import Logo from '@/components/Logo';
import { LangSwitch } from '@/components/LangSwitch';
import { useLoginMutation } from '@/services/auth/auth';
import { storeSession } from '@/slices/authSlice';
import { CaptchaField, type CaptchaValue } from '@/fara_captcha/Captcha';
import {
  useConfirmRegistrationMutation,
  useStartRegistrationMutation,
} from './api';

// Ошибки бэкенда приходят с человекочитаемым detail (FaraException).
// Исключение — политика пароля: там detail = коды правил, подписываем сами.
function errorMessage(err: unknown, t: TFunction): string {
  const data = (err as { data?: { content?: string; detail?: string } })?.data;
  if (data?.content === 'REGISTRATION_PASSWORD_POLICY') {
    return `${t('errors.passwordPolicy')} (${data.detail})`;
  }
  return data?.detail || t('errors.unknown');
}

/**
 * Регистрация: форма (имя, email, пароль) → код из письма → вход.
 * Оформление — как у страницы входа (те же CSS-классы), чтобы выглядело
 * одной и той же «дверью» в систему.
 */
export default function Register() {
  const { t } = useTranslation('registration');
  const dispatch = useDispatch();
  const [start, { isLoading: starting }] = useStartRegistrationMutation();
  const [confirm, { isLoading: confirming }] = useConfirmRegistrationMutation();
  const [login] = useLoginMutation();

  const [step, setStep] = useState<'form' | 'code'>('form');
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Регистрация зависит от модуля captcha — задачка есть всегда.
  const [captcha, setCaptcha] = useState<CaptchaValue>({
    token: '',
    answer: '',
  });
  // Инкремент → CaptchaField берёт новую задачку (после неудачной отправки).
  const [captchaAttempt, setCaptchaAttempt] = useState(0);
  const onCaptchaChange = useCallback(
    (value: CaptchaValue) => setCaptcha(value),
    [],
  );

  const form = useForm({
    initialValues: { name: '', login: '', password: '' },
    validate: {
      name: value => (value.trim() ? null : t('errors.nameRequired')),
      login: value =>
        /^\S+@\S+\.\S+$/.test(value) ? null : t('errors.emailInvalid'),
      password: value => (value ? null : t('errors.passwordRequired')),
    },
  });

  const handleStart = async (values: typeof form.values) => {
    setError(null);
    try {
      await start({
        ...values,
        captcha_token: captcha.token,
        captcha_answer: captcha.answer,
      }).unwrap();
      setStep('code');
    } catch (err) {
      setError(errorMessage(err, t));
      // Капча одноразовая — после ошибки берём новую задачку.
      setCaptchaAttempt(attempt => attempt + 1);
    }
  };

  const handleConfirm = async () => {
    setError(null);
    try {
      await confirm({ login: form.values.login, code }).unwrap();
      // Пользователь создан — входим сразу, пароль ещё в форме. Дальше
      // роут /register сам уведёт на домашнюю страницу.
      const session = await login({
        login: form.values.login,
        password: form.values.password,
      }).unwrap();
      dispatch(storeSession({ session }));
    } catch (err) {
      setError(errorMessage(err, t));
    }
  };

  return (
    <div className={classes.wrapper}>
      <Paper className={`${classes.form} ${classes.formElevated}`} radius={0}>
        {/* Язык — правый верхний угол, как на странице входа */}
        <div className={classes.langSwitcher}>
          <LangSwitch />
        </div>

        <Stack gap="xl" className={classes.formInner}>
          <div className={classes.logoBlock}>
            <Logo variant="login" />
          </div>

          <div>
            <Text className={classes.title}>{t('title')}</Text>
            <Text size="sm" c="dimmed" mt={4}>
              {step === 'form'
                ? t('description')
                : t('codeSent', { login: form.values.login })}
            </Text>
          </div>

          {step === 'form' ? (
            <form onSubmit={form.onSubmit(handleStart)}>
              <Stack gap="md">
                <TextInput
                  {...form.getInputProps('name')}
                  label={t('name')}
                  size="md"
                  classNames={{ label: classes.inputLabel }}
                />
                <TextInput
                  {...form.getInputProps('login')}
                  label={t('email')}
                  placeholder="example@mail.com"
                  size="md"
                  classNames={{ label: classes.inputLabel }}
                />
                <PasswordInput
                  {...form.getInputProps('password')}
                  label={t('password')}
                  placeholder="••••••••"
                  size="md"
                  classNames={{ label: classes.inputLabel }}
                />
                <CaptchaField
                  label={t('captcha.label')}
                  placeholder={t('captcha.placeholder')}
                  onChange={onCaptchaChange}
                  resetSignal={captchaAttempt}
                  classNames={{ label: classes.inputLabel }}
                />
                <Button
                  type="submit"
                  loading={starting}
                  disabled={!captcha.answer.trim()}
                  fullWidth
                  size="md"
                  className={classes.submitBtn}>
                  {t('sendCode')}
                </Button>
              </Stack>
            </form>
          ) : (
            <Stack gap="md" align="center">
              <PinInput
                length={6}
                type="number"
                size="lg"
                value={code}
                onChange={setCode}
                oneTimeCode
                autoFocus
              />
              <Button
                onClick={handleConfirm}
                loading={confirming}
                disabled={code.length < 6}
                fullWidth
                size="md"
                className={classes.submitBtn}>
                {t('confirm')}
              </Button>
              <Anchor
                size="sm"
                component="button"
                type="button"
                onClick={() => setStep('form')}>
                {t('changeEmail')}
              </Anchor>
            </Stack>
          )}

          {error && (
            <Text c="red" size="sm" ta="center">
              {error}
            </Text>
          )}

          <Text ta="center" size="sm" c="dimmed">
            {t('haveAccount')}{' '}
            <Anchor component={Link} to="/login" size="sm">
              {t('signIn')}
            </Anchor>
          </Text>
        </Stack>
      </Paper>

      <div className={classes.background}>
        <AnimatedBackground />
      </div>
    </div>
  );
}
