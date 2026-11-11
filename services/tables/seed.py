from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert

from services.tables.models import DiningTable


def seed(connection):
    for number in range(1, 13):
        connection.execute(insert(DiningTable).values(
            id=uuid5(NAMESPACE_URL, f"https://mesa-facil.example/demo/table/{number}"),
            number=number, available=True, version=1,
        ).on_conflict_do_nothing())
