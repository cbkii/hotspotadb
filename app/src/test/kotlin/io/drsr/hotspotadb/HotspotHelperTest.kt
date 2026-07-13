package io.drsr.hotspotadb

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.InetAddress

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

    @Test
    fun `station address rejection does not claim IPv4 is absent`() {
        val evaluation =
            HotspotHelper.evaluateAddresses(
                interfaceName = "wlan0",
                addresses = listOf(InetAddress.getByName("192.168.1.5")),
                score = 70,
                excludeIp = "192.168.1.5",
                allowFixedAlias = false,
            )

        assertTrue(evaluation.candidates.isEmpty())
        assertEquals(listOf("wlan0:station-ip(192.168.1.5)"), evaluation.rejected)
    }

    @Test
    fun `fixed alias rejection does not claim IPv4 is absent`() {
        val evaluation =
            HotspotHelper.evaluateAddresses(
                interfaceName = "ap0",
                addresses = listOf(InetAddress.getByName(HotspotHelper.FIXED_IP)),
                score = 100,
                excludeIp = null,
                allowFixedAlias = false,
            )

        assertTrue(evaluation.candidates.isEmpty())
        assertEquals(
            listOf("ap0:fixed-alias(${HotspotHelper.FIXED_IP})"),
            evaluation.rejected,
        )
    }

    @Test
    fun `no eligible IPv4 address receives generic rejection`() {
        val evaluation =
            HotspotHelper.evaluateAddresses(
                interfaceName = "ap0",
                addresses = listOf(InetAddress.getLoopbackAddress()),
                score = 100,
                excludeIp = null,
                allowFixedAlias = false,
            )

        assertTrue(evaluation.candidates.isEmpty())
        assertEquals(listOf("ap0:no-usable-ipv4"), evaluation.rejected)
    }

    @Test
    fun `eligible IPv4 address becomes a candidate without rejection`() {
        val evaluation =
            HotspotHelper.evaluateAddresses(
                interfaceName = "ap0",
                addresses = listOf(InetAddress.getByName("192.168.43.1")),
                score = 100,
                excludeIp = null,
                allowFixedAlias = false,
            )

        assertEquals(
            listOf(
                HotspotHelper.InterfaceCandidate(
                    name = "ap0",
                    ip = "192.168.43.1",
                    score = 100,
                    reason = "usable IPv4",
                ),
            ),
            evaluation.candidates,
        )
        assertTrue(evaluation.rejected.isEmpty())
    }
}
