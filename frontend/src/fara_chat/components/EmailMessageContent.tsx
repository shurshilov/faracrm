import { useMemo } from 'react';
import { Box, Text, Spoiler, Anchor, ActionIcon, Tooltip } from '@mantine/core';
import { IconExternalLink, IconMail } from '@tabler/icons-react';
import DOMPurify from 'dompurify';
import styles from './EmailMessageContent.module.css';

interface EmailMessageContentProps {
  body: string;
  maxHeight?: number;
}

/**
 * Компонент для безопасного отображения HTML email сообщений.
 * 
 * Особенности:
 * - Санитизация HTML через DOMPurify (защита от XSS)
 * - Все ссылки открываются в новой вкладке
 * - Ссылки помечаются иконкой внешней ссылки
 * - Изображения отображаются inline
 * - Длинные сообщения сворачиваются
 */
export function EmailMessageContent({ 
  body, 
  maxHeight = 300 
}: EmailMessageContentProps) {
  // Санитизация HTML
  const sanitizedHtml = useMemo(() => {
    // Настраиваем DOMPurify
    const config: DOMPurify.Config = {
      ALLOWED_TAGS: [
        'p', 'br', 'b', 'i', 'u', 'strong', 'em', 'a', 'img',
        'div', 'span', 'blockquote', 'pre', 'code',
        'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'table', 'thead', 'tbody', 'tr', 'td', 'th',
        'hr', 'sub', 'sup', 'small',
      ],
      ALLOWED_ATTR: [
        'href', 'src', 'alt', 'title', 'style', 'class',
        'width', 'height', 'target', 'rel',
      ],
      ALLOW_DATA_ATTR: false,
      // Запрещаем опасные протоколы
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
    };

    // Санитизируем
    let clean = DOMPurify.sanitize(body, config);

    // После санитизации модифицируем ссылки
    const div = document.createElement('div');
    div.innerHTML = clean;

    // Все ссылки открываем в новой вкладке и добавляем rel="noopener noreferrer"
    const links = div.querySelectorAll('a');
    links.forEach(link => {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer nofollow');
      // Добавляем класс для стилизации
      link.classList.add(styles.externalLink);
    });

    // Ограничиваем размер изображений
    const images = div.querySelectorAll('img');
    images.forEach(img => {
      img.style.maxWidth = '100%';
      img.style.height = 'auto';
    });

    return div.innerHTML;
  }, [body]);

  // Проверяем, нужно ли сворачивание
  const isLongContent = body.length > 1000;

  if (isLongContent) {
    return (
      <Box className={styles.emailContent}>
        <Box className={styles.emailHeader}>
          <IconMail size={14} />
          <Text size="xs" c="dimmed">Email message</Text>
        </Box>
        <Spoiler 
          maxHeight={maxHeight} 
          showLabel="Показать полностью"
          hideLabel="Свернуть"
          styles={{
            control: {
              color: 'var(--mantine-color-blue-6)',
              fontSize: 'var(--mantine-font-size-xs)',
            }
          }}
        >
          <div 
            className={styles.emailBody}
            dangerouslySetInnerHTML={{ __html: sanitizedHtml }} 
          />
        </Spoiler>
      </Box>
    );
  }

  return (
    <Box className={styles.emailContent}>
      <Box className={styles.emailHeader}>
        <IconMail size={14} />
        <Text size="xs" c="dimmed">Email message</Text>
      </Box>
      <div 
        className={styles.emailBody}
        dangerouslySetInnerHTML={{ __html: sanitizedHtml }} 
      />
    </Box>
  );
}
