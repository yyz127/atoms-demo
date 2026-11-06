"""Apply the schema to the configured PostgreSQL database before deploying."""
from .accounts import migrate

if __name__ == '__main__':
    migrate()
    print('Account schema is ready.')
