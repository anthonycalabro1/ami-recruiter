"""
Notification module - Sends email alerts via Gmail when candidates are scored.
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config_loader import CONFIG


def send_notification(candidate_name, tier, functional_areas_and_scores, role_routing, dashboard_url="http://localhost:8501"):
    """Send an email notification when a candidate is scored."""

    # Check if notifications are enabled for this tier
    tier_lower = tier.lower()
    if not CONFIG.get(f'notify_on_{tier_lower}', True):
        return False

    # Check if Gmail is configured
    if CONFIG.get('gmail_address', '').startswith('YOUR_'):
        print(f"  [Notification] Gmail not configured. Skipping notification for {candidate_name}.")
        return False

    subject = f"🎯 AMI Candidate: {candidate_name} — {tier} Tier"

    # Build the email body
    body = f"""
    <html>
    <body style="font-family: Calibri, Arial, sans-serif; color: #333; max-width: 600px;">
        <div style="background-color: #1B3A5C; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">New AMI Candidate Scored</h2>
        </div>
        <div style="padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; width: 140px;">Candidate:</td>
                    <td style="padding: 8px 0;">{candidate_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Tier:</td>
                    <td style="padding: 8px 0;">
                        <span style="background-color: {_tier_color(tier)}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;">
                            {tier}
                        </span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Role Routing:</td>
                    <td style="padding: 8px 0;">{_format_routing(role_routing)}</td>
                </tr>
            </table>

            <h3 style="color: #1B3A5C; margin-top: 20px;">Functional Area Scores</h3>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">
                <tr style="background-color: #1B3A5C; color: white;">
                    <th style="padding: 8px; text-align: left;">Functional Area</th>
                    <th style="padding: 8px; text-align: center;">Score</th>
                    <th style="padding: 8px; text-align: center;">Tier</th>
                </tr>
    """

    for fa_info in functional_areas_and_scores:
        row_color = "#EDF2F7" if functional_areas_and_scores.index(fa_info) % 2 == 0 else "white"
        body += f"""
                <tr style="background-color: {row_color};">
                    <td style="padding: 8px;">{fa_info['area']}</td>
                    <td style="padding: 8px; text-align: center;">{fa_info['score']:.2f}</td>
                    <td style="padding: 8px; text-align: center;">
                        <span style="background-color: {_tier_color(fa_info['tier'])}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">
                            {fa_info['tier']}
                        </span>
                    </td>
                </tr>
        """

    body += f"""
            </table>

            <div style="margin-top: 20px; padding: 15px; background-color: #f0f7ff; border-radius: 8px;">
                <p style="margin: 0;">View full candidate details, phone screen questions, and take action on the dashboard.</p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = CONFIG['gmail_address']
        msg['To'] = CONFIG['notification_email']
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(CONFIG['gmail_address'], CONFIG['gmail_app_password'])
            server.sendmail(CONFIG['gmail_address'], CONFIG['notification_email'], msg.as_string())

        print(f"  [Notification] Email sent for {candidate_name} ({tier})")
        return True

    except Exception as e:
        print(f"  [Notification] Failed to send email: {e}")
        return False


def _tier_color(tier):
    """Get the color for a tier badge."""
    colors = {
        'HIGH': '#1B7A2F',
        'MEDIUM': '#CC7A00',
        'LOW': '#CC4400',
        'ELIMINATED': '#CC0000'
    }
    return colors.get(tier, '#666666')


def _format_routing(routing):
    """Format role routing for display."""
    routing_labels = {
        'senior_only': 'Senior (3-5 years AMI)',
        'senior_plus_manager_flag': 'Senior + Potential Manager Stretch (6-7 years AMI)',
        'manager_only': 'Manager (7+ years AMI)',
        'eliminated': 'Eliminated (< 3 years AMI)'
    }
    return routing_labels.get(routing, routing)


def send_error_notification(error_type, details, filename=None):
    """Send email notification for system errors."""
    if CONFIG.get('gmail_address', '').startswith('YOUR_') or CONFIG.get('gmail_address', '').startswith('SET_IN'):
        return False

    subject = f"⚠️ AMI Recruiter ERROR: {error_type}"

    body = f"""
    <html>
    <body style="font-family: Calibri, Arial, sans-serif; color: #333; max-width: 600px;">
        <div style="background-color: #CC0000; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">System Error</h2>
        </div>
        <div style="padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; width: 120px;">Error Type:</td>
                    <td style="padding: 8px 0;">{error_type}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">File:</td>
                    <td style="padding: 8px 0;">{filename or 'N/A'}</td>
                </tr>
            </table>
            <h3 style="color: #CC0000; margin-top: 20px;">Details</h3>
            <pre style="background: #f5f5f5; padding: 15px; border-radius: 4px; overflow-x: auto; font-size: 12px;">{details[:2000]}</pre>
            <div style="margin-top: 20px; padding: 15px; background-color: #fff3f3; border-radius: 8px;">
                <p style="margin: 0;">Check the pipeline console or log files for full details. The resume has been moved to the Failed folder.</p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = CONFIG['gmail_address']
        msg['To'] = CONFIG['notification_email']
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(CONFIG['gmail_address'], CONFIG['gmail_app_password'])
            server.sendmail(CONFIG['gmail_address'], CONFIG['notification_email'], msg.as_string())

        return True
    except Exception as e:
        print(f"  [Notification] Failed to send error email: {e}")
        return False


def generate_handoff_email(candidate_name, role_level):
    """Generate a pre-written handoff email template for copy/paste."""
    req_url = CONFIG.get(f'{role_level.lower()}_req_url', '[REQ_LINK]')

    template = f"""Subject: Next Steps — AMI {role_level} Role at EY

Hi {candidate_name},

Thank you for the great conversation. As I mentioned, I'd like to move you forward in our process.

The next step is to formally apply through our system so our recruiting team can get you into the pipeline. I've included the direct link to the requisition below:

{role_level} Role: {req_url}

When you apply, please mention that we've already spoken so the recruiting team can flag your application accordingly.

If you have any questions about the role or the process, don't hesitate to reach out.

Looking forward to working with you.

Best regards"""

    return template
