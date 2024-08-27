from homeassistant.exceptions import IntegrationError
import json
import logging
import typing

import requests

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT: int = 15

class Ubus:
    def __init__(
        self,
        executor_job: typing.Callable,
        url: str,
        username: str,
        password: str,
        timeout: int = DEFAULT_TIMEOUT,
        verify: bool = True
    ):
        self.executor_job = executor_job
        self.url = url
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify = verify
        self.session_id = ""
        self.rpc_id = 1

    async def api_call(
        self,
        subsystem: str,
        method: str,
        params: dict,
        rpc_method: str = "call"
    ) -> dict:
        _LOGGER.debug(f"Starting api_call with subsystem: {subsystem}, method: {method}, params: {params}")
        try:
            if self.session_id:
                return await self._api_call(rpc_method, subsystem, method, params)
        except PermissionError as err:
            _LOGGER.error(f"PermissionError during api_call: {err}")
        except NameError as err:
            _LOGGER.error(f"NameError during api_call: {err}")
            return {}  # Return an empty dict if the object is not found

        await self._login()
        return await self._api_call(rpc_method, subsystem, method, params)

    async def _login(self):
        _LOGGER.debug("Logging in to Ubus...")
        result = await self._api_call(
            "call",
            "session",
            "login",
            dict(username=self.username, password=self.password),
            "00000000000000000000000000000000")
        _LOGGER.debug(f"Login result: {result}")
        self.session_id = result["ubus_rpc_session"]

    async def _api_call(
        self,
        rpc_method: str,
        subsystem: str,
        method: str,
        params: dict,
        session: str = None,
    ) -> dict:
        _params = [session if session else self.session_id, subsystem]
        if method:
            _params.append(method)
        if params:
            _params.append(params)
        else:
            _params.append({})
        data = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": self.rpc_id,
                "method": rpc_method,
                "params": _params,
            }
        )
        _LOGGER.debug(f'New API call to [{self.url}] with data: {data}')
        self.rpc_id += 1
        try:
            def post():
                return requests.post(
                    self.url,
                    data=data,
                    timeout=self.timeout,
                    verify=self.verify
                )
            response = await self.executor_job(post)
        except Exception as err:
            _LOGGER.error(f"api_call exception: {err}")
            raise ConnectionError from err

        if response.status_code != 200:
            _LOGGER.error(f"api_call http error: {response.status_code}")
            raise ConnectionError(f"HTTP error: {response.status_code}")

        json_response = response.json()
        _LOGGER.debug(f'Raw JSON response from [{self.url}]: {json_response}')

        if "error" in json_response:
            code = json_response['error'].get('code')
            message = json_response['error'].get('message')
            _LOGGER.error(f"api_call RPC error: {json_response['error']}")
            if code == -32002:
                raise PermissionError(message)
            if code == -32000:
                raise NameError(message)
            raise ConnectionError(f"RPC error: {message}")

        result = json_response['result']
        if rpc_method == "list":
            return result
        result_code = result[0]
        if result_code == 8:
            raise ConnectionError(f"RPC error: not allowed")
        if result_code == 6:
            raise PermissionError(f"RPC error: insufficient permissions")
        if result_code == 0:
            return json_response['result'][1] if len(result) > 1 else {}
        raise ConnectionError(f"RPC error: {result[0]}")

    async def api_list(self):
        return await self.api_call("*", None, None, "list")