"""Your awesome Distance Vector router for CS 168."""

import sim.api as api
import sim.basics as basics

# We define infinity as a distance of 16.
INFINITY = 16

class DVRouter(basics.DVRouterBase):
    # NO_LOG = True # Set to True on an instance to disable its logging
    # POISON_MODE = True # Can override POISON_MODE here
    # DEFAULT_TIMER_INTERVAL = 5 # Can override this yourself for testing

    def __init__(self):
        """
        Called when the instance is initialized.

        You probably want to do some additional initialization here.

        """
        self.destinations_to_poison = [] # Expired routes whose destinations we should poison
        self.host_to_port = {}
        # Store things as (port, latency, creation_time) pairs"""
        self.routing_table = {}
        self.port_to_latency = {}
        self.start_timer()  # Starts calling handle_timer() at correct rate

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this Entity goes up.

        The port attached to the link and the link latency are passed
        in.

        """
        self.port_to_latency[port] = latency
        self.send_dv_to_port(port)

    def send_dv_to_port(self, port):
        for destination in self.routing_table:
            routing_port = self.get_routing_port(destination)
            latency = self.get_routing_distance(destination)
            if (routing_port != port):
                self.send_routing_packet(destination, port,latency)
            elif (self.POISON_MODE): # routing_port = port. Poison reverse
                self.send_routing_packet(destination, port, INFINITY)
            # else do nothing for split horizon
        if self.POISON_MODE:
            for destination in self.destinations_to_poison:
                if destination not in self.host_to_port: # hosts always have routes
                    self.send_routing_packet(destination, port, INFINITY)

    def send_routing_packet(self, destination, out_port, latency):
        packet = basics.RoutePacket(destination, latency)
        self.send(packet, port=out_port, flood=False)

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this Entity does down.

        The port number used by the link is passed in.

        """
        self.remove_hosts_on_port(port) # Must be before next line
        deleted_routes = self.remove_paths_using_port(port)
        del self.port_to_latency[port]

    def remove_paths_using_port(self, port):
        # Returns list of destinations that were removed
        current_time = api.current_time()
        removed_destinations = []
        for destination in self.routing_table:
            out_port = self.get_routing_port(destination)
            if (port == out_port):
                removed_destinations.append(destination)
        for destination in removed_destinations:
            self.remove_route(destination)
            # ALways maintain path to connected host
            self.add_default_host_route(destination, current_time)

    def remove_hosts_on_port(self, port):
        hosts_to_remove = []
        for host in self.host_to_port:
            out_port = self.host_to_port[host]
            if (port == out_port):
                hosts_to_remove.append(host)
        for host in hosts_to_remove:
            del self.host_to_port[host]

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
        latency = packet.latency
        destination = packet.destination
        self.update_route(destination, port, latency)

    def update_route(self, destination, port, latency):
        creation_time = api.current_time()
        port_latency = self.port_to_latency[port]
        total_distance = self.add_latencies(latency, port_latency)
        if (destination not in self.routing_table):
            if total_distance != INFINITY:
                self.routing_table[destination] = (port, total_distance, creation_time)
        else: # Destination in routing table
            prev_port = self.get_routing_port(destination)
            prev_latency = self.get_routing_distance(destination)
            if (port == prev_port):
                if total_distance == INFINITY:
                    self.remove_route(destination)
                else: # Always trust the most recent
                    self.routing_table[destination] = (port, total_distance, creation_time)
            elif (total_distance <= prev_latency):
                self.routing_table[destination] = (port, total_distance, creation_time)
        self.add_default_host_route(destination, creation_time) # Make sure host always has route

    def remove_route(self, destination):
        if destination in self.routing_table:
            del self.routing_table[destination]
            if self.POISON_MODE: # Route poisoning
                self.destinations_to_poison.append(destination)

    def add_latencies(self, lat1, lat2):
        return min(lat1 + lat2, INFINITY)

    def add_default_host_route(self, destination,creation_time):
        # Always keep entry for host
        if (destination in self.host_to_port):
            host_port = self.host_to_port[destination]
            new_latency = self.port_to_latency[host_port]
            if (destination not in self.routing_table):
                self.routing_table[destination] = (host_port, new_latency, creation_time)
            elif (new_latency < self.get_routing_distance(destination)):
                self.routing_table[destination] = (host_port, new_latency, creation_time)

    def handle_host_discovery_packet(self, packet, port):
        host = packet.src
        self.host_to_port[host] = port
        self.update_route(host, port, 0.0)

    def handle_data_packet(self, packet, port):
        destination = packet.dst
        if destination in self.routing_table:
            out_port = self.get_routing_port(destination)
            if (out_port != port): # No hairpin
                self.send(packet, port=out_port, flood=False)

    def handle_timer(self):
        """
        Called periodically.

        When called, your router should send tables to neighbors.  It
        also might not be a bad place to check for whether any entries
        have expired.

        """
        self.remove_expired_entries()
        self.send_table_to_neighbors()

    def remove_expired_entries(self):
        current_time = api.current_time()
        entries_to_remove = []
        for destination in self.routing_table:
            creation_time = self.get_creation_time(destination)
            time_elapsed = current_time - creation_time
            if time_elapsed >= self.ROUTE_TIMEOUT:
                entries_to_remove.append(destination)
        for destination in entries_to_remove:
            self.remove_route(destination)
            self.add_default_host_route(destination, current_time)

    def send_table_to_neighbors(self):
        for port in self.get_neighbors():
            self.send_dv_to_port(port)
        self.destinations_to_poison = []

    def get_neighbors(self):
        return self.port_to_latency.keys()

    def get_routing_port(self, destination):
        return self.routing_table[destination][0]

    def get_routing_distance(self, destination):
        return self.routing_table[destination][1]

    def get_creation_time(self, destination):
        return self.routing_table[destination][2]
