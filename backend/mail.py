"""Send transactional authentication messages through Resend's async SDK."""
import asyncio
import httpx
import resend
from resend.exceptions import ResendError


async def send_login_link(key: str, sender: str, email: str, link: str, attempt_id: str, template_id: str = ""):
    resend.api_key = key
    params = {'from': sender, 'to': [email], 'subject': 'Atmos 登录链接',
              'text': f'请在 15 分钟内打开此一次性链接登录：\n{link}\n如果不是你本人操作，请忽略此邮件。'}
    if template_id:
        params = {'from': sender, 'to': [email], 'template': {'id': template_id, 'variables': {'LOGIN_URL': link}}}
    options = {'idempotency_key': 'login/' + attempt_id}
    for attempt in range(3):
        try:
            result = await resend.Emails.send_async(params, options)
            if not result.get('id'):
                raise ValueError('Resend did not return an email ID')
            return
        except ResendError as exc:
            try:
                code = int(exc.code)
            except (ValueError, TypeError):
                raise
            if attempt == 2 or (code != 429 and not 500 <= code <= 599):
                raise
            delay = 0.5 * (2 ** attempt)
            if code == 429:
                try:
                    delay = max(delay, float(exc.headers.get('retry-after', exc.headers.get('Retry-After', 0))))
                except (ValueError, TypeError):
                    raise exc
                # Do not keep an interactive request waiting indefinitely.
                if delay > 5:
                    raise
        except httpx.RequestError:
            if attempt == 2:
                raise
            delay = 0.5 * (2 ** attempt)
        await asyncio.sleep(delay)
