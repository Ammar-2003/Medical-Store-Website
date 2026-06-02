@echo off
cd /d "C:\Users\ansju\Desktop\Hanan_Medical_Store_System"

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Start Django development server
start cmd /k "python manage.py runserver"

:: Wait a few seconds to give server time to start (optional but useful)
timeout /t 5 >nul

:: Open Google and your local Django site in default browser
start https://www.google.com
start http://127.0.0.1:8000

pause
