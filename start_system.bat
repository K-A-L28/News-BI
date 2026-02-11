@echo off
echo Iniciando Sistema de Boletines...
echo.

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Iniciar el sistema principal
python main.py

pause
