import unittest

from process_manager import find_available_port, local_url


class ProcessManagerTest(unittest.TestCase):
    """验证本地服务地址生成逻辑。"""

    def test_find_available_port_returns_bindable_port(self) -> None:
        port = find_available_port()

        self.assertGreater(port, 0)

    def test_local_url_uses_loopback_address(self) -> None:
        self.assertEqual(local_url(8501), "http://127.0.0.1:8501")


if __name__ == "__main__":
    unittest.main()
