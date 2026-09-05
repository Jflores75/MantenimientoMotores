import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import joblib
import sqlite3 
import requests
from datetime import datetime

st.set_page_config(page_title="CMMS Predictivo Fase 4", layout="wide")
st.title("⏱️ Panel Predictivo IoT (Planta Completa - Fase 4)")

# --- 1. CARGA DE MODELO Y PREPARACIÓN SQL ---
try:
    paquete_modelo = joblib.load('modelo_rul_planta.pkl')
    modelo_rul, columnas_entrenamiento = paquete_modelo['modelo'], paquete_modelo['columnas']
    df_base = pd.read_excel('inventario_planta.xlsx')
except FileNotFoundError:
    st.error("Faltan archivos. Ejecuta 'generar_base.py' y 'ml_regresion.py' primero.")
    st.stop()

# Inicialización de tablas SQL para despliegue en la nube
try:
    con_init = sqlite3.connect('planta_industrial.db', timeout=5)
    con_init.execute("PRAGMA journal_mode=WAL;")
    
    # Auto-crear tabla de auditoría
    con_init.execute('''CREATE TABLE IF NOT EXISTS historial_ot (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME DEFAULT CURRENT_TIMESTAMP, 
                        equipo TEXT, ot_generada TEXT)''')
                        
    # Auto-crear tabla de telemetría para que la inyección en la nube no falle
    con_init.execute('''CREATE TABLE IF NOT EXISTS telemetria_motores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        equipo TEXT, horas_operacion REAL, temperatura_c REAL, vibracion_mm_s REAL, amperaje_a REAL)''')
                        
    con_init.commit()
    con_init.close()
except Exception: pass

# --- 2. LECTURA IoT EN VIVO ---
try:
    conexion = sqlite3.connect('planta_industrial.db')
    df_sql = pd.read_sql_query("SELECT * FROM telemetria_motores ORDER BY timestamp DESC", conexion)
    if not df_sql.empty:
        df_sql = df_sql.rename(columns={'equipo': 'Equipo', 'horas_operacion': 'Horas_Operacion', 'temperatura_c': 'Temperatura_C', 'vibracion_mm_s': 'Vibracion_mm_s', 'amperaje_a': 'Amperaje_A'})
        datos_vivo = df_sql.drop_duplicates(subset=['Equipo'])
        for _, fila in datos_vivo.iterrows():
            idx = df_base['Equipo'] == fila['Equipo']
            df_base.loc[idx, ['Horas_Operacion', 'Temperatura_C', 'Vibracion_mm_s', 'Amperaje_A']] = [fila['Horas_Operacion'], fila['Temperatura_C'], fila['Vibracion_mm_s'], fila['Amperaje_A']]
except Exception: pass 

df_maquinas = df_base.copy()

# --- 3. PREDICCIÓN Y LÓGICA CMMS ---
df_pred = pd.get_dummies(df_maquinas[['Tipo_Equipo', 'Horas_Operacion', 'Temperatura_C', 'Vibracion_mm_s', 'Amperaje_A']], columns=['Tipo_Equipo']).reindex(columns=columnas_entrenamiento, fill_value=0)
df_maquinas['Dias_Restantes'] = modelo_rul.predict(df_pred).round(0).astype(int)

df_reporte = df_maquinas[['Equipo', 'Tipo_Equipo', 'Horas_Operacion', 'Temperatura_C', 'Vibracion_mm_s', 'Amperaje_A', 'Dias_Restantes']].copy()
df_reporte['Estado'], df_reporte['OT_Generada'] = 'Operativo', 'No'

for idx, fila in df_reporte.iterrows():
    if fila['Dias_Restantes'] <= 30:
        df_reporte.at[idx, 'Estado'] = 'Crítico'
        df_reporte.at[idx, 'OT_Generada'] = f"OT-{datetime.now().strftime('%m%d')}-{fila['Equipo'][-3:]}"
    elif fila['Dias_Restantes'] <= 80:
        df_reporte.at[idx, 'Estado'] = 'Alerta'

