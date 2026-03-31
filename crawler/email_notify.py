"""
算电通 - 邮件通知模块
QQ邮箱 SMTP 发送爬虫结果通知
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

# QQ邮箱配置（授权码通过环境变量读取，不硬编码）
QQ_EMAIL = 'ch132456@qq.com'
QQ_SMTP_HOST = 'smtp.qq.com'
QQ_SMTP_PORT = 465

def get_auth_code():
    """从环境变量或配置文件读取授权码"""
    # 优先从环境变量读取
    code = os.environ.get('QQ_EMAIL_AUTH_CODE')
    if code:
        return code
    # 从本地配置文件读取（不提交到git）
    config_path = os.path.join(os.path.dirname(__file__), '..', 'data', '.email_config')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return None

def send_notification(subject, body_html, to_email=None):
    """发送邮件通知"""
    auth_code = get_auth_code()
    if not auth_code:
        print('[邮件] 未配置授权码，跳过发送')
        return False

    to_email = to_email or QQ_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = QQ_EMAIL
    msg['To'] = to_email

    html_part = MIMEText(body_html, 'html', 'utf-8')
    msg.attach(html_part)

    try:
        with smtplib.SMTP_SSL(QQ_SMTP_HOST, QQ_SMTP_PORT) as server:
            server.login(QQ_EMAIL, auth_code)
            server.sendmail(QQ_EMAIL, [to_email], msg.as_string())
        print(f'[邮件] 发送成功 -> {to_email}')
        return True
    except Exception as e:
        print(f'[邮件] 发送失败: {e}')
        return False

def notify_electricity_update(updated_provinces, failed_provinces, duration):
    """电价更新完成通知"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subject = f'[算电通] 全国电价数据已更新 - {now[:10]}'

    updated_list = ''.join([f'<li>{p}</li>' for p in updated_provinces])
    failed_list = ''.join([f'<li>{p}</li>' for p in failed_provinces]) if failed_provinces else '<li>无</li>'

    body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #2196F3;">⚡ 算电通 - 全国电价数据更新完成</h2>
    <p>更新时间：{now}</p>
    <p>耗时：{duration} 秒</p>

    <h3 style="color: #4CAF50;">✅ 成功更新 ({len(updated_provinces)} 个省份)</h3>
    <ul>{updated_list}</ul>

    <h3 style="color: #FF9800;">⚠️ 未获取到数据 ({len(failed_provinces)} 个省份)</h3>
    <ul>{failed_list}</ul>

    <p style="color: #666; font-size: 12px;">
    此邮件由算电通自动发送，下次更新将在12天后进行。
    </p>
    </body></html>
    """
    return send_notification(subject, body)

def notify_deepseek_update(models_updated):
    """DeepSeek价格更新通知"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subject = f'[算电通] DeepSeek价格已更新 - {now[:10]}'
    models_list = ''.join([f'<li>{m}</li>' for m in models_updated])

    body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #9C27B0;">🤖 算电通 - DeepSeek价格更新完成</h2>
    <p>更新时间：{now}</p>
    <h3>已更新模型：</h3>
    <ul>{models_list}</ul>
    <p style="color: #666; font-size: 12px;">此邮件由算电通自动发送，下次更新将在3天后进行。</p>
    </body></html>
    """
    return send_notification(subject, body)

def setup_auth_code(auth_code):
    """保存授权码到本地配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'data', '.email_config')
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(auth_code)
    print(f'[邮件] 授权码已保存到: {config_path}')

if __name__ == '__main__':
    # 初始化：保存授权码
    setup_auth_code('jpchcvlvdvqfbcgg')
    print('[邮件] 配置完成，测试发送...')
    send_notification('[算电通] 邮件配置测试', '<h2>邮件配置成功！算电通已就绪。</h2>')
