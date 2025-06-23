import psycopg2


def get_connection(
    host: str, database: str, user: str, password: str, port: int = 5432
) -> psycopg2.extensions.connection:
    """
    Create and return a PostgreSQL connection.
    """
    return psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port,
    )

def execute_query(
    connection: psycopg2.extensions.connection,
    query: str
) -> None:
    """
    Create a table in the PostgreSQL database.
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        connection.commit()