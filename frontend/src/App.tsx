import { store } from '@store/store';
import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { Layout } from '@/layout/Layout';
import { theme } from './theme';
import { ApiErrorModal } from './components/ErrorModal/ErrorModal';
// import { ApiErrorModal } from './components/ErrorModal';

export default function App() {
  return (
    <MantineProvider theme={theme}>
      <Notifications position="bottom-right" zIndex={1000} />
      <Provider store={store}>
        <BrowserRouter>
          <Layout />
          <ApiErrorModal />
        </BrowserRouter>
      </Provider>
    </MantineProvider>
  );
}
