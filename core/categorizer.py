"""
core/categorizer.py
===================
Automatic category deduction engine for Taskmaster.

Deduction Rules (in priority order):
1. Trabajo:
   - Tasks involving third-party names (e.g., "reunión con Juan", "llamar a Carlos", "hablar con María").
   - Meetings & interviews ("reunión", "entrevista", "meeting", "call", "standup", "sprint", "sync").
   - Work & corporate keywords ("cliente", "informe", "reporte", "presupuesto", "factura", "deadline", "deploy", etc.).
2. Hogar:
   - Household chores, cleaning, laundry, repairs, cooking, groceries/supermarket, home utilities.
   - Automatically triggers the creation of the "Hogar" category if it does not yet exist.
3. Salud:
   - Medical appointments, doctors, dentists, gym, workouts, sports, medicines, pharmacy, health.
4. Estudio:
   - University, courses, homework, reading chapters, exams, learning, thesis.
5. Personal:
   - Celebrations (birthdays, anniversaries), friends, family, leisure, hobbies, movies, trips.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional, Set


def normalize_text(text: str) -> str:
    """Normalize text by converting to lowercase and stripping accents."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Common First Names (Spanish, Latin American & International in tech)
# ---------------------------------------------------------------------------
COMMON_NAMES: Set[str] = {
    # Spanish / Latin American
    "juan", "pedro", "carlos", "maria", "laura", "sofia", "ana", "lucas",
    "mateo", "martin", "diego", "valentina", "camila", "santiago", "andres",
    "alejandro", "gabriel", "daniel", "david", "pablo", "manuel", "javier",
    "fernando", "agustin", "nicolas", "tomas", "rodrigo", "gonzalo", "facundo",
    "joaquin", "julian", "federico", "sebastian", "franco", "ignacio", "lucia",
    "paula", "martina", "florencia", "micaela", "antonella", "natalia",
    "victoria", "mariana", "daniela", "marcelo", "claudio", "gustavo",
    "esteban", "marcos", "hugo", "alberto", "roberto", "eduardo", "jorge",
    "ricardo", "raul", "felipe", "cesar", "mario", "sergio", "alvaro",
    "enrique", "elena", "claudia", "patricia", "monica", "silvia", "carolina",
    "gabriela", "veronica", "julia", "andrea", "lorena", "paola", "clara",
    "teresa", "rosa", "irene", "carmen", "alicia", "beatriz", "matias",
    "mati", "maxi", "maximiliano", "leo", "leonardo", "guillermo", "guille",
    "emiliano", "emi", "bautista", "benjamin", "valentin", "benja", "valen",
    "lauti", "lautaro", "nahuel", "mauro", "damian", "gonza", "fede", "nico",
    "seba", "fer", "santi", "manu", "dani", "gabi", "nacho", "fran", "juana",
    "cande", "candelaria", "delfina", "delfi", "lula", "lu", "sol", "luz",
    # Common international
    "john", "mike", "michael", "alex", "sarah", "sara", "emma", "chris",
    "sam", "tom", "thomas", "mark", "steve", "bob", "alice", "brian",
    "kevin", "eric", "jason", "ryan", "lisa", "karen", "emily", "jessica",
    "adam", "oliver", "james", "william", "ben", "jack", "luke", "henry",
}

# Words following 'con', 'a', 'para', etc. that are NOT 3rd party work names
NON_WORK_TARGETS: Set[str] = {
    # Family & Friends (Personal)
    "mama", "papa", "mami", "papi", "padres", "madre", "padre",
    "hermano", "hermana", "hijo", "hija", "abuelo", "abuela",
    "tio", "tia", "primo", "prima", "sobrino", "sobrina",
    "novio", "novia", "pareja", "esposo", "esposa", "marido", "mujer",
    "amigo", "amiga", "amigos", "amigas", "vecino", "vecina",
    # Pets & Animals
    "perro", "perros", "gato", "gatos", "mascota", "mascotas",
    # Places / Household
    "casa", "depto", "departamento", "hogar", "cocina", "bano", "patio",
    "jardin", "cuarto", "sala", "comedor", "plomero", "electricista", "gasista",
    # Health roles
    "medico", "doctor", "doctora", "dentista", "odontologo", "psicologo", "terapeuta",
}


# ---------------------------------------------------------------------------
# Keywords by Category
# ---------------------------------------------------------------------------

REUNION_KEYWORDS: Set[str] = {
    "reunion", "reuniones", "entrevista", "entrevistas", "meeting", "meetings",
    "call", "calls", "standup", "sprint", "daily", "sync", "demo", "review",
    "retrospectiva", "retro", "1:1", "one on one", "videollamada", "zoom",
    "teams", "meet", "llamada de trabajo", "conferencia",
}

