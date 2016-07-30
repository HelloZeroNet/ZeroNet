import pytest
import time

# stats.i2p
TEST_B64 = 'Okd5sN9hFWx-sr0HH8EFaxkeIMi6PC5eGTcjM1KB7uQ0ffCUJ2nVKzcsKZFHQc7pLONjOs2LmG5H-2SheVH504EfLZnoB7vxoamhOMENnDABkIRGGoRisc5AcJXQ759LraLRdiGSR0WTHQ0O1TU0hAz7vAv3SOaDp9OwNDr9u902qFzzTKjUTG5vMTayjTkLo2kOwi6NVchDeEj9M7mjj5ySgySbD48QpzBgcqw1R27oIoHQmjgbtbmV2sBL-2Tpyh3lRe1Vip0-K0Sf4D-Zv78MzSh8ibdxNcZACmZiVODpgMj2ejWJHxAEz41RsfBpazPV0d38Mfg4wzaS95R5hBBo6SdAM4h5vcZ5ESRiheLxJbW0vBpLRd4mNvtKOrcEtyCvtvsP3FpA-6IKVswyZpHgr3wn6ndDHiVCiLAQZws4MsIUE1nkfxKpKtAnFZtPrrB8eh7QO9CkH2JBhj7bG0ED6mV5~X5iqi52UpsZ8gnjZTgyG5pOF8RcFrk86kHxAAAA'

@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestI2P:
    def testAddDest(self, i2p_manager):
        # Add
        dest = i2p_manager.addDest()
        assert dest
        assert dest in i2p_manager.dest_conns

        # Delete
        assert i2p_manager.delDest(dest)
        assert dest not in i2p_manager.dest_conns

    def testSignDest(self, i2p_manager):
        dest = i2p_manager.addDest()

        # Sign
        sign = i2p_manager.getPrivateDest(dest).sign("hello")
        assert len(sign) == dest.signature_size()

        # Verify
        assert dest.verify("hello", sign)
        assert not dest.verify("not hello", sign)

        # Delete
        i2p_manager.delDest(dest)

    def testSiteDest(self, i2p_manager):
        assert i2p_manager.getDest("address1") != i2p_manager.getDest("address2")
        assert i2p_manager.getDest("address1") == i2p_manager.getDest("address1")
