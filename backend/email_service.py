import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

def send_welcome_email(to_email, name):
    """
    Sends a welcome email to the new user.
    If credentials are missing, it logs the email content instead (Mock mode).
    """
    subject = "¡Bienvenido a Hailcast!"
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
          <h2 style="color: #2563eb;">¡Bienvenido, {name}! 🌩️</h2>
          <p>Gracias por registrarte en <strong>Hailcast</strong>, tu sistema de predicción meteorológica avanzado.</p>
          <p>Ahora tienes acceso a:</p>
          <ul>
            <li>Visualización de radar en tiempo real.</li>
            <li>Predicciones de tormentas con IA.</li>
            <li>Alertas meteorológicas.</li>
          </ul>
          <p>Si tienes alguna pregunta, no dudes en responder a este correo.</p>
          <br>
          <p>Saludos,<br>El equipo de Hailcast</p>
        </div>
      </body>
    </html>
    """

    if not SMTP_USER or not SMTP_PASS:
        logging.warning("⚠️ SMTP credentials not found. MOCKING EMAIL SENDING.")
        logging.info(f"--- MOCK EMAIL TO: {to_email} ---\nSubject: {subject}\nBody:\n{html_content}\n-----------------------------")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        
        logging.info(f"✅ Welcome email sent to {to_email}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to send email to {to_email}: {e}")
        return False

def send_password_reset_email(to_email, reset_link):
    """
    Sends a password reset email with a unique secure link.
    """
    subject = "Restablecer tu contraseña en Hailcast"
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
          <h2 style="color: #2563eb;">Restablecer contraseña 🔐</h2>
          <p>Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en <strong>Hailcast</strong>.</p>
          <p>Si no fuiste tú, puedes ignorar este correo sin problema.</p>
          <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Restablecer mi Contraseña</a>
          </div>
          <p style="font-size: 12px; color: #666;">El enlace expirará en 1 hora por seguridad.</p>
          <br>
          <p>Saludos,<br>El equipo de Hailcast</p>
        </div>
      </body>
    </html>
    """

    if not SMTP_USER or not SMTP_PASS:
        logging.warning("⚠️ SMTP credentials not found. MOCKING EMAIL SENDING.")
        logging.info(f"--- MOCK EMAIL TO: {to_email} ---\nSubject: {subject}\nBody:\n{html_content}\n-----------------------------")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        
        logging.info(f"✅ Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to send reset email to {to_email}: {e}")
        return False
