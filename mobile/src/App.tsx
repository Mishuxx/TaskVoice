import React, { useState, useEffect, useMemo } from 'react';
import { registerPlugin, Capacitor } from '@capacitor/core';
import { supabase, Task, Category, GamificationProfile } from './supabase';
import { 
  CheckCircle2, Circle, Mic, MicOff, Plus, Flame, 
  Trophy, Calendar, Clock, RefreshCw, Trash2, Tag, 
  Sparkles, Check, ChevronRight, BarChart3, Swords, 
  ListTodo, ChevronDown, Edit3, X, AlertCircle, Award,
  Shield, Zap, Star, Radio, Bell, BellOff
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { 
  initNotifications, 
  requestNotificationPermission, 
  scheduleTaskReminder, 
  cancelTaskReminder, 
  sendTestNotification 
} from './notifications';

interface VoiceInputPluginType {
  isAvailable(): Promise<{ available: boolean }>;
  promptSpeech(options?: { language?: string; prompt?: string }): Promise<{ success: boolean; text: string; matches?: string[] }>;
}

const VoiceInput = registerPlugin<VoiceInputPluginType>('VoiceInput');

function parseVoiceCommand(text: string, categoriesList: Category[]): { title: string; categoryId?: number; priority: number } {
  let clean = text.trim();
  const prefixes = [
    /^a[ñn]adir tarea (de |para )?/i,
    /^nueva tarea (de |para )?/i,
    /^crear tarea (de |para )?/i,
    /^agregar tarea (de |para )?/i,
    /^anotar (de |para )?/i,
    /^grabar tarea (de |para )?/i,
    /^tarea (de |para )?/i,
  ];
  for (const p of prefixes) {
    if (p.test(clean)) {
      clean = clean.replace(p, '');
      break;
    }
  }

  if (clean.length > 0) {
    clean = clean.charAt(0).toUpperCase() + clean.slice(1);
  }

  let priority = 2;
  if (/urgente|alta prioridad|prioridad alta|inmediat[oa]/i.test(clean)) {
    priority = 3;
    clean = clean.replace(/urgente|alta prioridad|prioridad alta|inmediat[oa]/gi, '').trim();
  } else if (/baja prioridad|prioridad baja/i.test(clean)) {
    priority = 1;
    clean = clean.replace(/baja prioridad|prioridad baja/gi, '').trim();
  }

  let categoryId: number | undefined = undefined;
  const lower = clean.toLowerCase();
  for (const cat of categoriesList) {
    const cName = cat.name.toLowerCase();
    if (cName.includes('salud') && /salud|m[eé]dic|ejercicio|espalda|terapia|gimnasio|agua|pastilla|remedio|doctor/i.test(lower)) {
      categoryId = cat.id;
      break;
    }
    if (cName.includes('trabaj') && /trabajo|reuni[oó]n|cliente|informe|azure|aws|skillea|diego|proyecto|correo|reporte/i.test(lower)) {
      categoryId = cat.id;
      break;
    }
    if (cName.includes('estudio') && /estudio|curso|libro|aprender|nota|certificaci[oó]n|examen|tarea|clase/i.test(lower)) {
      categoryId = cat.id;
      break;
    }
    if (cName.includes('personal') && /personal|comprar|casa|gato|perro|comida|nevera|basura|llave|limpieza|mercado/i.test(lower)) {
      categoryId = cat.id;
      break;
    }
  }

  return { title: clean, categoryId, priority };
}

interface Subtask {
  id: number;
  task_id: number;
  title: string;
  completed: boolean;
}

const RANKS = [
  { level: 1, title: "Recluta Terran", icon: "⚔️", desc: "Primeros pasos en la línea de frente." },
  { level: 2, title: "Soldado Marine", icon: "🛡️", desc: "Veterano de escaramuzas tácticas." },
  { level: 3, title: "Fantasma Psiónico", icon: "⚡", desc: "Especialista en operaciones encubiertas." },
  { level: 4, title: "Inquisidor del Vacío", icon: "🔥", desc: "Purificador de sectores hostiles." },
  { level: 5, title: "Piloto Siege Tank", icon: "💎", desc: "Poder de fuego destructivo y disciplinado." },
  { level: 6, title: "Exiliado Ascendente", icon: "🌌", desc: "Ha trascendido las pruebas del laberinto." },
  { level: 7, title: "Matadioses del Atlas", icon: "👑", desc: "Dominador de las fuerzas cósmicas." },
  { level: 8, title: "Capitán Battlecruiser", icon: "🪐", desc: "Comandante supremo de flotas estelares." },
  { level: 9, title: "Alto Templario", icon: "🌟", desc: "Maestría psiónica y concentración absoluta." },
  { level: 10, title: "Arconte Supremo", icon: "⚡", desc: "Fusión pura de energía y voluntad imparable." },
];

function getRank(level: number) {
  let curr = RANKS[0];
  let next = RANKS[1];
  for (let i = 0; i < RANKS.length; i++) {
    if (level >= RANKS[i].level) {
      curr = RANKS[i];
      next = RANKS[i + 1] || null;
    }
  }
  return { current: curr, next };
}

export function App() {
  // Navigation tabs: 3 Layers identical to PC
  const [activeLayer, setActiveLayer] = useState<'tasks' | 'dashboard' | 'missions'>('tasks');

  // Core Data
  const [tasks, setTasks] = useState<Task[]>([]);
  const [subtasks, setSubtasks] = useState<Record<number, Subtask[]>>({});
  const [expandedTasks, setExpandedTasks] = useState<Record<number, boolean>>({});
  const [categories, setCategories] = useState<Category[]>([]);
  const [profile, setProfile] = useState<GamificationProfile>({
    id: 1, xp: 0, level: 1, total_xp: 0, streak_days: 1, tasks_completed_count: 0
  });

  // Filters & UI States
  const [filterCat, setFilterCat] = useState<number | null>(null);
  const [filterPrio, setFilterPrio] = useState<number | null>(null);
  const [showCompleted, setShowCompleted] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [newSubtaskInputs, setNewSubtaskInputs] = useState<Record<number, string>>({});
  const [notifEnabled, setNotifEnabled] = useState(false);

  // Tactical Voice Command Modal States
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  const [voiceState, setVoiceState] = useState<'idle' | 'listening' | 'recognized' | 'error'>('idle');
  const [voiceTranscript, setVoiceTranscript] = useState('');
  const [voiceParsedTitle, setVoiceParsedTitle] = useState('');
  const [voiceParsedCategory, setVoiceParsedCategory] = useState<number | null>(null);
  const [voiceParsedPriority, setVoiceParsedPriority] = useState<number>(2);
  const [voiceErrorMessage, setVoiceErrorMessage] = useState('');

  // Complex Task Modal
  const [modalOpen, setModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState('');
  const [modalDesc, setModalDesc] = useState('');
  const [modalCat, setModalCat] = useState<number | null>(null);
  const [modalPriority, setModalPriority] = useState<number>(2);
  const [modalDueDate, setModalDueDate] = useState('');
  const [modalRecurring, setModalRecurring] = useState(false);

  useEffect(() => {
    loadAll();

    // Check and initialize notification channel & permissions
    initNotifications().then(active => {
      setNotifEnabled(active);
    });

    const channel = supabase
      .channel('bh_mobile_realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'bh_tasks' }, () => loadTasks())
      .on('postgres_changes', { event: '*', schema: 'public', table: 'bh_subtasks' }, () => loadSubtasks())
      .on('postgres_changes', { event: '*', schema: 'public', table: 'bh_gamification' }, () => loadProfile())
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  async function loadAll() {
    setSyncing(true);
    await Promise.all([loadTasks(), loadSubtasks(), loadCategories(), loadProfile()]);
    setSyncing(false);
  }

  async function loadTasks() {
    const { data } = await supabase
      .from('bh_tasks')
      .select('*')
      .eq('is_deleted', false)
      .order('id', { ascending: false });
    if (data) {
      setTasks(data);
      // Auto-schedule reminders for active tasks with due date
      data.forEach(t => {
        if (!t.completed && t.due_date) {
          scheduleTaskReminder(t);
        }
      });
    }
  }

  async function handleNotificationToggle() {
    const granted = await requestNotificationPermission();
    setNotifEnabled(granted);
    if (granted) {
      await sendTestNotification();
      alert("✅ ¡Notificaciones activadas!\nSe ha enviado una alerta táctica de prueba a tu barra de notificaciones.");
    } else {
      alert("⚠️ Notificaciones bloqueadas en Android.\n\nPara desbloquearlas manualmente:\n1. Abre Ajustes o Configuración en tu teléfono.\n2. Ve a Aplicaciones > BountyHunter.\n3. Entra a 'Notificaciones' y activa el interruptor 'Permitir notificaciones'.");
    }
  }

  async function loadSubtasks() {
    const { data } = await supabase.from('bh_subtasks').select('*');
    if (data) {
      const grouped: Record<number, Subtask[]> = {};
      data.forEach(st => {
        if (!grouped[st.task_id]) grouped[st.task_id] = [];
        grouped[st.task_id].push(st);
      });
      setSubtasks(grouped);
    }
  }

  async function loadCategories() {
    const { data } = await supabase.from('bh_categories').select('*');
    if (data) setCategories(data);
  }

  async function loadProfile() {
    const { data } = await supabase.from('bh_gamification').select('*').eq('id', 1).single();
    if (data) setProfile(data);
  }

  // Toggle complete task
  async function toggleTask(task: Task) {
    const nextCompleted = !task.completed;
    const now = new Date().toISOString();

    setTasks(prev => prev.map(t => t.id === task.id ? { ...t, completed: nextCompleted } : t));

    if (nextCompleted) {
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.8 },
        colors: ['#7C3AED', '#06B6D4', '#F59E0B']
      });

      const gainedXp = task.priority === 3 ? 60 : task.priority === 2 ? 35 : 20;
      const nextXp = profile.xp + gainedXp;
      const nextTotal = profile.total_xp + gainedXp;
      const nextLevel = Math.floor(nextTotal / 300) + 1;

      setProfile(p => ({
        ...p,
        xp: nextXp % 300,
        level: nextLevel,
        total_xp: nextTotal,
        tasks_completed_count: p.tasks_completed_count + 1
      }));

      await supabase.from('bh_gamification').update({
        xp: nextXp % 300,
        level: nextLevel,
        total_xp: nextTotal,
        tasks_completed_count: profile.tasks_completed_count + 1,
        updated_at: now
      }).eq('id', 1);
    }

    await supabase.from('bh_tasks').update({
      completed: nextCompleted,
      completed_at: nextCompleted ? now : null,
      updated_at: now
    }).eq('id', task.id);

    if (nextCompleted) {
      cancelTaskReminder(task.id);
    } else if (task.due_date) {
      scheduleTaskReminder({ ...task, completed: false });
    }
  }

  // Toggle subtask
  async function toggleSubtask(st: Subtask) {
    const nextCompleted = !st.completed;
    setSubtasks(prev => {
      const list = prev[st.task_id] || [];
      return {
        ...prev,
        [st.task_id]: list.map(item => item.id === st.id ? { ...item, completed: nextCompleted } : item)
      };
    });

    if (nextCompleted) {
      setProfile(p => ({ ...p, xp: (p.xp + 10) % 300, total_xp: p.total_xp + 10 }));
      await supabase.from('bh_gamification').update({
        xp: (profile.xp + 10) % 300,
        total_xp: profile.total_xp + 10,
        updated_at: new Date().toISOString()
      }).eq('id', 1);
    }

    await supabase.from('bh_subtasks').update({
      completed: nextCompleted,
      updated_at: new Date().toISOString()
    }).eq('id', st.id);
  }

  // Add subtask
  async function handleAddSubtask(taskId: number) {
    const val = (newSubtaskInputs[taskId] || '').trim();
    if (!val) return;

    setNewSubtaskInputs(prev => ({ ...prev, [taskId]: '' }));

    const { data } = await supabase.from('bh_subtasks').insert([{
      task_id: taskId,
      title: val,
      completed: false,
      updated_at: new Date().toISOString()
    }]).select().single();

    if (data) {
      setSubtasks(prev => ({
        ...prev,
        [taskId]: [...(prev[taskId] || []), data]
      }));
    }
  }

  // Quick Add
  async function handleQuickAdd(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!newTitle.trim()) return;

    const title = newTitle.trim();
    setNewTitle('');

    const { data } = await supabase.from('bh_tasks').insert([{
      title,
      priority: 2,
      category_id: filterCat,
      completed: false,
      progress: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_deleted: false
    }]).select().single();

    if (data) setTasks(prev => [data, ...prev]);
  }

  // Create Complex Task from Modal
  async function handleCreateComplexTask(e: React.FormEvent) {
    e.preventDefault();
    if (!modalTitle.trim()) return;

    const { data } = await supabase.from('bh_tasks').insert([{
      title: modalTitle.trim(),
      description: modalDesc.trim(),
      category_id: modalCat,
      priority: modalPriority,
      due_date: modalDueDate || null,
      is_recurring: modalRecurring,
      completed: false,
      progress: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_deleted: false
    }]).select().single();

    if (data) {
      if (data.due_date) {
        scheduleTaskReminder(data);
      }
      setTasks(prev => [data, ...prev]);
      setModalOpen(false);
      setModalTitle('');
      setModalDesc('');
      setModalDueDate('');
    }
  }

  // Tactical Voice Recognition (Native Android + Web Speech Fallback)
  async function startVoiceRecognition() {
    setVoiceModalOpen(true);
    setVoiceState('listening');
    setVoiceTranscript('');
    setVoiceParsedTitle('');
    setVoiceErrorMessage('');

    // 1. Android Capacitor Native Recognition (Google Speech Engine)
    if (Capacitor.isNativePlatform()) {
      try {
        const res = await VoiceInput.promptSpeech({
          language: 'es-ES',
          prompt: 'Comando de voz: Di tu tarea...',
        });

        if (res && res.success && res.text && res.text.trim()) {
          const raw = res.text.trim();
          setVoiceTranscript(raw);
          const parsed = parseVoiceCommand(raw, categories);
          setVoiceParsedTitle(parsed.title);
          setVoiceParsedCategory(parsed.categoryId ?? null);
          setVoiceParsedPriority(parsed.priority);
          setVoiceState('recognized');
        } else {
          setVoiceState('error');
          setVoiceErrorMessage('No se detectó audio o el comando fue cancelado.');
        }
      } catch (err: any) {
        console.error('Native voice error:', err);
        setVoiceState('error');
        setVoiceErrorMessage('Error de captura vocal: ' + (err?.message || 'Micrófono no disponible'));
      }
      return;
    }

    // 2. Browser Web Speech API Fallback
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceState('error');
      setVoiceErrorMessage('Reconocimiento web no disponible en este navegador. Utiliza la app instalada en tu móvil.');
      return;
    }

    try {
      const rec = new SpeechRecognition();
      rec.lang = 'es-ES';
      rec.continuous = false;
      rec.interimResults = true;

      rec.onstart = () => {
        setVoiceState('listening');
      };

      rec.onresult = (evt: any) => {
        let transcript = '';
        for (let i = evt.resultIndex; i < evt.results.length; ++i) {
          transcript += evt.results[i][0].transcript;
        }
        if (transcript) {
          setVoiceTranscript(transcript);
        }
      };

      rec.onerror = (evt: any) => {
        console.error('Speech recognition error:', evt);
        setVoiceState('error');
        setVoiceErrorMessage('Error al capturar voz (' + (evt.error || 'micrófono') + ').');
      };

      rec.onend = () => {
        setVoiceTranscript(prev => {
          if (prev.trim()) {
            const parsed = parseVoiceCommand(prev.trim(), categories);
            setVoiceParsedTitle(parsed.title);
            setVoiceParsedCategory(parsed.categoryId ?? null);
            setVoiceParsedPriority(parsed.priority);
            setVoiceState('recognized');
          } else {
            setVoiceState('error');
            setVoiceErrorMessage('No se detectó ningún comando vocal.');
          }
          return prev;
        });
      };

      rec.start();
    } catch (err: any) {
      console.error('Speech start exception:', err);
      setVoiceState('error');
      setVoiceErrorMessage('No se pudo activar el micrófono.');
    }
  }

  // Confirm and persist voice task
  async function confirmVoiceTask() {
    const titleToCreate = voiceParsedTitle.trim() || voiceTranscript.trim();
    if (!titleToCreate) return;

    const catId = voiceParsedCategory !== null ? voiceParsedCategory : (categories[0]?.id || null);
    const prio = voiceParsedPriority || 2;

    const newTask = {
      title: titleToCreate,
      description: 'Dictado por comando vocal',
      category_id: catId,
      due_date: '',
      priority: prio,
      progress: 0,
      completed: false,
      is_recurring: false,
      recurrence_days: '',
      recurrence_time: '',
      recurrence_type: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_deleted: false,
    };

    setVoiceModalOpen(false);

    // Optimistic UI insert
    const tempId = Date.now();
    setTasks(prev => [{ ...newTask, id: tempId }, ...prev]);

    // Give visual celebration + XP
    confetti({ particleCount: 50, spread: 60, origin: { y: 0.8 } });
    await addXP(10);

    // Save to Supabase
    const { data, error } = await supabase.from('bh_tasks').insert([newTask]).select();
    if (error) {
      console.error('Error creating voice task:', error);
      loadTasks();
    } else if (data && data[0]) {
      setTasks(prev => prev.map(t => t.id === tempId ? data[0] : t));
    }
  }

  // Delete task
  async function deleteTask(id: number) {
    cancelTaskReminder(id);
    setTasks(prev => prev.filter(t => t.id !== id));
    await supabase.from('bh_tasks').update({ is_deleted: true, updated_at: new Date().toISOString() }).eq('id', id);
  }

  // Filter tasks
  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      if (filterCat !== null && t.category_id !== filterCat) return false;
      if (filterPrio !== null && t.priority !== filterPrio) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = t.title.toLowerCase().includes(q);
        const matchesDesc = (t.description || '').toLowerCase().includes(q);
        if (!matchesTitle && !matchesDesc) return false;
      }
      return true;
    });
  }, [tasks, filterCat, filterPrio, searchQuery]);

  // Section splitting: HOY vs PRÓXIMAS vs COMPLETADAS (Identical to PC)
  const todayStr = new Date().toISOString().slice(0, 10);

  const todayTasks = useMemo(() => {
    return filteredTasks.filter(t => {
      if (t.completed) return false;
      const due = t.due_date;
      const created = t.created_at || '';
      return (due && (due.startsWith(todayStr) || due < todayStr)) || (!due && created.startsWith(todayStr));
    });
  }, [filteredTasks, todayStr]);

  const upcomingTasks = useMemo(() => {
    return filteredTasks.filter(t => {
      if (t.completed) return false;
      const due = t.due_date;
      const created = t.created_at || '';
      return !((due && (due.startsWith(todayStr) || due < todayStr)) || (!due && created.startsWith(todayStr)));
    });
  }, [filteredTasks, todayStr]);

  const completedTasks = useMemo(() => {
    return filteredTasks.filter(t => t.completed);
  }, [filteredTasks]);

  // Daily Mission calculation
  const totalTodayTargets = todayTasks.length + completedTasks.filter(t => (t.completed_at || '').startsWith(todayStr)).length;
  const completedTodayTargets = completedTasks.filter(t => (t.completed_at || '').startsWith(todayStr)).length;
  const rankInfo = getRank(profile.level);

  return (
    <div className="flex flex-col h-screen max-w-md mx-auto bg-bg-dark text-slate-100 select-none pb-safe">
      {/* 1. TOP HEADER & HUD BAR */}
      <header className="px-5 pt-8 pb-3 bg-bg-sidebar/95 backdrop-blur border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-accent-violet to-purple-600 flex items-center justify-center font-black text-xl shadow-lg shadow-purple-900/40">
            ⚔️
          </div>
          <div>
            <h1 className="text-lg font-black tracking-wider bg-gradient-to-r from-white via-purple-200 to-accent-turquoise bg-clip-text text-transparent">
              BOUNTYHUNTER
            </h1>
            <div className="flex items-center space-x-2 text-xs text-slate-400">
              <span className="flex items-center text-accent-gold font-semibold">
                <Flame className="w-3.5 h-3.5 mr-0.5 fill-accent-gold" />
                {profile.streak_days}d racha
              </span>
              <span>•</span>
              <span className="text-purple-400 font-semibold">{rankInfo.current.icon} Nv. {profile.level}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button 
            onClick={handleNotificationToggle}
            className={`p-2.5 rounded-xl bg-bg-surface border transition active:scale-95 ${
              notifEnabled 
                ? 'border-amber-500/40 text-accent-gold shadow-sm shadow-amber-950/40' 
                : 'border-border-subtle text-slate-500'
            }`}
            title={notifEnabled ? 'Notificaciones activas (toca para probar)' : 'Notificaciones bloqueadas (toca para activar)'}
          >
            {notifEnabled ? (
              <Bell className="w-4 h-4 text-accent-gold" />
            ) : (
              <BellOff className="w-4 h-4 text-rose-400" />
            )}
          </button>

          <button 
            onClick={loadAll} 
            disabled={syncing}
            className={`p-2.5 rounded-xl bg-bg-surface border border-border-subtle text-slate-300 hover:text-white transition active:scale-95 ${syncing ? 'animate-spin text-accent-violet' : ''}`}
            title="Sincronizar ahora"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* 2. LAYER NAVIGATION BAR (OPERACIONES / DASHBOARD / MISIONES) */}
      <nav className="flex px-4 py-2 bg-bg-surface/60 border-b border-border-subtle gap-1.5">
        <button
          onClick={() => setActiveLayer('tasks')}
          className={`flex-1 py-2 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 transition ${
            activeLayer === 'tasks'
              ? 'bg-accent-violet text-white shadow-md shadow-purple-900/50'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <ListTodo className="w-4 h-4" />
          <span>Operaciones</span>
        </button>

        <button
          onClick={() => setActiveLayer('dashboard')}
          className={`flex-1 py-2 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 transition ${
            activeLayer === 'dashboard'
              ? 'bg-accent-violet text-white shadow-md shadow-purple-900/50'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Dashboard</span>
        </button>

        <button
          onClick={() => setActiveLayer('missions')}
          className={`flex-1 py-2 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 transition ${
            activeLayer === 'missions'
              ? 'bg-accent-violet text-white shadow-md shadow-purple-900/50'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Swords className="w-4 h-4" />
          <span>Ascenso & RPG</span>
        </button>
      </nav>

      {/* 3. LAYER: OPERACIONES / TAREAS */}
      {activeLayer === 'tasks' && (
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Header controls (Non-scrollable) */}
          <div className="shrink-0 space-y-2.5 pb-2">
            {/* Daily Mission Banner (StarCraft HUD Style) */}
            <div className="mx-4 mt-3 p-3.5 rounded-2xl bg-gradient-to-r from-purple-950/40 via-bg-surface to-slate-900/70 border border-purple-800/40 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <span className="text-base">🎯</span>
                  <span className="text-xs font-extrabold tracking-wider text-purple-300">MISIÓN DEL DÍA</span>
                </div>
                <span className="text-[11px] font-mono text-accent-turquoise font-bold">
                  {completedTodayTargets} / {Math.max(1, totalTodayTargets)} completadas
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-950/80 overflow-hidden mb-2">
                <div 
                  className="h-full bg-gradient-to-r from-accent-violet via-purple-500 to-accent-turquoise rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, totalTodayTargets > 0 ? (completedTodayTargets / totalTodayTargets) * 100 : 0)}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-[10px] text-slate-400">
                <span>Completa todos los objetivos diarios</span>
                <span className="text-accent-gold font-bold">Recompensa: +150 XP 🎁</span>
              </div>
            </div>

            {/* Search & Priority Filter Pills */}
            <div className="px-4 flex items-center space-x-2">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Buscar misiones tácticas..."
                className="flex-1 px-3 py-1.5 rounded-xl bg-bg-surface border border-border-subtle text-xs text-white placeholder-slate-500 focus:outline-none focus:border-accent-violet"
              />
              <button
                onClick={() => setFilterPrio(filterPrio === 3 ? null : 3)}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1 ${
                  filterPrio === 3 ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-bg-surface text-slate-400 border border-border-subtle'
                }`}
              >
                <span>🔥 Alta</span>
              </button>
              <button
                onClick={() => startVoiceRecognition()}
                className="p-1.5 rounded-xl bg-cyan-500/15 text-cyan-400 border border-cyan-500/40 text-xs font-bold hover:bg-cyan-500 hover:text-white transition flex items-center gap-1 shadow-sm"
                title="Dictar por voz"
              >
                <Mic className="w-4 h-4" />
              </button>
              <button
                onClick={() => setModalOpen(true)}
                className="p-1.5 rounded-xl bg-accent-violet/20 text-accent-violet border border-accent-violet/40 text-xs font-bold hover:bg-accent-violet hover:text-white transition"
                title="Crear tarea compleja"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            {/* Categories Pill Slider */}
            <div className="px-4 flex space-x-2 overflow-x-auto no-scrollbar py-0.5">
              <button
                onClick={() => setFilterCat(null)}
                className={`px-3 py-1 rounded-full text-[11px] font-bold whitespace-nowrap transition ${
                  filterCat === null 
                    ? 'bg-accent-violet text-white shadow-md' 
                    : 'bg-bg-surface text-slate-400 border border-border-subtle'
                }`}
              >
                Todas ({tasks.filter(t => !t.completed).length})
              </button>
              {categories.map(cat => {
                const count = tasks.filter(t => t.category_id === cat.id && !t.completed).length;
                return (
                  <button
                    key={cat.id}
                    onClick={() => setFilterCat(filterCat === cat.id ? null : cat.id)}
                    className={`px-3 py-1 rounded-full text-[11px] font-bold whitespace-nowrap flex items-center space-x-1.5 transition ${
                      filterCat === cat.id
                        ? 'bg-white text-slate-900 shadow-md'
                        : 'bg-bg-surface text-slate-300 border border-border-subtle'
                    }`}
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cat.color }} />
                    <span>{cat.name}</span>
                    {count > 0 && <span className="opacity-60 text-[10px]">({count})</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tasks List (Dedicated Scrollable Area with clean margins) */}
          <div className="flex-1 overflow-y-auto px-4 py-2 space-y-4">
            {/* SECTION: HOY */}
            {todayTasks.length > 0 && (
              <div>
                <div className="flex items-center space-x-2 mb-2 px-1">
                  <span className="w-2 h-2 rounded-full bg-accent-turquoise animate-pulse" />
                  <h3 className="text-xs font-black tracking-wider text-slate-300 uppercase">
                    HOY ({todayTasks.length})
                  </h3>
                </div>
                <div className="space-y-2.5">
                  {todayTasks.map(task => renderTaskCard(task))}
                </div>
              </div>
            )}

            {/* SECTION: PRÓXIMAS */}
            {upcomingTasks.length > 0 && (
              <div>
                <div className="flex items-center space-x-2 mb-2 px-1">
                  <span className="w-2 h-2 rounded-full bg-purple-400" />
                  <h3 className="text-xs font-black tracking-wider text-slate-400 uppercase">
                    PRÓXIMAS ({upcomingTasks.length})
                  </h3>
                </div>
                <div className="space-y-2.5">
                  {upcomingTasks.map(task => renderTaskCard(task))}
                </div>
              </div>
            )}

            {/* Empty state */}
            {todayTasks.length === 0 && upcomingTasks.length === 0 && completedTasks.length === 0 && (
              <div className="h-48 flex flex-col items-center justify-center text-center text-slate-500 space-y-2">
                <div className="w-12 h-12 rounded-2xl bg-bg-surface flex items-center justify-center text-2xl border border-border-subtle">
                  🎯
                </div>
                <p className="font-semibold text-slate-300">¡Sector despejado Comandante!</p>
                <p className="text-xs max-w-xs text-slate-500">Agrega una tarea o pulsa el botón de voz para dictarla.</p>
                <button
                  type="button"
                  onClick={() => startVoiceRecognition()}
                  className="mt-2 px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600/30 to-cyan-500/30 border border-cyan-400/50 text-cyan-300 font-bold text-xs flex items-center gap-2 hover:brightness-125 transition active:scale-95 shadow-md shadow-violet-950/50"
                >
                  <Mic className="w-4 h-4 text-cyan-400 animate-pulse" />
                  <span>Dictar Tarea por Voz</span>
                </button>
              </div>
            )}

            {/* SECTION: COMPLETADAS */}
            {completedTasks.length > 0 && (
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2 px-1">
                  <h3 className="text-xs font-black tracking-wider text-slate-500 uppercase">
                    COMPLETADAS ({completedTasks.length})
                  </h3>
                  <button 
                    onClick={() => setShowCompleted(!showCompleted)}
                    className="text-[11px] text-purple-400 font-semibold"
                  >
                    {showCompleted ? 'Ocultar' : 'Mostrar'}
                  </button>
                </div>
                {showCompleted && (
                  <div className="space-y-2 opacity-60">
                    {completedTasks.map(task => renderTaskCard(task))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Quick-add & Voice Command Bar */}
          <div className="p-3 bg-bg-sidebar/95 backdrop-blur border-t border-border-subtle shrink-0">
            <div className="flex items-center gap-2">
              {/* Dedicated prominent Voice Dictation Button */}
              <button
                type="button"
                onClick={() => startVoiceRecognition()}
                className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-gradient-to-r from-violet-600/30 via-purple-700/25 to-cyan-500/25 border border-violet-500/60 hover:border-cyan-400 text-white text-xs font-black tracking-wider uppercase transition active:scale-95 shadow-md shadow-violet-950/60 group shrink-0"
                title="Dictar tarea por voz"
              >
                <span className="relative flex h-3.5 w-3.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                  <Mic className="relative inline-flex w-3.5 h-3.5 text-cyan-300 group-hover:scale-110 transition-transform" />
                </span>
                <span className="text-[11px] font-extrabold text-cyan-200">VOZ</span>
              </button>

              {/* Text Quick-add input */}
              <form onSubmit={handleQuickAdd} className="flex-1 flex items-center gap-1.5">
                <input
                  type="text"
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  placeholder="Escribir tarea... (o pulsa VOZ)"
                  className="flex-1 pl-3 pr-3 py-2.5 rounded-xl bg-bg-surface border border-border-subtle focus:border-accent-violet focus:outline-none text-xs placeholder-slate-500 text-white min-w-0"
                />
                <button
                  type="submit"
                  disabled={!newTitle.trim()}
                  className="px-3 py-2.5 rounded-xl bg-accent-violet text-white font-extrabold text-xs hover:bg-purple-600 disabled:opacity-30 transition active:scale-95 shadow-md shadow-purple-900/30 shrink-0"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* 4. LAYER: DASHBOARD DE RENDIMIENTO */}
      {activeLayer === 'dashboard' && (
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          <div>
            <h2 className="text-base font-extrabold text-white">Panel de Rendimiento Táctico</h2>
            <p className="text-xs text-slate-400">Métricas operativas en tiempo real sincronizadas con PC.</p>
          </div>

          {/* Stat Cards Grid */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-4 rounded-2xl bg-bg-surface border border-border-subtle flex flex-col justify-between">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">TOTAL TAREAS</span>
              <p className="text-2xl font-black text-white mt-1">{tasks.length}</p>
              <span className="text-[10px] text-accent-turquoise mt-1 font-medium">{tasks.filter(t => !t.completed).length} activas</span>
            </div>

            <div className="p-4 rounded-2xl bg-bg-surface border border-border-subtle flex flex-col justify-between">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">COMPLETADAS</span>
              <p className="text-2xl font-black text-accent-green mt-1">{tasks.filter(t => t.completed).length}</p>
              <span className="text-[10px] text-slate-400 mt-1 font-medium">Histórico global</span>
            </div>

            <div className="p-4 rounded-2xl bg-bg-surface border border-border-subtle flex flex-col justify-between">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">TASA DE ÉXITO</span>
              <p className="text-2xl font-black text-accent-gold mt-1">
                {tasks.length > 0 ? Math.round((tasks.filter(t => t.completed).length / tasks.length) * 100) : 0}%
              </p>
              <span className="text-[10px] text-slate-400 mt-1 font-medium">Eficacia militar</span>
            </div>

            <div className="p-4 rounded-2xl bg-bg-surface border border-border-subtle flex flex-col justify-between">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">RACHA ACTIVA</span>
              <p className="text-2xl font-black text-purple-400 mt-1 flex items-center">
                🔥 {profile.streak_days}
              </p>
              <span className="text-[10px] text-slate-400 mt-1 font-medium">Días consecutivos</span>
            </div>
          </div>

          {/* Category Distribution Breakdown */}
          <div className="p-4 rounded-2xl bg-bg-surface border border-border-subtle space-y-3">
            <h3 className="text-xs font-extrabold tracking-wider text-slate-300 uppercase">
              DISTRIBUCIÓN POR CATEGORÍA
            </h3>
            <div className="space-y-2">
              {categories.map(cat => {
                const count = tasks.filter(t => t.category_id === cat.id).length;
                const percent = tasks.length > 0 ? (count / tasks.length) * 100 : 0;
                return (
                  <div key={cat.id} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="flex items-center space-x-1.5 font-medium text-slate-300">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cat.color }} />
                        <span>{cat.name}</span>
                      </span>
                      <span className="font-mono text-slate-400">{count} ({percent.toFixed(0)}%)</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-slate-900 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundColor: cat.color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Tactical Notification Status Card */}
          <div className="p-4 rounded-2xl bg-bg-surface border border-border-subtle flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className={`p-2.5 rounded-xl ${notifEnabled ? 'bg-amber-500/10 text-accent-gold border border-amber-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`}>
                {notifEnabled ? <Bell className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
              </div>
              <div>
                <p className="text-xs font-black text-white">Alertas & Recordatorios</p>
                <p className="text-[11px] text-slate-400">
                  {notifEnabled ? 'Activas (recibes avisos tácticos 15m antes)' : 'Bloqueadas por el sistema Android'}
                </p>
              </div>
            </div>
            <button
              onClick={handleNotificationToggle}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition active:scale-95 ${
                notifEnabled
                  ? 'bg-slate-900 border border-border-subtle text-slate-300 hover:text-white'
                  : 'bg-accent-violet text-white shadow-md shadow-purple-900/30'
              }`}
            >
              {notifEnabled ? 'Probar' : 'Desbloquear'}
            </button>
          </div>
        </div>
      )}

      {/* 5. LAYER: MISIONES & ASCENSO RPG */}
      {activeLayer === 'missions' && (
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Current Rank Banner */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-purple-900/40 via-bg-surface to-slate-900 border border-purple-500/40 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-purple-400">RANGO MILITAR ACTUAL</span>
                <h2 className="text-lg font-black text-white flex items-center gap-1.5 mt-0.5">
                  <span>{rankInfo.current.icon}</span>
                  <span>{rankInfo.current.title}</span>
                </h2>
              </div>
              <div className="text-right">
                <span className="text-xs font-mono text-accent-turquoise font-extrabold">NIVEL {profile.level}</span>
                <p className="text-[11px] text-slate-400 font-mono">{profile.total_xp} XP Total</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 italic">{rankInfo.current.desc}</p>

            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-400">Progreso de ascenso</span>
                <span className="text-accent-turquoise font-mono">{profile.xp} / 300 XP</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-950 overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-accent-violet via-purple-500 to-accent-turquoise transition-all duration-500 rounded-full"
                  style={{ width: `${Math.min(100, (profile.xp / 300) * 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Roster of Ascension */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-extrabold tracking-wider text-slate-400 uppercase px-1">
              ESCALAFÓN DE ASCENSO Y HONOR
            </h3>
            <div className="space-y-2">
              {RANKS.map(r => {
                const isUnlocked = profile.level >= r.level;
                const isCurrent = rankInfo.current.level === r.level;
                return (
                  <div 
                    key={r.level}
                    className={`p-3 rounded-xl border flex items-center justify-between transition ${
                      isCurrent 
                        ? 'bg-purple-950/40 border-purple-500 shadow-md'
                        : isUnlocked 
                          ? 'bg-bg-surface/90 border-border-subtle opacity-80'
                          : 'bg-bg-dark/50 border-border-subtle/50 opacity-40'
                    }`}
                  >
                    <div className="flex items-center space-x-3">
                      <span className="text-xl">{r.icon}</span>
                      <div>
                        <div className="flex items-center space-x-2">
                          <p className="text-xs font-bold text-white">{r.title}</p>
                          <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-slate-800 text-slate-300">
                            Nv. {r.level}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-0.5">{r.desc}</p>
                      </div>
                    </div>

                    <div>
                      {isCurrent ? (
                        <span className="text-[10px] font-black text-accent-gold uppercase tracking-wider">ACTIVO</span>
                      ) : isUnlocked ? (
                        <Check className="w-4 h-4 text-accent-green" />
                      ) : (
                        <span className="text-xs">🔒</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* 6. COMPLEX TASK MODAL */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm rounded-2xl bg-bg-surface border border-border-glow p-5 shadow-2xl space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <h3 className="text-sm font-black text-white flex items-center gap-1.5">
                <span>➕</span>
                <span>Nueva Tarea Táctica</span>
              </h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateComplexTask} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-400 mb-1 font-bold">Título de la misión:</label>
                <input
                  type="text"
                  required
                  value={modalTitle}
                  onChange={e => setModalTitle(e.target.value)}
                  placeholder="ej. Actualizar informe de resultados"
                  className="w-full px-3 py-2 rounded-xl bg-bg-card border border-border-subtle text-white focus:outline-none focus:border-accent-violet"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-bold">Descripción / Notas:</label>
                <textarea
                  rows={2}
                  value={modalDesc}
                  onChange={e => setModalDesc(e.target.value)}
                  placeholder="Detalles operacionales..."
                  className="w-full px-3 py-2 rounded-xl bg-bg-card border border-border-subtle text-white focus:outline-none focus:border-accent-violet resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1 font-bold">Categoría:</label>
                  <select
                    value={modalCat || ''}
                    onChange={e => setModalCat(e.target.value ? Number(e.target.value) : null)}
                    className="w-full px-2 py-2 rounded-xl bg-bg-card border border-border-subtle text-white focus:outline-none focus:border-accent-violet"
                  >
                    <option value="">Sin categoría</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 font-bold">Prioridad:</label>
                  <select
                    value={modalPriority}
                    onChange={e => setModalPriority(Number(e.target.value))}
                    className="w-full px-2 py-2 rounded-xl bg-bg-card border border-border-subtle text-white focus:outline-none focus:border-accent-violet"
                  >
                    <option value={1}>🟢 Baja</option>
                    <option value={2}>🟡 Media</option>
                    <option value={3}>🔴 Alta (+60 XP)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-bold">Fecha / Hora límite:</label>
                <input
                  type="datetime-local"
                  value={modalDueDate}
                  onChange={e => setModalDueDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-bg-card border border-border-subtle text-white focus:outline-none focus:border-accent-violet"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="rec_check"
                  checked={modalRecurring}
                  onChange={e => setModalRecurring(e.target.checked)}
                  className="rounded bg-bg-card border-border-subtle text-accent-violet focus:ring-0"
                />
                <label htmlFor="rec_check" className="text-slate-300 font-medium">Tarea recurrente (se reinicia)</label>
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-border-subtle">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-3 py-2 rounded-xl bg-bg-card text-slate-400 hover:text-white"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-accent-violet font-bold text-white shadow-md shadow-purple-900/40"
                >
                  Guardar Misión
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 7. TACTICAL VOICE COMMAND HUD MODAL */}
      {voiceModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in">
          <div className="w-full max-w-sm rounded-2xl bg-slate-950 border-2 border-violet-500/60 p-5 shadow-2xl shadow-violet-950/80 space-y-4 relative overflow-hidden">
            {/* Ambient StarCraft HUD glow */}
            <div className="absolute -top-16 -right-16 w-36 h-36 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none" />
            <div className="absolute -bottom-16 -left-16 w-36 h-36 bg-violet-500/10 rounded-full blur-2xl pointer-events-none" />

            {/* Header */}
            <div className="flex items-center justify-between border-b border-violet-500/20 pb-3">
              <div className="flex items-center space-x-2">
                <div className="p-2 rounded-xl bg-violet-950/80 border border-violet-500/50 text-cyan-400">
                  <Mic className="w-4 h-4 animate-pulse" />
                </div>
                <div>
                  <h3 className="text-xs font-black tracking-widest uppercase text-white flex items-center gap-1.5">
                    <span>COMANDO POR VOZ</span>
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                  </h3>
                  <p className="text-[10px] text-slate-400 font-mono">BountyHunter Vocal HUD v1.2</p>
                </div>
              </div>
              <button 
                onClick={() => setVoiceModalOpen(false)} 
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-900 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* State Visualizer: Listening */}
            {voiceState === 'listening' && (
              <div className="py-6 flex flex-col items-center justify-center space-y-4">
                {/* Holographic Radar Waves */}
                <div className="relative flex items-center justify-center w-24 h-24">
                  <div className="absolute inset-0 rounded-full border-2 border-cyan-400/20 animate-ping" />
                  <div className="absolute inset-2 rounded-full border border-violet-400/40 animate-pulse" />
                  <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-violet-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-cyan-500/30">
                    <Mic className="w-7 h-7 text-white animate-bounce" />
                  </div>
                </div>

                {/* Animated Audio Equalizer Bars */}
                <div className="flex items-center gap-1.5 h-8">
                  <div className="w-1 bg-cyan-400 rounded-full animate-pulse h-4" />
                  <div className="w-1 bg-violet-400 rounded-full animate-bounce [animation-delay:-0.2s] h-7" />
                  <div className="w-1 bg-amber-400 rounded-full animate-pulse [animation-delay:-0.4s] h-5" />
                  <div className="w-1 bg-cyan-300 rounded-full animate-bounce [animation-delay:-0.1s] h-8" />
                  <div className="w-1 bg-violet-500 rounded-full animate-pulse [animation-delay:-0.3s] h-6" />
                  <div className="w-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.5s] h-3" />
                </div>

                <div className="text-center space-y-1">
                  <p className="text-sm font-extrabold text-white tracking-wide">ESCUCHANDO TU VOZ...</p>
                  <p className="text-[11px] text-slate-400 max-w-xs">
                    Di algo como: <span className="text-cyan-300 font-medium">"Comprar comida para gatos"</span> o <span className="text-violet-300 font-medium">"Añadir tarea reunión mañana"</span>
                  </p>
                </div>

                {voiceTranscript && (
                  <div className="w-full p-3 rounded-xl bg-slate-900/90 border border-violet-500/30 text-center">
                    <p className="text-[10px] text-slate-400 uppercase font-mono tracking-wider">Transcripción en vivo:</p>
                    <p className="text-xs font-semibold text-cyan-300 mt-1 italic">"{voiceTranscript}"</p>
                  </div>
                )}
              </div>
            )}

            {/* State Visualizer: Recognized */}
            {voiceState === 'recognized' && (
              <div className="space-y-4 py-2">
                <div className="p-3.5 rounded-xl bg-violet-950/40 border border-violet-500/40 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase tracking-wider text-cyan-400 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" /> COMANDO CAPTURADO
                    </span>
                    <span className="text-[10px] font-bold text-accent-gold">+10 XP</span>
                  </div>
                  <input
                    type="text"
                    value={voiceParsedTitle}
                    onChange={e => setVoiceParsedTitle(e.target.value)}
                    placeholder="Título de la tarea"
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-violet-500/50 text-white font-bold text-xs focus:outline-none focus:border-cyan-400"
                  />
                  <p className="text-[10px] text-slate-400 italic font-mono">"{voiceTranscript}"</p>
                </div>

                {/* Category Selector */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] font-black uppercase text-slate-400">CATEGORÍA:</label>
                    <span className="text-[10px] text-slate-500">Toca para cambiar</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {categories.map(cat => (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() => setVoiceParsedCategory(cat.id)}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition flex items-center gap-1 ${
                          voiceParsedCategory === cat.id
                            ? 'bg-violet-600 text-white border border-cyan-400 shadow-sm'
                            : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cat.color }} />
                        {cat.name}
                      </button>
                    ))}
                  </div>

                  {/* Priority Selector */}
                  <div className="pt-2">
                    <label className="text-[10px] font-black uppercase text-slate-400 block mb-1">PRIORIDAD:</label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        { id: 1, label: '🟢 Baja' },
                        { id: 2, label: '🟡 Media' },
                        { id: 3, label: '🔴 Alta' },
                      ].map(p => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setVoiceParsedPriority(p.id)}
                          className={`py-1.5 rounded-lg text-[11px] font-bold border transition ${
                            voiceParsedPriority === p.id
                              ? 'bg-slate-800 border-cyan-400 text-white'
                              : 'bg-slate-950 border-slate-800 text-slate-400'
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Confirm Action Buttons */}
                <div className="pt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={() => startVoiceRecognition()}
                    className="flex-1 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-300 font-bold text-xs hover:bg-slate-800 transition active:scale-95 flex items-center justify-center gap-1"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Repetir
                  </button>
                  <button
                    type="button"
                    onClick={confirmVoiceTask}
                    className="flex-[2] py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 text-white font-black text-xs hover:brightness-110 transition active:scale-95 shadow-lg shadow-cyan-950/50 flex items-center justify-center gap-1.5"
                  >
                    <Check className="w-4 h-4" /> CREAR TAREA
                  </button>
                </div>
              </div>
            )}

            {/* State Visualizer: Error or Cancelled */}
            {voiceState === 'error' && (
              <div className="py-4 text-center space-y-4">
                <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center justify-center mx-auto">
                  <MicOff className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-bold text-rose-300">No se capturó la voz</p>
                  <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                    {voiceErrorMessage || 'Verifica que hayas concedido permiso de micrófono o habla más cerca del dispositivo.'}
                  </p>
                </div>
                <div className="flex gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setVoiceModalOpen(false)}
                    className="flex-1 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 font-bold text-xs"
                  >
                    Cerrar
                  </button>
                  <button
                    type="button"
                    onClick={() => startVoiceRecognition()}
                    className="flex-1 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs flex items-center justify-center gap-1.5"
                  >
                    <Mic className="w-3.5 h-3.5" /> Reintentar
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );

  // Helper renderer for a single task card with subtasks checklist
  function renderTaskCard(task: Task) {
    const cat = categories.find(c => c.id === task.category_id);
    const taskSubtasks = subtasks[task.id] || [];
    const isExpanded = !!expandedTasks[task.id];
    const completedSub = taskSubtasks.filter(s => s.completed).length;

    return (
      <div 
        key={task.id}
        className="rounded-2xl bg-bg-surface/90 border border-border-subtle hover:border-border-glow transition shadow-sm overflow-hidden"
      >
        <div className="p-3.5 flex items-start space-x-3">
          <button 
            onClick={() => toggleTask(task)}
            className="mt-0.5 text-slate-500 hover:text-accent-green transition active:scale-125"
          >
            {task.completed ? (
              <CheckCircle2 className="w-5 h-5 text-accent-green fill-green-500/10" />
            ) : (
              <Circle className="w-5 h-5 text-slate-400 hover:text-purple-400" />
            )}
          </button>

          <div className="flex-1 min-w-0" onClick={() => setExpandedTasks(prev => ({ ...prev, [task.id]: !isExpanded }))}>
            <p className={`font-semibold text-xs leading-snug break-words ${task.completed ? 'line-through text-slate-500' : 'text-slate-100'}`}>
              {task.title}
            </p>
            {task.description && (
              <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{task.description}</p>
            )}

            <div className="flex flex-wrap items-center gap-1.5 mt-2 text-[10px]">
              {cat && (
                <span 
                  className="px-2 py-0.5 rounded-md font-bold"
                  style={{ backgroundColor: `${cat.color}22`, color: cat.color }}
                >
                  {cat.name}
                </span>
              )}
              {task.priority === 3 && (
                <span className="px-2 py-0.5 rounded-md font-bold bg-red-500/20 text-red-400">
                  Alta
                </span>
              )}
              {task.due_date && (
                <span className="flex items-center text-slate-400">
                  <Clock className="w-3 h-3 mr-0.5" />
                  {task.due_date.replace('T', ' ')}
                </span>
              )}
              {task.is_recurring && (
                <span className="text-purple-400 font-bold">🔁 Recurrente</span>
              )}
              {taskSubtasks.length > 0 && (
                <span className="text-accent-turquoise font-mono font-bold">
                  [{completedSub}/{taskSubtasks.length} subtareas]
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-1">
            <button 
              onClick={() => setExpandedTasks(prev => ({ ...prev, [task.id]: !isExpanded }))}
              className="p-1 text-slate-500 hover:text-slate-300"
            >
              <ChevronDown className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180 text-purple-400' : ''}`} />
            </button>
            <button 
              onClick={() => deleteTask(task.id)}
              className="text-slate-600 hover:text-red-400 p-1"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Expandable Subtasks Checklist */}
        {isExpanded && (
          <div className="px-4 pb-3 pt-1 border-t border-border-subtle/60 bg-bg-card/40 space-y-2">
            <p className="text-[10px] font-black uppercase tracking-wider text-slate-400 mt-1">
              Subtareas ({completedSub}/{taskSubtasks.length})
            </p>
            {taskSubtasks.map(st => (
              <div key={st.id} className="flex items-center space-x-2 pl-2">
                <button onClick={() => toggleSubtask(st)}>
                  {st.completed ? (
                    <CheckCircle2 className="w-4 h-4 text-accent-green" />
                  ) : (
                    <Circle className="w-4 h-4 text-slate-500 hover:text-purple-400" />
                  )}
                </button>
                <span className={`text-xs ${st.completed ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                  {st.title}
                </span>
              </div>
            ))}

            {/* Quick add subtask form */}
            <div className="flex items-center space-x-1 pt-1">
              <input
                type="text"
                value={newSubtaskInputs[task.id] || ''}
                onChange={e => setNewSubtaskInputs(prev => ({ ...prev, [task.id]: e.target.value }))}
                onKeyDown={e => { if (e.key === 'Enter') handleAddSubtask(task.id); }}
                placeholder="+ Añadir subtarea táctica..."
                className="flex-1 px-2.5 py-1 rounded-lg bg-bg-surface border border-border-subtle text-[11px] text-white focus:outline-none focus:border-accent-violet"
              />
              <button
                onClick={() => handleAddSubtask(task.id)}
                className="px-2 py-1 rounded-lg bg-accent-violet text-[11px] font-bold text-white"
              >
                +
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }
}

export default App;
