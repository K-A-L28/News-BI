@echo off
echo Iniciando Servidor API...
echo.

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Iniciar el servidor API
python -m controllers.api_server

pause
