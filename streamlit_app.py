import streamlit as st
import datetime
import bcrypt
import random
import re
import time
import psycopg2
import psycopg2.extras

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS
# ==========================================
st.set_page_config(
    page_title="Mundo Virtual Santa Teresa del Tuy",
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
    .avatar-badge {
        background-color: #0284c7; color: white; padding: 4px 12px;
        border-radius: 20px; font-weight: bold; font-size: 0.85em;
        display: inline-block;
    }
    .tuy-coin { color: #f59e0b; font-weight: bold; }
    .chat-bubble {
        background-color: #1e293b; border-left: 4px solid #0284c7;
        padding: 8px 12px; margin-bottom: 8px; border-radius: 4px;
    }
    .stButton>button { border-radius: 8px; font-weight: bold; transition: all 0.2s; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. CONEXIÓN A SUPABASE (PostgreSQL en la nube)
# ==========================================
def get_conn():
    """Devuelve una conexión a la base de datos PostgreSQL de Supabase usando variables separadas."""
    return psycopg2.connect(
        host=st.secrets["db"]["host"],
        port=st.secrets["db"]["port"],
        user=st.secrets["db"]["user"],
        password=st.secrets["db"]["password"],
        dbname=st.secrets["db"]["dbname"],
        options="-c search_path=public"
    )


def init_db():
    """Crea las tablas si no existen y el usuario admin por defecto."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comprado INTEGER DEFAULT 0,
            zona TEXT DEFAULT 'Santa Teresa (Centro)',
            sector TEXT DEFAULT 'Plaza Bolívar',
            vestuario TEXT DEFAULT 'Franela tricolor y Jeans',
            personalidad TEXT DEFAULT 'Rumbero/a y alegre',
            saldo REAL DEFAULT 100.0,
            es_admin INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS locales (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            zona TEXT NOT NULL,
            sector TEXT NOT NULL,
            propietario TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_mensajes (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            sector TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            tipo TEXT DEFAULT 'hablar',
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id SERIAL PRIMARY KEY,
            titulo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            sector TEXT NOT NULL,
            fecha_evento TEXT NOT NULL,
            creador TEXT NOT NULL
        )
    """)

    c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        admin_hash = hash_password("admin123")
        c.execute(
            "INSERT INTO usuarios (username, password_hash, comprado, es_admin) VALUES ('admin', %s, 1, 1)",
            (admin_hash,)
        )

    conn.commit()
    c.close()
    conn.close()


# ==========================================
# 3. FUNCIONES AUXILIARES
# ==========================================
def hash_password(password: str) -> str:
    """Hashea una contraseña con bcrypt. Devuelve str para guardar en Postgres."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def valid_username(name: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_]{3,20}$", name))


# ==========================================
# 4. DATOS GEOGRÁFICOS Y CONSTANTES
# ==========================================
SECTORES_MAPA = {
    "Santa Teresa (Centro)": [
        "Plaza Bolívar", "Casco Central", "La Estación",
        "El Calvario", "La Virginia", "Sector El Mamón"
    ],
    "El Cartanal": [
        "Sectores 1 al 10", "Urb. Luis Tovar",
        "Las Paragüitas", "Zona Industrial Cloris"
    ],
    "Las Dos Lagunas": [
        "Los Bloques de Dos Lagunas", "Sector El Desvío", "Las Casitas"
    ]
}

OPCIONES_VESTUARIO = [
    "👕 Franela Tricolor y Jeans",
    "🎽 Camiseta de Los Leones del Caracas y Gorra",
    "👔 Liquiliqui Tradicional",
    "👗 Vestido Playero y Sandalias",
    "🧥 Chaqueta Deportiva y Monos",
    "👕 Camisa de Guayabera Blanca"
]

OPCIONES_PERSONALIDAD = [
    "🔥 Rumbero/a y alegre",
    "☕ Comerciante y negociador/a",
    "🎨 Poeta y cronista local",
    "⚽ Pelotero / Deportista de corazón",
    "🤫 Observador/a del pueblo"
]

TRABAJOS_DISPONIBLES = [
    {"titulo": "Vendedor/a de Cepillados en la Plaza", "pago": 15.0, "energia": "Baja"},
    {"titulo": "Mecánico/a en Zona Industrial Cloris", "pago": 35.0, "energia": "Alta"},
    {"titulo": "Chofer de Carrito Por Puesto (Ruta Cartanal-Centro)", "pago": 25.0, "energia": "Media"},
    {"titulo": "Organizador/a de Parrandas y San Juan", "pago": 30.0, "energia": "Media"}
]


# ==========================================
# 5. MÓDULO DE AUTENTICACIÓN
# ==========================================
def modulo_autenticacion():
    st.markdown("<h1 style='text-align: center; color: #0284c7;'>🏙️ Mundo Virtual Santa Teresa del Tuy</h1>", unsafe_allow_html=True)
    st.caption("<p style='text-align: center;'>Explora, trabaja, funda tu negocio y comparte con tus vecinos tereseños.</p>", unsafe_allow_html=True)

    col_main = st.columns([1, 2, 1])[1]

    with col_main:
        pestana = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta Nueva"])

        # --- LOGIN ---
        with pestana[0]:
            user_login = st.text_input("Usuario:", key="login_user")
            pass_login = st.text_input("Contraseña:", type="password", key="login_pass")

            if st.button("🚀 Entrar al Juego", use_container_width=True):
                conn = get_conn()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT * FROM usuarios WHERE username = %s", (user_login,))
                user = cur.fetchone()
                cur.close()
                conn.close()

                if user and verify_password(pass_login, user["password_hash"]):
                    st.session_state.usuario_logueado = user_login
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas o usuario inexistente.")

        # --- REGISTRO ---
        with pestana[1]:
            user_reg = st.text_input("Crea tu Nombre de Usuario:", key="reg_user")
            pass_reg = st.text_input("Crea tu Contraseña:", type="password", key="reg_pass")

            zona_init = st.selectbox("Zona de Inicio:", list(SECTORES_MAPA.keys()))
            sector_init = st.selectbox("Sector de Origen:", SECTORES_MAPA[zona_init])
            vestuario_init = st.selectbox("Vestuario Inicial:", OPCIONES_VESTUARIO)
            per_init = st.selectbox("Personalidad:", OPCIONES_PERSONALIDAD)

            st.markdown("---")
            st.caption("⚙️ **Simulación para pruebas de desarrollo:**")
            dias_simulados = st.slider("Simular días de antigüedad de la cuenta:", 0, 15, 0)

            if st.button("💾 Crear Personaje y Guardar", use_container_width=True):
                if not user_reg or not pass_reg:
                    st.warning("Completa todos los campos obligatorios.")
                    return
                if not valid_username(user_reg):
                    st.error("Usuario inválido. Solo letras, números y guion bajo (3-20 caracteres).")
                    return

                conn = get_conn()
                cur = conn.cursor()
                try:
                    fecha_registro = datetime.datetime.now() - datetime.timedelta(days=dias_simulados)
                    cur.execute("""
                        INSERT INTO usuarios (username, password_hash, fecha_creacion, zona, sector, vestuario, personalidad)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (user_reg, hash_password(pass_reg), fecha_registro, zona_init, sector_init, vestuario_init, per_init))
                    conn.commit()
                    st.success("¡Cuenta registrada con éxito! Ya puedes iniciar sesión.")
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    st.error("El nombre de usuario ya está registrado en el servidor.")
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error al registrar: {e}")
                finally:
                    cur.close()
                    conn.close()


# ==========================================
# 6. JUEGO PRINCIPAL
# ==========================================
def juego_principal():
    u_actual = st.session_state.usuario_logueado

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM usuarios WHERE username = %s", (u_actual,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()

    if user_data is None:
        st.error("Usuario no encontrado. Cerrando sesión.")
        del st.session_state.usuario_logueado
        st.rerun()
        return

    fecha_creacion = user_data["fecha_creacion"]
    if isinstance(fecha_creacion, str):
        fecha_creacion = datetime.datetime.fromisoformat(fecha_creacion)
    dias_transcurridos = (datetime.datetime.now() - fecha_creacion).days

    # --- RESTRICCIÓN DE 10 DÍAS ---
    if dias_transcurridos >= 10 and not user_data["comprado"] and not user_data["es_admin"]:
        st.error(f"⚠️ Tu personaje **{u_actual}** ha cumplido {dias_transcurridos} días de actividad libre.")
        st.warning("🚨 **MUNDOS DEL TUY - ANUNCIO DE ADQUISICIÓN EXCLUSIVA** 🚨")
        st.markdown(
            f"Has explorado Santa Teresa, El Cartanal y Las Dos Lagunas durante el periodo de prueba.\n\n"
            f"Para continuar jugando con **{u_actual}**, conservar tu saldo de **{user_data['saldo']:.2f} TuyCoins**, "
            f"tus propiedades y tu historial sin límites, adquiere la membresía definitiva."
        )
        col_buy, col_logout = st.columns(2)
        with col_buy:
            if st.button("💳 Adquirir Personaje Definitivo (Simulado)", use_container_width=True):
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("UPDATE usuarios SET comprado = 1 WHERE username = %s", (u_actual,))
                conn.commit()
                cur.close()
                conn.close()
                st.success("¡Felicidades! Personaje desbloqueado permanentemente.")
                st.rerun()
        with col_logout:
            if st.button("🚪 Cerrar Sesión", use_container_width=True):
                del st.session_state.usuario_logueado
                st.rerun()
        return

    # --- SIDEBAR ---
    st.sidebar.markdown(f"### 👤 {user_data['username']}")
    if user_data["es_admin"]:
        st.sidebar.caption("⭐ **Administrador del Servidor**")
    elif user_data["comprado"]:
        st.sidebar.caption("⭐ **Cuenta Premium Definitiva**")
    else:
        st.sidebar.caption(f"⏳ Periodo de prueba: {dias_transcurridos} / 10 días")

    st.sidebar.markdown(f"💰 **Saldo:** <span class='tuy-coin'>{user_data['saldo']:.2f} TuyCoins</span>", unsafe_allow_html=True)
    st.sidebar.markdown(f"🎭 **Atuendo:** {user_data['vestuario']}")
    st.sidebar.markdown(f"🌟 **Personalidad:** {user_data['personalidad']}")
    st.sidebar.markdown("---")

    st.sidebar.subheader("🗺️ Moverse por el Municipio")
    zona_actual = user_data["zona"]
    sector_actual = user_data["sector"]

    nueva_zona = st.sidebar.selectbox(
        "Zona General:",
        list(SECTORES_MAPA.keys()),
        index=list(SECTORES_MAPA.keys()).index(zona_actual) if zona_actual in SECTORES_MAPA else 0
    )
    sectores_disponibles = SECTORES_MAPA[nueva_zona]
    idx_sector = sectores_disponibles.index(sector_actual) if sector_actual in sectores_disponibles else 0
    nuevo_sector = st.sidebar.selectbox("Sector Específico:", sectores_disponibles, index=idx_sector)

    if nueva_zona != zona_actual or nuevo_sector != sector_actual:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET zona = %s, sector = %s WHERE username = %s", (nueva_zona, nuevo_sector, u_actual))
        conn.commit()
        cur.close()
        conn.close()
        st.toast(f"🚚 Te has trasladado a {nuevo_sector} ({nueva_zona})")
        st.rerun()

    if st.sidebar.button("🚪 Salir del Juego", use_container_width=True):
        del st.session_state.usuario_logueado
        st.rerun()

    st.title(f"📍 {nuevo_sector}")
    st.caption(f"Ubicación actual: {nueva_zona} | Municipio Independencia")

    pestanas_juego = ["🏢 Comercios y Locales", "🎉 Chat del Sector", "💼 Empleos y Economía", "📅 Eventos Locales", "⚙️ Mi Perfil"]
    if user_data["es_admin"]:
        pestanas_juego.append("🛡️ Admin Panel")

    tabs = st.tabs(pestanas_juego)

    # --- TAB 1: COMERCIOS ---
    with tabs[0]:
        st.subheader(f"🏪 Establecimientos en {nuevo_sector}")
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM locales WHERE sector = %s", (nuevo_sector,))
        locales = cur.fetchall()
        cur.close()
        conn.close()

        if locales:
            for loc in locales:
                st.markdown(f"""
                <div class='game-card'>
                    <h4>🏪 {loc['nombre']}</h4>
                    <p><b>Categoría:</b> {loc['tipo']} | <b>Fundador:</b> @{loc['propietario']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay comercios registrados en este sector aún. ¡Sé el primero en fundar uno!")

        st.markdown("---")
        st.markdown("### ➕ Fundar un Nuevo Negocio / Local")
        with st.form("form_nuevo_local"):
            nom_local = st.text_input("Nombre del Local o Negocio:")
            tipo_local = st.selectbox("Tipo de Establecimiento:", [
                "Tasca / Discoteca", "Abasto / Bodega",
                "Comida Rápida y Perros Calientes", "Taller Mecánico / Autoperiquitos",
                "Fundación Cultural o Deportiva", "Cyber Café / Centro de Conexión"
            ])
            if st.form_submit_button("🔨 Registrar y Fundar Negocio"):
                if nom_local:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO locales (nombre, tipo, zona, sector, propietario)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (nom_local, tipo_local, nueva_zona, nuevo_sector, u_actual))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"¡Has fundado '{nom_local}' en {nuevo_sector}!")
                    st.rerun()
                else:
                    st.warning("Escribe el nombre del negocio.")

    # --- TAB 2: CHAT ---
    with tabs[1]:
        st.subheader(f"💬 Chat de la Comunidad - {nuevo_sector}")

        with st.form("form_chat", clear_on_submit=True):
            col_txt, col_tipo = st.columns([3, 1])
            with col_txt:
                msj_texto = st.text_input("Mensaje:", placeholder="Escribe un mensaje o acción...")
            with col_tipo:
                tipo_accion = st.selectbox("Estilo:", ["Hablar 💬", "Gritar 📢", "Acción/Rol 🎭"])

            if st.form_submit_button("Enviar Mensaje"):
                ultimo = st.session_state.get("ultimo_msj", 0)
                if time.time() - ultimo < 5:
                    st.warning("⏳ Espera 5 segundos entre mensajes.")
                elif msj_texto:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO chat_mensajes (username, sector, mensaje, tipo)
                        VALUES (%s, %s, %s, %s)
                    """, (u_actual, nuevo_sector, msj_texto, tipo_accion))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.session_state.ultimo_msj = time.time()
                    st.rerun()

        st.markdown("---")
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM chat_mensajes WHERE sector = %s ORDER BY id DESC LIMIT 15", (nuevo_sector,))
        mensajes = cur.fetchall()
        cur.close()
        conn.close()

        if mensajes:
            for m in mensajes:
                fecha_fmt = m["fecha"].strftime("%Y-%m-%d %H:%M") if hasattr(m["fecha"], "strftime") else str(m["fecha"])
                if m["tipo"] == "Gritar 📢":
                    st.markdown(f"📢 **[{m['username']}] (GRITA):** <span style='color:#ef4444;'>{m['mensaje']}</span> <small style='color:gray;'>({fecha_fmt})</small>", unsafe_allow_html=True)
                elif m["tipo"] == "Acción/Rol 🎭":
                    st.markdown(f"🎭 *[{m['username']}] {m['mensaje']}* <small style='color:gray;'>({fecha_fmt})</small>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='chat-bubble'><b>[{m['username']}]:</b> {m['mensaje']} <br><small style='color:#94a3b8;'>{fecha_fmt}</small></div>", unsafe_allow_html=True)
        else:
            st.caption("No hay mensajes en este sector aún. Escribe el primero.")

    # --- TAB 3: EMPLEOS ---
    with tabs[2]:
        st.subheader("💼 Bolsa de Trabajo y Producción Local")
        st.write("Trabaja en el municipio para ganar **TuyCoins** y mejorar tu estatus.")
        col_work1, col_work2 = st.columns(2)

        for idx, trab in enumerate(TRABAJOS_DISPONIBLES):
            col_target = col_work1 if idx % 2 == 0 else col_work2
            with col_target:
                st.markdown(f"""
                <div class='game-card'>
                    🎯 <b>{trab['titulo']}</b><br>
                    💰 Pago: <span class='tuy-coin'>+{trab['pago']} TuyCoins</span><br>
                    ⚡ Exigencia: {trab['energia']}
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Trabajar como {trab['titulo'].split()[0]}", key=f"job_{idx}"):
                    ganancia = trab["pago"] + random.randint(1, 5)
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET saldo = saldo + %s WHERE username = %s", (ganancia, u_actual))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.balloons()
                    st.success(f"¡Has completado tu jornada! Ganaste {ganancia:.2f} TuyCoins.")
                    st.rerun()

    # --- TAB 4: EVENTOS ---
    with tabs[3]:
        st.subheader("📅 Cartelera de Eventos y Parrandas")
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM eventos WHERE sector = %s ORDER BY id DESC", (nuevo_sector,))
        eventos = cur.fetchall()
        cur.close()
        conn.close()

        if eventos:
            for ev in eventos:
                st.markdown(f"""
                <div class='game-card'>
                    🎉 <b>{ev['titulo']}</b><br>
                    📍 Sector: {ev['sector']} | 📅 Fecha: {ev['fecha_evento']}<br>
                    📝 {ev['descripcion']}<br>
                    <small>Organizado por: @{ev['creador']}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay eventos programados en este sector por ahora.")

        st.markdown("---")
        st.markdown("### ➕ Crear Nuevo Evento Comunitario")
        with st.form("form_evento"):
            t_ev = st.text_input("Título del Evento:")
            d_ev = st.text_area("Descripción de la actividad:")
            f_ev = st.date_input("Fecha:", min_value=datetime.date.today())
            if st.form_submit_button("📢 Publicar Evento"):
                if t_ev and d_ev:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO eventos (titulo, descripcion, sector, fecha_evento, creador)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (t_ev, d_ev, nuevo_sector, str(f_ev), u_actual))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("¡Evento publicado en la cartelera del sector!")
                    st.rerun()

    # --- TAB 5: PERFIL ---
    with tabs[4]:
        st.subheader("⚙️ Configuración de Personaje")
        with st.form("form_perfil"):
            nuevo_vestuario = st.selectbox(
                "Cambiar Atuendo:", OPCIONES_VESTUARIO,
                index=OPCIONES_VESTUARIO.index(user_data["vestuario"]) if user_data["vestuario"] in OPCIONES_VESTUARIO else 0
            )
            nueva_personalidad = st.selectbox(
                "Cambiar Personalidad:", OPCIONES_PERSONALIDAD,
                index=OPCIONES_PERSONALIDAD.index(user_data["personalidad"]) if user_data["personalidad"] in OPCIONES_PERSONALIDAD else 0
            )
            if st.form_submit_button("💾 Guardar Cambios"):
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("UPDATE usuarios SET vestuario = %s, personalidad = %s WHERE username = %s",
                            (nuevo_vestuario, nueva_personalidad, u_actual))
                conn.commit()
                cur.close()
                conn.close()
                st.success("¡Perfil actualizado!")
                st.rerun()

    # --- TAB 6: ADMIN ---
    if user_data["es_admin"]:
        with tabs[5]:
            st.subheader("🛡️ Control Maestro del Servidor")
            conn = get_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT username, fecha_creacion, comprado, saldo, zona, sector FROM usuarios")
            todos_usuarios = cur.fetchall()
            cur.close()
            conn.close()

            st.markdown("### 👥 Lista de Ciudadanos Registrados")
            st.dataframe([dict(u) for u in todos_usuarios], use_container_width=True)

            st.markdown("---")
            st.markdown("### ⚙️ Modificar Estado de Usuario")
            user_target = st.selectbox(
                "Seleccionar usuario:",
                [u["username"] for u in todos_usuarios if u["username"] != "admin"]
            )
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                if st.button("⭐ Desbloquear / Comprar Cuenta Definitiva"):
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET comprado = 1 WHERE username = %s", (user_target,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"Usuario {user_target} actualizado a Premium.")
                    st.rerun()
            with col_a2:
                if st.button("💸 Otorgar 500 TuyCoins de Bono"):
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET saldo = saldo + 500 WHERE username = %s", (user_target,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"Se abonaron 500 TuyCoins a {user_target}.")
                    st.rerun()
            
            st.markdown("---")
            st.markdown("### 🔑 Restablecer Contraseña de Usuario")
            nueva_pass = st.text_input("Nueva contraseña para el usuario:", type="password", key="admin_new_pass")
            if st.button("🔄 Cambiar Contraseña"):
                if nueva_pass:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET password_hash = %s WHERE username = %s", 
                                (hash_password(nueva_pass), user_target))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"Contraseña de {user_target} actualizada correctamente.")
                else:
                    st.warning("Escribe una nueva contraseña.")


# ==========================================
# 7. FLUJO PRINCIPAL
# ==========================================
init_db()

if "usuario_logueado" not in st.session_state:
    modulo_autenticacion()
else:
    juego_principal()
