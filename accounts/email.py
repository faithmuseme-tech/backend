import threading
from django.conf import settings
from gmail.utils import send_email


def _send(to_email: str, subject: str, html: str):
    try:
        send_email(to_email, subject, html)
    except Exception:
        pass  # never crash the app over an email


def send_welcome_email(user):
    """Fire-and-forget welcome email after signup."""
    first_name = user.first_name or user.username or "there"
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://faithmuseme-tech.github.io/frontend')
    shop_url = f"{frontend_url}/shop"
    new_arrivals_url = f"{frontend_url}/new-arrivals"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Welcome to CartPulse</title>
</head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.07);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#4f46e5 0%,#06b6d4 100%);padding:40px 40px 32px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;">🛒 CartPulse</h1>
              <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">Premium Electronics &amp; More in Uganda</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px 40px 32px;">
              <h2 style="margin:0 0 12px;color:#1e1b4b;font-size:22px;font-weight:700;">
                Welcome aboard, {first_name}! 🎉
              </h2>
              <p style="margin:0 0 20px;color:#4b5563;font-size:15px;line-height:1.7;">
                We're thrilled to have you join the <strong>CartPulse</strong> family — Uganda's trusted destination for premium electronics, gadgets, and more.
              </p>
              <p style="margin:0 0 28px;color:#4b5563;font-size:15px;line-height:1.7;">
                Your account is all set. Here's what you can do right now:
              </p>

              <!-- Feature list -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td style="padding:12px 16px;background:#f0f4ff;border-radius:10px;margin-bottom:10px;">
                    <table cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:22px;padding-right:14px;">🔍</td>
                        <td>
                          <strong style="color:#1e1b4b;font-size:14px;">Browse thousands of products</strong><br/>
                          <span style="color:#6b7280;font-size:13px;">From Arduino boards to fashion sneakers — we've got it all.</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr><td style="height:10px;"></td></tr>
                <tr>
                  <td style="padding:12px 16px;background:#f0fdf4;border-radius:10px;">
                    <table cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:22px;padding-right:14px;">⚡</td>
                        <td>
                          <strong style="color:#1e1b4b;font-size:14px;">Exclusive deals &amp; new arrivals</strong><br/>
                          <span style="color:#6b7280;font-size:13px;">Be the first to grab flash deals and freshly stocked items.</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr><td style="height:10px;"></td></tr>
                <tr>
                  <td style="padding:12px 16px;background:#fff7ed;border-radius:10px;">
                    <table cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:22px;padding-right:14px;">🚚</td>
                        <td>
                          <strong style="color:#1e1b4b;font-size:14px;">Fast delivery across Uganda</strong><br/>
                          <span style="color:#6b7280;font-size:13px;">Order today and receive your items within 2 business days.</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- CTA Buttons -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="padding-bottom:12px;">
                    <a href="{shop_url}"
                       style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#06b6d4);color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;padding:14px 40px;border-radius:10px;letter-spacing:0.2px;">
                      🛍️ Start Shopping
                    </a>
                  </td>
                </tr>
                <tr>
                  <td align="center">
                    <a href="{new_arrivals_url}"
                       style="display:inline-block;background:#f9fafb;color:#4f46e5;text-decoration:none;font-size:14px;font-weight:600;padding:12px 32px;border-radius:10px;border:2px solid #e0e7ff;">
                      ✨ See New Arrivals
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <hr style="border:none;border-top:1px solid #e5e7eb;margin:0;"/>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;text-align:center;">
              <p style="margin:0 0 6px;color:#9ca3af;font-size:12px;">
                You're receiving this because you signed up at CartPulse.
              </p>
              <p style="margin:0;color:#9ca3af;font-size:12px;">
                &copy; 2025 CartPulse Uganda. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    thread = threading.Thread(
        target=_send,
        args=(user.email, "Welcome to CartPulse — Let's get you shopping! 🛒", html),
        daemon=True,
    )
    thread.start()
