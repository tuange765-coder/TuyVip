import streamlit as st
import datetime
import bcrypt
import random
import re
import time
import psycopg2
import psycopg2.extras
from groq import Groq

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS
# ==========================================
st.set_page_config(
    page_title="San Andrea GT",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0f172a; color: #f8fafc; }
    .game-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 2px solid #334155;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .tuy-coin { color: #f59e0b; font-weight: bold; }
    .chat-bubble {
        background-color: #1e293b; border-left: 4px solid #0284c7;
        padding: 8px 12px; margin-bottom: 8px; border-radius: 4px;
    }
    .stButton>button { border-radius: 8px; font-weight: bold; transition: all 0.2s; }
    @keyframes caminar-ida-vuelta {
        0% { left: -50px; }
        100% { left: 100%; }
    }
    .npc-caminando {
        position: absolute; bottom: 5px; font-size: 30px;
        animation: caminar-ida-vuelta 15s infinite linear;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. CONEXIÓN A SUPABASE Y TABLAS
# ==========================================
def get_conn():
    return psycopg2.connect(
        host=st.secrets["db"]["host"],
        port=st.secrets["db"]["port"],
        user=st.secrets["db"]["user"],
        password=st.secrets["db"]["password"],
        dbname=st.secrets["db"]["dbname"],
        options="-c search_path=public"
    )

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Tablas existentes
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comprado INTEGER DEFAULT 0, zona TEXT DEFAULT 'Santa Teresa (Centro)',
            sector TEXT DEFAULT 'Plaza Bolívar', vestuario TEXT DEFAULT 'Franela tricolor y Jeans',
            personalidad TEXT DEFAULT 'Rumbero/a y alegre', saldo REAL DEFAULT 100.0,
            es_admin INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS locales (
            id SERIAL PRIMARY KEY, nombre TEXT NOT NULL, tipo TEXT NOT NULL,
            zona TEXT NOT NULL, sector TEXT NOT NULL, propietario TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_mensajes (
            id SERIAL PRIMARY KEY, username TEXT NOT NULL, sector TEXT NOT NULL,
            mensaje TEXT NOT NULL, tipo TEXT DEFAULT 'hablar',
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id SERIAL PRIMARY KEY, titulo TEXT NOT NULL, descripcion TEXT NOT NULL,
            sector TEXT NOT NULL, fecha_evento TEXT NOT NULL, creador TEXT NOT NULL
        )
    """)

    # NUEVA TABLA: Memoria de los NPCs
    c.execute("""
        CREATE TABLE IF NOT EXISTS npc_memorias (
            id SERIAL PRIMARY KEY,
            npc_nombre TEXT NOT NULL,
            sector TEXT NOT NULL,
            recuerdo TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        admin_hash = hash_password("admin123")
        c.execute("INSERT INTO usuarios (username, password_hash, comprado, es_admin) VALUES ('admin', %s, 1, 1)", (admin_hash,))

    conn.commit()
    c.close()
    conn.close()


# ==========================================
# 3. FUNCIONES AUXILIARES
# ==========================================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except:
        return False

def valid_username(name: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_]{3,20}$", name))


# ==========================================
# 4. DATOS DEL JUEGO Y NPCS
# ==========================================
SECTORES_MAPA = {
    "Santa Teresa (Centro)": ["Plaza Bolívar", "Casco Central", "La Estación", "El Calvario", "La Virginia", "Sector El Mamón"],
    "El Cartanal": ["Sectores 1 al 10", "Urb. Luis Tovar", "Las Paragüitas", "Zona Industrial Cloris"],
    "Las Dos Lagunas": ["Los Bloques de Dos Lagunas", "Sector El Desvío", "Las Casitas"]
}

OPCIONES_VESTUARIO = [
    "👕 Franela Tricolor y Jeans", "🎽 Camiseta de Los Leones del Caracas y Gorra",
    "👔 Liquiliqui Tradicional", "👗 Vestido Playero y Sandalias",
    "🧥 Chaqueta Deportiva y Monos", "👕 Camisa de Guayabera Blanca"
]

OPCIONES_PERSONALIDAD = [
    "🔥 Rumbero/a y alegre", "☕ Comerciante y negociador/a",
    "🎨 Poeta y cronista local", "⚽ Pelotero / Deportista de corazón",
    "🤫 Observador/a del pueblo"
]

TRABAJOS_DISPONIBLES = [
    {"titulo": "Vendedor/a de Cepillados en la Plaza", "pago": 15.0, "energia": "Baja"},
    {"titulo": "Mecánico/a en Zona Industrial Cloris", "pago": 35.0, "energia": "Alta"},
    {"titulo": "Chofer de Carrito Por Puesto (Ruta Cartanal-Centro)", "pago": 25.0, "energia": "Media"},
    {"titulo": "Organizador/a de Parrandas y San Juan", "pago": 30.0, "energia": "Media"}
]

NPCS = [
    {"nombre": "San Andrea", "avatar": "🕵️‍♂️", "personalidad": "Eres San Andrea, carismático, sarcástico y buena gente. Usas un tono venezolano coloquial y te gusta el chisme."},
    {"nombre": "Doña Rosa", "avatar": "👵", "personalidad": "Eres Doña Rosa, una señora mayor, católica, chismosa y pendiente de todo el pueblo. Regañas con cariño."},
    {"nombre": "El Profe Luis", "avatar": "👨‍🏫", "personalidad": "Eres El Profe Luis, intelectual del pueblo. Das consejos, hablas de historia y te quejas del país con respeto."}
]


# ==========================================
# 5. MÓDULO DE AUTENTICACIÓN
# ==========================================
def modulo_autenticacion():
    st.markdown("<h1 style='text-align: center; color: #0284c7;'>🏙️ San Andrea GT</h1>", unsafe_allow_html=True)
    st.caption("<p style='text-align: center;'>Explora, trabaja, funda tu negocio y comparte con los vecinos.</p>", unsafe_allow_html=True)

    col_main = st.columns([1, 2, 1])[1]

    with col_main:
        pestana = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta Nueva"])

        with pestana[0]:
            user_login = st.text_input("Usuario:", key="login_user")
            pass_login = st.text_input("Contraseña:", type="password", key="login_pass")

            if st.button("🚀 Entrar al Juego", use_container_width=True):
                conn = get_conn()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT * FROM usuarios WHERE username = %s", (user_login,))
                user = cur.fetchone()
                cur.close(); conn.close()

                if user and verify_password(pass_login, user["password_hash"]):
                    st.session_state.usuario_logueado = user_login
                    st.query_params["user"] = user_login  # Guardar en URL para persistencia
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")

        with pestana[1]:
            user_reg = st.text_input("Nombre de Usuario:", key="reg_user")
            pass_reg = st.text_input("Contraseña:", type="password", key="reg_pass")
            zona_init = st.selectbox("Zona de Inicio:", list(SECTORES_MAPA.keys()))
            sector_init = st.selectbox("Sector de Origen:", SECTORES_MAPA[zona_init])
            vestuario_init = st.selectbox("Vestuario:", OPCIONES_VESTUARIO)
            per_init = st.selectbox("Personalidad:", OPCIONES_PERSONALIDAD)

            if st.button("💾 Crear Personaje", use_container_width=True):
                if not user_reg or not pass_reg:
                    st.warning("Completa los campos.")
                elif not valid_username(user_reg):
                    st.error("Usuario inválido (3-20 letras/números/_ ).")
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    try:
                        cur.execute("""
                            INSERT INTO usuarios (username, password_hash, zona, sector, vestuario, personalidad)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (user_reg, hash_password(pass_reg), zona_init, sector_init, vestuario_init, per_init))
                        conn.commit()
                        st.success("¡Cuenta creada! Inicia sesión.")
                    except psycopg2.errors.UniqueViolation:
                        conn.rollback()
                        st.error("Ese usuario ya existe.")
                    finally:
                        cur.close(); conn.close()


# ==========================================
# 6. LÓGICA DE MEMORIA DE NPCS
# ==========================================
def guardar_memoria_npc(nombre_npc, sector, recuerdo):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO npc_memorias (npc_nombre, sector, recuerdo) VALUES (%s, %s, %s)", (nombre_npc, sector, recuerdo))
    conn.commit()
    cur.close(); conn.close()

def obtener_memorias_npc(nombre_npc, sector, limite=5):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT recuerdo FROM npc_memorias 
        WHERE npc_nombre = %s AND sector = %s 
        ORDER BY id DESC LIMIT %s
    """, (nombre_npc, sector, limite))
    memorias = cur.fetchall()
    cur.close(); conn.close()
    return [m["recuerdo"] for m in reversed(memorias)]  # Orden cronológico


# ==========================================
# 7. JUEGO PRINCIPAL
# ==========================================
def juego_principal():
    u_actual = st.session_state.usuario_logueado

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM usuarios WHERE username = %s", (u_actual,))
    user_data = cur.fetchone()
    cur.close(); conn.close()

    if user_data is None:
        del st.session_state.usuario_logueado
        st.query_params.clear()
        st.rerun()
        return

    # Restricción de 10 días (lógica simplificada)
    fecha_creacion = user_data["fecha_creacion"]
    if isinstance(fecha_creacion, str):
        fecha_creacion = datetime.datetime.fromisoformat(fecha_creacion)
    dias = (datetime.datetime.now() - fecha_creacion).days

    if dias >= 10 and not user_data["comprado"] and not user_data["es_admin"]:
        st.error(f"⚠️ {u_actual} cumplió {dias} días de prueba.")
        if st.button("💳 Adquirir Personaje Definitivo"):
            conn = get_conn(); cur = conn.cursor()
            cur.execute("UPDATE usuarios SET comprado = 1 WHERE username = %s", (u_actual,))
            conn.commit(); cur.close(); conn.close()
            st.rerun()
        if st.button("🚪 Cerrar Sesión"):
            del st.session_state.usuario_logueado
            st.query_params.clear()
            st.rerun()
        return

    # --- SIDEBAR ---
    st.sidebar.markdown(f"### 👤 {user_data['username']}")
    if user_data["es_admin"]: st.sidebar.caption("⭐ Administrador")
    elif user_data["comprado"]: st.sidebar.caption("⭐ Premium")
    else: st.sidebar.caption(f"⏳ Prueba: {dias}/10 días")

    st.sidebar.markdown(f"💰 Saldo: <span class='tuy-coin'>{user_data['saldo']:.2f}</span> TuyCoins", unsafe_allow_html=True)
    st.sidebar.markdown(f"🎭 {user_data['vestuario']}")
    st.sidebar.markdown("---")

    # Viaje (esto se guarda automáticamente en la BD)
    zona_actual = user_data["zona"]
    sector_actual = user_data["sector"]
    nueva_zona = st.sidebar.selectbox("Zona:", list(SECTORES_MAPA.keys()), index=list(SECTORES_MAPA.keys()).index(zona_actual) if zona_actual in SECTORES_MAPA else 0)
    sectores = SECTORES_MAPA[nueva_zona]
    idx = sectores.index(sector_actual) if sector_actual in sectores else 0
    nuevo_sector = st.sidebar.selectbox("Sector:", sectores, index=idx)

    if nueva_zona != zona_actual or nuevo_sector != sector_actual:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET zona = %s, sector = %s WHERE username = %s", (nueva_zona, nuevo_sector, u_actual))
        conn.commit(); cur.close(); conn.close()
        st.toast(f"🚚 Te moviste a {nuevo_sector}")
        st.rerun()

    if st.sidebar.button("🚪 Salir (Guardar y Cerrar)", use_container_width=True):
        del st.session_state.usuario_logueado
        st.query_params.clear()
        st.rerun()

    st.title(f"📍 {nuevo_sector}")
    st.caption(f"{nueva_zona} | San Andrea GT")

    tabs = st.tabs(["🏢 Comercios", "🎉 Chat & NPCs", "💼 Empleos", "📅 Eventos", "⚙️ Perfil"])
    if user_data["es_admin"]: tabs.append("🛡️ Admin")

    # TAB COMERCIOS
    with tabs[0]:
        st.subheader(f"🏪 Locales en {nuevo_sector}")
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM locales WHERE sector = %s", (nuevo_sector,))
        locales = cur.fetchall(); cur.close(); conn.close()
        if locales:
            for l in locales: st.markdown(f"<div class='game-card'><b>🏪 {l['nombre']}</b> ({l['tipo']}) - Dueño: @{l['propietario']}</div>", unsafe_allow_html=True)
        else: st.info("No hay comercios. ¡Funda el primero!")
        
        with st.form("form_local"):
            nom = st.text_input("Nombre del local:")
            tip = st.selectbox("Tipo:", ["Tasca", "Abasto", "Comida", "Taller", "Fundación", "Cyber"])
            if st.form_submit_button("🔨 Fundar"):
                if nom:
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("INSERT INTO locales (nombre, tipo, zona, sector, propietario) VALUES (%s,%s,%s,%s,%s)", (nom, tip, nueva_zona, nuevo_sector, u_actual))
                    conn.commit(); cur.close(); conn.close()
                    st.rerun()

    # TAB CHAT & NPCs (CON MEMORIA)
    with tabs[1]:
        st.subheader(f"💬 Chat en {nuevo_sector}")
        
        # Animación
        st.markdown("""
        <div style="position: relative; height: 60px; background: #1e293b; border-radius: 10px; overflow: hidden; margin-bottom: 15px;">
            <div class="npc-caminando" style="animation-duration: 12s;">🕵️‍♂️</div>
            <div class="npc-caminando" style="animation-duration: 18s; animation-direction: reverse;">👵</div>
            <div class="npc-caminando" style="animation-duration: 15s;">👨‍🏫</div>
        </div>
        """, unsafe_allow_html=True)

        client = Groq(api_key=st.secrets["api_keys"]["GROQ_API_KEY"])

        # Botón para que los NPCs hablen entre ellos
        if st.button("🎲 Simular conversación entre NPCs"):
            with st.spinner("Los vecinos recuerdan y hablan..."):
                npcs_sel = random.sample(NPCS, 2)
                npc1, npc2 = npcs_sel[0], npcs_sel[1]
                
                # Obtener memorias de ambos
                mem1 = obtener_memorias_npc(npc1["nombre"], nuevo_sector)
                mem2 = obtener_memorias_npc(npc2["nombre"], nuevo_sector)
                
                prompt1 = f"Eres {npc1['nombre']}. {npc1['personalidad']} Tus recuerdos previos: {mem1}. Habla sobre algo que recuerdes o comenta la situación actual del pueblo. Máx 2 oraciones."
                res1 = client.chat.completions.create(messages=[{"role": "user", "content": prompt1}], model="llama3-8b-8192")
                txt1 = res1.choices[0].message.content
                
                guardar_memoria_npc(npc1["nombre"], nuevo_sector, txt1)
                conn = get_conn(); cur = conn.cursor()
                cur.execute("INSERT INTO chat_mensajes (username, sector, mensaje, tipo) VALUES (%s,%s,%s,%s)", (f"{npc1['avatar']} {npc1['nombre']}", nuevo_sector, txt1, "Hablar 💬"))
                conn.commit(); cur.close(); conn.close()

                prompt2 = f"Eres {npc2['nombre']}. {npc2['personalidad']} Tus recuerdos: {mem2}. {npc1['nombre']} dijo: '{txt1}'. Responde. Máx 2 oraciones."
                res2 = client.chat.completions.create(messages=[{"role": "user", "content": prompt2}], model="llama3-8b-8192")
                txt2 = res2.choices[0].message.content
                
                guardar_memoria_npc(npc2["nombre"], nuevo_sector, txt2)
                conn = get_conn(); cur = conn.cursor()
                cur.execute("INSERT INTO chat_mensajes (username, sector, mensaje, tipo) VALUES (%s,%s,%s,%s)", (f"{npc2['avatar']} {npc2['nombre']}", nuevo_sector, txt2, "Hablar 💬"))
                conn.commit(); cur.close(); conn.close()
                st.rerun()

        # Formulario de chat del jugador
        with st.form("chat_form", clear_on_submit=True):
            msg = st.text_input("Mensaje:")
            tipo = st.selectbox("Estilo:", ["Hablar 💬", "Hablar con NPC 🤖"])
            if st.form_submit_button("Enviar"):
                if msg:
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("INSERT INTO chat_mensajes (username, sector, mensaje, tipo) VALUES (%s,%s,%s,%s)", (u_actual, nuevo_sector, msg, tipo))
                    conn.commit(); cur.close(); conn.close()

                    if tipo == "Hablar con NPC 🤖":
                        npc = random.choice(NPCS)
                        mems = obtener_memorias_npc(npc["nombre"], nuevo_sector)
                        prompt = f"Eres {npc['nombre']}. {npc['personalidad']} Recuerdas: {mems}. Un jugador te dice: '{msg}'. Responde naturalmente."
                        res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama3-8b-8192")
                        resp = res.choices[0].message.content
                        guardar_memoria_npc(npc["nombre"], nuevo_sector, resp)
                        conn = get_conn(); cur = conn.cursor()
                        cur.execute("INSERT INTO chat_mensajes (username, sector, mensaje, tipo) VALUES (%s,%s,%s,%s)", (f"{npc['avatar']} {npc['nombre']}", nuevo_sector, resp, "Hablar 💬"))
                        conn.commit(); cur.close(); conn.close()
                    st.rerun()

        # Mostrar mensajes
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM chat_mensajes WHERE sector = %s ORDER BY id DESC LIMIT 15", (nuevo_sector,))
        msgs = cur.fetchall(); cur.close(); conn.close()
        for m in msgs:
            f = m['fecha'].strftime("%H:%M") if hasattr(m['fecha'], 'strftime') else ""
            st.markdown(f"<div class='chat-bubble'><b>[{m['username']}]:</b> {m['mensaje']} <small>({f})</small></div>", unsafe_allow_html=True)

    # TAB EMPLEOS
    with tabs[2]:
        st.subheader("💼 Trabajos")
        cols = st.columns(2)
        for i, t in enumerate(TRABAJOS_DISPONIBLES):
            with cols[i % 2]:
                st.markdown(f"<div class='game-card'><b>{t['titulo']}</b><br>Pago: {t['pago']} TuyCoins</div>", unsafe_allow_html=True)
                if st.button("Trabajar", key=f"w{i}"):
                    g = t["pago"] + random.randint(1, 5)
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET saldo = saldo + %s WHERE username = %s", (g, u_actual))
                    conn.commit(); cur.close(); conn.close()
                    st.success(f"Ganaste {g} TuyCoins!")
                    st.rerun()

    # TAB EVENTOS
    with tabs[3]:
        st.subheader("📅 Eventos")
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM eventos WHERE sector = %s", (nuevo_sector,))
        evs = cur.fetchall(); cur.close(); conn.close()
        for e in evs: st.markdown(f"<div class='game-card'><b>{e['titulo']}</b> - {e['fecha_evento']}<br>{e['descripcion']}</div>", unsafe_allow_html=True)
        
        with st.form("form_ev"):
            t_ev = st.text_input("Título:")
            d_ev = st.text_area("Descripción:")
            f_ev = st.date_input("Fecha:")
            if st.form_submit_button("Publicar"):
                if t_ev and d_ev:
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("INSERT INTO eventos (titulo, descripcion, sector, fecha_evento, creador) VALUES (%s,%s,%s,%s,%s)", (t_ev, d_ev, nuevo_sector, str(f_ev), u_actual))
                    conn.commit(); cur.close(); conn.close()
                    st.rerun()

    # TAB PERFIL
    with tabs[4]:
        st.subheader("⚙️ Perfil")
        with st.form("form_perf"):
            v = st.selectbox("Vestuario:", OPCIONES_VESTUARIO, index=OPCIONES_VESTUARIO.index(user_data["vestuario"]) if user_data["vestuario"] in OPCIONES_VESTUARIO else 0)
            p = st.selectbox("Personalidad:", OPCIONES_PERSONALIDAD, index=OPCIONES_PERSONALIDAD.index(user_data["personalidad"]) if user_data["personalidad"] in OPCIONES_PERSONALIDAD else 0)
            if st.form_submit_button("Guardar"):
                conn = get_conn(); cur = conn.cursor()
                cur.execute("UPDATE usuarios SET vestuario = %s, personalidad = %s WHERE username = %s", (v, p, u_actual))
                conn.commit(); cur.close(); conn.close()
                st.rerun()

    # TAB ADMIN
    if user_data["es_admin"]:
        with tabs[5]:
            st.subheader("🛡️ Admin")
            conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT username, comprado, saldo, zona, sector FROM usuarios")
            us = cur.fetchall(); cur.close(); conn.close()
            st.dataframe([dict(u) for u in us])
            target = st.selectbox("Usuario:", [u["username"] for u in us if u["username"] != "admin"])
            if st.button("⭐ Dar Premium"):
                conn = get_conn(); cur = conn.cursor()
                cur.execute("UPDATE usuarios SET comprado = 1 WHERE username = %s", (target,))
                conn.commit(); cur.close(); conn.close()
                st.rerun()
            if st.button("💸 +500 TuyCoins"):
                conn = get_conn(); cur = conn.cursor()
                cur.execute("UPDATE usuarios SET saldo = saldo + 500 WHERE username = %s", (target,))
                conn.commit(); cur.close(); conn.close()
                st.rerun()


# ==========================================
# 8. FLUJO PRINCIPAL CON PERSISTENCIA DE SESIÓN
# ==========================================
init_db()

# Restaurar sesión desde la URL si existe
if "usuario_logueado" not in st.session_state and "user" in st.query_params:
    st.session_state.usuario_logueado = st.query_params["user"]

if "usuario_logueado" not in st.session_state:
    modulo_autenticacion()
else:
    juego_principal()
