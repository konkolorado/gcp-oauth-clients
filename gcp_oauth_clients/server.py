import logging
import queue
import socket
import socketserver
import threading
from urllib import parse as urllib_parse

logger = logging.getLogger(__name__)


class Result:
    def __init__(self, code: str, state: str):
        self.code = code
        self.state = state


class LocalHandler(socketserver.StreamRequestHandler):

    result: queue.Queue = queue.Queue()

    def handle(self):
        requestline = self.rfile.readline().strip().decode("utf-8")
        words = requestline.rstrip("\r\n").split()

        if not 2 <= len(words) <= 3:
            logger.debug(f"Bad request syntax {requestline}")
            return False
        path = words[1]
        qargs = urllib_parse.urlsplit(path).query
        qargs_dict = dict(urllib_parse.parse_qsl(qargs))
        code, state = qargs_dict.get("code"), qargs_dict.get("state")
        if code is None:
            error = qargs_dict.get("error")
            logger.debug(f"Request missing code parameter, got {error=}")
            code = ""
        if state is None:
            error = qargs_dict.get("error")
            logger.debug(f"Request missing state parameter, got {error=}")
            state = ""

        self.wfile.write(
            """HTTP/1.1 200 OK
            Content-Type: text/html


            <html><body>You may now close this tab.</body></html>
            """.encode(
                "utf-8"
            )
        )
        self.result.put_nowait(Result(code=code, state=state))


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class LocalServer:
    def __init__(self) -> None:
        sock = socket.socket()
        sock.bind(("", 0))
        self.port = sock.getsockname()[1]

    def run(self):
        self.server = ThreadedTCPServer(("", self.port), LocalHandler)
        self.server.allow_reuse_address = True
        self.server_thread = threading.Thread(target=self.server.handle_request)
        self.server_thread.daemon = True
        self.server_thread.start()
        logger.debug(
            f"Started LocalServer 'thread_name': {self.server_thread.name} 'server_address': {self.server.server_address}, 'port': {self.port}"
        )

    def get_result_blocking(self) -> Result:
        logger.debug("Blocking until LocalServer result available")
        result = LocalHandler.result.get(block=True)
        logger.debug(f"LocalServer received result: {result}")
        return result

    def shutdown(self):
        logger.debug("Shutting down LocalServer")
