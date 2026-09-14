from fastapi import Request

def get_client_ip(request: Request) -> str:
    # Check common proxy headers
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For can be a comma-separated list, take the first one (the original client)
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    
    if request.client and request.client.host:
        return request.client.host
        
    return "unknown"
