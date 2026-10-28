"""Disposable localhost-only browser acceptance for canonical workspace pages."""

import os
import socket
import tempfile
import threading
from pathlib import Path


def main() -> None:
    """Serve isolated state and exercise direct page routing without live services."""
    root = Path(tempfile.mkdtemp(prefix="jobot-25-preview-"))
    os.environ.update(
        DATABASE_URL=f"sqlite:///{(root / 'preview.db').as_posix()}",
        CHROMA_DIR=str(root / "chroma"),
        ENCRYPTION_KEY_FILE=str(root / "key"),
        JOBOT_TESTING="1",
        ENV="testing",
        ANONYMIZED_TELEMETRY="False",
    )

    from playwright.sync_api import expect, sync_playwright
    from sqlmodel import Session
    from uvicorn import Config, Server

    from app.auth.dependencies import COOKIE_NAME
    from app.auth.security import create_user_session, hash_password
    from app.db.database import engine, init_db
    from app.db.models import User, UserProfile
    from app.main import app

    init_db()
    with Session(engine) as session:
        user = User(
            email="phase25@example.test",
            full_name="Phase 25 Preview",
            password_hash=hash_password("Phase25Preview123"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(UserProfile(user_id=user.id, full_name=user.full_name))
        session.commit()
        session_token = create_user_session(session, user.id).session_token

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    server = Server(Config(app, host="127.0.0.1", port=port, log_level="warning"))
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    while not server.started:
        threading.Event().wait(0.02)

    base_url = f"http://127.0.0.1:{port}"
    pages = {
        "/dashboard": ("dashboard", "/web/views/kanban"),
        "/jobs/board": ("jobs-board", "/web/views/kanban"),
        "/jobs/table": ("jobs-table", "/web/views/table"),
        "/queue": ("queue", "/web/views/queue"),
        "/profile": ("profile", "/web/views/profile"),
        "/settings": ("settings", "/web/views/settings"),
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies([{
                "name": COOKIE_NAME,
                "value": session_token,
                "url": base_url,
                "httpOnly": True,
                "sameSite": "Lax",
            }])
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base_url) else route.abort())
            page = context.new_page()

            for path, (active_page, fragment_path) in pages.items():
                page.goto(base_url + path)
                expect(page.locator("body")).to_have_attribute("data-page", active_page)
                expect(page.locator("#view-container")).to_have_attribute("hx-get", fragment_path)
                expect(page.locator("#popup-notifications")).to_be_attached()

            page.goto(base_url + "/dashboard")
            page.locator('a[href="/jobs/board"]').click()
            expect(page).to_have_url(base_url + "/jobs/board")
            page.go_back()
            expect(page).to_have_url(base_url + "/dashboard")
            page.go_forward()
            expect(page).to_have_url(base_url + "/jobs/board")

            for width, height in ((375, 812), (1440, 900)):
                page.set_viewport_size({"width": width, "height": height})
                page.goto(base_url + "/settings")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                expect(page.locator('a[href="/profile"]')).to_be_visible()

            browser.close()
    finally:
        server.should_exit = True
        server_thread.join(timeout=10)


if __name__ == "__main__":
    main()