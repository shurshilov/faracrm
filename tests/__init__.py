"""
Fara CRM Test Suite

Structure:
- unit/           Unit tests (no database required)
- integration/    Integration tests with database
  - users/        User module tests
  - security/     Security module tests  
  - partners/     Partners module tests
  - leads/        Leads module tests
  - sales/        Sales module tests
  - products/     Products module tests
  - chat/         Chat module tests
  - tasks/        Tasks module tests
  - attachments/  Attachments module tests
- fixtures/       Shared test data and factories

Run all tests:
    pytest tests/ -v

Run with coverage:
    pytest --cov=backend --cov-report=html --cov-report=term-missing

Run specific module:
    pytest tests/integration/users/ -v

Run only unit tests:
    pytest tests/unit/ -v -m unit
"""
