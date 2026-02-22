class ProxyManager:
    def __init__(self, proxies):
        self.proxies = proxies
        self.current_index = 0

    def get_current_proxy(self):
        return self.proxies[self.current_index]

    def rotate_proxy(self):
        self.current_index = (self.current_index + 1) % len(self.proxies)

    def __str__(self):
        return f'Current Proxy: {self.get_current_proxy()}'
