"""Simple test script for Database class functions."""

from db_functions import Database

# --- Config ---
EMAIL = "testuser@gmail.com"
PASSWORD = "password"
TEST_PORTFOLIO_NAME = "Test Portfolio"
TEST_STOCK_SYMBOL = "AAPL"
TEST_STOCK_QTY = 10


def test_create_new_user():
    print("=" * 50)
    print("TEST: create_new_user")
    print("=" * 50)
    Database.create_new_user(EMAIL, PASSWORD, TEST_PORTFOLIO_NAME)
    print()


def test_get_user_portfolios():
    print("=" * 50)
    print("TEST: get_user_portfolios")
    print("=" * 50)
    portfolios = Database.get_user_portfolios(EMAIL, PASSWORD)
    print(f"Result: {portfolios}")
    print()


def test_create_additional_portfolio():
    print("=" * 50)
    print("TEST: create_additional_portfolio")
    print("=" * 50)
    portfolio_id = Database.create_additional_portfolio(EMAIL, PASSWORD, TEST_PORTFOLIO_NAME)
    print(f"Result: {portfolio_id}")
    print()


def test_add_stock():
    print("=" * 50)
    print("TEST: test_add_stock")
    print("=" * 50)
    Database.test_add_stock(EMAIL, PASSWORD, TEST_STOCK_SYMBOL, TEST_STOCK_QTY, TEST_PORTFOLIO_NAME)
    print()


def test_delete_user():
    print("=" * 50)
    print("TEST: delete user")
    print("=" * 50)
    Database.delete_user(EMAIL, PASSWORD)
    print()

def test_delete_portfolio():
    print("=" * 50)
    print("TEST: delete portfolio")
    print("=" * 50)
    Database.delete_portfolio(EMAIL, PASSWORD, portfolio_name="Test Portfolio")
    print()

def test_delete_holding():
    print("=" * 50)
    print("TEST: delete holding")
    print("=" * 50)
    Database.delete_stock_by_holding_id(EMAIL, PASSWORD, "b4570e6c-01b3-40aa-9651-352eda82d895")
    print()



if __name__ == "__main__":
    # Uncomment create_new_user only if you need to register a new account.
    # test_create_new_user()

    # test_get_user_portfolios()
    # test_create_additional_portfolio()
    # test_add_stock()
    # test_delete_user()
    test_delete_holding()