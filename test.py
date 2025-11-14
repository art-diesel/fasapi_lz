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

def wait_for_title(driver, timeout=6):
    WebDriverWait(driver, timeout).until(lambda d: d.title != "")

def any_elem_found(driver, by, selector, timeout=6):
    WebDriverWait(driver, timeout).until(lambda d: len(d.find_elements(by, selector)) > 0)
    return driver.find_elements(by, selector)

def test_home_page(browser):
    browser.get(BASE + "/")
    wait_for_title(browser)
    elems = any_elem_found(browser, By.CSS_SELECTOR, ".container")
    assert len(elems) >= 1

def test_login_form_present(browser):
    browser.get(BASE + "/login")
    wait_for_title(browser)
    assert len(browser.find_elements(By.NAME, "username")) >= 1
    assert len(browser.find_elements(By.NAME, "password")) >= 1
    btns = browser.find_elements(By.CSS_SELECTOR, "button[type='submit']")
    assert len(btns) >= 1

def test_registration_form_present(browser):
    browser.get(BASE + "/reg")
    wait_for_title(browser)
    assert len(browser.find_elements(By.NAME, "username")) >= 1
    assert len(browser.find_elements(By.NAME, "password")) >= 1
    assert len(browser.find_elements(By.NAME, "password_confirm")) >= 1
    assert len(browser.find_elements(By.CSS_SELECTOR, "button[type='submit']")) >= 1

def test_404_and_403_templates(browser):
    browser.get(BASE + "/__nonexistent_path_for_404__")
    body_elems = browser.find_elements(By.TAG_NAME, "body")
    assert len(body_elems) == 1
    body_text = body_elems[0].text
    assert ("Ошибка 404" in body_text) or ("Не найдено" in body_text) or browser.title.lower().startswith("404")

    browser.get(BASE + "/admin")
    body_text = browser.find_elements(By.TAG_NAME, "body")[0].text
    assert ("Админ-панель" in body_text) or ("Ошибка 403" in body_text) or browser.title.lower().startswith("403")

def test_register_login_logout_flow(browser):
    user = f"user_{int(time.time())}"
    pwd = "P@ssw0rd123!"
    browser.get(BASE + "/reg")
    assert len(browser.find_elements(By.NAME, "username")) >= 1
    browser.find_elements(By.NAME, "username")[0].send_keys(user)
    browser.find_elements(By.NAME, "password")[0].send_keys(pwd)
    browser.find_elements(By.NAME, "password_confirm")[0].send_keys(pwd)
    browser.find_elements(By.CSS_SELECTOR, "button[type='submit']")[0].click()
    WebDriverWait(browser, 6).until(lambda d: d.current_url != BASE + "/reg" or "Добро пожаловать" in d.page_source)
    try:
        browser.get(BASE + "/logout")
    except Exception:
        pass
    browser.get(BASE + "/login")
    browser.find_elements(By.NAME, "username")[0].send_keys(user)
    browser.find_elements(By.NAME, "password")[0].send_keys(pwd)
    browser.find_elements(By.CSS_SELECTOR, "button[type='submit']")[0].click()
    WebDriverWait(browser, 6).until(EC.any_of(
        EC.title_contains("Главная"),
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Добро пожаловать') or contains(text(), 'Вы успешно вошли')]"))
    ))
    browser.get(BASE + "/logout")
    WebDriverWait(browser, 6).until(lambda d: d.current_url != "")

