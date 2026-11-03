@echo off
cd /d "%~dp0"
echo Preparando la aplicacion de CCM (la primera vez puede tardar unos minutos)...
python -m pip install -q -r requirements.txt
python -m streamlit run app.py
pause
