class NotificationQueue:
    def __init__(self):
        self.queue = []

    def add_notification(self, notification):
        self.queue.append(notification)

    def get_notifications(self):
        return self.queue

    def clear_notifications(self):
        self.queue = []

class NotificationService:
    def __init__(self, queue):
        self.queue = queue

    def send_notification(self, message):
        self.queue.add_notification(message)
        # Logic to send notification would go here
        print(f"Notification sent: {message}")
