import { store } from '@store/store';
import { MantineProvider } from '@mantine/core';
import { DatesProvider } from '@mantine/dates';
import { Notifications } from '@mantine/notifications';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Layout } from '@/layout/Layout';
import { theme } from './theme';
import { ApiErrorModal } from './components/ErrorModal/ErrorModal';
// import { ApiErrorModal } from './components/ErrorModal';

export default function App() {
  const { i18n } = useTranslation();
  // i18n.language может быть 'en-US' — dayjs/Mantine ждут 'en'
  const datesLocale = (i18n.language || 'en').split('-')[0];

  return (
    <MantineProvider theme={theme}>
      <DatesProvider settings={{ locale: datesLocale, firstDayOfWeek: 1 }}>
        <Notifications position="bottom-right" zIndex={1000} />
        <Provider store={store}>
          <BrowserRouter>
            <Layout />
            <ApiErrorModal />
          </BrowserRouter>
        </Provider>
      </DatesProvider>
    </MantineProvider>
  );
}
