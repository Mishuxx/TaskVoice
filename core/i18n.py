"""
core/i18n.py
============
Internationalisation (i18n) module for Taskmaster.
Supports Spanish (es) and English (en).
"""

from __future__ import annotations
from typing import Dict, Any, Optional

_CURRENT_LANG = "es"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "es": {
        # App & Window
        "app_title": "Taskmaster",
        
        # Navigation
        "nav_tasks": "Tareas",
        "nav_dashboard": "Dashboard",
        "nav_missions": "Misiones",
        "nav_settings": "Ajustes",
        "categories_header": "CATEGORÍAS",
        "new_category": "+ Nueva categoría",
        "cat_all": "Todas",

        # Top Bar
        "all_tasks_title": "Todas las tareas",
        "stats_subtitle": "{active} activas · {completed} completadas hoy",
        "search_placeholder": "Buscar tarea…",
        "theme_tooltip": "Cambiar tema",
        "settings_tooltip": "Ajustes y Bots (Telegram / WhatsApp)",

        # Quick Add
        "quick_add_placeholder": "Agregar tarea… (ej. Revisar correos a las 10:00)",
        "btn_add": "Agregar",
        "btn_complex": "Compleja",
        "voice_dictate": "Dictar",
        "voice_listening": "Escuchando…",

        # Filter Bar
        "filter_all": "Todas",
        "filter_today": "Hoy",
        "filter_high_prio": "Prioridad alta",
        "filter_show_completed": "Mostrar completadas",

        # Sections
        "section_today": "HOY",
        "section_upcoming": "PRÓXIMAS",
        "section_completed": "COMPLETADAS",

        # Mission Banner
        "daily_mission": "MISIÓN DEL DÍA",
        "mission_progress": "{done} de {total} objetivos completados",
        "mission_reward": "Completa todas para abrir el cofre: +150 XP",
        "chest_ready": "¡Cofre desbloqueado! +150 XP conseguidos",

        # Priorities
        "priority_high": "Alta",
        "priority_med": "Media",
        "priority_low": "Baja",

        # Dates & Statuses
        "due_overdue": "⚠ Vencida: {date}",
        "due_soon": "⏰ {date}",
        "due_date": "📅 {date}",

        # Task Card Actions
        "task_edit": "Editar",
        "task_add_subtask": "Añadir Subtarea",
        "task_move_cat": "Mover a Categoría",
        "task_delete": "Eliminar",

        # Empty State
        "empty_title": "Nada pendiente por aquí",
        "empty_subtitle": "Agrega una tarea o pulsa el micrófono para dictarla",

        # Status Bar
        "status_summary": "Total {total} · Activas {active} · Completadas hoy {completed}",
        "voice_status_ready": "Voz lista · di «Oye Taskmaster»",
        "voice_status_off": "Voz inactiva",
        "voice_status_listening": "Escuchando voz…",

        # Dashboard
        "dash_header_title": "Panel de Rendimiento y Estadísticas",
        "dash_header_subtitle": "Métricas en tiempo real, análisis de productividad y distribución de tareas.",
        "btn_refresh": "Actualizar",
        "btn_reset": "Reiniciar",
        "stat_total_tasks": "TOTAL DE TAREAS",
        "stat_active_tasks": "TAREAS ACTIVAS",
        "stat_completed": "COMPLETADAS",
        "stat_overdue": "VENCIDAS",
        "stat_active_done_hint": "{active} activas, {completed} hechas",
        "stat_today_hint": "{count} para hoy",
        "stat_success_rate": "{rate:.1f}% tasa de éxito",
        "stat_up_to_date": "Al día",
        "chart_compliance": "Estado Global de Cumplimiento",
        "chart_productivity": "Productividad Últimos 7 Días (Completadas)",
        "chart_categories": "Progreso por Categorías",
        "chart_priority": "Tareas por Prioridad",
        "chart_done_legend": "Hechas: {count}",
        "chart_active_legend": "Activas: {count}",
        "chart_overdue_legend": "Vencidas: {count}",

        # Player Card & Gamification
        "level_label": "NIVEL {level}",
        "xp_to_next": "{remaining} para N{next_lvl}",
        "medal_first_task": "Logro: Primera tarea completada",
        "medal_100_xp": "Logro: 100 XP acumulados",
        "medal_daily_mission": "Logro: Misión del día completada",

        # Settings
        "settings_title": "Ajustes – Taskmaster",
        "tab_general": "⚙ General",
        "tab_notifications": "🔔 Notificaciones",
        "tab_bots": "🤖 Bots (Telegram / WhatsApp)",
        "tab_voice": "🎙 Voz",
        "tab_categories": "🏷 Categorías",
        "lbl_theme": "Tema visual:",
        "lbl_language": "Idioma de interfaz:",
        "theme_dark": "Oscuro (StarCraft / HUD)",
        "theme_light": "Claro",
        "lang_es": "Español",
        "lang_en": "English",
        "btn_save": "Guardar",
        "btn_cancel": "Cancelar",

        # Task Edit Dialog
        "dlg_new_task": "Nueva Tarea",
        "dlg_edit_task": "Editar Tarea",
        "lbl_title": "Título:",
        "lbl_description": "Descripción:",
        "lbl_category": "Categoría:",
        "lbl_priority": "Prioridad:",
        "lbl_due_date": "Fecha y hora límite:",
        "lbl_recurring": "Tarea recurrente (se repite automáticamente)",
        "lbl_rec_type": "Frecuencia:",
        "lbl_rec_days": "Días activos:",
        "lbl_rec_times": "Horarios del día (instancias diarias):",
        "lbl_subtasks": "Subtareas:",
        "rec_preset_1x": "1x día (09:00)",
        "rec_preset_2x": "2x día (09:00, 18:00)",
        "rec_preset_3x": "3x día (08:00, 14:00, 20:00)",
        "btn_add_time": "+ Agregar hora",
        "btn_add_subtask": "+ Añadir subtarea",
    },

    "en": {
        # App & Window
        "app_title": "Taskmaster",

        # Navigation
        "nav_tasks": "Tasks",
        "nav_dashboard": "Dashboard",
        "nav_missions": "Missions",
        "nav_settings": "Settings",
        "categories_header": "CATEGORIES",
        "new_category": "+ New category",
        "cat_all": "All",

        # Top Bar
        "all_tasks_title": "All Tasks",
        "stats_subtitle": "{active} active · {completed} completed today",
        "search_placeholder": "Search task…",
        "theme_tooltip": "Toggle theme",
        "settings_tooltip": "Settings & Bots (Telegram / WhatsApp)",

        # Quick Add
        "quick_add_placeholder": "Add task… (e.g. Check emails at 10:00)",
        "btn_add": "Add",
        "btn_complex": "Complex",
        "voice_dictate": "Dictate",
        "voice_listening": "Listening…",

        # Filter Bar
        "filter_all": "All",
        "filter_today": "Today",
        "filter_high_prio": "High priority",
        "filter_show_completed": "Show completed",

        # Sections
        "section_today": "TODAY",
        "section_upcoming": "UPCOMING",
        "section_completed": "COMPLETED",

        # Mission Banner
        "daily_mission": "DAILY MISSION",
        "mission_progress": "{done} of {total} objectives completed",
        "mission_reward": "Complete all to unlock the chest: +150 XP",
        "chest_ready": "Chest unlocked! +150 XP earned",

        # Priorities
        "priority_high": "High",
        "priority_med": "Medium",
        "priority_low": "Low",

        # Dates & Statuses
        "due_overdue": "⚠ Overdue: {date}",
        "due_soon": "⏰ {date}",
        "due_date": "📅 {date}",

        # Task Card Actions
        "task_edit": "Edit",
        "task_add_subtask": "Add Subtask",
        "task_move_cat": "Move to Category",
        "task_delete": "Delete",

        # Empty State
        "empty_title": "Nothing pending here",
        "empty_subtitle": "Add a task or click the mic to dictate it",

        # Status Bar
        "status_summary": "Total {total} · Active {active} · Completed today {completed}",
        "voice_status_ready": "Voice ready · say «Hey Taskmaster»",
        "voice_status_off": "Voice inactive",
        "voice_status_listening": "Listening to voice…",

        # Dashboard
        "dash_header_title": "Performance & Statistics Panel",
        "dash_header_subtitle": "Real-time metrics, productivity analysis, and task distribution.",
        "btn_refresh": "Refresh",
        "btn_reset": "Reset",
        "stat_total_tasks": "TOTAL TASKS",
        "stat_active_tasks": "ACTIVE TASKS",
        "stat_completed": "COMPLETED",
        "stat_overdue": "OVERDUE",
        "stat_active_done_hint": "{active} active, {completed} done",
        "stat_today_hint": "{count} for today",
        "stat_success_rate": "{rate:.1f}% success rate",
        "stat_up_to_date": "Up to date",
        "chart_compliance": "Global Completion Status",
        "chart_productivity": "Last 7 Days Productivity (Completed)",
        "chart_categories": "Progress by Category",
        "chart_priority": "Tasks by Priority",
        "chart_done_legend": "Done: {count}",
        "chart_active_legend": "Active: {count}",
        "chart_overdue_legend": "Overdue: {count}",

        # Player Card & Gamification
        "level_label": "LEVEL {level}",
        "xp_to_next": "{remaining} to L{next_lvl}",
        "medal_first_task": "Achievement: First task completed",
        "medal_100_xp": "Achievement: 100 XP accumulated",
        "medal_daily_mission": "Achievement: Daily mission completed",

        # Settings
        "settings_title": "Settings – Taskmaster",
        "tab_general": "⚙ General",
        "tab_notifications": "🔔 Notifications",
        "tab_bots": "🤖 Bots (Telegram / WhatsApp)",
        "tab_voice": "🎙 Voice",
        "tab_categories": "🏷 Categories",
        "lbl_theme": "Visual theme:",
        "lbl_language": "Interface language:",
        "theme_dark": "Dark (StarCraft / HUD)",
        "theme_light": "Light",
        "lang_es": "Español",
        "lang_en": "English",
        "btn_save": "Save",
        "btn_cancel": "Cancel",

        # Task Edit Dialog
        "dlg_new_task": "New Task",
        "dlg_edit_task": "Edit Task",
        "lbl_title": "Title:",
        "lbl_description": "Description:",
        "lbl_category": "Category:",
        "lbl_priority": "Priority:",
        "lbl_due_date": "Due date and time:",
        "lbl_recurring": "Recurring task (repeats automatically)",
        "lbl_rec_type": "Frequency:",
        "lbl_rec_days": "Active days:",
        "lbl_rec_times": "Daily times (daily instances):",
        "lbl_subtasks": "Subtasks:",
        "rec_preset_1x": "1x day (09:00)",
        "rec_preset_2x": "2x day (09:00, 18:00)",
        "rec_preset_3x": "3x day (08:00, 14:00, 20:00)",
        "btn_add_time": "+ Add time",
        "btn_add_subtask": "+ Add subtask",
    }
}


def set_language(lang: str) -> None:
    """Set active application language ('es' or 'en')."""
    global _CURRENT_LANG
    clean = lang.lower().strip()
    _CURRENT_LANG = "en" if clean.startswith("en") else "es"


def get_language() -> str:
    """Return active language code ('es' or 'en')."""
    return _CURRENT_LANG


def tr(key: str, default: Optional[str] = None, **kwargs) -> str:
    """
    Translate a key into the active language, formatting placeholders if provided.
    Falls back to Spanish or the provided default if the key is missing.
    """
    lang_dict = TRANSLATIONS.get(_CURRENT_LANG, TRANSLATIONS["es"])
    template = lang_dict.get(key)
    if template is None:
        template = TRANSLATIONS["es"].get(key, default or key)
    
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
