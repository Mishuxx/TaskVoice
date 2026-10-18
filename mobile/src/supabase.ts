import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://wklsebcypnspferilraz.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_sbEUU0WhieAuQZMhcm1glQ_MpC9bT6Y';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export interface Task {
  id: number;
  title: string;
  description?: string;
  category_id?: number | null;
  due_date?: string | null;
  priority: number; // 1: Baja, 2: Media, 3: Alta
  progress: number;
  completed: boolean;
  is_recurring: boolean;
  recurrence_days?: string;
  recurrence_time?: string;
  recurrence_type?: string;
  created_at: string;
  completed_at?: string | null;
}

export interface Category {
  id: number;
  name: string;
  color: string;
}

export interface GamificationProfile {
  id: number;
  xp: number;
  level: number;
  total_xp: number;
  streak_days: number;
  tasks_completed_count: number;
}
