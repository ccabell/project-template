@echo off
echo.
echo ================================
echo   A360 PROJECT HUB DEPLOYMENT
echo ================================
echo.

echo [1/4] Syncing app.py to web_app.py (deployment file)...
copy app.py web_app.py > nul
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy app.py to web_app.py
    pause
    exit /b 1
)
echo ✅ Files synced successfully

echo.
echo [2/4] Adding changes to git...
git add web_app.py
if %errorlevel% neq 0 (
    echo ERROR: Failed to add files to git
    pause
    exit /b 1
)
echo ✅ Changes staged

echo.
echo [3/4] Committing changes...
git commit -m "Deploy A360 Project Hub - %date% %time%"
if %errorlevel% neq 0 (
    echo WARNING: No changes to commit (files already up to date)
    echo This is normal if you haven't made changes since last deploy.
) else (
    echo ✅ Changes committed
)

echo.
echo [4/4] Pushing to Streamlit Cloud...
git push origin b360-main
if %errorlevel% neq 0 (
    echo ERROR: Failed to push to repository
    pause
    exit /b 1
)
echo ✅ Pushed to deployment branch

echo.
echo ================================
echo        DEPLOYMENT COMPLETE!
echo ================================
echo.
echo Your app will be updated at:
echo https://ib8imbfngdgvpaj6xgnqup.streamlit.app/
echo.
echo Please wait 30-60 seconds for Streamlit Cloud to rebuild...
echo.
pause