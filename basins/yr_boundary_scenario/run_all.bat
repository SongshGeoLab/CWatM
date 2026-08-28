@echo off
REM 1. 启动 conda 环境
call "C:\ProgramData\Anaconda3\Scripts\activate.bat" CWM_YRB_2022

REM 2. 遍历当前路径下所有 settings*.txt
for %%f in (settings*.txt) do (
    set "filename=%%~nf"
    call :GetLastPart
    mkdir "%lastpart%"
    python ../../run_cwatm.py "%%f" -l
)
pause
goto :eof

:GetLastPart
REM 取最后一个 "_" 后面的部分
set "name=%filename%"
:loop
for /f "tokens=1* delims=_" %%a in ("%name%") do (
    if "%%b"=="" (
        set "lastpart=%%a"
    ) else (
        set "name=%%b"
        goto loop
    )
)
goto :eof