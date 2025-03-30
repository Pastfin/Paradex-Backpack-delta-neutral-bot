def convert_proxy_to_dict(proxy: str) -> dict:
    splitted = proxy.split(":")
    host, port, username, password = splitted
    proxies = {
        "http": f"http://{username}:{password}@{host}:{port}",
        "https": f"http://{username}:{password}@{host}:{port}",
    }
    return proxies
