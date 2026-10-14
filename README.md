# TaskVoice

**TaskVoice** es una aplicación de escritorio para gestión de tareas con reconocimiento de voz, desarrollada en Python con PyQt6.

---

## 📋 Características

- ✅ **Gestión completa de tareas** con subtareas, categorías, prioridades y fechas de vencimiento
- 🎙️ **Comandos de voz** para crear, completar y eliminar tareas sin usar el teclado
- 🔔 **Notificaciones de escritorio** con recordatorios automáticos 30 minutos antes del vencimiento
- 📊 **Barra de progreso** por tarea basada en subtareas completadas
- 🌙 **Tema oscuro/claro** moderno y elegante
- 🗂️ **Categorías personalizables** con colores
- 🔍 **Búsqueda y filtrado** de tareas
- 📌 **Icono en bandeja del sistema** con acceso rápido
- ⌨️ **Atajos de teclado** (Ctrl+N para nueva tarea)

---

## 🔧 Instalación

### Requisitos previos

- Python 3.9 o superior
- Windows 10/11
- Micrófono (para comandos de voz)

### Instalar dependencias

```bash
pip install -r requirements.txt
```

### Ejecutar la aplicación

```bash
python main.py
```

---

## 📦 Compilar ejecutable

Para generar un `.exe` independiente:

```bat
build.bat
```

El ejecutable se generará en `dist/TaskVoice.exe`.

---

## 🎙️ Comandos de voz

| Comando | Acción |
|---|---|
| `añadir tarea [título]` | Crea una nueva tarea con el título indicado |
| `nueva tarea [título]` | Crea una nueva tarea con el título indicado |
| `completar tarea [título]` | Marca como completada la tarea indicada |
| `eliminar tarea [título]` | Elimina la tarea indicada |
| `mostrar progreso` | Muestra el resumen de progreso general |

### Motores de reconocimiento de voz

- **Vosk (recomendado)**: Reconocimiento offline sin conexión a internet. Descarga un modelo desde [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) y configura la ruta en Ajustes → Voz.
- **Google Speech Recognition**: Requiere conexión a internet. No necesita configuración adicional.

---

## 🖥️ Uso

### Agregar una tarea
1. Haz clic en **"+ Nueva Tarea"** o presiona `Ctrl+N`
2. Escribe el título, descripción, categoría, prioridad y fecha de vencimiento
3. Añade subtareas según sea necesario
4. Haz clic en **"Guardar"**

### Usar comandos de voz
1. Haz clic en el botón del micrófono (🎙️) en la barra de herramientas
2. El botón se pondrá en rojo mientras escucha
3. Di un comando en voz alta
4. La acción se ejecutará automáticamente

### Completar una tarea
- Marca el checkbox en la tarjeta de la tarea, o
- Usa el menú contextual (clic derecho) → "Completar", o
- Di "completar tarea [título]" por voz

### Subtareas
- Haz doble clic en una tarea para editarla y añadir subtareas
- O haz clic derecho → "Añadir Subtarea"
- El progreso de la tarea se calcula automáticamente según las subtareas completadas

---

## ⚙️ Configuración

Ve a **Editar → Ajustes** para configurar:

- **General**: Tema (oscuro/claro), idioma
- **Notificaciones**: Habilitar/deshabilitar, tiempo de recordatorio, hora del resumen diario
- **Voz**: Motor de reconocimiento, modo (push-to-talk o continuo), ruta del modelo Vosk
- **Categorías**: Añadir, renombrar, cambiar colores o eliminar categorías

---

## 📁 Estructura del proyecto

```
TaskVoice/
├── main.py                 # Punto de entrada principal
├── requirements.txt        # Dependencias de Python
├── build.bat               # Script de compilación
├── README.md               # Este archivo
├── .gitignore
├── ui/
│   ├── main_window.py      # Ventana principal
│   ├── task_widget.py      # Widget de tarjeta de tarea
│   └── settings_dialog.py  # Diálogo de ajustes
├── core/
│   ├── tasks.py            # Base de datos SQLite y CRUD
│   ├── voice.py            # Reconocimiento de voz
│   └── notifier.py         # Notificaciones y recordatorios
└── assets/                 # Iconos y recursos
```

---

## 📄 Licencia

MIT License — libre para uso personal y comercial.

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor abre un issue o pull request en el repositorio.
