import { store } from '@store/store';
import { MantineProvider } from '@mantine/core';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { Layout } from '@/layout/Layout';
import { theme } from './theme';
import { ApiErrorModal } from './components/ErrorModal/ErrorModal';
// import { ApiErrorModal } from './components/ErrorModal';

export default function App() {
  return (
    <MantineProvider theme={theme}>
      <Provider store={store}>
        <BrowserRouter>
          <Layout />
          <ApiErrorModal />
        </BrowserRouter>
      </Provider>
    </MantineProvider>
  );
}
