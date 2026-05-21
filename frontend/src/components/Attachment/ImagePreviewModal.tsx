import { useState } from 'react';
import {
  Modal,
  Image,
  ActionIcon,
  Group,
  Tooltip,
  Box,
  Text,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconCopy,
  IconDownload,
  IconRotateClockwise,
  IconRotate,
  IconX,
  IconZoomIn,
  IconZoomOut,
} from '@tabler/icons-react';
import { triggerDownload } from '@/utils/attachmentUrls';
import classes from './ImagePreviewModal.module.css';

interface ImagePreviewModalProps {
  opened: boolean;
  onClose: () => void;
  src: string;
  filename?: string;
  onDownload?: () => void;
}

export function ImagePreviewModal({
  opened,
  onClose,
  src,
  filename,
  onDownload,
}: ImagePreviewModalProps) {
  const [rotation, setRotation] = useState(0);
  const [zoom, setZoom] = useState(1);

  const handleRotateRight = () => {
    setRotation((prev) => (prev + 90) % 360);
  };

  const handleRotateLeft = () => {
    setRotation((prev) => (prev - 90 + 360) % 360);
  };

  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + 0.25, 3));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(prev - 0.25, 0.5));
  };

  const handleDownload = () => {
    if (onDownload) {
      onDownload();
    } else {
      // Fallback: прямое скачивание из src (data:/blob:/URL)
      triggerDownload(src, filename || 'image');
    }
  };

  // Копирование URL картинки в буфер обмена. Полезно когда URL загруженной
  // иконки нужно вставить в другое место — например, в icons[].src
  // PWA-манифеста (см. форму компании, поле manifest_json).
  // src может быть data:base64 (только что загруженный файл, ещё не
  // отправленный на бэк) — такой URL копируем как есть, чужому
  // браузеру он не пригодится, но в JSON-манифест админ его всё равно
  // не вставит до сохранения.
  const handleCopyUrl = async () => {
    if (!src) return;
    try {
      // Абсолютный URL: относительный /api/... в буфере мало кому пригодится,
      // а в манифесте всё равно нужен абсолютный (или однозначно относительный
      // к origin). Поднимаем относительный к window.location.origin.
      const absolute = src.startsWith('data:')
        ? src
        : new URL(src, window.location.origin).toString();
      await navigator.clipboard.writeText(absolute);
      notifications.show({
        message: 'URL скопирован',
        color: 'green',
      });
    } catch {
      notifications.show({
        message: 'Не удалось скопировать URL',
        color: 'red',
      });
    }
  };

  const handleClose = () => {
    setRotation(0);
    setZoom(1);
    onClose();
  };

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
      }}
    >
      {/* Toolbar */}
      <Box className={classes.toolbar}>
        <Group justify="space-between" w="100%">
          <Text size="sm" c="white" truncate maw={300}>
            {filename}
          </Text>
          <Group gap="xs">
            <Tooltip label="Уменьшить">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleZoomOut}
              >
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
                onClick={handleZoomIn}
              >
                <IconZoomIn size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Box w={16} />
            <Tooltip label="Повернуть влево">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleRotateLeft}
              >
                <IconRotate size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Повернуть вправо">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleRotateRight}
              >
                <IconRotateClockwise size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Box w={16} />
            <Tooltip label="Скопировать URL">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleCopyUrl}
              >
                <IconCopy size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Скачать">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleDownload}
              >
                <IconDownload size={20} color="white" />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Закрыть">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={handleClose}
              >
                <IconX size={20} color="white" />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </Box>

      {/* Image container */}
      <Box className={classes.imageContainer} onClick={handleClose}>
        <Box
          className={classes.imageWrapper}
          onClick={(e) => e.stopPropagation()}
          style={{
            transform: `rotate(${rotation}deg) scale(${zoom})`,
          }}
        >
          <Image
            src={src}
            alt={filename}
            fit="contain"
            className={classes.image}
          />
        </Box>
      </Box>
    </Modal>
  );
}
