from ignite_test import main


class TestMain:
    def test_main(self) -> None:
        assert main.main() == 0
