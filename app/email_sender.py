import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


def parse_digest_to_sections(digest: str) -> list[dict]:
    """
    Parse the markdown digest into structured account sections.
    Each section is a dict with keys: title, cards (list of field dicts), briefing (str)
    """
    sections = []
    # Split on top-level ## headings (account blocks)
    blocks = re.split(r'\n(?=## \d+\.)', digest.strip())

    for block in blocks:
        if not block.strip() or block.strip().startswith('#  ') or block.strip().startswith('# '):
            continue

        header_match = re.match(r'## \d+\.\s+(.+)', block)
        if not header_match:
            continue

        account_name = header_match.group(1).strip()
        section = {"account": account_name, "fields": [], "briefing": None, "meetings": []}

        # Extract bold key-value fields like **Opportunity:** ...
        for m in re.finditer(r'\*\*([^*]+):\*\*\s*(.+)', block):
            key, val = m.group(1).strip(), m.group(2).strip()
            if key not in ("Account Summary", "Deal Status", "Key Risks",
                           "Suggested Talking Points", "Next Best Action"):
                section["fields"].append({"key": key, "value": val})

        # Extract meetings list
        meetings_match = re.search(r'\*\*Meetings Today:\*\*\n((?:- .+\n?)+)', block)
        if meetings_match:
            section["meetings"] = [
                line.lstrip('- ').strip()
                for line in meetings_match.group(1).strip().splitlines()
            ]

        # Extract AI Meeting Brief block
        brief_match = re.search(r'### AI Meeting Brief\n([\s\S]+?)(?=\n## |\Z)', block)
        if brief_match:
            section["briefing"] = brief_match.group(1).strip()

        sections.append(section)

    return sections


def stage_badge_color(stage: str) -> tuple[str, str]:
    """Return (bg, text) hex colors based on stage name."""
    stage_lower = stage.lower()
    if "technical" in stage_lower or "validation" in stage_lower:
        return "#dbeafe", "#1d4ed8"
    elif "proposal" in stage_lower or "price" in stage_lower:
        return "#fef9c3", "#a16207"
    elif "negotiation" in stage_lower or "review" in stage_lower:
        return "#fce7f3", "#be185d"
    elif "needs" in stage_lower or "analysis" in stage_lower:
        return "#d1fae5", "#065f46"
    elif "closed" in stage_lower:
        return "#f3f4f6", "#6b7280"
    return "#ede9fe", "#6d28d9"


def priority_bar_html(score_str: str) -> str:
    """Render a compact priority score bar."""
    try:
        score = int(score_str)
    except Exception:
        return ""
    pct = min(score, 100)
    if pct >= 70:
        bar_color = "#ef4444"
    elif pct >= 50:
        bar_color = "#f97316"
    else:
        bar_color = "#22c55e"
    return f"""
    <div style="margin-top:4px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <div style="flex:1;background:#e5e7eb;border-radius:99px;height:6px;overflow:hidden;">
          <div style="width:{pct}%;height:100%;background:{bar_color};border-radius:99px;"></div>
        </div>
        <span style="font-size:11px;font-weight:700;color:{bar_color};min-width:28px;">{score}</span>
      </div>
    </div>
    """


