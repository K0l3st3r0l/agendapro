#!/bin/bash
# ============================================================
# AgendaPro - Script de despliegue en producción
# ============================================================
set -e

echo "📅 Desplegando AgendaPro..."

# Verificar que existe .env
if [ ! -f .env ]; then
  echo "❌ Error: Falta el archivo .env"
  echo "   Copia .env.example a .env y rellena los valores."
  exit 1
fi

# Build y arranque
echo "📦 Construyendo imágenes..."
docker compose build

echo "🚀 Arrancando servicios..."
docker compose up -d

# Esperar a que la BD esté lista
echo "⏳ Esperando a la base de datos..."
sleep 10

# Ejecutar migraciones desde el contenedor db
echo "🗄️  Ejecutando migraciones..."
for f in $(ls -1 backend/migrations/*.sql | sort); do
    echo "  → $(basename $f)"
    docker compose exec -T db psql -U agendapro -d agendapro -f - < "$f" || true
done

echo ""
echo "✅ AgendaPro desplegado correctamente!"
echo "   Frontend: http://localhost (nginx)"
echo "   Backend:  http://localhost:8000"
echo ""
echo "⚠️  Recuerda configurar Nginx Proxy Manager para:"
echo "   agendapro.tudominio.com -> localhost"

# --- Auto-commit y push del repo agendapro ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

echo ""
echo "📤 Guardando cambios en git..."
if git -C "$SCRIPT_DIR" diff --quiet && git -C "$SCRIPT_DIR" diff --staged --quiet; then
    echo "⚠️  No hay cambios para commitear en agendapro."
else
    git -C "$SCRIPT_DIR" add -A
    git -C "$SCRIPT_DIR" commit -m "deploy: auto-commit ${TIMESTAMP}" || true
    if git -C "$SCRIPT_DIR" push origin main 2>&1; then
        echo "✓ Cambios pusheados a origin/main"
    else
        echo "⚠️  Push falló. Cambios commiteados localmente."
    fi
fi

# --- Auto-push de la wiki ---
echo ""
echo "📚 Verificando cambios en la wiki..."
bash /root/apps/wiki/wiki-push.sh "deploy: agendapro ${TIMESTAMP}"