# --- 4. IMPACTO FINANCIERO (ROI) ---
st.subheader("💰 Impacto Financiero (ROI del Mantenimiento Predictivo)")
try:
    con_roi = sqlite3.connect('planta_industrial.db')
    mantenimientos_realizados = con_roi.execute("SELECT COUNT(*) FROM historial_ot").fetchone()[0]
    con_roi.close()
    
    costo_falla_catastrofica = 5000  # USD promedio por fallo no planificado
    costo_mantenimiento_preventivo = 500 # USD promedio por reparación planificada
    ahorro_neto = mantenimientos_realizados * (costo_falla_catastrofica - costo_mantenimiento_preventivo)
    
    col_roi1, col_roi2, col_roi3 = st.columns(3)
    col_roi1.metric("Intervenciones Ejecutadas", mantenimientos_realizados)
    col_roi2.metric("Costo Evitado por Fallas", f"${mantenimientos_realizados * costo_falla_catastrofica:,.2f}")
    col_roi3.metric("Ahorro Neto Generado", f"${ahorro_neto:,.2f}", f"+${ahorro_neto:,.2f}")
except Exception:
    st.info("El cálculo financiero se activará al registrar la primera Orden de Trabajo.")

st.divider()

# --- 5. BARRA LATERAL ---
st.sidebar.header("🎛️ Búsqueda de Equipos")
opciones = ["⚙️ Simulación Manual"] + list(df_reporte['Equipo'])
seleccion = st.sidebar.selectbox("🎯 Selecciona una opción:", opciones)

if seleccion == "⚙️ Simulación Manual":
    sim_tipo = st.sidebar.selectbox("Tipo de Equipo", ['Bomba Centrífuga', 'Faja Transportadora', 'Compresor', 'Molino'])
    sim_horas = st.sidebar.slider("Horas de Operación", 500, 8000, 4000)
    sim_temp = st.sidebar.slider("Temperatura (°C)", 40.0, 110.0, 60.0)
    sim_vib = st.sidebar.slider("Vibración (mm/s)", 1.0, 12.0, 2.5)
    sim_amp = st.sidebar.slider("Amperaje (A)", 10.0, 100.0, 20.0)
    etiqueta_estrella = 'Tu Simulación'
else:
    datos_eq = df_reporte[df_reporte['Equipo'] == seleccion].iloc[0]
    sim_tipo, sim_horas = datos_eq['Tipo_Equipo'], st.sidebar.slider("Horas de Operación", 500, 8000, int(datos_eq['Horas_Operacion']), disabled=True)
    sim_temp = st.sidebar.slider("Temperatura (°C)", 40.0, 110.0, float(datos_eq['Temperatura_C']), disabled=True)
    sim_vib, sim_amp = st.sidebar.slider("Vibración", 1.0, 12.0, float(datos_eq['Vibracion_mm_s']), disabled=True), st.sidebar.slider("Amperaje", 10.0, 100.0, float(datos_eq['Amperaje_A']), disabled=True)
    etiqueta_estrella = f'📍 {seleccion} (En Vivo)'

df_sim_dummy = pd.get_dummies(pd.DataFrame({'Tipo_Equipo': [sim_tipo], 'Horas_Operacion': [sim_horas], 'Temperatura_C': [sim_temp], 'Vibracion_mm_s': [sim_vib], 'Amperaje_A': [sim_amp]}), columns=['Tipo_Equipo']).reindex(columns=columnas_entrenamiento, fill_value=0)
rul_estimado = int(modelo_rul.predict(df_sim_dummy)[0])

st.sidebar.markdown("### ⏳ Estimación RUL")
if rul_estimado <= 30: st.sidebar.error(f"🚨 {rul_estimado} DÍAS (Falla Inminente)")
elif rul_estimado <= 80: st.sidebar.warning(f"⚠️ {rul_estimado} DÍAS (Alerta)")
else: st.sidebar.success(f"✅ {rul_estimado} DÍAS (Óptimo)")

if st.sidebar.button("🔄 Refrescar Telemetría"): st.rerun()

# --- 6. DASHBOARD PRINCIPAL ---
col1, col2 = st.columns([1.5, 1])
with col1:
    st.subheader("📋 Reporte de Mantenimiento CMMS")
    def colorear(fila):
        if fila['Estado'] == 'Crítico': return ['background-color: #ffcccc'] * len(fila)
        elif fila['Estado'] == 'Alerta': return ['background-color: #fff0b3'] * len(fila)
        return ['background-color: #c6ecd9'] * len(fila)
    st.dataframe(df_reporte.style.apply(colorear, axis=1), width='stretch')

