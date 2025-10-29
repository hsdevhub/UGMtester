import json
from pathlib import Path
import streamlit as st

# =========================
# Config & Load Data
# =========================
st.set_page_config(page_title="Test Vigilancia y Seguridad", page_icon="🛡️", layout="wide")

DATA_PATH = Path(__file__).parent / "questions.json"

@st.cache_data
def load_bank(path: Path):
    if not path.exists():
        st.error("❌ No se encontró 'cuestionario.json' junto al script. Colócalo y recarga.")
        st.stop()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Espera estructura: {"lotes":[{lote_id, preguntas:[{n, lote, pregunta, respuesta_a,b,c, correcta, ...}], ...}]}
    return data

BANK = load_bank(DATA_PATH)

# Flatten helpers
def flatten_questions(bank):
    flat = []
    for lote in bank.get("lotes", []):
        lote_id = lote.get("lote_id")
        for q in lote.get("preguntas", []):
            q_copy = dict(q)
            q_copy["lote_id"] = lote_id
            flat.append(q_copy)
    return flat

ALL_QUESTIONS = flatten_questions(BANK)

# =========================
# Session State
# =========================
def _init_state():
    ss = st.session_state
    ss.setdefault("mode", "full")  # "full" | "lote1" | "lote2" | "lote3" | "review"
    ss.setdefault("show_correct_between", False)
    ss.setdefault("current_index", 0)
    # answers: { n (int): { "attempts": int, "correct": bool, "selected": "A"/"B"/"C", "lote_id": int } }
    ss.setdefault("answers", {})
    # bloqueos: si una pregunta tuvo 1 fallo, no permite más intentos (máx 1 fallo)
    ss.setdefault("locked", set())  # set de n
    ss.setdefault("last_feedback", None)

_init_state()

# =========================
# Utility functions
# =========================
def get_questions_for_mode(mode: str):
    if mode == "full":
        return ALL_QUESTIONS
    elif mode in {"lote1", "lote2", "lote3"}:
        target = int(mode.replace("lote", ""))
        return [q for q in ALL_QUESTIONS if q.get("lote_id") == target]
    elif mode == "review":
        # Solo las falladas (contestadas y no correctas)
        failed_ids = [n for n, a in st.session_state.answers.items() if a.get("attempts", 0) >= 1 and not a.get("correct", False)]
        return [q for q in ALL_QUESTIONS if q["n"] in failed_ids]
    return []

def get_correct_letter(q):
    # El JSON usa "correcta" como letra "A"/"B"/"C" (o texto en algunos casos)
    corr = q.get("correcta")
    # Normalizamos letras si vinieran como texto
    if isinstance(corr, str):
        corr_up = corr.strip().upper()
        if corr_up in {"A","B","C"}:
            return corr_up
        # Si viene como texto de respuesta, mapeamos
        mapping = {"A": q.get("respuesta_a"), "B": q.get("respuesta_b"), "C": q.get("respuesta_c")}
        for k,v in mapping.items():
            if v and str(v).strip().lower() == corr.strip().lower():
                return k
    return "A"

def is_lot_completed(lote_id: int):
    # Completado = todas las preguntas del lote correctas
    lot_questions = [q for q in ALL_QUESTIONS if q.get("lote_id") == lote_id]
    if not lot_questions:
        return False
    for q in lot_questions:
        a = st.session_state.answers.get(q["n"], {})
        if not a.get("correct", False):
            return False
    return True

def totals():
    ans = st.session_state.answers
    attempted = sum(1 for _n, a in ans.items() if a.get("attempts", 0) >= 1)
    correct = sum(1 for _n, a in ans.items() if a.get("correct", False))
    wrong = attempted - correct
    total_questions = len(ALL_QUESTIONS)
    # progreso = % de preguntas correctas sobre el total
    progress = correct / total_questions if total_questions else 0.0
    # lotes 1..3 con trofeos
    completed_lots = sum(1 for lid in (1,2,3) if is_lot_completed(lid))
    return dict(
        attempted=attempted,
        correct=correct,
        wrong=wrong,
        total=total_questions,
        progress=progress,
        completed_lots=completed_lots
    )