def briefing_html(brief_md: str) -> str:
    """Convert briefing markdown to styled HTML."""
    if not brief_md:
        return ""

    def render_section(title_icon: str, title: str, pattern: str) -> str:
        m = re.search(pattern, brief_md, re.DOTALL)
        if not m:
            return ""
        content = m.group(1).strip()
        # Convert bullet points
        content = re.sub(r'^- (.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
        if "<li>" in content:
            content = f"<ul style='margin:6px 0 0 0;padding-left:18px;color:#374151;font-size:13px;line-height:1.7;'>{content}</ul>"
        else:
            content = f"<p style='margin:6px 0 0 0;color:#374151;font-size:13px;line-height:1.7;'>{content}</p>"
        return f"""
        <div style="margin-bottom:16px;">
          <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-bottom:4px;">
            {title_icon} {title}
          </div>
          {content}
        </div>"""

    html = ""
    html += render_section("📋", "Account Summary",
                            r'\*\*Account Summary:\*\*\s*([\s\S]+?)(?=\n\*\*Deal Status|\Z)')
    html += render_section("📊", "Deal Status",
                            r'\*\*Deal Status:\*\*\s*([\s\S]+?)(?=\n\*\*Key Risks|\Z)')
    html += render_section("⚠️", "Key Risks",
                            r'\*\*Key Risks:\*\*\s*([\s\S]+?)(?=\n\*\*Suggested Talking|\Z)')
    html += render_section("💬", "Suggested Talking Points",
                            r'\*\*Suggested Talking Points:\*\*\s*([\s\S]+?)(?=\n\*\*Next Best|\Z)')
    html += render_section("🎯", "Next Best Action",
                            r'\*\*Next Best Action:\*\*\s*([\s\S]+?)(?=\n## |\Z)')
    return html


def build_account_card(section: dict, index: int) -> str:
    """Build a full account card HTML block."""
    fields_map = {f["key"]: f["value"] for f in section["fields"]}

    opportunity = fields_map.get("Opportunity", section["account"])
    stage = fields_map.get("Stage", "")
    amount = fields_map.get("Amount", "")
    priority = fields_map.get("Priority Score", "")
    why = fields_map.get("Why This Matters", "")
    action = fields_map.get("Suggested Action", "")

    stage_bg, stage_fg = stage_badge_color(stage)
    priority_html = priority_bar_html(priority)

    meetings_html = ""
    if section["meetings"]:
        items = "".join(
            f'<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #f3f4f6;">'
            f'<span style="color:#6366f1;font-size:15px;">📅</span>'
            f'<span style="font-size:13px;color:#374151;">{m}</span>'
            f'</div>'
            for m in section["meetings"]
        )
        meetings_html = f"""
        <div style="margin:16px 0;padding:12px 16px;background:#f8f7ff;border-radius:8px;border-left:3px solid #6366f1;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6366f1;margin-bottom:6px;">
            Meetings Today
          </div>
          {items}
        </div>"""

    brief = ""
    if section["briefing"]:
        brief = f"""
        <details style="margin-top:16px;">
          <summary style="cursor:pointer;font-size:12px;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.08em;color:#6366f1;list-style:none;display:flex;
                          align-items:center;gap:6px;">
            <span style="font-size:14px;">🧠</span> AI Meeting Brief
            <span style="margin-left:auto;font-size:10px;color:#9ca3af;">(click to expand)</span>
          </summary>
          <div style="margin-top:14px;padding:16px;background:#fafafa;border-radius:8px;border:1px solid #e5e7eb;">
            {briefing_html(section["briefing"])}
          </div>
        </details>"""

    # Amount formatting
    amount_display = ""
    if amount:
        amount_display = f"""
        <div style="text-align:right;">
          <div style="font-size:22px;font-weight:800;color:#111827;letter-spacing:-0.5px;">{amount}</div>
          <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Deal Value</div>
        </div>"""

    return f"""
    <div style="
        background:#ffffff;
        border-radius:12px;
        border:1px solid #e5e7eb;
        overflow:hidden;
        margin-bottom:20px;
        box-shadow:0 1px 4px rgba(0,0,0,0.06);
    ">
      <!-- Card Header -->
      <div style="
          background:linear-gradient(135deg,#1e1b4b 0%,#312e81 100%);
          padding:20px 24px;
          display:flex;
          align-items:flex-start;
          justify-content:space-between;
          gap:16px;
      ">
        <div>
          <div style="font-size:11px;font-weight:600;text-transform:uppercase;
                      letter-spacing:0.1em;color:#a5b4fc;margin-bottom:6px;">
            #{index} — {section["account"]}
          </div>
          <div style="font-size:17px;font-weight:700;color:#ffffff;line-height:1.3;">
            {opportunity}
          </div>
          <div style="margin-top:10px;display:inline-block;
                      padding:3px 10px;border-radius:99px;
                      background:{stage_bg};color:{stage_fg};
                      font-size:11px;font-weight:700;letter-spacing:0.04em;">
            {stage}
          </div>
        </div>
        <div style="text-align:right;min-width:100px;">
          <div style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">{amount}</div>
          <div style="font-size:10px;color:#a5b4fc;text-transform:uppercase;letter-spacing:0.06em;">Deal Value</div>
          {"" if not priority else f'<div style="margin-top:8px;">{priority_html}</div>'}
        </div>
      </div>

      <!-- Card Body -->
      <div style="padding:20px 24px;">
        {"" if not why else f'''
        <div style="padding:12px 14px;background:#fffbeb;border-radius:8px;border-left:3px solid #f59e0b;margin-bottom:14px;">
          <span style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#d97706;">
            Why This Matters
          </span>
          <p style="margin:4px 0 0 0;font-size:13px;color:#374151;line-height:1.6;">{why}</p>
        </div>'''}

        {"" if not action else f'''
        <div style="padding:12px 14px;background:#f0fdf4;border-radius:8px;border-left:3px solid #22c55e;margin-bottom:14px;">
          <span style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#16a34a;">
            ⚡ Suggested Action
          </span>
          <p style="margin:4px 0 0 0;font-size:13px;color:#374151;line-height:1.6;">{action}</p>
        </div>'''}

        {meetings_html}
        {brief}
      </div>
    </div>"""


def build_html_email(digest: str) -> str:
    sections = parse_digest_to_sections(digest)
    cards_html = "".join(
        build_account_card(s, i + 1) for i, s in enumerate(sections)
    )

    today_str = __import__("datetime").date.today().strftime("%A, %B %-d, %Y")
    total_value = 0
    for s in sections:
        for f in s["fields"]:
            if f["key"] == "Amount":
                try:
                    total_value += int(f["value"].replace("$", "").replace(",", ""))
                except Exception:
                    pass

    total_value_str = f"${total_value:,}" if total_value else "—"
    meetings_count = sum(len(s["meetings"]) for s in sections)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Prep Digest</title>
</head>
<body style="margin:0;padding:0;background:#0f0e17;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">

  <!-- Outer wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:#0f0e17;padding:32px 16px;">
    <tr><td align="center">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="max-width:680px;">

        <!-- ===== HERO HEADER ===== -->
        <tr><td style="
            background:linear-gradient(135deg,#1e1b4b 0%,#4338ca 60%,#7c3aed 100%);
            border-radius:16px 16px 0 0;
            padding:36px 36px 28px;
            text-align:left;
        ">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;
                      letter-spacing:0.14em;color:#a5b4fc;margin-bottom:12px;">
            {today_str}
          </div>
          <h1 style="margin:0;font-size:32px;font-weight:800;color:#ffffff;
                     letter-spacing:-1px;line-height:1.1;">
            🚀 Daily Prep Digest
          </h1>
          <p style="margin:10px 0 0 0;font-size:15px;color:#c7d2fe;line-height:1.5;">
            Your personalized revenue intelligence briefing for today's meetings.
          </p>

          <!-- Stats row -->
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="margin-top:24px;">
            <tr>
              <td style="text-align:center;padding:14px;background:rgba(255,255,255,0.12);
                         border-radius:10px;width:33%;">
                <div style="font-size:26px;font-weight:800;color:#ffffff;">{len(sections)}</div>
                <div style="font-size:11px;color:#a5b4fc;text-transform:uppercase;
                            letter-spacing:0.07em;margin-top:2px;">Accounts</div>
              </td>
              <td width="12"></td>
              <td style="text-align:center;padding:14px;background:rgba(255,255,255,0.12);
                         border-radius:10px;width:33%;">
                <div style="font-size:26px;font-weight:800;color:#ffffff;">{total_value_str}</div>
                <div style="font-size:11px;color:#a5b4fc;text-transform:uppercase;
                            letter-spacing:0.07em;margin-top:2px;">Pipeline</div>
              </td>
              <td width="12"></td>
              <td style="text-align:center;padding:14px;background:rgba(255,255,255,0.12);
                         border-radius:10px;width:33%;">
                <div style="font-size:26px;font-weight:800;color:#ffffff;">{meetings_count}</div>
                <div style="font-size:11px;color:#a5b4fc;text-transform:uppercase;
                            letter-spacing:0.07em;margin-top:2px;">Meetings</div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- ===== ACCOUNT CARDS ===== -->
        <tr><td style="
            background:#f9fafb;
            padding:24px;
            border-radius:0 0 16px 16px;
        ">
          {cards_html}

          <!-- Footer -->
          <div style="text-align:center;padding-top:20px;border-top:1px solid #e5e7eb;margin-top:8px;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">
              Generated by your Daily Prep Copilot &nbsp;·&nbsp;
              <a href="#" style="color:#6366f1;text-decoration:none;">Unsubscribe</a>
            </p>
          </div>
        </td></tr>

      </table>
    </td></tr>
  </table>

</body>
</html>"""
    return html


def send_daily_digest_email(digest: str):
    try:
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_APP_PASSWORD")
        recipient = os.getenv("EMAIL_RECIPIENT")

        if not sender or not password or not recipient:
            print("Email credentials missing")
            return

        html_body = build_html_email(digest)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚀 Daily Prep Digest"
        msg["From"] = sender
        msg["To"] = recipient
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)

        print(f"Email sent to {recipient}")
    except Exception as e:
        print(f"Email send failed: {e}")