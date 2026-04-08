"""BridgeAI load test with Locust.

Usage:
    locust -f scripts/locustfile.py --host http://localhost:8000
    # Then open http://localhost:8089 in browser
"""

from locust import HttpUser, between, task


class BridgeAIUser(HttpUser):
    """Simulates a typical BridgeAI user flow."""

    wait_time = between(1, 3)
    token: str = ""

    def on_start(self) -> None:
        """Login or register on spawn."""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "locust_user", "password": "LocustPass123!"},
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
            return

        resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "locust_user",
                "password": "LocustPass123!",
                "email": "locust@test.local",
                "nickname": "locust",
            },
        )
        if resp.status_code in (200, 201):
            self.token = resp.json().get("access_token", "")

    @property
    def _auth_headers(self) -> dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(5)
    def health_check(self) -> None:
        self.client.get("/api/v1/system/health")

    @task(3)
    def list_agents(self) -> None:
        self.client.get("/api/v1/agents", headers=self._auth_headers)

    @task(2)
    def get_root(self) -> None:
        self.client.get("/")

    @task(1)
    def list_conversations(self) -> None:
        self.client.get("/api/v1/chat/conversations", headers=self._auth_headers)
