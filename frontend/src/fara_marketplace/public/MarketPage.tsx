import { useEffect, useState } from 'react';
import {
  Center,
  Group,
  Loader,
  Pagination,
  SegmentedControl,
  Select,
  SimpleGrid,
  Text,
  TextInput,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { CATEGORIES, useListMarketAppsQuery } from '../api';
import { AppCard } from './AppCard';
import { MarketHeader } from './MarketHeader';
import classes from './market.module.css';

type Pricing = 'all' | 'free' | 'paid';
type Sort = 'popular' | 'new' | 'price';

const PAGE_SIZE = 24;

/** Публичный каталог: поиск, категория, платные/бесплатные, сортировка. */
export default function MarketPage() {
  const { t } = useTranslation('marketplace');
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [category, setCategory] = useState<string | null>(null);
  const [pricing, setPricing] = useState<Pricing>('all');
  const [sort, setSort] = useState<Sort>('popular');
  const [page, setPage] = useState(1);

  // Смена фильтра/поиска/сортировки — снова с первой страницы.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, category, pricing, sort]);

  const { data, isLoading } = useListMarketAppsQuery({
    search: debouncedSearch.trim() || undefined,
    category: category || undefined,
    free: pricing === 'all' ? undefined : pricing === 'free',
    sort,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
  const apps = data?.data || [];
  const totalPages = Math.ceil((data?.total || 0) / PAGE_SIZE);

  return (
    <div className={classes.root}>
      <MarketHeader />
      <div className={classes.container}>
        <div className={classes.hero}>
          <span className={classes.heroBadge}>{t('public.badge')}</span>
          <h1 className={classes.heroTitle}>{t('public.title')}</h1>
          <p className={classes.heroSubtitle}>{t('public.subtitle')}</p>
        </div>

        {/* Фильтры: телефон — столбик, планшет — 2×2, десктоп — одна строка. */}
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="sm" mb="xl">
          <TextInput
            leftSection={<IconSearch size={16} />}
            placeholder={t('public.searchPlaceholder')}
            value={search}
            onChange={e => setSearch(e.currentTarget.value)}
          />
          <Select
            clearable
            placeholder={t('public.allCategories')}
            data={CATEGORIES.map(value => ({
              value,
              label: t(`categories.${value}`),
            }))}
            value={category}
            onChange={setCategory}
          />
          <SegmentedControl
            fullWidth
            value={pricing}
            onChange={value => setPricing(value as Pricing)}
            data={[
              { value: 'all', label: t('public.all') },
              { value: 'free', label: t('public.free') },
              { value: 'paid', label: t('public.paid') },
            ]}
          />
          <Select
            allowDeselect={false}
            data={[
              { value: 'popular', label: t('public.sortPopular') },
              { value: 'new', label: t('public.sortNew') },
              { value: 'price', label: t('public.sortPrice') },
            ]}
            value={sort}
            onChange={value => setSort((value as Sort) || 'popular')}
          />
        </SimpleGrid>

        {isLoading ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : apps.length === 0 ? (
          <Text ta="center" c="dimmed" py="xl">
            {t('public.empty')}
          </Text>
        ) : (
          <>
            <div className={classes.grid}>
              {apps.map(app => (
                <AppCard key={app.id} app={app} />
              ))}
            </div>
            {totalPages > 1 && (
              <Group justify="center" mt="xl">
                <Pagination
                  total={totalPages}
                  value={page}
                  onChange={setPage}
                  color="teal"
                />
              </Group>
            )}
          </>
        )}
      </div>
    </div>
  );
}
