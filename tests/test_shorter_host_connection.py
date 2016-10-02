import sim
import sim.api as api
import sim.basics as basics

from tests.test_simple import GetPacketHost

class CountingHub(api.Entity):
    pings = 0

    def handle_rx(self, packet, in_port):
        self.send(packet, in_port, flood=True)
        if isinstance(packet, basics.Ping):
            api.userlog.debug('%s saw a ping' % (self.name, ))
            self.pings += 1

def launch():
    h1 = GetPacketHost.create("h1")
    h2 = GetPacketHost.create("h2")

    s1 = sim.config.default_switch_type.create('s1')
    s2 = sim.config.default_switch_type.create('s2')
    c1 = CountingHub.create('c1')

    h1.linkTo(s1,latency=4)
    h2.linkTo(s1)
    s1.linkTo(s2)
    s2.linkTo(c1, latency=1)
    c1.linkTo(h1, latency=1)


    def test_tasklet():
        t = 25.5
        yield t  # Wait for routing to converge

        api.userlog.debug("Sending test ping 1")
        h2.ping(h1)

        yield t

        api.userlog.debug("Failing s1-s2 link")
        s1.unlinkTo(s2)

        yield t

        api.userlog.debug("Sending test ping 2")
        h2.ping(h1)

        yield t

        if h1.pings != 2:
            api.userlog.error("h1 got %s packets instead of 2", h1.pings)
            good = False
        elif c1.pings != 1:
            api.userlog.error("c1 got %s pings instead of 1", c1.pings)
            good = False
        else:
            api.userlog.debug("Test passed successfully!")
            good = True

        # End the simulation and (if not running in interactive mode) exit.
        import sys
        sys.exit(0 if good else 1)

    api.run_tasklet(test_tasklet)

