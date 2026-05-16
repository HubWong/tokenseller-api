from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import smtplib
from app.features.db_base import ApiResp
from jose import JWTError, jwt
from app.core.config import settings

# send email to other, get email from token

smtp_server = settings.SMTP_SERVER
port = settings.SMTP_PORT
sender_email = settings.SMTP_SENDER_EMAIL
sender_password = settings.SMTP_SENDER_PASSWORD
my_domain = settings.FRONTEND_URL
sender_name = settings.PROJECT_NAME

secret_key = settings.SECRET_KEY
algorithm = settings.SECRET_KEY_ALGORITHM
token_expire_minutes = settings.EXPIRE_TOKEN_MINUTES_LOST_PWD

class SmtpSvc:
    def __init__(self, from_email, sender_pwd, appRouteUrl):
        self.smtp_svr = smtp_server
        self.port = port
        self.sender = from_email or sender_email
        self.sender_pwd = sender_pwd or sender_password
        self.appRoute = appRouteUrl       

    async def send_link_with_token(
        self, toEmail: str, token: str, subject: str = "Reset Your Password"
    )-> ApiResp:        
              
        message = MIMEMultipart()
        message["From"] =formataddr((sender_name,sender_email)) # 'noreply@p2p_lover.com'
        message["To"] = toEmail
        message["Subject"] = subject
        link_to_user =f'{my_domain}/{self.appRoute}?token={token}'
        body = f"Click the link to reset your password: {link_to_user}\n\n" \
               f"If you did not request a password reset, please ignore this email.\n\n"

        message.attach(MIMEText(body, "plain"))
        server = None
        try:
            server = smtplib.SMTP(self.smtp_svr, self.port)
            server.starttls()  # 启用TLS加密
            server.login(self.sender, self.sender_pwd)
            server.sendmail(self.sender, toEmail, message.as_string())
            print(f"Verification email sent to {toEmail}")
            return ApiResp(success=True,message=f'请于{token_expire_minutes}分钟之内完成密码修改')
        except Exception as e:
            print(f"email sending failed: {e}")
            return ApiResp(success=False,message=str(e))
        finally:
            if server:
                server.quit()

    # 工具函数：生成JWT
    @staticmethod
    def create_reset_token(email: str):
        expire = datetime.now(timezone.utc) + timedelta(minutes=token_expire_minutes)
        to_encode = {"sub": email, "exp": expire}
        return jwt.encode(to_encode, secret_key, algorithm=algorithm)

    @staticmethod
    def get_mail_exp(token: str )-> str|None:
        """
        just get email from token
        """
        try:
            payload = jwt.decode(token, secret_key, algorithms=algorithm)
            email = payload.get("sub")            
            return email       
        except JWTError as e:
            print(e)
            return None

    async def send_code(self,toEmail:str, strCode: str):
        message = MIMEMultipart()
        message["From"] =formataddr((sender_name,sender_email)) # 'noreply@p2p_lover.com'
        message["To"] = toEmail
        message["Subject"] = 'Your license Code'

        body = f"Your license code is: {strCode}\n\n" \
               f"If you did not request this code, please ignore this email.\n\n"

        message.attach(MIMEText(body, "plain"))
        server = None
        try:
            server = smtplib.SMTP(self.smtp_svr, self.port)
            server.starttls()  # 启用TLS加密
            server.login(self.sender, self.sender_pwd)
            server.sendmail(self.sender, toEmail, message.as_string())
            print(f"Verification email sent to {toEmail}")
            return ApiResp(success=True,message='请不要分享这个代码给其他人')
        except Exception as e:
            print(f"failed {e}")
            return ApiResp(success=False,message=str(e))
        finally:
            if server:
                server.quit()

smtp = SmtpSvc(from_email="gogowyb@gmail.com",
               sender_pwd="szfm bjhc xkjn ssll",
                appRouteUrl="pwd_reset")