def trophy_strip(n):
    return "🏆"*n if n>0 else "—"

def reset_results():
    st.session_state.answers = {}
    st.session_state.locked = set()
    st.session_state.current_index = 0
    st.session_state.last_feedback = None

def next_question():
    st.session_state.current_index += 1
    st.session_state.last_feedback = None

def prev_question():
    st.session_state.current_index = max(0, st.session_state.current_index - 1)
    st.session_state.last_feedback = None

# =========================
# Sidebar Controls
# =========================
st.sidebar.header("⚙️ Controles")
mode = st.sidebar.selectbox(
    "Modo",
    ["Hacer test completo", "Hacer lote 1", "Hacer lote 2", "Hacer lote 3", "Revisión (solo falladas)"],
    index=["Hacer test completo","Hacer lote 1","Hacer lote 2","Hacer lote 3","Revisión (solo falladas)"].index(
        {"full":"Hacer test completo","lote1":"Hacer lote 1","lote2":"Hacer lote 2","lote3":"Hacer lote 3","review":"Revisión (solo falladas)"}[st.session_state.mode]
    )
)
mode_map = {
    "Hacer test completo": "full",
    "Hacer lote 1": "lote1",
    "Hacer lote 2": "lote2",
    "Hacer lote 3": "lote3",
    "Revisión (solo falladas)": "review"
}
if mode_map[mode] != st.session_state.mode:
    st.session_state.mode = mode_map[mode]
    st.session_state.current_index = 0
    st.session_state.last_feedback = None

st.session_state.show_correct_between = st.sidebar.checkbox(
    "Mostrar respuesta correcta entre pregunta y pregunta",
    value=st.session_state.show_correct_between
)

if st.sidebar.button("🔄 Resetear resultados", use_container_width=True):
    reset_results()
    st.rerun()

# =========================
# Header KPI + Progress
# =========================
st.markdown("### 📊 Resultados Totales")
t = totals()
c1, c2, c3, c4 = st.columns([2,1,1,2])
with c1:
    st.write(f"**Respondidas:** {t['attempted']} / {t['total']}")
with c2:
    st.metric("✅ Aciertos", t["correct"])
with c3:
    st.metric("❌ Fallos", t["wrong"])
with c4:
    st.markdown("**Lotes completos (1–3):**")
    st.markdown(f"{trophy_strip(t['completed_lots'])}")

st.progress(t["progress"], text=f"Progreso global: {int(t['progress']*100)}%")

# Badges de lotes 1–3 con color cuando se completan
b1, b2, b3 = st.columns(3)
for idx, col in zip((1,2,3), (b1,b2,b3)):
    done = is_lot_completed(idx)
    color = "#22c55e" if done else "#e5e7eb"  # verde vs gris
    text_color = "#000000" if not done else "#ffffff"
    with col:
        st.markdown(
            f"""
            <div style="padding:10px;border-radius:8px;background:{color};color:{text_color};text-align:center;font-weight:600;">
              Lote {idx} {'✅' if done else '⏳'}
            </div>
            """,
            unsafe_allow_html=True
        )

st.divider()

# =========================
# Question Flow
# =========================
questions = get_questions_for_mode(st.session_state.mode)
total_in_mode = len(questions)

if total_in_mode == 0:
    st.info("No hay preguntas para este modo. Si estás en **Revisión**, ¡quizá no fallaste ninguna! 🎉")
    st.stop()

# Clamp index
st.session_state.current_index = min(st.session_state.current_index, total_in_mode - 1)
q = questions[st.session_state.current_index]