TRABAJO_KEYWORDS: Set[str] = {
    "cliente", "clientes", "jefe", "jefa", "gerente", "colega", "colegas",
    "equipo", "socio", "socios", "empleado", "empresa", "oficina", "laboral",
    "empleo", "trabajo", "informe", "reporte", "presentacion", "presupuesto",
    "factura", "facturas", "cobro", "pago cliente", "honorarios", "sueldo",
    "propuesta", "licitacion", "contrato", "proveedor", "proveedores",
    "deadline", "entrega cliente", "ticket", "tickets", "bug", "bugs",
    "deploy", "commit", "merge", "pull request", "pr", "repositorio", "release",
    "produccion", "backend", "frontend", "api", "database", "servidor",
    "slack", "jira", "trello", "linkedin", "curriculum", "cv", "portfolio",
    "kpi", "okr", "roadmap", "pitch", "inversor", "auditoria",
}

HOGAR_KEYWORDS: Set[str] = {
    # Cleaning & Maintenance
    "limpiar", "limpieza", "ordenar", "barrer", "trapear", "aspirar", "fregar",
    "lavar", "lavadora", "lavarropas", "secar", "secarropas", "lavar ropa", "planchar", "tender", "doblar ropa",
    # Cooking & Kitchen
    "cocina", "cocinar", "platos", "vajilla", "olla", "sarten", "desayuno", "almuerzo",
    "cena", "comida", "hacer comida", "receta", "alimentos",
    # Supermarket & Groceries
    "supermercado", "super", "mercado", "mandados", "despensa", "almacen",
    "verduleria", "carniceria", "panaderia", "compras de la casa", "compras del hogar",
    "leche", "pan", "huevos", "carne", "fruta", "frutas", "verdura", "verduras",
    "detergente", "jabon", "lavandina", "papel higienico", "desinfectante", "shampoo",
    # Home areas & Furniture
    "casa", "hogar", "departamento", "depto", "habitacion", "cuarto", "living",
    "comedor", "patio", "jardin", "bano", "inodoro", "ducha", "plantas", "regar",
    "basura", "reciclar", "reciclaje", "tacho", "mueble", "cortinas", "sabanas",
    # Repairs & Trades
    "reparar", "arreglar", "grifo", "canilla", "foco", "lamparita", "bombilla",
    "enchufe", "gotera", "humedad", "pintar pared", "plomero", "gasista",
    "electricista", "persiana", "cerradura", "puerta", "ventana", "ferreteria",
    # Home bills
    "alquiler", "expensas", "factura luz", "factura gas", "factura agua",
    "servicio internet", "abono hogar", "tasa municipal",
}

SALUD_KEYWORDS: Set[str] = {
    "medico", "doctor", "doctora", "dentista", "odontologo", "oftalmologo",
    "psicologo", "terapeuta", "nutricionista", "kinesiologo", "pediatra",
    "turno medico", "cita medica", "clinica", "hospital", "sanatorio", "guardia",
    "gym", "gimnasio", "entrenar", "entrenamiento", "ejercicio", "rutina",
    "crossfit", "pesas", "spinning", "yoga", "pilates", "cardio", "correr",
    "running", "trotar", "caminar", "estiramiento", "bici", "bicicleta",
    "pastilla", "pastillas", "medicamento", "medicamentos", "remedio", "remedios",
    "farmacia", "receta medica", "vitamina", "vitaminas", "dosis", "ibuprofeno",
    "paracetamol", "antibiotico", "analisis", "analisis sangre", "presion",
    "dieta", "salud", "dormir", "siesta", "descansar", "hidratarse", "calorias",
}

ESTUDIO_KEYWORDS: Set[str] = {
    "estudiar", "estudio", "repasar", "resumen", "apuntes", "memorizar",
    "examen", "parcial", "final", "evaluacion", "test", "quiz", "tp",
    "trabajo practico", "tesis", "paper", "investigacion",
    "universidad", "facultad", "facu", "colegio", "escuela", "instituto",
    "catedra", "materia", "curso", "clase", "leccion", "tutorial", "aprender",
    "practicar", "leer libro", "leer capitulo", "lectura obligatoria",
    "idioma", "ingles", "frances", "aleman", "italiano", "portugues",
    "tarea de", "deberes", "guia de ejercicios", "biblioteca",
}

PERSONAL_KEYWORDS: Set[str] = {
    "cumpleanos", "cumple", "aniversario", "fiesta", "regalo", "festejo",
    "amigo", "amigos", "amiga", "amigas", "familia", "mama", "papa", "hermano",
    "hermana", "hijo", "hija", "novio", "novia", "pareja", "asado", "cena afuera",
    "pelicula", "serie", "cine", "netflix", "jugar", "gaming", "partida",
    "videojuego", "playstation", "steam", "hobby", "guitarra", "musica",
    "viaje", "viajar", "vacaciones", "hotel", "vuelo", "pasajes", "maleta",
    "valija", "escapada", "paseo", "tramite", "banco", "tarjeta", "dni",
    "pasaporte", "renovar registro", "carnet", "barberia", "peluqueria",
    "ropa", "ropa nueva", "comprar ropa", "zapatillas", "zapatos", "vestido",
    "remera", "pantalon", "outfit", "shopping", "fin de semana",
}


