#!/bin/bash

# Script para crear la estructura de archivos y carpetas para Textocorrector ELE
echo "Creando estructura de archivos y carpetas para Textocorrector ELE..."

# Crear directorios principales
mkdir -p assets
mkdir -p config
mkdir -p core
mkdir -p features/herramientas
mkdir -p utils
mkdir -p ui/views
mkdir -p .streamlit

# Crear archivos vacíos
# Archivo principal
touch app.py

# Archivos de configuración
touch config/__init__.py
touch config/settings.py
touch config/prompts.py

# Archivos del core
touch core/__init__.py
touch core/assistant_client.py
touch core/openai_client.py
touch core/firebase_client.py
touch core/circuit_breaker.py
touch core/session_manager.py

# Archivos de features
touch features/__init__.py
touch features/correccion.py
touch features/ejercicios.py
touch features/simulacro.py
touch features/perfil.py
touch features/exportacion.py
touch features/plan_estudio.py

# Archivos de herramientas
touch features/herramientas/__init__.py
touch features/herramientas/transcripcion.py
touch features/herramientas/consignas.py
touch features/herramientas/imagenes.py

# Archivos de utilidades
touch utils/__init__.py
touch utils/analytics.py
touch utils/text_processing.py
touch utils/visualization.py
touch utils/file_utils.py

# Archivos de UI
touch ui/__init__.py
touch ui/main_layout.py
touch ui/login.py
touch ui/sidebar.py

# Archivos de vistas
touch ui/views/__init__.py
touch ui/views/correccion_view.py
touch ui/views/ejercicios_view.py
touch ui/views/simulacro_view.py
touch ui/views/herramientas_view.py
touch ui/views/perfil_view.py
touch ui/views/plan_view.py
touch ui/views/about_view.py

# Crear requirements.txt
cat > requirements.txt << 'EOL'
streamlit>=1.27.0
openai>=1.0.0
firebase-admin>=6.2.0
pandas>=2.0.0
plotly>=5.17.0
python-docx>=0.8.11
pillow>=10.0.0
matplotlib>=3.7.0
pdfkit>=1.0.0
EOL

# Crear archivo .streamlit/secrets.toml con plantilla
mkdir -p .streamlit
cat > .streamlit/secrets.toml << 'EOL'
# Configuración de OpenAI
[openai]
api_key = "tu_clave_api_aqui"

# Configuración de Firebase
[firebase]
project_id = "tu_project_id_aqui"
private_key = "tu_private_key_aqui"
client_email = "tu_email_aqui"
EOL

# Crear .env con plantilla
cat > .env << 'EOL'
# API Keys y configuraciones
OPENAI_API_KEY=tu_clave_api_aqui
FIREBASE_PROJECT_ID=tu_project_id_aqui
FIREBASE_PRIVATE_KEY=tu_private_key_aqui
FIREBASE_CLIENT_EMAIL=tu_email_aqui
EOL

# Crear .gitignore
cat > .gitignore << 'EOL'
# Archivos sensibles
.env
.streamlit/secrets.toml

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# Archivos del sistema
.DS_Store
Thumbs.db

# Entornos virtuales
venv/
ENV/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo
EOL

# Crear placeholder para archivo de logo
touch assets/Spanish_FactorIA_Logo.png

echo "¡Estructura de directorios y archivos creada con éxito!"
echo "Ahora puedes llenar cada archivo con su contenido correspondiente."