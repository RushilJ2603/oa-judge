@echo off
REM ============================================================================
REM  OA Judge — turn the mock interviewer ON for you and your friends.
REM
REM  While this window is open the site shows "Interviewer online" and anyone
REM  signed in can run interviews. Close it (or press Ctrl+C) and the site goes
REM  back to offline and the server sleeps, so it costs nothing when unused.
REM
REM  The interviewer runs inside WSL because the Antigravity CLI (agy) is not
REM  available to native Windows. The token is read from .env, which is
REM  gitignored, so it never appears in this file.
REM ============================================================================
title OA Judge - Interviewer Host (close this window to go offline)
color 0A

echo.
echo   ===========================================================
echo     OA JUDGE - MOCK INTERVIEWER HOST
echo   ===========================================================
echo.
echo     Starting... your friends will see "Interviewer online"
echo     once this says it is waiting for turns.
echo.
echo     Keep this window OPEN during interviews.
echo     Close it when you are done to stop hosting.
echo.
echo   -----------------------------------------------------------
echo.

wsl.exe -d Ubuntu -- bash -lc "cd '/mnt/c/Users/jishu/Desktop/oa-judge' && if [ ! -f .env ]; then echo 'ERROR: .env is missing - the worker token lives there.'; exit 1; fi && set -a && . ./.env && set +a && exec python3 -u interview_worker.py --server https://oa123.fly.dev --concurrency 12"

echo.
echo   -----------------------------------------------------------
echo     Interviewer stopped. The site now shows "offline".
echo   -----------------------------------------------------------
echo.
pause
