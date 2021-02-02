#!/usr/bin/env python
from threading import Event, Thread
from util import *

import sys
import logging
import socket
import struct


logger = logging.getLogger('client')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class TcpClient:
    def __init__(self, stun_host, stun_port):
        self.stun_host = stun_host
        self.stun_port = stun_port

    def accept(self, port):
        logger.info("accept %s", port)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.listen(1)
        s.settimeout(5)

        while not self.stop.is_set():
            try:
                conn, addr = s.accept()
            except socket.timeout:
                continue
            else:
                logger.info("Accept %s connected!", port)
                return

    def connect(self, local_addr, addr):
        logger.info("connect from %s to %s", local_addr, addr)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(local_addr)
        s.settimeout(2)

        while not self.stop.is_set():
            try:
                s.connect(addr)
            except socket.timeout:
                continue
            except socket.error:
                continue

            logger.info("connected from %s to %s success!", local_addr, addr)
            self.stop.set()
            return s

    def tcp_punch(self):
        self.stop = Event()

        sa = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sa.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sa.connect((self.stun_host, self.stun_port))
        priv_addr = sa.getsockname()

        send_msg(sa, addr_to_msg(priv_addr))
        data = recv_msg(sa)
        logger.info("client %s %s - received data: %s", priv_addr[0], priv_addr[1], data)
        pub_addr = msg_to_addr(data)
        send_msg(sa, addr_to_msg(pub_addr))

        data = recv_msg(sa)
        pubdata, privdata = data.split(b'|')
        client_pub_addr = msg_to_addr(pubdata)
        client_priv_addr = msg_to_addr(privdata)
        logger.info(
            "client public is %s and private is %s, peer public is %s private is %s",
            pub_addr, priv_addr, client_pub_addr, client_priv_addr,
        )

        try:
            accept_thread = Thread(target=TcpClient.accept, args=(self, client_pub_addr[1],))
            accept_thread.start()

            return self.connect(priv_addr, client_pub_addr)
        finally:
            accept_thread.join()

    def sending_worker(self, a, b):
        try:
            while True:
                try:
                    data = a.recv(65536)
                except socket.timeout:
                    if self.stop.is_set():
                        return
                    continue

                if not data:
                    break
                print('data:', data)

                b.sendall(data)
        except Exception as e:
            print('Exception', e)
        finally:
            self.stop.set()

    def proxy(self, s1, s2):
        self.stop = Event()

        t1 = Thread(target=TcpClient.sending_worker, args=(self, s2, s1))
        t2 = Thread(target=TcpClient.sending_worker, args=(self, s1, s2))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        s1.close()
        s2.close()

    def start_client(self, ip, port):
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.bind((ip, port))
        client_sock.listen()

        try:
            while True:
                print('awaiting connection on', ip, port)
                client_conn, addr = client_sock.accept()
                client_conn.settimeout(2)
                print('>>>>> received local connection', addr)
                
                server_sock = self.tcp_punch()
                self.proxy(client_conn, server_sock)
        finally:
            client_sock.close()

    def start_server(self, ip, port):
        while True:
            client_sock = self.tcp_punch()

            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.settimeout(2)
            server_sock.connect((ip, port))
            
            self.proxy(client_sock, server_sock)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, message='%(asctime)s %(message)s')
    c = TcpClient(*addr_from_args(sys.argv[1:]))
    if sys.argv[1] == 'client':
        c.start_client('localhost', 12345)
    elif sys.argv[1] == 'server':
        c.start_server('192.168.1.8', 25565)
