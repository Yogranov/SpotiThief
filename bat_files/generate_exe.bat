cd ..
del SpotiThief.exe
venv\Scripts\pyinstaller.exe --onefile --paths=venv\Lib\site-packages exe_export.py
rename dist\exe_export.exe SpotiThief.exe
move dist\SpotiThief.exe .
rmdir /s /q build
rmdir /s /q dist
del exe_export.spec
