import aiohttp
import async_timeout

from conf import gateway_settings


async def make_request(url: str, method: str, data: dict = None, headers: dict = None):
    """
    Args:
        url: is the url for one of the in-network services
        method: is the lower version of one of the HTTP methods: GET, POST, PUT, DELETE # noqa
        data: is the payload
        headers: is the header to put additional headers into request
    """
    if not data:
        data = {}

    with async_timeout.timeout(gateway_settings.GATEWAY_TIMEOUT):
        async with aiohttp.ClientSession() as session:
            request = getattr(session, method)
            async with request(url, json=data, headers=headers) as response:
                resp_data = await response.json()
                return resp_data, response.status