def matches_keywords(norm_text: str, words_set: Set[str], keywords: Set[str]) -> bool:
    """Accurately match whole words or exact multi-word phrases."""
    padded = f" {norm_text} "
    for kw in keywords:
        if " " in kw:
            if f" {kw} " in padded:
                return True
        else:
            if kw in words_set:
                return True
    return False


# ---------------------------------------------------------------------------
# Third-Party Person Name Detection
# ---------------------------------------------------------------------------

def has_third_party_name(raw_text: str, norm_text: str, words_set: Set[str]) -> bool:
    """
    Detect whether the task text explicitly addresses or involves a third-party person.
    Examples:
      - 'reunión con Juan'
      - 'llamar a Carlos'
      - 'enviar informe a María'
      - 'hablar con Pedro sobre el proyecto'
    """
    # 1. Regex for prepositions or interaction verbs followed by a potential name
    pattern = (
        r"\b(?:con|a|para|de|llamar|hablar|escribir|contactar|consultar|"
        r"entrevistar|preguntar|reunirme|juntarme)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ]+)"
    )

    for match in re.finditer(pattern, raw_text, re.IGNORECASE):
        target = match.group(1)
        target_norm = normalize_text(target)

        # Exclude common non-work targets (family, pets, places, home)
        if target_norm in NON_WORK_TARGETS:
            continue

        # If name is in our known names set
        if target_norm in COMMON_NAMES:
            return True

        # If the word was capitalized in the original text (and isn't a weekday / time stopword)
        if target[0].isupper() and len(target) >= 3:
            stopwords = {
                "hoy", "manana", "tarde", "noche", "casa", "lunes", "martes",
                "miercoles", "jueves", "viernes", "sabado", "domingo", "fin",
                "semana", "mes", "ano", "tiempo", "favor", "tarea",
            }
            if target_norm not in stopwords and target_norm not in NON_WORK_TARGETS:
                return True

    # 2. Check for standalone names in the token set
    candidate_names = (words_set & COMMON_NAMES) - NON_WORK_TARGETS
    if candidate_names:
        # If accompanied by personal celebration, it's personal rather than work
        if any(pk in words_set for pk in ["cumpleanos", "cumple", "aniversario", "boda", "casamiento", "regalo"]):
            return False
        return True

    return False


# ---------------------------------------------------------------------------
# Main Deduction Function
# ---------------------------------------------------------------------------

def deduce_category_name(title: str, description: str = "") -> Optional[str]:
    """
    Analyze the title and description of a task and return the deduced category name:
    'Trabajo', 'Hogar', 'Salud', 'Estudio', 'Personal', or None.
    """
    combined = f"{title} {description}".strip()
    if not combined:
        return None

    raw_text = combined
    norm_text = normalize_text(combined)
    words_set = set(re.findall(r"\b[a-z0-9_:]+\b", norm_text))

    # Detect if it's an explicit celebration/birthday (takes priority over name matching)
    has_celebration = matches_keywords(
        norm_text, words_set,
        {"cumpleanos", "cumple", "aniversario", "boda", "regalo de cumpleanos", "fiesta sorpresa"}
    )

    # 1. TRABAJO:
    # Meetings, interviews, 3rd party names, or explicit work terms
    if not has_celebration:
        # Check meeting keywords first
        if matches_keywords(norm_text, words_set, REUNION_KEYWORDS):
            return "Trabajo"

        # Check third party person names
        if has_third_party_name(raw_text, norm_text, words_set):
            return "Trabajo"

        # Check general work keywords
        if matches_keywords(norm_text, words_set, TRABAJO_KEYWORDS):
            return "Trabajo"

    # 2. HOGAR:
    # Home chores, cleaning, repairs, groceries/supermarket, home utilities
    if matches_keywords(norm_text, words_set, HOGAR_KEYWORDS):
        return "Hogar"

    # Also detect "comprar" with grocery/food words
    if "comprar" in words_set and any(
        w in words_set
        for w in ["comida", "leche", "pan", "huevos", "carne", "verdura", "verduras", "fruta", "frutas", "detergente", "jabon"]
    ):
        return "Hogar"

    # 3. SALUD:
    # Doctors, medicine, workout, fitness
    if matches_keywords(norm_text, words_set, SALUD_KEYWORDS):
        return "Salud"

    # 4. ESTUDIO:
    # Academic, study, exams, university, courses
    if matches_keywords(norm_text, words_set, ESTUDIO_KEYWORDS):
        return "Estudio"

    # 5. PERSONAL:
    # Celebrations, family, entertainment, hobbies
    if has_celebration or matches_keywords(norm_text, words_set, PERSONAL_KEYWORDS):
        return "Personal"

    return None
