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
        if self.creation_time is not None:
            return ((self.current_time - self.creation_time) >= timeout)
        return False


class DistanceVector:
    """Distance vector for a given node"""
    def __init__(self):
        self.entries_by_dest = {}

    def get_destination_list(self):
        return self.entries_by_dest.keys()

    def update(self,destination,distance,time=None):
        """Returns boolean indicating whether distance for a given entry has updated."""
        changed = True
        if self.contains(destination):
            old_distance = self.entries_by_dest[destination].distance
            if (old_distance == distance):
                changed = False
        self.entries_by_dest[destination] = DVEntry(distance,time)
        return changed

    def contains(self, destination):
        return destination in self.entries_by_dest

    def get_distance(self,destination):
        """Returns None if destination not in this DistanceVector"""
        if destination in self.entries_by_dest:
            return self.entries_by_dest[destination].distance
        return None

    def remove_expired_entries(self, current_time, timeout):
        to_remove = []
        for dest in self.entries_by_dest:
            entry = self.entries_by_dest[dest]
            if (entry.is_expired(current_time, timeout)):
               to_remove.append(dest) # can't delete here
        for dest in to_remove:
            self.remove(dest)

    def remove(self, destination):
        if destination in self.entries_by_dest:
            del self.entries_by_dest[destination]

class RoutingTable:
    def __init__(self):
        self.table = {}

    def __str__(self):
        return str(self.table)

    def update(self, destination, port):
        self.table[destination] = port

    def remove(self, destination):
        if destination in self.table:
            del self.table[destination]

    def contains(self, destination):
        return destination in self.table

    def get_port(self,destination):
        return self.table[destination]

    def get_destination_list(self):
        return self.table.keys()


