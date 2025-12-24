# src/outlook_app_mailer.py
from __future__ import annotations

from typing import List, Optional
import win32com.client  # type: ignore


def send_mail_via_outlook_app(
    to_addrs: List[str],
    subject: str,
    html_body: str,
    cc_addrs: Optional[List[str]] = None,
) -> None:
    """
    Send email using local Outlook desktop app (COM automation).
    - Requires Outlook installed & signed-in on this Windows PC.
    - Sends HTML (BodyFormat = HTML).
    """
    if not to_addrs:
        raise ValueError("to_addrs is empty.")

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # 0 = MailItem

    mail.To = ";".join(to_addrs)
    if cc_addrs:
        mail.CC = ";".join(cc_addrs)

    mail.Subject = subject
    mail.HTMLBody = html_body

    # Send immediately
    mail.Send()
