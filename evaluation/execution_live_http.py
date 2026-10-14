"""One stdlib HTTPS request; no redirects, environment proxies, SDK or retries."""

import http.client
import json
import socket
import ssl
from urllib.parse import urlsplit

from execution_live_wire import contains_secret, projection
from execution_plan import Store
from execution_records import endpoint
from offline_bundle import MAX_BYTES, require


class NativeHTTP:
    def dispatch(self, request_bytes, secret, check):
        request = Store.decode_json(request_bytes)
        endpoint(request["url"])
        require(
            request["method"] == "POST"
            and request["headers"] == {"Content-Type": "application/json"},
            "Exact native public request",
        )
        require(
            isinstance(secret, str)
            and 1 <= len(secret) <= 4096
            and all(33 <= ord(c) <= 126 for c in secret),
            "Credential format",
        )
        body = json.dumps(
            request["body"], ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
        require(
            not contains_secret(request["body"], secret) and len(body) <= MAX_BYTES,
            "No credential in public model input",
        )
        parts = urlsplit(request["url"])
        connection = None
        try:
            connection = http.client.HTTPSConnection(
                parts.hostname,
                parts.port,
                timeout=check() / 1_000_000_000,
                context=ssl.create_default_context(),
            )
            connection.connect()
            socket_handle = connection.sock
            socket_handle.settimeout(check() / 1_000_000_000)
            connection.request(
                "POST",
                parts.path or "/",
                body=body,
                headers={**request["headers"], "Authorization": "Bearer " + secret},
            )
            response = connection.getresponse()
            chunks, size = [], 0
            while True:
                socket_handle.settimeout(check() / 1_000_000_000)
                chunk = response.read(min(65536, MAX_BYTES // 2 + 1 - size))
                size += len(chunk)
                require(size <= MAX_BYTES // 2, "Native response byte cap")
                if not chunk:
                    break
                chunks.append(chunk)
                if response.isclosed():
                    break
            rid = response.getheader("x-typesafe-request-id") or response.getheader(
                "x-request-id"
            )
            return {
                "response": projection(response.status, b"".join(chunks), rid, secret),
                "errorClass": None,
            }
        except (OSError, http.client.HTTPException) as error:
            name = (
                "SSLCertVerificationError"
                if isinstance(error, ssl.SSLCertVerificationError)
                else "SSLEOFError"
                if isinstance(error, ssl.SSLEOFError)
                else "ReadTimeout"
                if isinstance(error, (socket.timeout, TimeoutError))
                else "RemoteProtocolError"
                if isinstance(error, http.client.HTTPException)
                else "ConnectError"
            )
            return {"response": None, "errorClass": name}
        finally:
            if connection is not None:
                connection.close()
