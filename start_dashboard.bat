@echo off
echo 🚀 Iniciando Dashboard con Worker...
echo.
echo 📊 El dashboard estará disponible en: http://127.0.0.1:8000
echo 🔄 El worker se ejecutará en segundo plano
echo.
python controllers\worker.py
pause
