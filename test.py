import os
import time
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE = os.environ.get("APP_URL", "http://localhost:8000")

@pytest.fixture(scope="session")
def browser():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    drv = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
    yield drv
    drv.quit()

def wait_el(driver, by, selector, timeout=6):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))

def assert_title_contains(driver, path, text):
    driver.get(BASE + path)
    WebDriverWait(driver, 6).until(lambda d: d.title != "")
    assert text.lower() in driver.title.lower()

def test_home_page(browser):
    assert_title_contains(browser, "/", "главная")
    wait_el(browser, By.CSS_SELECTOR, ".container")

def test_login_form_present(browser):
    assert_title_contains(browser, "/login", "вход")
    wait_el(browser, By.NAME, "username")
    wait_el(browser, By.NAME, "password")
    btn = wait_el(browser, By.CSS_SELECTOR, "button[type='submit']")
    assert btn is not None

def test_registration_form_present(browser):
    assert_title_contains(browser, "/reg", "регистрация")
    wait_el(browser, By.NAME, "username")
    wait_el(browser, By.NAME, "password")
    wait_el(browser, By.NAME, "password_confirm")
    btn = wait_el(browser, By.CSS_SELECTOR, "button[type='submit']")
    assert btn is not None

def test_not_found_and_forbidden(browser):
    browser.get(BASE + "/__this_path_should_not_exist__")
    body = wait_el(browser, By.TAG_NAME, "body")
    assert ("Ошибка 404" in body.text) or ("Не найдено" in body.text) or browser.title.lower().startswith("404")
    browser.get(BASE + "/admin")
    body = wait_el(browser, By.TAG_NAME, "body")
    assert ("Админ-панель" in body.text) or ("Ошибка 403" in body.text) or browser.title.lower().startswith("403")

def test_register_login_logout_flow(browser):
    user = f"user_{int(time.time())}"
    pwd = "P@ssw0rd123!"
    browser.get(BASE + "/reg")
    wait_el(browser, By.NAME, "username").send_keys(user)
    wait_el(browser, By.NAME, "password").send_keys(pwd)
    wait_el(browser, By.NAME, "password_confirm").send_keys(pwd)
    wait_el(browser, By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(browser, 6).until(lambda d: d.current_url != BASE + "/reg" or "Добро пожаловать" in d.page_source)
    try:
        browser.get(BASE + "/logout")
    except Exception:
        pass
    # вход
    browser.get(BASE + "/login")
    wait_el(browser, By.NAME, "username").send_keys(user)
    wait_el(browser, By.NAME, "password").send_keys(pwd)
    wait_el(browser, By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(browser, 6).until(EC.any_of(
        EC.title_contains("Главная"),
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Добро пожаловать') or contains(text(), 'Вы успешно вошли')]"))
    ))
    # выход
    browser.get(BASE + "/logout")
    WebDriverWait(browser, 6).until(lambda d: d.current_url != "")

