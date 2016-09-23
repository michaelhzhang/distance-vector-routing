"""Your awesome Distance Vector router for CS 168."""

import sim.api as api
import sim.basics as basics

# We define infinity as a distance of 16.
INFINITY = 16

class DVEntry:
    def __init__(self,distance,time):
        self.distance = distance
        self.creation_time = time

    def is_expired(self,current_time, timeout):
        return ((self.current_time - self.creation_time) >= timeout)


class DistanceVector:
    """Distance vector for a given node"""
    def __init__(self):
        self.entries_by_dest = {}

    def update(self,destination,distance,time):
        """Returns boolean indicating whether distance for a given entry has updated."""
        changed = True
        if destination in self.entries_by_dest:
            old_distance = self.entries_by_dest[destination].distance
            if (old_distance == distance):
                changed = False
        self.entries_by_dest[destination] = DVEntry(distance,time)
        return changed

    def get_distance(self,destination):
        return self.entries_by_dest[destination].distance

    def remove_expired_entries(self, current_time, timeout):
        to_remove = []
        for dest in self.entries_by_dest:
            entry = self.entries_by_dest[dest]
            if (entry.is_expired(current_time, timeout)):
               to_remove.append(dest) # can't delete here
        for dest in to_remove:
            self.remove_entry(dest)

    def remove_entry(self, destination):
        del self.entries_by_dest[destination]

class RoutingTable:
    def __init__(self):
        self.table = {}

    def update(self, destination, port):
        self.table[destination] = port

    def get_outgoing_port(self,destination):
        return self.table[destination]


class DVRouter(basics.DVRouterBase):
    # NO_LOG = True # Set to True on an instance to disable its logging
    # POISON_MODE = True # Can override POISON_MODE here
    # DEFAULT_TIMER_INTERVAL = 5 # Can override this yourself for testing

    """Plan for dealing with poisoning stuff:
        Split horizon: Upon receiving a routing packet, keep track of where you got it from
        and don't send anything back that way.
        Poisoned reverse: Upon receiving a routing packet, keep track of where you got it from
        and set that distance to infinity.
        Route poisoning: When updating own_distance_vector, keep track of any destinations
        which you can no longer get to. If poison mode is off, then remove it and do nothing.
        If poison mode, then set the distance to infinity."""

    def __init__(self):
        """
        Called when the instance is initialized.

        You probably want to do some additional initialization here.

        """
        self.own_distance_vector = DistanceVector()
        self.distance_vector_table = {}
        self.routing_table = RoutingTable()
        self.ports_to_neighbor_switches = {}
        self.ports_to_hosts = {}
        self.start_timer()  # Starts calling handle_timer() at correct rate

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this Entity goes up.

        The port attached to the link and the link latency are passed
        in.

        """
        # Update distance_vector_table
        # Update own_distance_vector and broadcast updated entry to old neighbors
        # Update routing table
        # Send entire distance vector to new neighbor switch.
        pass

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this Entity does down.

        The port number used by the link is passed in.

        """
        # Update distance_vector_table
        # Update own_distance_vector and broadcast updated entry to neighbors,
        # poisoning routes if necessary
        # Update routing table
        pass

    def handle_rx(self, packet, port):
        """
        Called by the framework when this Entity receives a packet.

        packet is a Packet (or subclass).
        port is the port number it arrived on.

        You definitely want to fill this in.

        """
        #self.log("RX %s on %s (%s)", packet, port, api.current_time())
        if isinstance(packet, basics.RoutePacket):
            neighbor = packet.src
            destination = packet.destination
            distance = packet.latency
            self.update_distance_vector_table(neighbor,destination,distance)
            self.recompute_routes()
        elif isinstance(packet, basics.HostDiscoveryPacket):
            self.ports_to_hosts[port] = packet.src
        else: # TODO
            # Totally wrong behavior for the sake of demonstration only: send
            # the packet back to where it came from!
            self.send(packet, port=port)

    def update_distance_vector_table(self,neighbor,destination,distance):
        current_time = sim.api.current_time()
        dv_to_update = self.distance_vector_table[neighbor] # TODO: Need to check if in table?
        dv.update(destination,distance,current_time)

    def recompute_routes(self, neighbor_to_ignore = None):
        """Bulk of the algorithm logic will be in here.

        Goes through the distance vector table and updates own_distance_vector
        accordingly. Sends updates to neighbors if there are any changes.
        Updates routing table with new outgoing ports.

        Neighbor_to_ignore should either have no route packets sent to it, or
        should have used poisoned reverse.
        TODO: Route poisoning should be implemented here."""
        pass

    def handle_timer(self):
        """
        Called periodically.

        When called, your router should send tables to neighbors.  It
        also might not be a bad place to check for whether any entries
        have expired.

        """
        # Update distance vector table to remove expired entries
        # Recompute distance vector
        # Send everything in distance vector to neighbors
        pass