# Card
st.markdown(f"#### Pregunta {st.session_state.current_index+1} de {total_in_mode}  —  (Nº {q['n']} · Lote {q['lote_id']})")
st.markdown(f"**{q['pregunta']}**")

opts_map = {
    "A": q.get("respuesta_a", ""),
    "B": q.get("respuesta_b", ""),
    "C": q.get("respuesta_c", "")
}

prev_answer = st.session_state.answers.get(q["n"], {})
locked = (q["n"] in st.session_state.locked)

# Radio options
choice = st.radio(
    "Elige una opción:",
    options=["A","B","C"],
    format_func=lambda k: f"{k}) {opts_map.get(k,'')}",
    index=["A","B","C"].index(prev_answer.get("selected","A")) if prev_answer.get("selected") in {"A","B","C"} else 0,
    disabled=locked and prev_answer.get("correct") is False  # si quedó bloqueada por 1 fallo, no deja cambiar
)

c_left, c_mid, c_right = st.columns([1,1,2])

with c_left:
    if st.button("⬅️ Anterior", use_container_width=True):
        prev_question()
        st.rerun()

with c_mid:
    submitted = st.button("Responder", use_container_width=True, disabled=(locked and not prev_answer.get("correct", False)))
with c_right:
    if st.button("➡️ Siguiente", use_container_width=True):
        next_question()
        st.rerun()

if submitted:
    correct_letter = get_correct_letter(q)
    a = st.session_state.answers.get(q["n"], {"attempts": 0, "correct": False, "selected": None, "lote_id": q["lote_id"]})
    # Si ya estaba correcto, solo avanzamos selección
    if a.get("correct", False):
        a["selected"] = choice
        st.session_state.answers[q["n"]] = a
        if st.session_state.show_correct_between:
            st.success(f"✅ Ya estaba correcta. Respuesta correcta: {correct_letter}) {opts_map[correct_letter]}")
        next_question()
        st.rerun()
    else:
        # evaluar
        a["attempts"] = a.get("attempts", 0) + 1
        a["selected"] = choice
        if choice == correct_letter:
            a["correct"] = True
            st.session_state.answers[q["n"]] = a
            if st.session_state.show_correct_between:
                st.success(f"✅ Correcto. {correct_letter}) {opts_map[correct_letter]}")
            next_question()
            st.rerun()
        else:
            # fallo
            st.session_state.answers[q["n"]] = a
            # Máximo un fallo → bloquear y pasar
            st.session_state.locked.add(q["n"])
            if st.session_state.show_correct_between:
                st.error(f"❌ Incorrecto. Correcta: {correct_letter}) {opts_map[correct_letter]}")
            next_question()
            st.rerun()

# =========================
# Footer: Quick Review Panel
# =========================
with st.expander("📋 Resumen rápido de este modo"):
    colA, colB, colC = st.columns(3)
    mode_ids = {qq["n"] for qq in questions}
    mode_attempted = [n for n,a in st.session_state.answers.items() if n in mode_ids and a.get("attempts",0)>=1]
    mode_correct = [n for n,a in st.session_state.answers.items() if n in mode_ids and a.get("correct",False)]
    mode_wrong = [n for n,a in st.session_state.answers.items() if n in mode_ids and a.get("attempts",0)>=1 and not a.get("correct",False)]
    with colA:
        st.metric("Respondidas (modo)", len(mode_attempted), delta=None)
    with colB:
        st.metric("Aciertos (modo)", len(mode_correct), delta=None)
    with colC:
        st.metric("Fallos (modo)", len(mode_wrong), delta=None)

    st.write("**Falladas (IDs):**", ", ".join(map(str, mode_wrong)) if mode_wrong else "—")
    st.write("**Correctas (IDs):**", ", ".join(map(str, mode_correct)) if mode_correct else "—")

st.caption("Tip: activa en la barra lateral «Mostrar respuesta correcta…» si quieres feedback inmediato. Para reiniciar todo, usa «Resetear resultados».")