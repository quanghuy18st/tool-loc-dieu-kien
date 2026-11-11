import re
from datetime import datetime

import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = (
    "https://qq88chiase.pages.dev/"
    "?utm_medium=chat&utm_campaign=link-shared-in-chat"
    "&utm_source=livechat.com&utm_content=secure.livechatinc.com"
)

st.set_page_config(
    page_title="QQ88 - Xác minh điều kiện",
    page_icon="🔎",
    layout="centered",
)

st.title("🔎 QQ88 – Xác minh điều kiện")
st.caption(
    "Nhập username và 6 số cuối trên cùng một dòng. Tool kiểm tra một tài khoản "
    "mỗi lần và dừng ngay sau khi đọc thông báo xác minh."
)


def classify_result(message: str) -> str:
    text = " ".join((message or "").lower().split())

    if "xác minh thành công" in text:
        return "ĐỦ ĐIỀU KIỆN"

    if (
        "tài khoản đã tham gia sự kiện" in text
        or ("đã được phê duyệt" in text and "7 ngày" in text)
    ):
        return "ĐÃ THAM GIA – CHỜ 7 NGÀY"

    if "không đủ điều kiện" in text or "chưa đủ điều kiện" in text:
        return "KHÔNG ĐỦ ĐIỀU KIỆN"

    if "lỗi" in text or "thất bại" in text:
        return "LỖI / KHÔNG XÁC ĐỊNH"

    return "KHÔNG XÁC ĐỊNH"


def first_visible(locators, timeout_ms=1500):
    for locator in locators:
        try:
            candidate = locator.first
            candidate.wait_for(state="visible", timeout=timeout_ms)
            return candidate
        except Exception:
            continue
    return None


def open_verification_form(page):
    candidates = [
        page.locator('button:has(img[alt="gift"])'),
        page.locator('button:has(img[src*="button2"])'),
        page.get_by_role(
            "button",
            name=re.compile(r"đăng ký chia sẻ và nhận thưởng", re.I),
        ),
    ]

    username_input = first_visible(
        [
            page.get_by_placeholder("Nhập tài khoản của bạn"),
            page.locator('input[placeholder*="tài khoản"]'),
        ],
        timeout_ms=500,
    )
    if username_input:
        return

    button = first_visible(candidates, timeout_ms=1800)
    if not button:
        raise RuntimeError(
            "Không tìm thấy nút mở biểu mẫu. Website có thể đã đổi giao diện."
        )

    button.click(timeout=5000)
    page.wait_for_timeout(800)


def fill_username(page, username):
    field = first_visible(
        [
            page.get_by_placeholder("Nhập tài khoản của bạn"),
            page.locator('input[placeholder*="tài khoản"]'),
        ],
        timeout_ms=2500,
    )
    if not field:
        raise RuntimeError("Không tìm thấy ô username trên biểu mẫu.")
    field.fill(username)


def fill_bank_tail(page, tail):
    one_char = page.locator('input[maxlength="1"]')
    visible_boxes = []

    try:
        for i in range(one_char.count()):
            item = one_char.nth(i)
            if item.is_visible():
                visible_boxes.append(item)
    except Exception:
        visible_boxes = []

    if len(visible_boxes) >= 6:
        for i, digit in enumerate(tail):
            visible_boxes[i].fill(digit)
        return

    single = first_visible(
        [
            page.locator('input[placeholder*="số"]'),
            page.locator('input[inputmode="numeric"]'),
            page.locator('input[type="tel"]'),
            page.locator('input[type="number"]'),
            page.locator('input[maxlength="6"]'),
        ],
        timeout_ms=1200,
    )
    if not single:
        raise RuntimeError("Không tìm thấy 6 ô nhập mã ngân hàng.")
    single.fill(tail)


def submit_and_read(page):
    check_button = first_visible(
        [
            page.get_by_role("button", name=re.compile(r"kiểm tra", re.I)),
            page.locator('button:has-text("KIỂM TRA")'),
        ],
        timeout_ms=2000,
    )
    if not check_button:
        raise RuntimeError("Không tìm thấy nút KIỂM TRA.")

    check_button.click(timeout=5000)

    for phrase in [
        "Xác minh thành công",
        "Tài khoản đã tham gia sự kiện",
        "Không đủ điều kiện",
        "Lỗi",
    ]:
        try:
            page.get_by_text(phrase, exact=False).first.wait_for(
                state="visible", timeout=8000
            )
            break
        except PlaywrightTimeoutError:
            continue

    page.wait_for_timeout(1000)
    return page.locator("body").inner_text(timeout=5000)


def check_one_account(username, bank_tail):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            page = browser.new_page(viewport={"width": 1365, "height": 900})
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            open_verification_form(page)
            fill_username(page, username)
            fill_bank_tail(page, bank_tail)

            body_text = submit_and_read(page)
            status = classify_result(body_text)
            return status, body_text[-1800:]
        finally:
            browser.close()


# One text field: username + one space + six bank-tail digits.
with st.form("single_check"):
    account_line = st.text_input(
        "Tài khoản và 6 số cuối (cùng một dòng)",
        placeholder="lilacat84 030965",
        help="Ví dụ: lilacat84 030965",
    )
    submitted = st.form_submit_button(
        "MỞ QQ88 VÀ KIỂM TRA",
        type="primary",
        use_container_width=True,
    )

if submitted:
    parts = account_line.strip().split()

    if len(parts) != 2:
        st.error("Nhập đúng định dạng: username 123456")
    else:
        username, bank_tail = parts

        if not re.fullmatch(r"[A-Za-z0-9_.-]{2,80}", username):
            st.error("Username không đúng định dạng.")
        elif not re.fullmatch(r"\d{6}", bank_tail):
            st.error("6 số cuối phải gồm đúng 6 chữ số.")
        else:
            try:
                with st.spinner("Đang mở QQ88 và đọc thông báo xác minh..."):
                    status, excerpt = check_one_account(username, bank_tail)

                st.session_state["last_result"] = {
                    "username": username,
                    "status": status,
                    "excerpt": excerpt,
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                st.success("Đã đọc xong thông báo xác minh.")
            except Exception as error:
                st.error(f"Không thể hoàn tất: {error}")

if st.session_state.get("last_result"):
    result = st.session_state["last_result"]
    st.subheader("Kết quả xác minh")
    st.write(f"**Tài khoản:** `{result['username']}`")
    st.write(f"**Trạng thái:** {result['status']}")

    with st.expander("Nội dung website đọc được"):
        st.text(result["excerpt"])

    output = f"{result['username']} | {result['status']}\n"
    st.download_button(
        "⬇️ Tải ket_qua.txt",
        data=output.encode("utf-8"),
        file_name="ket_qua.txt",
        mime="text/plain",
    )
    st.caption(f"Thời gian kiểm tra: {result['checked_at']}")

st.divider()
st.caption(
    "Mã 6 số chỉ được dùng trong lượt chạy hiện tại, không ghi vào file kết quả. "
    "Tool kiểm tra một tài khoản mỗi lần và dừng sau khi đọc thông báo xác minh."
)
