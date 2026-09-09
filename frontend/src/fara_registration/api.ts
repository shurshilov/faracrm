import { authApi } from '@/services/auth/auth';

export interface RegistrationStartArgs {
  name: string;
  login: string;
  password: string;
  // Капча — только если установлен модуль captcha (иначе не отправляются).
  captcha_token?: string;
  captcha_answer?: string;
}

export interface RegistrationConfirmArgs {
  login: string;
  code: string;
}

// Эндпоинты живут в authApi: у него «тихий» baseQuery без глобальной модалки
// ошибок — ошибки регистрации показываем прямо в форме, как на странице входа.
const registrationApi = authApi.injectEndpoints({
  endpoints: build => ({
    startRegistration: build.mutation<
      { data: { login: string; expires_at: string } },
      RegistrationStartArgs
    >({
      query: body => ({
        url: '/registration',
        method: 'POST',
        // Канал доставки кода — почта (модуль registration_email).
        body: { ...body, channel: 'email' },
      }),
    }),

    confirmRegistration: build.mutation<
      { data: { user_id: number } },
      RegistrationConfirmArgs
    >({
      query: body => ({
        url: '/registration/confirm',
        method: 'POST',
        body,
      }),
    }),
  }),
});

export const { useStartRegistrationMutation, useConfirmRegistrationMutation } =
  registrationApi;
