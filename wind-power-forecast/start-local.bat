@echo off
chcp 65001 > nul
REM 璁剧疆鐜鍙橀噺
SET DB_HOST=localhost
SET DB_PORT=54321
SET DB_USER=system
SET DB_PASSWORD=12345678ab
SET DB_NAME=windpower
SET MINIO_ENDPOINT=localhost
SET MINIO_PORT=9900
SET APP_PORT=5002
SET APP_DEBUG=false

REM 鍒囨崲鍒癉鐩?
d:

REM 鍚姩鍚庣锛堝湪鏂扮獥鍙ｄ腑杩愯锛?
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend && call conda activate wind-power-env && set APP_PORT=%APP_PORT% && set APP_DEBUG=%APP_DEBUG% && python app.py"

REM 鍚姩鍚庣锛堝湪鏂扮獥鍙ｄ腑杩愯锛?
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend-autopredict && call conda activate wind-power-env && python app.py"

REM 鍚姩鍓嶇锛堝湪鏂扮獥鍙ｄ腑杩愯锛?
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\frontend && set NODE_OPTIONS=--trace-deprecation && npm run serve"

REM 鎻愮ず鐢ㄦ埛
echo 鍓嶅悗绔湇鍔″惎鍔ㄤ腑锛岃绋嶇瓑...
echo 鍚庣灏嗗湪: http://localhost:%APP_PORT%
echo 鍓嶇灏嗗湪: http://localhost:8080
echo.
echo 鎸変换鎰忛敭鍏抽棴姝ょ獥鍙?..
pause > nul
exit 