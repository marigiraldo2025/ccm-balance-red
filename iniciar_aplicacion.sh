#!/bin/sh
cd "$(dirname "$0")"
echo "Preparando la aplicacion de CCM (la primera vez puede tardar unos minutos)..."
python3 -m pip install -q -r requirements.txt
python3 -m streamlit run app.py
