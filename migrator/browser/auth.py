import asyncio

from .session import BrowserSession


class AuthenticationError(RuntimeError):
    pass


async def wait_for_login(browser: BrowserSession) -> dict:
    browser.invalidate_refs()
    try:
        await asyncio.to_thread(
            input, "Complete login in the browser, then press Enter here to start extraction: "
        )
    except EOFError:
        raise AuthenticationError("Login handoff requires an interactive terminal") from None
    browser.check_page()
    return {"status": "operator_confirmed", "source": "cliniko",
            "summary": "The operator completed login and handed the browser to extraction."}
