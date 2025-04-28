#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Herramienta de diagnóstico para perfiles de estudiantes
-------------------------------------------------------
Este script ejecuta una serie de verificaciones para diagnosticar
por qué el sistema podría estar usando valores predeterminados 
en lugar de datos reales del perfil del estudiante.
"""

import logging
import streamlit as st
import json
import traceback

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar dependencias necesarias
from core.firebase_client import get_user_data, initialize_firebase, ensure_profile_fields
from core.session_manager import get_user_info, get_session_var
from features.correccion import get_student_profile

def diagnosticar_perfil_estudiante():
    """
    Ejecuta diagnósticos para verificar por qué el sistema podría estar
    usando valores predeterminados en lugar de datos reales del perfil.
    """
    st.title("🔍 Diagnóstico de Perfil de Estudiante")
    
    # Paso 1: Verificar el usuario actual
    st.subheader("1. Verificación del usuario actual")
    user_info = get_user_info()
    
    if user_info:
        user_id = user_info.get("uid")
        email = user_info.get("email")
        st.success(f"✅ Usuario en sesión: {email} (UID: {user_id})")
    else:
        st.error("❌ No hay usuario en sesión")
        st.warning("Por favor, inicia sesión para continuar")
        return
    
    # Paso 2: Verificar inicialización de Firebase
    st.subheader("2. Verificación de conexión con Firebase")
    db, success = initialize_firebase()
    
    if success and db:
        st.success("✅ Firebase inicializado correctamente")
        
        # Verificar estado en session_state
        if st.session_state.get("firebase_status"):
            st.success("✅ Estado de Firebase en session_state: OK")
        else:
            st.error("❌ Estado de Firebase en session_state: Error")
    else:
        st.error("❌ Error inicializando Firebase")
        st.info("Revisa las credenciales de Firebase y los logs de la aplicación")
        return
    
    # Paso 3: Verificar thread_id en session_state
    st.subheader("3. Verificación de thread_id")
    thread_id = get_session_var("thread_id")
    
    if thread_id:
        st.success(f"✅ Thread ID en sesión: {thread_id}")
    else:
        st.warning("⚠️ No hay thread_id en la sesión actual")
        st.info("El thread_id se generará automáticamente en la primera corrección")
    
    # Paso 4: Obtener datos directos de Firebase
    st.subheader("4. Datos directos de Firebase")
    
    try:
        user_data_raw = get_user_data(user_id)
        
        if user_data_raw:
            st.success("✅ Datos obtenidos de Firebase")
            
            # Mostrar información relevante
            with st.expander("Ver datos raw de Firebase"):
                # Filtrar datos sensibles antes de mostrar
                filtered_data = {k: v for k, v in user_data_raw.items() 
                               if k not in ['private_key', 'token', 'key', 'password']}
                st.json(filtered_data)
            
            # Verificar campos clave
            nivel_firebase = user_data_raw.get("nivel")
            correcciones_firebase = user_data_raw.get("numero_correcciones")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if nivel_firebase:
                    st.success(f"✅ Nivel en Firebase: {nivel_firebase}")
                else:
                    st.error("❌ No se encontró campo 'nivel' en Firebase")
            
            with col2:
                if correcciones_firebase is not None:
                    st.success(f"✅ Correcciones en Firebase: {correcciones_firebase}")
                else:
                    st.error("❌ No se encontró campo 'numero_correcciones' en Firebase")
        else:
            st.error("❌ No se encontraron datos en Firebase para este usuario")
            st.info("Esto puede deberse a problemas de permisos o a que el usuario no existe en Firestore")
    except Exception as e:
        st.error(f"❌ Error obteniendo datos de Firebase: {str(e)}")
        st.code(traceback.format_exc())
    
    # Paso 5: Verificar función get_student_profile
    st.subheader("5. Verificación de get_student_profile")
    
    try:
        perfil = get_student_profile(user_id)
        
        if perfil:
            st.success("✅ Perfil obtenido correctamente")
            
            # Mostrar perfil completo
            with st.expander("Ver perfil completo"):
                st.json(perfil)
            
            # Verificar campos clave
            nivel_perfil = perfil.get("nivel_mcer")
            correcciones_perfil = perfil.get("numero_correcciones")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if nivel_perfil:
                    if nivel_perfil == "B1" and nivel_firebase and nivel_firebase != "B1":
                        st.error(f"❌ Nivel en perfil: {nivel_perfil} (Valor por defecto)")
                        st.info(f"No coincide con el valor en Firebase: {nivel_firebase}")
                    else:
                        st.success(f"✅ Nivel en perfil: {nivel_perfil}")
                else:
                    st.error("❌ No se encontró campo 'nivel_mcer' en el perfil")
            
            with col2:
                if correcciones_perfil is not None:
                    if correcciones_perfil == 0 and correcciones_firebase and correcciones_firebase != 0:
                        st.error(f"❌ Correcciones en perfil: {correcciones_perfil} (Valor por defecto)")
                        st.info(f"No coincide con el valor en Firebase: {correcciones_firebase}")
                    else:
                        st.success(f"✅ Correcciones en perfil: {correcciones_perfil}")
                else:
                    st.error("❌ No se encontró campo 'numero_correcciones' en el perfil")
        else:
            st.error("❌ No se pudo obtener el perfil del estudiante")
    except Exception as e:
        st.error(f"❌ Error obteniendo perfil del estudiante: {str(e)}")
        st.code(traceback.format_exc())
    
    # Paso 6: Verificar y reparar campos del perfil
    st.subheader("6. Verificación y reparación de campos")
    
    if st.button("Verificar y reparar campos del perfil"):
        try:
            actualizado = ensure_profile_fields(user_id)
            
            if actualizado:
                st.success("✅ Se han actualizado campos faltantes en el perfil")
                st.info("Recarga esta página para ver los cambios")
            else:
                st.success("✅ El perfil ya tiene todos los campos necesarios")
        except Exception as e:
            st.error(f"❌ Error al verificar/reparar campos: {str(e)}")
            st.code(traceback.format_exc())
    
    # Paso 7: Conclusiones y soluciones
    st.subheader("7. Conclusiones y soluciones")
    
    # Verificar si hay problemas en el mapeado de campos
    if (nivel_firebase and nivel_perfil == "B1" and nivel_firebase != "B1") or \
       (correcciones_firebase is not None and correcciones_perfil == 0 and correcciones_firebase != 0):
        st.warning("⚠️ Se detectó un problema de mapeo entre los datos de Firebase y el perfil")
        st.info("""
        **Problema detectado**: La función `get_student_profile` está usando valores predeterminados 
        a pesar de que existen valores reales en Firebase.
        
        **Posibles causas**:
        1. Inconsistencia en los nombres de campos "nivel" vs "nivel_mcer"
        2. El valor en Firebase podría no estar en el formato esperado
        3. Posible problema en la función `get_user_data` de Firebase
        
        **Solución recomendada**:
        - Revisar `features/correccion.py` para asegurar que el mapeo de campos sea correcto
        - Revisar `firebase_client.py` para garantizar que devuelva siempre los campos correctos
        """)
    else:
        st.success("✅ No se detectaron problemas de mapeo entre datos de Firebase y perfil")
    
    # Agregar botón para actualizar manualmente el perfil
    st.subheader("8. Actualizar perfil manualmente")
    
    with st.form("actualizar_perfil"):
        st.write("Actualiza manualmente los valores del perfil (solo para diagnóstico)")
        
        nivel_input = st.selectbox(
            "Nivel MCER",
            ["A1", "A2", "B1", "B2", "C1", "C2"],
            index=["A1", "A2", "B1", "B2", "C1", "C2"].index(nivel_perfil if nivel_perfil in ["A1", "A2", "B1", "B2", "C1", "C2"] else "B1")
        )
        
        idioma_input = st.text_input(
            "Idioma nativo",
            value=perfil.get("idioma_nativo", "") if perfil else ""
        )
        
        num_correcciones = st.number_input(
            "Número de correcciones",
            min_value=0,
            value=perfil.get("numero_correcciones", 0) if perfil else 0
        )
        
        submitted = st.form_submit_button("Actualizar perfil")
        
        if submitted:
            try:
                from core.firebase_client import update_user_profile
                
                # Preparar datos actualizados
                profile_data = {
                    "nivel": nivel_input,
                    "idioma_nativo": idioma_input,
                    "numero_correcciones": int(num_correcciones)
                }
                
                # Actualizar perfil
                success = update_user_profile(user_id, profile_data)
                
                if success:
                    st.success("✅ Perfil actualizado correctamente")
                    st.info("Recarga esta página para ver los cambios")
                else:
                    st.error("❌ Error actualizando el perfil")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.code(traceback.format_exc())

if __name__ == "__main__":
    diagnosticar_perfil_estudiante()
