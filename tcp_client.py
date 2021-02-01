#!/usr/bin/env python
import sys
import logging
import socket
import struct
from threading import Event, Thread
from util import *
import os


logger = logging.getLogger('client')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
STOP = Event()
STOP2 = Event()


def accept(port):
    logger.info("accept %s", port)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.bind(('', port))
    s.listen(1)
    s.settimeout(5)

    while not STOP.is_set():
        try:
            conn, addr = s.accept()
        except socket.timeout:
            continue
        else:
            logger.info("Accept %s connected!", port)
            return


def connect(local_addr, addr):
    logger.info("connect from %s to %s", local_addr, addr)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.bind(local_addr)

    while not STOP.is_set():
        try:
            s.connect(addr)
        except socket.error:
            continue

        logger.info("connected from %s to %s success!", local_addr, addr)
        STOP.set()
        return s


def sending_worker(a, b):
    while True:
        try:
            data = a.recv(1024)
            if not data:
                break

            print(data)
            b.sendall(data)
        except Exception as e:
            print('Exception', e)


def proxy(s1, s2):
    try:
        t1 = Thread(target=sending_worker, args=(s2, s1))
        t2 = Thread(target=sending_worker, args=(s1, s2))
        t1.start()
        t2.start()
        
        input('press enter to stop!')
        STOP2.set()
    finally:
        t1.join()
        t2.join()


def client_proxy(s):
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.bind(('127.0.0.1', 1244))
    s2.listen()

    conn, addr = s2.accept()
    try:
        proxy(s, conn)
    finally:
        conn.close()
        s2.close()


def server_proxy(s, port):
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.connect(('127.0.0.1', port))
    
    try:
        proxy(s, s2)
    finally:
        s2.close()


def main(host, port):
    sa = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sa.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sa.connect((host, port))
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
        accept_thread = Thread(target=accept, args=(client_pub_addr[1],))
        accept_thread.start()

        s = connect(priv_addr, client_pub_addr)
        client_proxy(s)
        #server_proxy(s)
    finally:
        accept_thread.join()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, message='%(asctime)s %(message)s')
    main(*addr_from_args(sys.argv))
