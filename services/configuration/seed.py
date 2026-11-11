import os

from sqlalchemy.dialects.postgresql import insert

from services.configuration.models import EstablishmentConfiguration, StaffUser
from services.configuration.passwords import hash_password


def seed(connection):
    connection.execute(insert(EstablishmentConfiguration).values(
        id=1, revision=1, pickup=True, delivery=False, tables=False, tablet=False, tv=True,
    ).on_conflict_do_nothing(index_elements=["id"]))

    for username in ("admin", "operator"):
        password = os.environ.get(f"MESA_DEMO_{username.upper()}_PASSWORD")
        if password:
            connection.execute(insert(StaffUser).values(
                username=username, role=username, password_hash=hash_password(password),
            ).on_conflict_do_nothing(index_elements=["username"]))
