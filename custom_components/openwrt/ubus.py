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
        try:
            if self.session_id != "":
                return await self._api_call(rpc_method, subsystem, method, params)
        except PermissionError as err:
            pass
        await self._login()
        return await self._api_call(rpc_method, subsystem, method, params)

    async def _login(self):
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
        _LOGGER.debug('New call [%s] %s', self.url, data)
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
            _LOGGER.error("api_call exception: %s", err)
            raise ConnectionError from err

        if response.status_code != 200:
            _LOGGER.error("api_call http error: %d", response.status_code)
            raise ConnectionError(f"Http error: {response.status_code}")

        json_response = response.json()
        _LOGGER.debug('Raw json: [%s] %s', self.url, json_response)

        if "error" in json_response:
            code = json_response['error'].get('code')
            message = json_response['error'].get('message')
            _LOGGER.error("api_call rpc error: %s", json_response["error"])
            if code == -32002:
                raise PermissionError(message)
            if code == -32000:
                raise NameError(message)
            raise ConnectionError(f"rpc error: {message}")
        result  = json_response['result']
        if rpc_method == "list":
            return result
        result_code = result[0]
        if result_code == 8:
            raise ConnectionError(f"rpc error: not allowed")            
        if result_code == 6:
            raise PermissionError(f"rpc error: insufficient permissions")
        if  result_code == 0:
            return json_response['result'][1] if len(result) > 1 else {}
        raise ConnectionError(f"rpc error: {result[0]}")
    


