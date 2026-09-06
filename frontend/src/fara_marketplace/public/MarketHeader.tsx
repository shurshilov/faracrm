import { Button } from '@mantine/core';
import { Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { LangSwitch } from '@/components/LangSwitch';
import { selectIsLoggedIn } from '@/slices/authSlice';
import classes from './market.module.css';

/**
 * Шапка публичных страниц: логотип, язык, вход/регистрация или кабинет.
 * Раскладка — CSS-сетка в market.module.css (.topnav / .lang / .actions):
 * на десктопе одна строка, на телефоне кнопки во второй строке.
 */
export function MarketHeader() {
  const { t } = useTranslation('marketplace');
  const authenticated = useSelector(selectIsLoggedIn);

  return (
    <header className={classes.topnav}>
      <Link to="/market" className={classes.logo}>
        {/* Логомарк «F» проекта (он же фавикон) — компактнее полного лого */}
        <img src="/logo-mark.svg" alt="" className={classes.mark} />
        FARA
      </Link>
      <div className={classes.lang}>
        <LangSwitch />
      </div>
      <div className={classes.actions}>
        {authenticated ? (
          <Button component={Link} to="/marketplace_app" variant="light">
            {t('public.cabinet')}
          </Button>
        ) : (
          <>
            <Button component={Link} to="/login" variant="default">
              {t('public.signIn')}
            </Button>
            <Button
              component={Link}
              to="/register"
              className={classes.btnPrimary}>
              {t('public.register')}
            </Button>
          </>
        )}
      </div>
    </header>
  );
}
