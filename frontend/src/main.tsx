// import '@mantine/core/styles.css';
import '@mantine/core/styles.layer.css';
import '@mantinex/mantine-header/styles.css';
import 'mantine-datatable/styles.layer.css';
import '@mantine/dates/styles.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './i18n'; // Инициализация i18next

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
