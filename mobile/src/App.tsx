import React, { useState, useEffect } from 'react';
import { supabase, Task, Category, GamificationProfile } from './supabase';
import { 
  CheckCircle2, Circle, Mic, MicOff, Plus, Flame, 
  Trophy, Calendar, Clock, RefreshCw, Trash2, Tag, 
  Sparkles, Check, ChevronRight
} from 'lucide-react';
import confetti from 'canvas-confetti';

export function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [profile, setProfile] = useState<GamificationProfile>({
    id: 1, xp: 0, level: 1, total_xp: 0, streak_days: 1, tasks_completed_count: 0
  });
  const [activeTab, setActiveTab] = useState<'tasks' | 'profile'>('tasks');
  const [filterCat, setFilterCat] = useState<number | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // Load initial data & subscribe to real-time changes
  useEffect(() => {
    loadData();

    // Subscribe to Realtime updates from PC app or other devices
    const channel = supabase
      .channel('bountyhunter_realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'bh_tasks' }, () => {
        loadTasks();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'bh_gamification' }, () => {
        loadProfile();
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  async function loadData() {
    setSyncing(true);
    await Promise.all([loadTasks(), loadCategories(), loadProfile()]);
    setSyncing(false);
  }

  async function loadTasks() {
    const { data } = await supabase
      .from('bh_tasks')
      .select('*')
      .eq('is_deleted', false)
      .order('id', { ascending: false });
    if (data) setTasks(data);
  }

  async function loadCategories() {
    const { data } = await supabase.from('bh_categories').select('*');
    if (data) setCategories(data);
  }

  async function loadProfile() {
    const { data } = await supabase.from('bh_gamification').select('*').eq('id', 1).single();
    if (data) setProfile(data);
  }

  // Toggle complete
  async function toggleTask(task: Task) {
    const nextCompleted = !task.completed;
    const now = new Date().toISOString();

    // Optimistic UI update
    setTasks(prev => prev.map(t => t.id === task.id ? { ...t, completed: nextCompleted } : t));

    if (nextCompleted) {
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.8 },
        colors: ['#7C3AED', '#06B6D4', '#F59E0B']
      });

      // Update XP locally & remotely
      const gainedXp = task.priority === 3 ? 50 : task.priority === 2 ? 30 : 20;
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
  }

  // Quick Add Task
  async function handleAddTask(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!newTitle.trim()) return;

    const title = newTitle.trim();
    setNewTitle('');

    const newTaskPayload = {
      title,
      priority: 2,
      category_id: filterCat,
      completed: false,
      progress: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_deleted: false
    };

    const { data } = await supabase
      .from('bh_tasks')
      .insert([newTaskPayload])
      .select()
      .single();

    if (data) {
      setTasks(prev => [data, ...prev]);
    }
  }

  // Voice recognition (Web Speech API / Native Android bridge)
  function toggleVoice() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("El reconocimiento de voz no está soportado en este navegador web, pero funcionará en la app instalada.");
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'es-ES';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      if (transcript) {
        setNewTitle(transcript);
      }
    };

    recognition.start();
  }

  // Delete task
  async function deleteTask(id: number) {
    setTasks(prev => prev.filter(t => t.id !== id));
    await supabase.from('bh_tasks').update({ is_deleted: true, updated_at: new Date().toISOString() }).eq('id', id);
  }

  const filteredTasks = tasks.filter(t => {
    if (filterCat !== null && t.category_id !== filterCat) return false;
    return true;
  });

  const activeTasks = filteredTasks.filter(t => !t.completed);
  const completedTasks = filteredTasks.filter(t => t.completed);

  return (
    <div className="flex flex-col h-screen max-w-md mx-auto bg-bg-dark text-slate-100 select-none pb-safe">
      {/* Top Header Bar */}
      <header className="px-5 pt-8 pb-3 bg-bg-sidebar/90 backdrop-blur border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-accent-violet to-purple-500 flex items-center justify-center font-black text-xl shadow-lg shadow-purple-900/30">
            ⚔️
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-purple-300 bg-clip-text text-transparent">
              BountyHunter
            </h1>
            <div className="flex items-center space-x-2 text-xs text-slate-400">
              <span className="flex items-center text-accent-gold font-semibold">
                <Flame className="w-3.5 h-3.5 mr-0.5 fill-accent-gold" />
                {profile.streak_days} días racha
              </span>
              <span>•</span>
              <span className="text-purple-400 font-medium">Nv. {profile.level}</span>
            </div>
          </div>
        </div>

        <button 
          onClick={loadData} 
          disabled={syncing}
          className={`p-2.5 rounded-xl bg-bg-surface border border-border-subtle text-slate-300 hover:text-white transition active:scale-95 ${syncing ? 'animate-spin text-accent-violet' : ''}`}
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </header>

      {/* Level XP Bar */}
      <div className="px-5 py-2.5 bg-bg-surface/50 border-b border-border-subtle">
        <div className="flex justify-between items-center text-xs mb-1.5 font-medium">
          <span className="text-slate-400">Rango: <b className="text-purple-300">Cazador de Élite</b></span>
          <span className="text-accent-turquoise font-mono">{profile.xp} / 300 XP</span>
        </div>
        <div className="w-full h-2 rounded-full bg-slate-800/80 overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-accent-violet via-purple-500 to-accent-turquoise transition-all duration-500 rounded-full"
            style={{ width: `${Math.min(100, (profile.xp / 300) * 100)}%` }}
          />
        </div>
      </div>

      {/* Category Pills Slider */}
      <div className="px-5 py-3 flex space-x-2 overflow-x-auto no-scrollbar">
        <button
          onClick={() => setFilterCat(null)}
          className={`px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition ${
            filterCat === null 
              ? 'bg-accent-violet text-white shadow-md shadow-purple-900/40' 
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
              className={`px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap flex items-center space-x-1.5 transition ${
                filterCat === cat.id
                  ? 'bg-white text-slate-900 shadow-md'
                  : 'bg-bg-surface text-slate-300 border border-border-subtle'
              }`}
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cat.color }} />
              <span>{cat.name}</span>
              {count > 0 && <span className="opacity-60 text-[10px]">({count})</span>}
            </button>
          );
        })}
      </div>

      {/* Task List Scroll Area */}
      <div className="flex-1 overflow-y-auto px-5 py-2 space-y-3">
        {activeTasks.length === 0 && completedTasks.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-center text-slate-500 space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-bg-surface flex items-center justify-center text-2xl border border-border-subtle">
              🎯
            </div>
            <p className="font-semibold text-slate-300">¡Zona despejada!</p>
            <p className="text-xs max-w-xs text-slate-500">No hay recompensas pendientes. Agrega una tarea o dítala con el micrófono.</p>
          </div>
        ) : (
          <>
            {/* Active Tasks */}
            {activeTasks.map(task => {
              const cat = categories.find(c => c.id === task.category_id);
              return (
                <div 
                  key={task.id}
                  className="p-4 rounded-2xl bg-bg-surface/80 border border-border-subtle hover:border-border-glow transition flex items-start space-x-3.5 shadow-sm active:scale-[0.99]"
                >
                  <button 
                    onClick={() => toggleTask(task)}
                    className="mt-0.5 text-slate-500 hover:text-accent-green transition active:scale-125"
                  >
                    <Circle className="w-5 h-5 text-slate-400 hover:text-purple-400" />
                  </button>

                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm leading-snug text-slate-100 break-words">
                      {task.title}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 mt-2 text-[11px]">
                      {cat && (
                        <span 
                          className="px-2 py-0.5 rounded-md font-semibold text-[10px]"
                          style={{ backgroundColor: `${cat.color}22`, color: cat.color }}
                        >
                          {cat.name}
                        </span>
                      )}
                      {task.due_date && (
                        <span className="flex items-center text-slate-400">
                          <Clock className="w-3 h-3 mr-1" />
                          {task.due_date}
                        </span>
                      )}
                      {task.is_recurring && (
                        <span className="text-purple-400 font-medium">🔁 Recurrente</span>
                      )}
                    </div>
                  </div>

                  <button 
                    onClick={() => deleteTask(task.id)}
                    className="text-slate-600 hover:text-red-400 p-1 transition"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              );
            })}

            {/* Completed section */}
            {completedTasks.length > 0 && (
              <div className="pt-4">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 px-1">
                  Completadas ({completedTasks.length})
                </p>
                <div className="space-y-2 opacity-60">
                  {completedTasks.map(task => (
                    <div 
                      key={task.id}
                      className="p-3.5 rounded-xl bg-bg-card/40 border border-border-subtle flex items-center space-x-3"
                    >
                      <button onClick={() => toggleTask(task)}>
                        <CheckCircle2 className="w-5 h-5 text-accent-green fill-green-500/10" />
                      </button>
                      <p className="text-sm line-through text-slate-400 flex-1 truncate">
                        {task.title}
                      </p>
                      <button onClick={() => deleteTask(task.id)} className="text-slate-600 hover:text-red-400 p-1">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Floating Bottom Quick-Add & Voice Input */}
      <div className="p-4 bg-bg-sidebar/95 backdrop-blur border-t border-border-subtle">
        <form onSubmit={handleAddTask} className="flex items-center space-x-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              placeholder="Nueva recompensa o tarea táctica..."
              className="w-full pl-4 pr-10 py-3 rounded-xl bg-bg-surface border border-border-subtle focus:border-accent-violet focus:outline-none text-sm placeholder-slate-500 text-white"
            />
            <button
              type="button"
              onClick={toggleVoice}
              className={`absolute right-2 top-2 p-1.5 rounded-lg transition active:scale-90 ${
                isListening ? 'bg-red-500 text-white animate-pulse' : 'text-slate-400 hover:text-white'
              }`}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
          </div>

          <button
            type="submit"
            disabled={!newTitle.trim()}
            className="p-3 rounded-xl bg-accent-violet text-white font-medium hover:bg-purple-600 disabled:opacity-40 disabled:hover:bg-accent-violet transition active:scale-95 shadow-lg shadow-purple-900/30"
          >
            <Plus className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