class DVRouter(basics.DVRouterBase):
    # NO_LOG = True # Set to True on an instance to disable its logging
    # POISON_MODE = True # Can override POISON_MODE here
    DEFAULT_TIMER_INTERVAL = 5 # Can override this yourself for testing

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
        self.own_distance_vector.update(self, 0) # Set 0 distance to self
        self.distance_vector_table = {}
        self.routing_table = RoutingTable()
        self.ports_to_latencies = {}
        self.start_timer()  # Starts calling handle_timer() at correct rate

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this Entity goes up.

        The port attached to the link and the link latency are passed
        in.

        """
        self.ports_to_latencies[port] = latency
        # Can't update anything else because don't have any
        # information about this new neighbor
        # Send entire distance vector to new neighbor switch.
        self.send_all_distance_info(port)

    def send_all_distance_info(self, port):
        """Sends all distance info to port. Used when new neighbor connects."""
        for dest in self.own_distance_vector.get_destination_list():
            distance = self.own_distance_vector.get_distance(dest)
            route_packet = basics.RoutePacket(dest, distance)
            if (dest == self) or (self.routing_table.get_port(dest) != port):
                self.send(route_packet,port=port)
            elif self.POISON_MODE: # if one host disconnects and reconnects at same port
                poison_packet = basics.RoutePacket(destination, INFINITY)
                self.send(poison_packet, port_to_poison)

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this Entity does down.

        The port number used by the link is passed in.

        """
        del self.ports_to_latencies[port]
        # Update routes
        to_recompute = []
        for dest in self.routing_table.get_destination_list():
            if self.routing_table.get_port(dest) == port:
                to_recompute.append(dest) # Can't delete from routing table yet
        for dest in to_recompute: # Make sure these don't get used in route recomputation
            self.routing_table.remove(dest)
        for dest in to_recompute:
            route_changed, no_route, port_to_poison = self.update_route_to_dest(dest)
            if (no_route and self.POISON_MODE):
                self.poison_route(dest)
            elif route_changed: # found a new route
                self.send_route_update(dest, port_to_poison)

    def remove_from_all_distance_vectors(self, to_remove):
        self.own_distance_vector.remove(to_remove)
        for dv in self.distance_vector_table.values():
            dv.remove(to_remove)

    def handle_rx(self, packet, port):
        """
        Called by the framework when this Entity receives a packet.

        packet is a Packet (or subclass).
        port is the port number it arrived on.

        You definitely want to fill this in.

        """
        #self.log("RX %s on %s (%s)", packet, port, api.current_time())
        if isinstance(packet, basics.RoutePacket):
            self.handle_route_packet(packet,port)
        elif isinstance(packet, basics.HostDiscoveryPacket):
            self.handle_host_discovery_packet(packet, port)
        else:
            self.handle_data_packet(packet, port)

    def handle_route_packet(self, packet, port):
        neighbor = packet.src
        destination = packet.destination
        distance = packet.latency
        self.update_distance_vector_table(neighbor,destination,distance)
        if (distance == 0): # Neighbor declaring itself
            self.routing_table.update(neighbor, port) # A bit hacky.
        route_changed, no_route, port_to_poison = self.update_route_to_dest(destination)
        if (route_changed):
            self.send_route_update(destination, port_to_poison)
        elif (no_route):
            self.routing_table.remove(destination)
            if self.POISON_MODE: # Route poisoning
                self.poison_route(destination)

    def update_distance_vector_table(self,entity_to_update,destination,distance):
        current_time = api.current_time()
        if entity_to_update in self.distance_vector_table:
            dv_to_update = self.distance_vector_table[entity_to_update]
        else:
            dv_to_update = DistanceVector()
            self.distance_vector_table[entity_to_update] = dv_to_update
        dv_to_update.update(destination,distance,current_time)

    def update_route_to_dest(self, destination):
        """Computes the new optimal route to destination.
        Returns boolean indicating whether or not route was changed and the
        port that was used (for split horizon and poisoned reverse)."""
        route_changed = False
        no_route = False
        best_dist, best_port = self.find_best_route(destination)
        if (best_dist is None): # No route
            no_route = True
        else:
            route_changed = self.own_distance_vector.update(destination, best_dist)
            if self.routing_table.contains(destination):
                old_port = self.routing_table.get_port(destination)
                # Send update packets to neighbors if either the distance or the
                # outgoing port changed. Need to update even if distance
                # doesn't update in order to poison routes.
                if (old_port != best_port):
                    route_changed = True
            else: # route certainly changed if not previously in routing_table
                route_changed = True
            self.routing_table.update(destination, best_port)
        return route_changed, no_route, best_port

    def find_best_route(self, destination):
        best_dist = None
        best_port = None
        for entity in self.distance_vector_table:
            distance_vector = self.distance_vector_table[entity]
            entity_distance = distance_vector.get_distance(destination)
            if (entity_distance is not None) and (self.routing_table.contains(entity)):
                candidate_port = self.routing_table.get_port(entity)
                total_distance = self.add_distances(self.ports_to_latencies[candidate_port],
                                                    entity_distance)
                update_best = (best_dist is None) or (total_distance < best_dist)
                update_best = update_best and (total_distance < INFINITY)
                if update_best:
                    best_dist = total_distance
                    best_port = candidate_port
        return best_dist, best_port

    def add_distances(self, distance1,distance2):
        """
        Adds 2 latencies, but caps the sum at INFINITY.
        """
        return min(distance1+distance2, INFINITY)

    def send_route_update(self, destination, port_to_poison):
        """Sends routing packets to all ports for destination, except for
        port_to_poison, which is ignored if POISON_MODE is off, and poisoned
        otherwise."""
        distance = self.own_distance_vector.get_distance(destination)
        route_packet = basics.RoutePacket(destination, distance)
        # Flood packet to neighbors
        self.send(route_packet, port=port_to_poison, flood=True)
        if self.POISON_MODE: # if POISON_MODE is off, don't send anything (split horizon)
            self.poison_reverse(destination, port_to_poison)

    def poison_route(self, destination):
        poison_packet = basics.RoutePacket(destination, INFINITY)
        self.send(poison_packet, flood=False)

    def poison_reverse(self, destination, port_to_poison):
        poison_packet = basics.RoutePacket(destination, INFINITY)
        self.send(poison_packet, port_to_poison)


    def handle_host_discovery_packet(self, packet, port):
        # Host will not send you any routing packets, so must update distance now
        host = packet.src
        # Host has a distance of 0 to itself and can't route anywhere else.
        self.update_distance_vector_table(host,host,0)
        self.routing_table.update(host, port) # Know we can go through this port
        self.update_route_to_dest(host)

    def handle_data_packet(self, packet, port):
        destination = packet.dst
        if self.routing_table.contains(destination):
            outgoing_port = self.routing_table.get_port(destination)
            # Don't send packets the same way they came
            if (outgoing_port != port):
                self.send(packet, port=outgoing_port)

    def handle_timer(self):
        """
        Called periodically.

        When called, your router should send tables to neighbors.  It
        also might not be a bad place to check for whether any entries
        have expired.

        """
        # Update distance vector table to remove expired entries
        current_time = api.current_time()
        self.own_distance_vector.remove_expired_entries(current_time, self.ROUTE_TIMEOUT)
        # Recompute distance vector. Send everything in distance vector to neighbors.
        for dest in self.own_distance_vector.get_destination_list():
            route_changed, no_route, port_to_poison = self.update_route_to_dest(dest)
            self.send_route_update(dest, port_to_poison)


