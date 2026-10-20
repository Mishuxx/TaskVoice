import { LocalNotifications, ScheduleOptions } from '@capacitor/local-notifications';
import { Capacitor } from '@capacitor/core';
import { Task } from './supabase';

export const NOTIF_CHANNEL_ID = 'bh_tactical_alerts';

/**
 * Initialize notification channel and check/request permissions.
 */
export async function initNotifications(): Promise<boolean> {
  if (!Capacitor.isNativePlatform()) {
    console.log('[Notifications] Web platform, skipping native notifications init.');
    return false;
  }

  try {
    // 1. Create High-Priority Notification Channel for Android
    await LocalNotifications.createChannel({
      id: NOTIF_CHANNEL_ID,
      name: 'Alertas Tácticas BountyHunter',
      description: 'Recordatorios de misiones y alertas operativas',
      importance: 5, // High importance (heads-up notification + sound)
      visibility: 1,
      vibration: true,
      sound: undefined,
    });

    // 2. Check and request permission if needed
    const permStatus = await LocalNotifications.checkPermissions();
    if (permStatus.display === 'prompt' || permStatus.display === 'prompt-with-rationale') {
      const requested = await LocalNotifications.requestPermissions();
      return requested.display === 'granted';
    }

    return permStatus.display === 'granted';
  } catch (err) {
    console.warn('[Notifications] Error initializing notifications:', err);
    return false;
  }
}

/**
 * Explicitly prompt user for notification permission
 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!Capacitor.isNativePlatform()) {
    if ('Notification' in window) {
      const res = await Notification.requestPermission();
      return res === 'granted';
    }
    return false;
  }

  try {
    const res = await LocalNotifications.requestPermissions();
    return res.display === 'granted';
  } catch (err) {
    console.error('[Notifications] Permission request error:', err);
    return false;
  }
}

/**
 * Schedule a reminder notification for a task with a due date.
 * Typically 15-30 minutes before due date, or exact due date if close.
 */
export async function scheduleTaskReminder(task: Task): Promise<void> {
  if (!Capacitor.isNativePlatform() || !task.due_date || task.completed) return;

  try {
    const dueTime = new Date(task.due_date.replace(' ', 'T')).getTime();
    const now = Date.now();

    // If due date has already passed, don't schedule
    if (dueTime <= now) return;

    // Schedule 15 minutes before due time, or at due time if less than 15 mins left
    let triggerTime = dueTime - 15 * 60 * 1000;
    let notifBody = `La misión "${task.title}" vence en 15 minutos.`;

    if (triggerTime <= now) {
      triggerTime = dueTime;
      notifBody = `¡Atención Comandante! La misión "${task.title}" ha llegado a su tiempo límite.`;
    }

    // Task IDs are integers; local notifications accept numeric IDs
    const notifId = Math.abs(task.id % 2147483647);

    // Cancel any existing reminder for this task first
    await cancelTaskReminder(task.id);

    await LocalNotifications.schedule({
      notifications: [
        {
          id: notifId,
          title: `🎯 BountyHunter: ${task.title}`,
          body: notifBody,
          channelId: NOTIF_CHANNEL_ID,
          schedule: { at: new Date(triggerTime) },
          smallIcon: 'ic_launcher',
          extra: { taskId: task.id },
        },
      ],
    });
  } catch (err) {
    console.warn(`[Notifications] Could not schedule reminder for task ${task.id}:`, err);
  }
}

/**
 * Cancel a reminder notification for a task.
 */
export async function cancelTaskReminder(taskId: number): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;

  try {
    const notifId = Math.abs(taskId % 2147483647);
    await LocalNotifications.cancel({ notifications: [{ id: notifId }] });
  } catch (err) {
    console.warn(`[Notifications] Could not cancel reminder for task ${taskId}:`, err);
  }
}

/**
 * Send an immediate test notification to confirm the system works.
 */
export async function sendTestNotification(): Promise<boolean> {
  if (!Capacitor.isNativePlatform()) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('🎯 BountyHunter Test', { body: 'Sistema táctico operativo en Web' });
      return true;
    }
    return false;
  }

  try {
    await initNotifications();
    await LocalNotifications.schedule({
      notifications: [
        {
          id: 99999,
          title: '⚔️ BountyHunter: Sistema Operativo',
          body: '¡Notificaciones tácticas desbloqueadas y activas!',
          channelId: NOTIF_CHANNEL_ID,
          schedule: { at: new Date(Date.now() + 1000) }, // 1 second from now
          smallIcon: 'ic_launcher',
        },
      ],
    });
    return true;
  } catch (err) {
    console.error('[Notifications] Test notification failed:', err);
    return false;
  }
}
