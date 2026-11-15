@echo off
REM ===== Đóng gói Ứng dụng Kế toán cho Windows (chạy trong thư mục ung-dung-ke-toan) =====
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."

where python >nul 2>nul || (echo [LOI] Chua cai Python 3.11+ ^(https://www.python.org/downloads/^) & exit /b 1)

if not exist .venv (
    echo [1/5] Tao moi truong ao .venv ...
    python -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat

echo [2/5] Cai thu vien ...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller pytest || exit /b 1

echo [3/5] Chay kiem thu tu dong ...
set QT_QPA_PLATFORM=offscreen
python -m pytest -q tests || (echo [LOI] Kiem thu that bai - dung dong goi & exit /b 1)
set QT_QPA_PLATFORM=

echo [4/5] Dong goi PyInstaller ...
pyinstaller --noconfirm packaging\ketoan.spec || exit /b 1

echo [5/5] Kem du lieu mau va tai lieu ...
if not exist dist\UngDungKeToan\sample_data mkdir dist\UngDungKeToan\sample_data
python -c "from ketoan.data.seed import create_database; create_database(r'dist\UngDungKeToan\sample_data\ketoan_demo.db').close()"
copy /y docs\HUONG_DAN_CAI_DAT.md dist\UngDungKeToan\ >nul
xcopy /e /i /y sample_data\hoa_don_xml dist\UngDungKeToan\sample_data\hoa_don_xml >nul

echo.
echo Hoan tat: dist\UngDungKeToan\UngDungKeToan.exe
echo (Tuy chon) Tao bo cai dat: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
endlocal
