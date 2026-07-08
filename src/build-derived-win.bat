:: ABOUT
:: Windows batch file to generate translation, ui and help files derived
:: on sources in the Artisan repository.
::
:: LICENSE
:: This program or module is free software: you can redistribute it and/or
:: modify it under the terms of the GNU General Public License as published
:: by the Free Software Foundation, either version 2 of the License, or
:: version 3 of the License, or (at your option) any later versison. It is
:: provided for educational purposes and is distributed in the hope that
:: it will be useful, but WITHOUT ANY WARRANTY; without even the implied
:: warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
:: the GNU General Public License for more details.
::
:: AUTHOR
:: Dave Baxter, Marko Luther 2023

:: on entry to this script the current path must be the src folder
::
:: script commandline option LEGACY used to flag a legacy build
::

@echo off
:: test for existence of required environment variables
setlocal enabledelayedexpansion
if not defined PYTHON_PATH (
    if defined PYTHONPATH (
        set PYTHON_PATH=%PYTHONPATH%
        echo PYTHON_PATH not set, defaulting to %PYTHONPATH%
    ) else (
        echo PYTHON_PATH not set, set it manually.  Exiting...
        exit /b 1
    )
)
if not defined PYUIC (
    echo PYUIC not set, defaulting to pyuic6.exe
    set PYUIC=pyuic6.exe
)
if not defined PYQT (
    echo PYQT not set, defaulting to 6
    set PYQT=6
)

::
:: Generate translation, ui, and help files derived from repository sources
::

:: convert help files from .xlsx to .py
echo ************* help files **************
python ..\doc\help_dialogs\Script\xlsx_to_artisan_help.py all
if ERRORLEVEL 1 (echo ** Failed in xlsx_to_artisan_help.py & exit /b 1) else (echo ** Success)

:: convert .ui files to .py files
echo ************* ui/uic **************
for /r %%a IN (ui\*.ui) DO (
    echo %%~na
    %PYUIC% -o uic\%%~na.py ui\%%~na.ui
    if ERRORLEVEL 1 (echo ** Failed in pyuic & exit /b 1)
)
echo ** Success

:: Process translation files
echo ************* pylupdate **************
echo *** Processing translation files with pylupdate6pro.py
python pylupdate6pro.py
if ERRORLEVEL 1 (echo ** Failed in pylupdate6pro.py & exit /b 1) else (echo ** Success)

echo ************* lrelease **************
cd translations
:: Resolve lrelease.exe. The legacy ..\..\QtLinguist path is an AppVeyor-era
:: layout that does not exist on the GitHub runner. Prefer the qt6-applications
:: wheel (same source the macOS/Linux build uses), then the aqt Qt install
:: (%QT_PATH%\bin), then the legacy path.
set "LRELEASE_EXE="
for /f "usebackq delims=" %%q in (`python -c "import os,qt6_applications;p=os.path.join(os.path.dirname(qt6_applications.__file__),'Qt','bin','lrelease.exe');print(p if os.path.exists(p) else '')" 2^>nul`) do set "LRELEASE_EXE=%%q"
if not defined LRELEASE_EXE if exist "%QT_PATH%\bin\lrelease.exe" set "LRELEASE_EXE=%QT_PATH%\bin\lrelease.exe"
if not defined LRELEASE_EXE if exist "..\..\QtLinguist\lrelease.exe" set "LRELEASE_EXE=..\..\QtLinguist\lrelease.exe"
if not defined LRELEASE_EXE (echo ** Failed: lrelease.exe not found & exit /b 1)
echo *** using lrelease: %LRELEASE_EXE%
"%LRELEASE_EXE%" -version
for /r %%a IN (*.ts) DO (
    "%LRELEASE_EXE%" %%~a
    if ERRORLEVEL 1 (echo ** Failed in "%LRELEASE_EXE%" %%~a & exit /b 1)
)
echo ** Success
cd ..

:: Zip the generated files
7z a ..\generated-win.zip ..\doc\help_dialogs\Output_html\ help\ translations\ uic\
if ERRORLEVEL 1 (echo ** Failed in 7z & exit /b 1) else (echo ** Success)
::
::  End of generating derived files
::
