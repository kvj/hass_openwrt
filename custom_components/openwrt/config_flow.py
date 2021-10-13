from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from .constants import DOMAIN

import logging
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required('id'): cv.string,
    vol.Required('address'): cv.string,
    vol.Required('username'): cv.string,
    vol.Optional('password'): cv.string,
    vol.Required('https', default=False): cv.boolean,
    vol.Optional('port', default=0): cv.positive_int,
    vol.Optional('path', default="/ubus"): cv.string,
})

class OpenWrtConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    async def async_step_reauth(self, user_input):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input):
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        _LOGGER.debug(f"Input: {user_input}")
        await self.async_set_unique_id(user_input["address"])
        self._abort_if_unique_id_configured()
        title = "%s - %s" % (user_input["id"], user_input["address"])
        return self.async_create_entry(title=title, data=user_input)
