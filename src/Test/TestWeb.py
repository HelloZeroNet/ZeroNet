import urllib

import pytest

try:
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support.expected_conditions import staleness_of
    from selenium.common.exceptions import NoSuchElementException
except:
    pass


class WaitForPageLoad(object):
    def __init__(self, browser):
        self.browser = browser

    def __enter__(self):
        self.old_page = self.browser.find_element_by_tag_name('html')

    def __exit__(self, *args):
        WebDriverWait(self.browser, 5).until(staleness_of(self.old_page))


def wget(url):
    content = urllib.urlopen(url).read()
    assert "server error" not in content.lower(), "Got a server error! " + repr(url)
    return content

@pytest.mark.usefixtures("resetSettings")
@pytest.mark.webtest
class TestWeb:
    def testFileSecurity(self, site_url):
        assert "Not Found" in wget("%s/media/sites.json" % site_url)
        assert "Forbidden" in wget("%s/media/./sites.json" % site_url)
        assert "Forbidden" in wget("%s/media/../config.py" % site_url)
        assert "Forbidden" in wget("%s/media/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../sites.json" % site_url)
        assert "Forbidden" in wget("%s/media/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/..//sites.json" % site_url)
        assert "Forbidden" in wget("%s/media/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../../zeronet.py" % site_url)

        assert "Not Found" in wget("%s/raw/sites.json" % site_url)
        assert "Forbidden" in wget("%s/raw/./sites.json" % site_url)
        assert "Forbidden" in wget("%s/raw/../config.py" % site_url)
        assert "Forbidden" in wget("%s/raw/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../sites.json" % site_url)
        assert "Forbidden" in wget("%s/raw/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/..//sites.json" % site_url)
        assert "Forbidden" in wget("%s/raw/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../../zeronet.py" % site_url)

        assert "Forbidden" in wget("%s/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../sites.json" % site_url)
        assert "Forbidden" in wget("%s/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/..//sites.json" % site_url)
        assert "Forbidden" in wget("%s/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../../zeronet.py" % site_url)

        assert "Forbidden" in wget("%s/content.db" % site_url)
        assert "Forbidden" in wget("%s/./users.json" % site_url)
        assert "Forbidden" in wget("%s/./key-rsa.pem" % site_url)
        assert "Forbidden" in wget("%s/././././././././././//////sites.json" % site_url)

    def testLinkSecurity(self, browser, site_url):
        browser.get("%s/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/test/security.html" % site_url)
        assert browser.title == "ZeroHello - ZeroNet"
        assert browser.current_url == "%s/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/test/security.html" % site_url

        # Switch to inner frame
        browser.switch_to.frame(browser.find_element_by_id("inner-iframe"))
        assert "wrapper_nonce" in browser.current_url
        browser.switch_to.default_content()

        # Clicking on links without target
        browser.switch_to.frame(browser.find_element_by_id("inner-iframe"))
        with WaitForPageLoad(browser):
            browser.find_element_by_id("link_to_current").click()
        assert "wrapper_nonce" not in browser.current_url  # The browser object back to default content
        assert "Forbidden" not in browser.page_source
        # Check if we have frame inside frame
        browser.switch_to.frame(browser.find_element_by_id("inner-iframe"))
        with pytest.raises(NoSuchElementException):
            assert not browser.find_element_by_id("inner-iframe")
        browser.switch_to.default_content()

        # Clicking on link with target=_top
        browser.switch_to.frame(browser.find_element_by_id("inner-iframe"))
        with WaitForPageLoad(browser):
            browser.find_element_by_id("link_to_top").click()
        assert "wrapper_nonce" not in browser.current_url  # The browser object back to default content
        assert "Forbidden" not in browser.page_source
        browser.switch_to.default_content()

        # Try to escape from inner_frame
        browser.switch_to.frame(browser.find_element_by_id("inner-iframe"))
        assert "wrapper_nonce" in browser.current_url  # Make sure we are inside of the inner-iframe
        with WaitForPageLoad(browser):
            browser.execute_script("window.top.location = window.location")
        assert "wrapper_nonce" in browser.current_url  # We try to use nonce-ed html without iframe
        assert "<iframe" in browser.page_source  # Only allow to use nonce once-time
        browser.switch_to.default_content()
