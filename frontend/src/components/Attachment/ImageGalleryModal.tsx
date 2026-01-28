import { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  Image,
  ActionIcon,
  Group,
  Tooltip,
  Box,
  Text,
  Loader,
} from '@mantine/core';
import {
  IconDownload,
  IconRotateClockwise,
  IconRotate,
  IconX,
  IconZoomIn,
  IconZoomOut,
  IconChevronLeft,
  IconChevronRight,
} from '@tabler/icons-react';
import { useSelector } from 'react-redux';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { selectCurrentSession } from '@/slices/authSlice';
import { isImageMimetype } from './fileIcons';
import classes from './ImagePreviewModal.module.css';

export interface GalleryItem {
  id?: number;
  name?: string;
  mimetype?: string;
  content?: string; // base64
}

interface ImageGalleryModalProps {
  opened: boolean;
  onClose: () => void;
  items: GalleryItem[];
  initialIndex?: number;
  onDownload?: (item: GalleryItem) => void;
}

export function ImageGalleryModal({
  opened,
  onClose,
  items,
  initialIndex = 0,
  onDownload,
}: ImageGalleryModalProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [rotation, setRotation] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [imageError, setImageError] = useState(false);

  const session = useSelector(selectCurrentSession);

  // Фильтруем только изображения для навигации
  const imageItems = items.filter(item => isImageMimetype(item.mimetype));
  const currentItem = imageItems[currentIndex];
  const hasMultipleImages = imageItems.length > 1;

  // Сброс при открытии
  useEffect(() => {
    if (opened) {
      setCurrentIndex(initialIndex);
      setRotation(0);
      setZoom(1);
    }
  }, [opened, initialIndex]);

  // Загрузка изображения
  useEffect(() => {
    if (!opened || !currentItem) return;

    setLoadedSrc(null);
    setImageError(false);
    setRotation(0);
    setZoom(1);

    // Если есть base64 контент
    if (currentItem.content) {
      setLoadedSrc(
        `data:${currentItem.mimetype};base64,${currentItem.content}`,
      );
      return;
    }

    // Загружаем через API
    if (currentItem.id && session?.token) {
      setIsLoading(true);

      fetch(`${API_BASE_URL}/attachments/${currentItem.id}/preview`, {
        headers: {
          Authorization: `Bearer ${session.token}`,
        },
      })
        .then(response => {
          if (!response.ok) throw new Error('Failed to load image');
          return response.blob();
        })
        .then(blob => {
          const reader = new FileReader();
          reader.onload = () => {
            setLoadedSrc(reader.result as string);
          };
          reader.readAsDataURL(blob);
        })
        .catch(() => {
          setImageError(true);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [opened, currentIndex, currentItem, session?.token]);

  // Навигация
  const goToPrevious = useCallback(() => {
    setCurrentIndex(prev => (prev > 0 ? prev - 1 : imageItems.length - 1));
  }, [imageItems.length]);

  const goToNext = useCallback(() => {
    setCurrentIndex(prev => (prev < imageItems.length - 1 ? prev + 1 : 0));
  }, [imageItems.length]);

  // Клавиатурная навигация
  useEffect(() => {
    if (!opened) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowLeft':
          goToPrevious();
          break;
        case 'ArrowRight':
          goToNext();
          break;
        case 'Escape':
          handleClose();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [opened, goToPrevious, goToNext]);

  const handleRotateRight = () => {
    setRotation(prev => (prev + 90) % 360);
  };

  const handleRotateLeft = () => {
    setRotation(prev => (prev - 90 + 360) % 360);
  };

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.25, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.25, 0.5));
  };

  const handleDownload = () => {
    if (onDownload && currentItem) {
      onDownload(currentItem);
    } else if (loadedSrc && currentItem) {
      const link = document.createElement('a');
      link.href = loadedSrc;
      link.download = currentItem.name || 'image';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const handleClose = () => {
    setRotation(0);
    setZoom(1);
    onClose();
  };

  if (!currentItem) return null;

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      size="xl"
      fullScreen
      padding={0}
      withCloseButton={false}
      classNames={{
        body: classes.modalBody,
        content: classes.modalContent,
      }}>
      {/* Toolbar */}
      <Box className={classes.toolbar}>
        <Group justify="space-between" w="100%">
          <Group gap="xs">
            <Text size="sm" c="white" truncate maw={300}>
              {currentItem.name}
            </Text>
            {hasMultipleImages && (
              <Text size="sm" c="dimmed">
                {currentIndex + 1} / {imageItems.length}
              </Text>
            )}
          </Group>
          <Group gap="xs">
            <Tooltip label="Уменьшить">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleZoomOut}>
                <IconZoomOut size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Text size="sm" c="white" w={50} ta="center">
              {Math.round(zoom * 100)}%
            </Text>
            <Tooltip label="Увеличить">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleZoomIn}>
                <IconZoomIn size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Box w={16} />
            <Tooltip label="Повернуть влево">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleRotateLeft}>
                <IconRotate size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Повернуть вправо">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleRotateRight}>
                <IconRotateClockwise size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Box w={16} />
            <Tooltip label="Скачать">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleDownload}>
                <IconDownload size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Закрыть">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleClose}>
                <IconX size={20} color="white" />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </Box>

      {/* Navigation arrows */}
      {hasMultipleImages && (
        <>
          <ActionIcon
            className={classes.navButton}
            style={{ left: 16 }}
            variant="filled"
            color="dark"
            size="xl"
            radius="xl"
            onClick={goToPrevious}>
            <IconChevronLeft size={28} />
          </ActionIcon>
          <ActionIcon
            className={classes.navButton}
            style={{ right: 16 }}
            variant="filled"
            color="dark"
            size="xl"
            radius="xl"
            onClick={goToNext}>
            <IconChevronRight size={28} />
          </ActionIcon>
        </>
      )}

      {/* Image container */}
      <Box className={classes.imageContainer} onClick={handleClose}>
        {isLoading ? (
          <Loader size="lg" color="white" />
        ) : imageError ? (
          <Text c="white">Ошибка загрузки изображения</Text>
        ) : loadedSrc ? (
          <Box
            className={classes.imageWrapper}
            onClick={e => e.stopPropagation()}
            style={{
              transform: `rotate(${rotation}deg) scale(${zoom})`,
            }}>
            <Image
              src={loadedSrc}
              alt={currentItem.name}
              fit="contain"
              className={classes.image}
            />
          </Box>
        ) : null}
      </Box>
    </Modal>
  );
}
