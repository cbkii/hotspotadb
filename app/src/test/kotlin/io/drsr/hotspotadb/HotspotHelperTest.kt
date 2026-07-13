package io.drsr.hotspotadb

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HotspotHelperTest {
    @Test
    fun `SoftAP interface families receive deterministic priority`() {
        assertEquals(100, HotspotHelper.scoreInterfaceName("ap0"))
        assertEquals(90, HotspotHelper.scoreInterfaceName("swlan0"))
        assertEquals(80, HotspotHelper.scoreInterfaceName("softap0"))
        assertEquals(70, HotspotHelper.scoreInterfaceName("wlan1"))
        assertEquals(50, HotspotHelper.scoreInterfaceName("vendor_ap_bridge"))
        assertEquals(10, HotspotHelper.scoreInterfaceName("rndis0"))
        assertEquals(10, HotspotHelper.scoreInterfaceName("eth0"))
    }

    @Test
    fun `cellular tunnel and non-SoftAP wireless interfaces are rejected`() {
        listOf(
            "lo",
            "rmnet_data0",
            "ccmni0",
            "tun0",
            "tap0",
            "wg0",
            "v4-wlan0",
            "dummy0",
            "ip6tnl0",
            "p2p0",
            "aware0",
            "nan0",
            "bnep0",
            "bt-pan",
        ).forEach { name -> assertNull(name, HotspotHelper.scoreInterfaceName(name)) }
    }
}
