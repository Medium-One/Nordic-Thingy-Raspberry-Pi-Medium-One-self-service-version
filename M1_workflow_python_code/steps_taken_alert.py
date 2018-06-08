import Store
import FreeSMS
import Email
 
email_address = 'demo@medium.one'
phone_number = '1234567890'
 
 
last_steps = Store.get('last_steps')
if not last_steps:
    last_steps = 0 
 
steps = IONode.get_input('in1')['event_data']['value']
current_step_count = steps - last_steps
Store.set_data('last_steps', steps)
if current_step_count > 10 and not Store.get('sent_alert'):
    alert_message = "Your Nordic Thingy has moved!"
    email = Email.Email(sender='alerts@medium.one', display_name='Medium One Alerts',
                        recipients=[email_address], subject='Alert: Motion Detected', message=alert_message, attachments=None)
    email.send()
    FreeSMS.sendSMS(phone_number, alert_message) 
    Store.set_data('sent_alert', 'true', ttl=86400) # 86400 seconds = 1 day
 
 
 

