@echo off
setlocal

cd /d "%~dp0"
set "BUILD_ENV=%CD%\.venv-build-windows"

py -3 -m venv "%BUILD_ENV%"
if errorlevel 1 exit /b %errorlevel%

"%BUILD_ENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%

"%BUILD_ENV%\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b %errorlevel%

"%BUILD_ENV%\Scripts\python.exe" -m unittest -v
if errorlevel 1 exit /b %errorlevel%

"%BUILD_ENV%\Scripts\python.exe" -m PyInstaller --clean --noconfirm Ani-Watch.spec
if errorlevel 1 exit /b %errorlevel%

echo Executavel criado em: %CD%\dist\Ani-Watch.exe
endlocal