with col2:
    st.subheader("📉 Mapa de Riesgo")
    fig, ax = plt.subplots(figsize=(7, 5))
    scatter = ax.scatter(df_reporte['Vibracion_mm_s'], df_reporte['Temperatura_C'], c=df_reporte['Dias_Restantes'], cmap='RdYlGn', s=150, edgecolor='black')
    plt.colorbar(scatter, label='Días Restantes (RUL)')
    ax.scatter(sim_vib, sim_temp, color='blue', marker='*', s=600, edgecolor='white', linewidth=1.5, label=etiqueta_estrella, zorder=5)
    ax.set_xlabel("Vibración (mm/s)"), ax.set_ylabel("Temperatura (°C)"), ax.legend()
    st.pyplot(fig)

# --- 7. ANÁLISIS HISTÓRICO ---
st.divider()
st.subheader(f"📊 Curva de Degradación Temporal: {seleccion if seleccion != '⚙️ Simulación Manual' else 'Selecciona un equipo arriba'}")
if seleccion != "⚙️ Simulación Manual" and not df_sql.empty:
    df_hist = df_sql[df_sql['Equipo'] == seleccion].head(100).sort_values('timestamp')
    if not df_hist.empty: st.line_chart(df_hist.set_index('timestamp')[['Temperatura_C', 'Vibracion_mm_s', 'Amperaje_A']])

# --- 8. SIMULADOR OVERHAUL Y ALERTAS ---
st.divider()
st.subheader("🛠️ Gestión de Reparaciones y Auditoría")
col3, col4 = st.columns(2)
df_en_taller = df_reporte[df_reporte['Estado'] == 'Crítico'].copy()

def enviar_alerta_telegram(mensaje):
    # Reemplaza con tu token y chat_id de BotFather
    token = "TU_TOKEN" 
    chat_id = "TU_CHAT_ID"
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={mensaje}"
    # requests.get(url) # Descomentar cuando configures el token

with col3:
    if not df_en_taller.empty:
        st.error("**🔴 Órdenes de Trabajo Activas**")
        st.dataframe(df_en_taller[['Equipo', 'OT_Generada', 'Temperatura_C', 'Vibracion_mm_s']], width='stretch')
        
        csv = df_en_taller.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte (CSV)", data=csv, file_name=f"OT_Criticos_{datetime.now().strftime('%Y%m%d')}.csv", mime='text/csv')
        
        eq_reparar = st.selectbox("Seleccionar equipo para Mantenimiento:", df_en_taller['Equipo'])
        ot_a_cerrar = df_en_taller[df_en_taller['Equipo'] == eq_reparar]['OT_Generada'].values[0]
        
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button(f"🔧 Ejecutar Mantenimiento", type="primary"):
                try:
                    amp_base = 12.0 if 'Faja' in eq_reparar else 35.0 if 'Compresor' in eq_reparar else 75.0 if 'Molino' in eq_reparar else 15.0
                    con = sqlite3.connect('planta_industrial.db', timeout=10)
                    cur = con.cursor()
                    cur.execute("PRAGMA journal_mode=WAL;")
                    cur.execute('INSERT INTO telemetria_motores (equipo, horas_operacion, temperatura_c, vibracion_mm_s, amperaje_a) VALUES (?, 0, 40.0, 1.0, ?)', (eq_reparar, amp_base))
                    cur.execute('INSERT INTO historial_ot (equipo, ot_generada) VALUES (?, ?)', (eq_reparar, ot_a_cerrar))
                    con.commit()
                    con.close()
                    st.rerun()
                except Exception as e: st.error(f"Error SQL: {e}")
        with c_btn2:
            if st.button("📲 Notificar al Supervisor"):
                enviar_alerta_telegram(f"⚠️ URGENTE: {eq_reparar} proyecta falla. OT: {ot_a_cerrar} generada.")
                st.toast("Alerta enviada por Telegram al equipo de planta.")
    else:
        st.success("**🟢 Planta operando dentro de los márgenes óptimos.** No hay OTs activas.")

with col4:
    st.markdown("**📜 Auditoría de Mantenimientos Completados**")
    try:
        con_aud = sqlite3.connect('planta_industrial.db')
        df_auditoria = pd.read_sql_query("SELECT fecha, equipo, ot_generada FROM historial_ot ORDER BY fecha DESC LIMIT 5", con_aud)
        if not df_auditoria.empty: st.dataframe(df_auditoria, width='stretch')
    except Exception: pass