// Copyright 2025 FARA CRM
// Звонок входящего вызова — общий для внутренних звонков и для звонилки в АТС.
//
// Синтезируем тон, а не проигрываем файл: файл пришлось бы класть в статику,
// тащить через сборку и разрешать в CSP, а нужен обычный вызывной сигнал —
// 425 Гц, секунда через три, как в городской телефонии. Двадцать строк
// WebAudio вместо ассета.

const TONE_HZ = 425;
const ON_SEC = 1;
const OFF_SEC = 3;
// Громкость намеренно небольшая: сигнал должен привлечь внимание, а не
// напугать человека в наушниках.
const VOLUME = 0.15;

let audioCtx: AudioContext | null = null;
let repeat: ReturnType<typeof setInterval> | null = null;
let ringing = false;

function context(): AudioContext | null {
  if (audioCtx) return audioCtx;
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!Ctor) return null;
  audioCtx = new Ctor();
  return audioCtx;
}

/** Один гудок с мягкими фронтами — без них слышен щелчок на старте и срезе. */
function beep(ctx: AudioContext): void {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  const now = ctx.currentTime;

  osc.type = 'sine';
  osc.frequency.value = TONE_HZ;
  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(VOLUME, now + 0.05);
  gain.gain.setValueAtTime(VOLUME, now + ON_SEC - 0.05);
  gain.gain.linearRampToValueAtTime(0, now + ON_SEC);

  osc.connect(gain).connect(ctx.destination);
  osc.start(now);
  osc.stop(now + ON_SEC);
}

export function startRinging(): void {
  if (ringing) return;
  const ctx = context();
  if (!ctx) return;
  ringing = true;

  // Контекст мог остаться приостановленным с прошлого звонка или не
  // запуститься вовсе — до первого клика по странице браузер звук не даёт.
  // Отказ не мешает остальному: карточка входящего всё равно показана.
  void ctx.resume().catch(() => undefined);
  beep(ctx);
  repeat = setInterval(() => beep(ctx), (ON_SEC + OFF_SEC) * 1000);
}

export function stopRinging(): void {
  ringing = false;
  if (repeat) clearInterval(repeat);
  repeat = null;
  // Контекст не закрываем: их количество на вкладку ограничено, а на
  // следующем звонке он понадобится снова.
  void audioCtx?.suspend().catch(() => undefined);
}
