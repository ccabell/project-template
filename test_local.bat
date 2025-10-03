@echo off
echo Testing A360 Project Hub locally...
echo.
echo Open your browser to: http://localhost:8504
echo.
echo Press Ctrl+C to stop
echo.
python -m streamlit run web_app.py --server.port 8504
pause