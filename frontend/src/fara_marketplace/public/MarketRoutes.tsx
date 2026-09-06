import { Route, Routes } from 'react-router-dom';
import MarketPage from './MarketPage';
import AppPage from './AppPage';

/** Публичные страницы каталога: /market и /market/:id (без входа). */
export default function MarketRoutes() {
  return (
    <Routes>
      <Route index element={<MarketPage />} />
      <Route path=":id" element={<AppPage />} />
    </Routes>
  );
}
