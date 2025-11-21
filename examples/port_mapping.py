"""Map fixed and dynamic ports, then access via host."""

from podman_runner import Container, ContainerConfig

config = ContainerConfig(
    name="port-example",
    image="docker.io/library/nginx:alpine",
    ports={80: None, 443: None},  # 80 and 443 will be auto-mapped to a free port
)

with Container(config) as c:
    host_port = c.get_port(80)
    print(f"Nginx accessible at http://localhost:{host_port}")

    # Auto-mapped port example
    dynamic = c.get_port(443)
    print(f"HTTPS would be on: {dynamic}")

    # Test HTTP
    import requests

    response = requests.get(f"http://localhost:{host_port}", timeout=5)
    print(f"Status: {response.status_code}")
