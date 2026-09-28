"""SMTP e-mail delivery (iCloud, Gmail or any provider). Also archives every mail to data/outbox/."""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger(__name__)


def send_email(cfg: dict, subject: str, html_body: str, text_body: str | None = None) -> bool:
    em = cfg["email"]
    # always keep a copy on disk (useful for audits and when SMTP is not configured yet)
    outbox = os.path.join(cfg["data_dir"], "outbox")
    os.makedirs(outbox, exist_ok=True)
    kind = "monthly" if "mensile" in subject.lower() else "test" if "test" in subject.lower() else "new"
    fn = os.path.join(outbox, f"{datetime.now():%Y%m%d-%H%M%S}-{kind}.html")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"<!-- Subject: {subject} -->\n{html_body}")

    if em.get("dry_run") or not em.get("smtp_user") or not em.get("smtp_password"):
        log.warning("e-mail not sent (dry_run or SMTP credentials missing) - saved to %s", fn)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("Garage Monitor", em["sender"]))
    msg["To"] = em["recipient"]
    msg.set_content(text_body or "Questo messaggio richiede un client che supporti HTML.")
    msg.add_alternative(html_body, subtype="html")

    try:
        if int(em["smtp_port"]) == 465:
            with smtplib.SMTP_SSL(em["smtp_host"], em["smtp_port"], context=ssl.create_default_context(), timeout=60) as s:
                s.login(em["smtp_user"], em["smtp_password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(em["smtp_host"], em["smtp_port"], timeout=60) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.login(em["smtp_user"], em["smtp_password"])
                s.send_message(msg)
        log.info("e-mail sent to %s: %s", em["recipient"], subject)
        return True
    except Exception:
        log.exception("e-mail delivery failed (copy kept in %s)", fn)
        return False
