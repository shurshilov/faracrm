import { Group, Rating, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useGetMarketReviewsQuery } from '../api';

/** Отзывы о приложении: средняя оценка и список, новые первыми. */
export function ReviewList({ appId }: { appId: number }) {
  const { t, i18n } = useTranslation('marketplace');
  const { data } = useGetMarketReviewsQuery(appId);
  const reviews = data?.data || [];

  if (!reviews.length) {
    return (
      <Text size="sm" c="dimmed">
        {t('reviews.empty')}
      </Text>
    );
  }

  const average =
    reviews.reduce((sum, review) => sum + review.rating, 0) / reviews.length;

  return (
    <Stack gap="md">
      <Group gap="xs">
        <Rating value={average} fractions={10} readOnly />
        <Text size="sm" c="dimmed">
          {t('reviews.summary', {
            average: average.toFixed(1),
            count: reviews.length,
          })}
        </Text>
      </Group>
      {reviews.map(review => (
        <Stack key={review.id} gap={4}>
          <Group gap="xs">
            <Text size="sm" fw={500}>
              {review.author?.name}
            </Text>
            <Rating value={review.rating} readOnly size="xs" />
            <Text size="xs" c="dimmed">
              {new Date(review.date).toLocaleDateString(i18n.language)}
            </Text>
          </Group>
          {review.text && (
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {review.text}
            </Text>
          )}
        </Stack>
      ))}
    </Stack>
  );
}
