from __future__ import annotations

import base64
import logging
import socket
import time
import http.client
import xmlrpc.client
from typing import Any

from app.config.models import AppConfig
from app.services.odoo_profiles import ResolvedOdooConnection, resolve_odoo_connection


logger = logging.getLogger("conti.odoo")


class OdooHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, host_header: str | None = None, *args, **kwargs):
        super().__init__(host, *args, **kwargs)
        self.host_header = host_header

    def putrequest(self, method, url, skip_host=False, skip_accept_encoding=False):
        if self.host_header:
            skip_host = True
        super().putrequest(method, url, skip_host=skip_host, skip_accept_encoding=skip_accept_encoding)
        if self.host_header:
            self.putheader("Host", self.host_header)


class OdooHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, host_header: str | None = None, *args, **kwargs):
        super().__init__(host, *args, **kwargs)
        self.host_header = host_header

    def putrequest(self, method, url, skip_host=False, skip_accept_encoding=False):
        if self.host_header:
            skip_host = True
        super().putrequest(method, url, skip_host=skip_host, skip_accept_encoding=skip_accept_encoding)
        if self.host_header:
            self.putheader("Host", self.host_header)


class OdooTransport(xmlrpc.client.Transport):
    def __init__(self, db_name: str, host_header: str | None = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.db_name = db_name
        self.host_header = host_header

    def send_headers(self, connection, headers) -> None:
        super().send_headers(connection, headers)
        if self.db_name:
            connection.putheader("X-Odoo-Database", self.db_name)

    def make_connection(self, host):
        connection = OdooHTTPConnection(host, host_header=self.host_header)
        return connection


class OdooSafeTransport(xmlrpc.client.SafeTransport):
    def __init__(self, db_name: str, host_header: str | None = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.db_name = db_name
        self.host_header = host_header

    def send_headers(self, connection, headers) -> None:
        super().send_headers(connection, headers)
        if self.db_name:
            connection.putheader("X-Odoo-Database", self.db_name)

    def make_connection(self, host):
        connection = OdooHTTPSConnection(host, host_header=self.host_header)
        return connection


class OdooRPCClient:
    def __init__(self, config: AppConfig, connection: ResolvedOdooConnection) -> None:
        self._config = config
        self.connection = connection
        self._uid: int | None = None
        self.models = None

    @property
    def uid(self) -> int:
        if self._uid is None:
            self._connect()
        return self._uid or 0

    def _connect(self) -> None:
        socket.setdefaulttimeout(self._config.odoo.connect_timeout_seconds)
        transport_class = OdooSafeTransport if self.connection.url.startswith("https") else OdooTransport

        host_header = self.connection.host_header
        if not host_header and ("odoo18" in self.connection.url or "localhost" in self.connection.url or "127.0.0.1" in self.connection.url):
            port = "8069"
            clean_url = self.connection.url.replace("http://", "").replace("https://", "")
            if ":" in clean_url:
                port = clean_url.split(":")[-1].split("/")[0]
            host_header = f"{self.connection.db}:{port}"

        common = xmlrpc.client.ServerProxy(
            f"{self.connection.url}/xmlrpc/2/common",
            allow_none=True,
            transport=transport_class(
                db_name=self.connection.db,
                host_header=host_header,
            ),
        )

        uid = common.authenticate(
            self.connection.db,
            self.connection.username,
            self.connection.password,
            self.connection.context,
        )
        if not uid:
            raise ValueError(f"Autenticación Odoo fallida para la conexión '{self.connection.name}'")

        self._uid = int(uid)
        self.models = xmlrpc.client.ServerProxy(
            f"{self.connection.url}/xmlrpc/2/object",
            allow_none=True,
            transport=transport_class(
                db_name=self.connection.db,
                host_header=host_header,
            ),
        )
        logger.info(
            "Conectado a Odoo connection=%s db=%s uid=%s",
            self.connection.name,
            self.connection.db,
            self._uid,
        )

    def _ensure_connected(self) -> None:
        if self.models is None or self._uid is None:
            self._connect()

    def _execute_kw_with_retry(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        payload = kwargs or {}
        for attempt in range(self._config.odoo.max_retries):
            try:
                self._ensure_connected()
                return self.models.execute_kw(
                    self.connection.db,
                    self.uid,
                    self.connection.password,
                    model,
                    method,
                    args,
                    payload,
                )
            except (xmlrpc.client.ProtocolError, ConnectionRefusedError, OSError) as exc:
                logger.warning(
                    "Error de conexión Odoo intento=%s/%s model=%s method=%s error=%s",
                    attempt + 1,
                    self._config.odoo.max_retries,
                    model,
                    method,
                    exc,
                )
                self._uid = None
                self.models = None
                if attempt >= self._config.odoo.max_retries - 1:
                    raise
                time.sleep(1)

    def search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"fields": fields or [], "limit": limit, "offset": offset}
        if order:
            kwargs["order"] = order
        return self._execute_kw_with_retry(model, "search_read", [domain], kwargs)

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict[str, Any]]:
        return self._execute_kw_with_retry(model, "read", [ids], {"fields": fields or []})

    def create(self, model: str, data: dict[str, Any], **kwargs: Any) -> int:
        return int(self._execute_kw_with_retry(model, "create", [data], kwargs))

    def write(self, model: str, ids: list[int], data: dict[str, Any]) -> bool:
        return bool(self._execute_kw_with_retry(model, "write", [ids, data]))

    def unlink(self, model: str, ids: list[int]) -> bool:
        return bool(self._execute_kw_with_retry(model, "unlink", [ids]))

    def search_count(self, model: str, domain: list[Any]) -> int:
        return int(self._execute_kw_with_retry(model, "search_count", [domain]))

    def execute_method(self, model: str, method: str, args: list[Any], **kwargs: Any) -> Any:
        return self._execute_kw_with_retry(model, method, args, kwargs)

    def create_attachment(self, model: str, record_id: int, filename: str, file_content: bytes) -> int:
        attachment_data = {
            "name": filename,
            "datas": base64.b64encode(file_content).decode("utf-8"),
            "res_model": model,
            "res_id": record_id,
        }
        return self.create("ir.attachment", attachment_data)

    def post_message(self, model: str, record_id: int, subject: str, body: str, partner_ids: list[int]) -> bool:
        self.execute_method(
            model,
            "message_post",
            [[record_id]],
            body=body,
            subject=subject,
            message_type="notification",
            partner_ids=partner_ids,
        )
        return True


def get_odoo_client(config: AppConfig, arguments: dict[str, Any] | None = None) -> OdooRPCClient:
    connection = resolve_odoo_connection(config, arguments)
    client = OdooRPCClient(config=config, connection=connection)
    client._ensure_connected()
    return client
