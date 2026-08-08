@echo off
title Ngan Hang Cau Hoi Toan
cd /d D:\MathBank

:: Khởi chạy Streamlit ẩn dưới hệ thống
start /min "" streamlit run app.py --theme.base="light" --server.headless true

:: Vòng lặp chờ cổng 8501 thực sự sẵn sàng
:WAIT_LOOP
powershell -Command "try { $client = New-Object System.Net.Sockets.TcpClient('localhost', 8501); $client.Close(); exit 0 } catch { exit 1 }"
if %errorlevel% neq 0 (
    timeout /t 1 /nobreak >nul
    goto WAIT_LOOP
)

:: Khi cổng 8501 đã mở hoàn tất, bật cửa sổ App
start chrome --app=http://localhost:8501