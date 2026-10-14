"""Real browser regression for the sales workflow, with isolated database data."""

import socket
import threading
import time

import uvicorn
from playwright.sync_api import sync_playwright

from app.main import app
from app.config import settings


def test_sales_workflow_in_browser(client):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", loop="asyncio"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path=settings.PLAYWRIGHT_EXECUTABLE_PATH
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(10000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}")
            page.get_by_label("Email", exact=True).fill("admin@example.com")
            page.get_by_label("Mật khẩu", exact=True).fill("Test-Password-2026")
            page.get_by_role("button", name="Đăng nhập →").click()
            page.get_by_role("heading", name="Một ngày tốt để kết nối.").wait_for()
            page.get_by_role("button", name="＋ Thêm khách hàng").click()
            page.get_by_label("Tên doanh nghiệp").fill("Browser Company")
            page.get_by_label("Email liên hệ").fill("contact@example.com")
            page.get_by_role("button", name="Lưu thay đổi").click()
            page.get_by_role("heading", name="Browser Company").wait_for()
            page.get_by_role("button", name="Chỉnh sửa", exact=True).click()
            page.get_by_label("Trạng thái", exact=True).select_option("interested")
            page.get_by_label("Ghi chú", exact=True).fill("Khách hàng quan tâm tới giải pháp.")
            page.get_by_role("button", name="Lưu thay đổi").click()
            page.get_by_role("heading", name="Browser Company").wait_for()
            page.get_by_role("button", name="＋ Tạo cơ hội").click()
            page.get_by_label("Tên cơ hội").fill("Browser Deal")
            page.get_by_label("Giá trị · VND", exact=True).fill("25000000")
            page.get_by_role("button", name="Lưu thay đổi").click()
            page.get_by_role("heading", name="Pipeline bán hàng").wait_for()
            page.get_by_role("heading", name="Browser Deal", exact=True).wait_for()
            page.locator('[data-deal]').first.click()
            page.get_by_role("button", name="Chỉnh sửa cơ hội").click()
            page.get_by_label("Giá trị · VND", exact=True).fill("30000000")
            page.get_by_role("button", name="Lưu thay đổi").click()
            page.locator("#modal .details h2").filter(has_text="30.000.000").wait_for()
            page.get_by_label("Giai đoạn deal").select_option("qualified")
            page.get_by_role("button", name="Cập nhật giai đoạn").click()
            page.locator('#stage-form select').wait_for()
            page.get_by_label("Thêm ghi chú").fill("Đã xác nhận ngân sách, hẹn demo thứ hai.")
            page.get_by_role("button", name="Lưu ghi chú").click()
            page.get_by_text("Đã xác nhận ngân sách, hẹn demo thứ hai.", exact=True).wait_for()
            page.get_by_role("button", name="Xem khách hàng", exact=True).click()
            page.locator('[data-related-deal]').wait_for()
            page.locator('[data-related-deal]').click()
            page.locator('#modal-title').filter(has_text='Browser Deal').wait_for()
            page.get_by_role("button", name="Đóng", exact=True).click()
            page.locator('[data-stage="qualified"] [data-deal]').wait_for()
            page.locator('[data-stage="qualified"] [data-deal]').drag_to(page.locator('[data-stage="demo_scheduled"]'))
            page.locator('[data-stage="demo_scheduled"] [data-deal]').wait_for()
            page.locator('[data-stage="demo_scheduled"] [data-deal]').click()
            page.get_by_label("Giai đoạn deal").select_option("won")
            page.get_by_role("button", name="Cập nhật giai đoạn").click()
            page.locator('#stage-form select').wait_for()
            page.get_by_role("button", name="Đóng", exact=True).click()
            page.locator('[data-stage="won"] [data-deal]').wait_for()
            page.get_by_role("button", name="▤ Khách hàng").click()
            page.get_by_label("Tìm khách hàng", exact=True).fill("Browser Company")
            page.get_by_role("button", name="Tìm kiếm", exact=True).click()
            page.get_by_role("button", name="Browser Company", exact=True).wait_for()
            page.screenshot(path="/tmp/chatask-sales-desktop.png", full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path="/tmp/chatask-sales-mobile.png", full_page=True)
            assert page.locator('body').evaluate('(el) => el.scrollWidth <= window.innerWidth')
            page.reload()
            page.get_by_role("heading", name="Một ngày tốt để kết nối.").wait_for()
            page.get_by_role("button", name="Đăng xuất", exact=True).click()
            page.get_by_role("heading", name="Đăng nhập workspace").wait_for()
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
