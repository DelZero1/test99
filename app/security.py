from __future__ import annotations

from telegram import Update


class SenderValidationError(Exception):
    pass


def validate_sender(update: Update, allowed_user_id: int) -> int:
    user = update.effective_user
    if user is None:
        raise SenderValidationError("Nedostaju podaci o korisniku.")
    if user.id != allowed_user_id:
        raise SenderValidationError("Korisnik nije dopušten.")
    return user.id
