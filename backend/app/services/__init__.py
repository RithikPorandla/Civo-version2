"""Pure-Python business logic — independent of FastAPI and SQLAlchemy sessions.

Services take plain data in and return plain data out so they are trivially
unit-testable. API layer wires them into HTTP endpoints; migration and seed
scripts call them directly.
"""
