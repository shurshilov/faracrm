import { useState, useRef, useCallback, useEffect } from 'react';
import { ActionIcon, Group, Text, Box, Tooltip } from '@mantine/core';
import {
  IconMicrophone,
  IconPlayerStop,
  IconTrash,
  IconSend,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import classes from './VoiceRecorder.module.css';

interface VoiceRecorderProps {
  /** Вызывается когда запись отправлена (кнопка отправки внутри компонента) */
  onRecorded: (file: {
    name: string;
    mimetype: string;
    size: number;
    content: string;
    is_voice: boolean;
  }) => void;
  /** Вызывается когда запись готова но не отправлена (для внешней кнопки отправки) */
  onRecordingReady?: (
    file: {
      name: string;
      mimetype: string;
      size: number;
      content: string;
      is_voice: boolean;
    } | null,
  ) => void;
  onCancel?: () => void;
  disabled?: boolean;
  /** Показывать кнопку отправки внутри компонента (по умолчанию true) */
  showSendButton?: boolean;
}

type RecordingState = 'idle' | 'recording' | 'recorded';

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function VoiceRecorder({
  onRecorded,
  onRecordingReady,
  onCancel,
  disabled,
  showSendButton = true,
}: VoiceRecorderProps) {
  const { t } = useTranslation('chat');
  const [state, setState] = useState<RecordingState>('idle');
  const [duration, setDuration] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<{
    name: string;
    mimetype: string;
    size: number;
    content: string;
    is_voice: boolean;
  } | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Cleanup
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [audioUrl]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setState('recorded');

        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());

        // Конвертируем в base64 и уведомляем родителя
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = (reader.result as string).split(',')[1];
          const filename = `voice_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.webm`;
          const file = {
            name: filename,
            mimetype: 'audio/webm',
            size: blob.size,
            content: base64,
            is_voice: true,
          };
          setPendingFile(file);
          onRecordingReady?.(file);
        };
        reader.readAsDataURL(blob);
      };

      mediaRecorder.start(100); // Collect data every 100ms
      setState('recording');
      setDuration(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setDuration(d => d + 1);
      }, 1000);
    } catch (error) {
      console.error('Error starting recording:', error);
      // Could show notification here
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && state === 'recording') {
      mediaRecorderRef.current.stop();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [state]);

  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
    }

    setAudioBlob(null);
    setAudioUrl(null);
    setDuration(0);
    setState('idle');
    setPendingFile(null);
    onRecordingReady?.(null);
    onCancel?.();
  }, [state, audioUrl, onCancel, onRecordingReady]);

  const sendRecording = useCallback(() => {
    if (!pendingFile) return;

    onRecorded(pendingFile);

    // Reset state
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(null);
    setAudioUrl(null);
    setDuration(0);
    setState('idle');
    setPendingFile(null);
    onRecordingReady?.(null);
  }, [pendingFile, audioUrl, onRecorded, onRecordingReady]);

  // Idle state - show microphone button
  if (state === 'idle') {
    return (
      <Tooltip label={t('recordVoice')} position="top">
        <ActionIcon
          variant="subtle"
          size="lg"
          onClick={startRecording}
          disabled={disabled}>
          <IconMicrophone size={20} />
        </ActionIcon>
      </Tooltip>
    );
  }

  // Recording or recorded state
  return (
    <Box className={classes.container}>
      <Group gap="xs" wrap="nowrap">
        {state === 'recording' && (
          <>
            <Box className={classes.recordingIndicator} />
            <Text size="sm" fw={500} c="red">
              {formatTime(duration)}
            </Text>
            <Tooltip label={t('stopRecording')} position="top">
              <ActionIcon
                variant="filled"
                color="red"
                size="md"
                onClick={stopRecording}>
                <IconPlayerStop size={16} />
              </ActionIcon>
            </Tooltip>
          </>
        )}

        {state === 'recorded' && (
          <>
            <audio
              src={audioUrl || undefined}
              controls
              className={classes.audioPreview}
            />
            <Text size="xs" c="dimmed">
              {formatTime(duration)}
            </Text>
          </>
        )}

        <Tooltip label={t('cancel')} position="top">
          <ActionIcon
            variant="subtle"
            color="gray"
            size="md"
            onClick={cancelRecording}>
            <IconTrash size={16} />
          </ActionIcon>
        </Tooltip>

        {state === 'recorded' && showSendButton && (
          <Tooltip label={t('send')} position="top">
            <ActionIcon
              variant="filled"
              color="blue"
              size="md"
              onClick={sendRecording}>
              <IconSend size={16} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
    </Box>
  );
}

export default VoiceRecorder;
