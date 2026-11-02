@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   REAL-TIME MICROservice ANOMALY DETECTION - TEST PIPELINE
echo ============================================================
echo.
echo This will collect metrics and make predictions until Ctrl+C.
echo Output: test_dataset.csv
echo.

if not exist "..\isolation_forest_model.pkl" (
    echo ERROR: Trained model not found:
    echo   ..\isolation_forest_model.pkl
    echo Keep isolation_forest_model.pkl in the parent metric-collector folder.
    pause
    exit /b 1
)

python -c "import requests,pandas,joblib,sklearn" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Required Python packages are missing.
    echo Run: python -m pip install requests pandas joblib scikit-learn
    pause
    exit /b 1
)

python test_metric_collector.py
set EXITCODE=%ERRORLEVEL%

echo.
if not "%EXITCODE%"=="0" (
    echo Pipeline exited with error code %EXITCODE%.
) else (
    echo Pipeline stopped.
)
pause
exit /b %EXITCODE%
