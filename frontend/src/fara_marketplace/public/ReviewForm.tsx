import { useState } from 'react';
import { Anchor, Button, Rating, Stack, Text, Textarea } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { useCreateMutation } from '@/services/api/crudApi';
import { selectCurrentSession, selectIsLoggedIn } from '@/slices/authSlice';
import { useGetMarketReviewsQuery } from '../api';

/**
 * Форма отзыва: только для вошедших, один отзыв на приложение и не о своём.
 * Те же проверки держит бэк (MarketplaceReview.create) — здесь форма просто
 * не показывается, когда отзыв всё равно не примут.
 */
export function ReviewForm({
  appId,
  vendorId,
}: {
  appId: number;
  vendorId: number | null;
}) {
  const { t } = useTranslation('marketplace');
  const authenticated = useSelector(selectIsLoggedIn);
  const userId = useSelector(selectCurrentSession)?.user_id?.id;
  const { data, refetch } = useGetMarketReviewsQuery(appId);
  const [create, { isLoading }] = useCreateMutation();
  const [rating, setRating] = useState(0);
  const [text, setText] = useState('');

  if (!authenticated) {
    return (
      <Anchor component={Link} to="/login" size="sm">
        {t('reviews.signIn')}
      </Anchor>
    );
  }
  if (userId === vendorId) return null;
  if (data?.data.some(review => review.author?.id === userId)) {
    return (
      <Text size="sm" c="dimmed">
        {t('reviews.already')}
      </Text>
    );
  }

  const handleSubmit = async () => {
    await create({
      model: 'marketplace_review',
      values: { app_id: appId, rating, text: text.trim() || null },
    }).unwrap();
    setRating(0);
    setText('');
    refetch();
    notifications.show({ message: t('reviews.sent') });
  };

  return (
    <Stack gap="xs">
      <Rating value={rating} onChange={setRating} size="lg" />
      <Textarea
        placeholder={t('reviews.placeholder')}
        value={text}
        onChange={e => setText(e.currentTarget.value)}
        autosize
        minRows={3}
      />
      <Button
        onClick={handleSubmit}
        loading={isLoading}
        disabled={!rating}
        w="fit-content">
        {t('reviews.submit')}
      </Button>
    </Stack>
  );
}
