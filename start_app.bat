@echo off
echo Starting A360 Project Hub...
echo.
echo Your app will open at: http://localhost:8503
echo.
echo Press Ctrl+C to stop the server
echo.
python -m streamlit run simple_app.py --server.port 8503
pause