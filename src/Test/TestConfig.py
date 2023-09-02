import pytest

import Config


@pytest.mark.usefixtures("resetSettings")
class TestConfig:
    def testParse(self):
        # Defaults
        config_test = Config.Config("zeronet.py".split(" "))
        config_test.parse(silent=True, parse_config=False)
        assert not config_test.debug
        assert not config_test.debug_socket

        # Test parse command line with unknown parameters (ui_password)
        config_test = Config.Config("zeronet.py --debug --debug_socket --ui_password hello".split(" "))
        config_test.parse(silent=True, parse_config=False)
        assert config_test.debug
        assert config_test.debug_socket
        with pytest.raises(AttributeError):
            config_test.ui_password

        # More complex test
        args = "zeronet.py --unknown_arg --debug --debug_socket --ui_restrict 127.0.0.1 1.2.3.4 "
        args += "--another_unknown argument --use_openssl False siteSign address privatekey --inner_path users/content.json"
        config_test = Config.Config(args.split(" "))
        config_test.parse(silent=True, parse_config=False)
        assert config_test.debug
        assert "1.2.3.4" in config_test.ui_restrict
        assert not config_test.use_openssl
        assert config_test.inner_path == "users/content.json"
