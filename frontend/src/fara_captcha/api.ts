import { authApi } from '@/services/auth/auth';

export interface CaptchaChallenge {
  token: string;
  /** Задачка картинкой (PNG data-URI) — в DOM только пиксели, не текст. */
  image: string;
}

// Живёт в authApi: «тихий» baseQuery (без глобальной модалки ошибок) и
// ручка публичная — задачку берём до входа, на странице регистрации.
const captchaApi = authApi.injectEndpoints({
  endpoints: build => ({
    getCaptcha: build.query<{ data: CaptchaChallenge }, void>({
      query: () => '/captcha/new',
    }),
  }),
});

export const { useLazyGetCaptchaQuery } = captchaApi;
